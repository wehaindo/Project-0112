import json
import logging

from odoo import http
from odoo.http import request
from odoo.addons.weha_base_api.libs.common import invalid_response, valid_response
from odoo.addons.weha_base_api.contollers.main import validate_token
from .utils import _picking_data, _apply_validate_lines, _process_backorder

_logger = logging.getLogger(__name__)


class StockTransferAPI(http.Controller):
    """
    Internal Transfer endpoints.

    GET  /api/stock/transfer              - list internal transfers
    GET  /api/stock/transfer/<id>         - transfer detail
    POST /api/stock/transfer              - create internal transfer
    POST /api/stock/transfer/<id>/validate - validate transfer
    """

    # -------------------------------------------------------------------------
    # List
    # -------------------------------------------------------------------------

    @validate_token
    @http.route("/api/stock/transfer", methods=["GET"], type="http", auth="none", csrf=False)
    def list_transfers(self, **params):
        """
        List internal transfers.

        Query params (all optional):
          - warehouse_id  (int)
          - state         (str) draft | waiting | confirmed | assigned | done | cancel
          - limit         (int, default 50)
          - offset        (int, default 0)
          - origin        (str) source document filter
        """
        try:
            limit       = int(params.get("limit",  50))
            offset      = int(params.get("offset", 0))
            state       = params.get("state")
            origin      = params.get("origin", "")
            warehouse_id = params.get("warehouse_id")

            domain = [("picking_type_id.code", "=", "internal")]
            if state:
                domain.append(("state", "=", state))
            if origin:
                domain.append(("origin", "ilike", origin))
            if warehouse_id:
                domain.append(("picking_type_id.warehouse_id", "=", int(warehouse_id)))

            pickings = request.env["stock.picking"].sudo().search(
                domain, limit=limit, offset=offset, order="scheduled_date desc, id desc"
            )
            total = request.env["stock.picking"].sudo().search_count(domain)
            return valid_response({
                "total":  total,
                "limit":  limit,
                "offset": offset,
                "data":   [_picking_data(p) for p in pickings],
            })
        except Exception as e:
            _logger.exception("Error listing transfers")
            return invalid_response("server_error", str(e), 500)

    # -------------------------------------------------------------------------
    # Detail
    # -------------------------------------------------------------------------

    @validate_token
    @http.route("/api/stock/transfer/<int:picking_id>", methods=["GET"], type="http", auth="none", csrf=False)
    def get_transfer(self, picking_id, **params):
        """Return a single internal transfer by id."""
        try:
            picking = request.env["stock.picking"].sudo().browse(picking_id)
            if not picking.exists() or picking.picking_type_id.code != "internal":
                return invalid_response("not_found", "Transfer not found", 404)
            return valid_response(_picking_data(picking))
        except Exception as e:
            _logger.exception("Error fetching transfer %s", picking_id)
            return invalid_response("server_error", str(e), 500)

    # -------------------------------------------------------------------------
    # Create
    # -------------------------------------------------------------------------

    @validate_token
    @http.route("/api/stock/transfer", methods=["POST"], type="http", auth="none", csrf=False)
    def create_transfer(self, **params):
        """
        Create a new internal transfer.

        JSON body:
        {
            "warehouse_id":     <int>,          -- required; resolves picking_type (internal)
            "location_id":      <int>,          -- required; source location
            "location_dest_id": <int>,          -- required; destination location
            "origin":           "<str>",        -- optional
            "scheduled_date":   "YYYY-MM-DD",   -- optional
            "note":             "<str>",        -- optional
            "lines": [
                {
                    "product_id": <int>,        -- required
                    "qty":        <float>,      -- required
                    "uom_id":     <int>,        -- optional
                    "lot_id":     <int>         -- optional; existing lot/serial
                },
                ...
            ]
        }
        """
        try:
            body = request.httprequest.get_data(as_text=True)
            payload = json.loads(body) if body else {}

            warehouse_id      = payload.get("warehouse_id")
            location_id       = payload.get("location_id")
            location_dest_id  = payload.get("location_dest_id")

            if not warehouse_id:
                return invalid_response("missing_field", "warehouse_id is required", 400)
            if not location_id:
                return invalid_response("missing_field", "location_id is required", 400)
            if not location_dest_id:
                return invalid_response("missing_field", "location_dest_id is required", 400)

            lines = payload.get("lines", [])
            if not lines:
                return invalid_response("missing_field", "lines are required", 400)

            warehouse = request.env["stock.warehouse"].sudo().browse(int(warehouse_id))
            if not warehouse.exists():
                return invalid_response("not_found", "Warehouse not found", 404)

            picking_type = warehouse.int_type_id

            move_vals = []
            for line in lines:
                product = request.env["product.product"].sudo().browse(int(line["product_id"]))
                if not product.exists():
                    return invalid_response("not_found", "Product %s not found" % line["product_id"], 404)
                uom_id = int(line["uom_id"]) if line.get("uom_id") else product.uom_id.id
                move_vals.append({
                    "name":            product.display_name,
                    "product_id":      product.id,
                    "product_uom_qty": float(line["qty"]),
                    "product_uom":     uom_id,
                    "location_id":     int(location_id),
                    "location_dest_id": int(location_dest_id),
                })

            vals = {
                "picking_type_id":  picking_type.id,
                "location_id":      int(location_id),
                "location_dest_id": int(location_dest_id),
                "move_ids":         [(0, 0, m) for m in move_vals],
                "origin":           payload.get("origin", ""),
                "note":             payload.get("note", ""),
            }
            if payload.get("scheduled_date"):
                vals["scheduled_date"] = payload["scheduled_date"]

            picking = request.env["stock.picking"].sudo().create(vals)
            picking.action_confirm()
            picking.action_assign()

            return valid_response({"id": picking.id, "name": picking.name, "state": picking.state}, status=201)
        except json.JSONDecodeError:
            return invalid_response("invalid_json", "Request body is not valid JSON", 400)
        except Exception as e:
            _logger.exception("Error creating transfer")
            return invalid_response("server_error", str(e), 500)

    # -------------------------------------------------------------------------
    # Validate
    # -------------------------------------------------------------------------

    @validate_token
    @http.route("/api/stock/transfer/<int:picking_id>/validate", methods=["POST"], type="http", auth="none", csrf=False)
    def validate_transfer(self, picking_id, **params):
        """
        Validate (complete) an internal transfer.

        JSON body (optional):
        {
            "lines": [
                {
                    "move_id":  <int>,     -- required
                    "qty_done": <float>,   -- required
                    "rfid_tag": "<str>",   -- RFID tag = lot/serial name
                    "lot_name": "<str>",   -- alias for rfid_tag
                    "lot_id":   <int>      -- use existing lot by id
                }
            ],
            "backorder": false
        }
        """
        try:
            picking = request.env["stock.picking"].sudo().browse(picking_id)
            if not picking.exists() or picking.picking_type_id.code != "internal":
                return invalid_response("not_found", "Transfer not found", 404)
            if picking.state in ("done", "cancel"):
                return invalid_response("invalid_state", "Transfer is already %s" % picking.state, 400)

            body = request.httprequest.get_data(as_text=True)
            payload = json.loads(body) if body else {}

            _apply_validate_lines(picking, payload.get("lines", []))

            res = picking.with_context(skip_backorder=not payload.get("backorder", True)).button_validate()
            _process_backorder(res, payload.get("backorder", True))

            return valid_response({"id": picking.id, "name": picking.name, "state": picking.state})
        except json.JSONDecodeError:
            return invalid_response("invalid_json", "Request body is not valid JSON", 400)
        except Exception as e:
            _logger.exception("Error validating transfer %s", picking_id)
            return invalid_response("server_error", str(e), 500)
