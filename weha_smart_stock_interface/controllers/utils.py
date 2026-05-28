import logging
from odoo.http import request

_logger = logging.getLogger(__name__)


def _resolve_lot(product, lot_id=None, lot_name=None, rfid_tag=None, company_id=None, create=True):
    """
    Resolve or create a stock.lot from lot_id, lot_name, or rfid_tag.
    rfid_tag is treated as the lot/serial number name directly.

    Priority: lot_id > rfid_tag > lot_name

    Returns a stock.lot record or False.
    """
    if product.tracking == "none":
        return False

    # Resolve by ID first
    if lot_id:
        lot = request.env["stock.lot"].sudo().browse(int(lot_id))
        return lot if lot.exists() else False

    # rfid_tag is the lot name
    name = rfid_tag or lot_name
    if not name:
        return False

    lot = request.env["stock.lot"].sudo().search([
        ("name",       "=", name),
        ("product_id", "=", product.id),
    ], limit=1)

    if lot:
        return lot

    if not create:
        return False

    cid = company_id or request.env.company.id
    lot = request.env["stock.lot"].sudo().create({
        "name":       name,
        "product_id": product.id,
        "company_id": cid,
    })
    _logger.info("Created lot/serial '%s' for product %s (id=%s)", name, product.display_name, product.id)
    return lot


def _move_line_detail(ml):
    """Serialize a single stock.move.line (detail level)."""
    lot = ml.lot_id
    return {
        "move_line_id": ml.id,
        "lot_id":       lot.id   if lot else None,
        "lot_name":     lot.name if lot else "",
        "rfid_tag":     lot.name if lot else "",   # rfid_tag == lot name
        "qty_reserved": ml.reserved_uom_qty,
        "qty_done":     ml.qty_done,
    }


def _picking_line_data(move):
    """Serialize a stock.move with its move lines."""
    return {
        "move_id":        move.id,
        "product_id":     move.product_id.id,
        "product_name":   move.product_id.display_name,
        "default_code":   move.product_id.default_code or "",
        "barcode":        move.product_id.barcode or "",
        "tracking":       move.product_id.tracking,
        "uom":            move.product_uom.name,
        "uom_id":         move.product_uom.id,
        "product_qty":    move.product_uom_qty,
        "quantity_done":  move.quantity,
        "state":          move.state,
        "lots":           [_move_line_detail(ml) for ml in move.move_line_ids],
    }


def _picking_data(picking):
    """Serialize a stock.picking record."""
    return {
        "id":                 picking.id,
        "name":               picking.name,
        "state":              picking.state,
        "picking_type":       picking.picking_type_id.name,
        "picking_type_id":    picking.picking_type_id.id,
        "origin":             picking.origin or "",
        "partner_id":         picking.partner_id.id   if picking.partner_id else None,
        "partner_name":       picking.partner_id.name if picking.partner_id else "",
        "location_id":        picking.location_id.id,
        "location_name":      picking.location_id.complete_name,
        "location_dest_id":   picking.location_dest_id.id,
        "location_dest_name": picking.location_dest_id.complete_name,
        "scheduled_date":     picking.scheduled_date.strftime("%Y-%m-%d %H:%M:%S") if picking.scheduled_date else "",
        "date_done":          picking.date_done.strftime("%Y-%m-%d %H:%M:%S") if picking.date_done else "",
        "note":               picking.note or "",
        "move_lines":         [_picking_line_data(m) for m in picking.move_ids],
    }


def _apply_validate_lines(picking, lines):
    """
    Apply done quantities and lot/rfid_tag assignments from the validate payload lines.
    If lines is empty, auto-fills qty_done = reserved qty for every move line.
    """
    if not lines:
        for move in picking.move_ids:
            for ml in move.move_line_ids:
                ml.qty_done = ml.reserved_uom_qty
        return

    for line_data in lines:
        move_id = line_data.get("move_id")
        if not move_id:
            continue
        move = picking.move_ids.filtered(lambda m: m.id == int(move_id))
        if not move:
            continue

        lot = _resolve_lot(
            product=move.product_id,
            lot_id=line_data.get("lot_id"),
            lot_name=line_data.get("lot_name"),
            rfid_tag=line_data.get("rfid_tag"),
            company_id=picking.company_id.id,
            create=True,
        )

        qty_done = float(line_data.get("qty_done", 0))

        # If serial tracking, one move_line per unit
        if move.product_id.tracking == "serial":
            _apply_serial_lines(move, lot, qty_done, picking)
        else:
            for ml in move.move_line_ids:
                ml.qty_done = qty_done
                if lot:
                    ml.lot_id = lot.id


def _apply_serial_lines(move, lot, qty_done, picking):
    """
    For serial-tracked products: ensure one move.line per serial.
    If a lot is provided write it; otherwise leave existing assignment.
    """
    existing = move.move_line_ids
    if existing:
        ml = existing[0]
        ml.qty_done = 1
        if lot:
            ml.lot_id = lot.id
    else:
        request.env["stock.move.line"].sudo().create({
            "move_id":         move.id,
            "picking_id":      picking.id,
            "product_id":      move.product_id.id,
            "product_uom_id":  move.product_uom.id,
            "location_id":     move.location_id.id,
            "location_dest_id": move.location_dest_id.id,
            "lot_id":          lot.id if lot else False,
            "qty_done":        1,
        })


def _process_backorder(res, want_backorder):
    """Handle stock.backorder.confirmation wizard if button_validate returns it."""
    if not isinstance(res, dict):
        return
    if res.get("res_model") != "stock.backorder.confirmation":
        return
    wizard = request.env[res["res_model"]].sudo().with_context(
        **res.get("context", {})
    ).create({})
    if want_backorder:
        wizard.process()
    else:
        wizard.process_cancel_backorder()
