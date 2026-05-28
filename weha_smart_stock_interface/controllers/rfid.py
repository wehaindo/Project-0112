import json
import logging

from odoo import http
from odoo.http import request
from odoo.addons.weha_base_api.libs.common import invalid_response, valid_response
from odoo.addons.weha_base_api.contollers.main import validate_token

_logger = logging.getLogger(__name__)


def _lot_data(lot):
    return {
        "id":          lot.id,
        "name":        lot.name,
        "rfid_tag":    lot.name,   # rfid_tag IS the lot/serial name
        "product_id":  lot.product_id.id,
        "product_name": lot.product_id.display_name,
        "default_code": lot.product_id.default_code or "",
        "barcode":      lot.product_id.barcode or "",
        "tracking":     lot.product_id.tracking,
        "qty_available": lot.product_qty,
        "expiration_date": lot.expiration_date.strftime("%Y-%m-%d") if lot.expiration_date else "",
    }


class StockRFIDAPI(http.Controller):
    """
    RFID / Lot-Serial endpoints.

    GET  /api/stock/rfid/lookup          - look up a lot/serial by rfid_tag
    GET  /api/stock/rfid/lots            - list all lots/serials (with filters)
    POST /api/stock/rfid/register        - create a lot/serial mapped to an rfid_tag
    DELETE /api/stock/rfid/<int:lot_id>  - remove a lot/serial record
    POST /api/stock/rfid/scan            - resolve rfid_tag → product + stock info
    """

    # -------------------------------------------------------------------------
    # Lookup by rfid_tag
    # -------------------------------------------------------------------------

    @validate_token
    @http.route("/api/stock/rfid/lookup", methods=["GET"], type="http", auth="none", csrf=False)
    def lookup(self, **params):
        """
        Resolve an rfid_tag to a lot/serial record.

        Query params:
          - rfid_tag   (str)  required
          - product_id (int)  optional; narrow search to a specific product
        """
        try:
            rfid_tag   = params.get("rfid_tag", "").strip()
            product_id = params.get("product_id")

            if not rfid_tag:
                return invalid_response("missing_field", "rfid_tag is required", 400)

            domain = [("name", "=", rfid_tag)]
            if product_id:
                domain.append(("product_id", "=", int(product_id)))

            lots = request.env["stock.lot"].sudo().search(domain)
            if not lots:
                return invalid_response("not_found", "No lot/serial found for rfid_tag '%s'" % rfid_tag, 404)

            return valid_response({"data": [_lot_data(l) for l in lots]})
        except Exception as e:
            _logger.exception("Error in RFID lookup")
            return invalid_response("server_error", str(e), 500)

    # -------------------------------------------------------------------------
    # List lots / serials
    # -------------------------------------------------------------------------

    @validate_token
    @http.route("/api/stock/rfid/lots", methods=["GET"], type="http", auth="none", csrf=False)
    def list_lots(self, **params):
        """
        List lot/serial numbers.

        Query params (all optional):
          - product_id  (int)
          - search      (str)  partial match on lot name / rfid_tag
          - limit       (int, default 100)
          - offset      (int, default 0)
        """
        try:
            limit      = int(params.get("limit",  100))
            offset     = int(params.get("offset", 0))
            product_id = params.get("product_id")
            search     = params.get("search", "")

            domain = []
            if product_id:
                domain.append(("product_id", "=", int(product_id)))
            if search:
                domain.append(("name", "ilike", search))

            lots  = request.env["stock.lot"].sudo().search(domain, limit=limit, offset=offset, order="name asc")
            total = request.env["stock.lot"].sudo().search_count(domain)

            return valid_response({
                "total":  total,
                "limit":  limit,
                "offset": offset,
                "data":   [_lot_data(l) for l in lots],
            })
        except Exception as e:
            _logger.exception("Error listing lots")
            return invalid_response("server_error", str(e), 500)

    # -------------------------------------------------------------------------
    # Register (create) rfid_tag → lot/serial
    # -------------------------------------------------------------------------

    @validate_token
    @http.route("/api/stock/rfid/register", methods=["POST"], type="http", auth="none", csrf=False)
    def register(self, **params):
        """
        Register an RFID tag as a lot/serial number.

        JSON body:
        {
            "rfid_tag":        "<str>",   -- required; becomes the lot/serial name
            "product_id":      <int>,     -- required
            "expiration_date": "YYYY-MM-DD"  -- optional; for lots with expiry
        }
        """
        try:
            body    = request.httprequest.get_data(as_text=True)
            payload = json.loads(body) if body else {}

            rfid_tag   = (payload.get("rfid_tag") or "").strip()
            product_id = payload.get("product_id")

            if not rfid_tag:
                return invalid_response("missing_field", "rfid_tag is required", 400)
            if not product_id:
                return invalid_response("missing_field", "product_id is required", 400)

            product = request.env["product.product"].sudo().browse(int(product_id))
            if not product.exists():
                return invalid_response("not_found", "Product not found", 404)
            if product.tracking == "none":
                return invalid_response(
                    "tracking_disabled",
                    "Product '%s' has no lot/serial tracking enabled" % product.display_name,
                    400,
                )

            # Prevent duplicates
            existing = request.env["stock.lot"].sudo().search([
                ("name",       "=", rfid_tag),
                ("product_id", "=", product.id),
            ], limit=1)
            if existing:
                return valid_response(_lot_data(existing))

            vals = {
                "name":       rfid_tag,
                "product_id": product.id,
                "company_id": request.env.company.id,
            }
            if payload.get("expiration_date"):
                vals["expiration_date"] = payload["expiration_date"]

            lot = request.env["stock.lot"].sudo().create(vals)
            _logger.info("RFID tag '%s' registered as lot id=%s for product %s", rfid_tag, lot.id, product.display_name)

            return valid_response(_lot_data(lot), status=201)
        except json.JSONDecodeError:
            return invalid_response("invalid_json", "Request body is not valid JSON", 400)
        except Exception as e:
            _logger.exception("Error registering RFID tag")
            return invalid_response("server_error", str(e), 500)

    # -------------------------------------------------------------------------
    # Delete a lot/serial
    # -------------------------------------------------------------------------

    @validate_token
    @http.route("/api/stock/rfid/<int:lot_id>", methods=["DELETE"], type="http", auth="none", csrf=False)
    def delete_lot(self, lot_id, **params):
        """
        Delete a lot/serial (and its associated RFID tag).

        Only allowed when no stock moves reference the lot.
        """
        try:
            lot = request.env["stock.lot"].sudo().browse(lot_id)
            if not lot.exists():
                return invalid_response("not_found", "Lot/serial not found", 404)

            if lot.product_qty > 0:
                return invalid_response(
                    "stock_exists",
                    "Cannot delete lot '%s': it still has %.2f units on hand" % (lot.name, lot.product_qty),
                    400,
                )

            name = lot.name
            lot.unlink()
            return valid_response({"deleted": True, "rfid_tag": name})
        except Exception as e:
            _logger.exception("Error deleting lot %s", lot_id)
            return invalid_response("server_error", str(e), 500)

    # -------------------------------------------------------------------------
    # Scan — full stock info for an rfid_tag
    # -------------------------------------------------------------------------

    @validate_token
    @http.route("/api/stock/rfid/scan", methods=["POST"], type="http", auth="none", csrf=False)
    def scan(self, **params):
        """
        Scan an RFID tag and return full stock context.

        Useful for handheld RFID readers during receiving / transfer / delivery.

        JSON body:
        {
            "rfid_tag":    "<str>",   -- required
            "location_id": <int>      -- optional; show qty at a specific location
        }

        Returns product info, lot/serial details, and on-hand quantity.
        """
        try:
            body    = request.httprequest.get_data(as_text=True)
            payload = json.loads(body) if body else {}

            rfid_tag    = (payload.get("rfid_tag") or "").strip()
            location_id = payload.get("location_id")

            if not rfid_tag:
                return invalid_response("missing_field", "rfid_tag is required", 400)

            lots = request.env["stock.lot"].sudo().search([("name", "=", rfid_tag)])
            if not lots:
                return invalid_response("not_found", "RFID tag '%s' not registered" % rfid_tag, 404)

            results = []
            for lot in lots:
                product = lot.product_id

                # Build quant domain
                quant_domain = [
                    ("lot_id",     "=", lot.id),
                    ("product_id", "=", product.id),
                ]
                if location_id:
                    quant_domain.append(("location_id", "=", int(location_id)))
                else:
                    quant_domain.append(("location_id.usage", "=", "internal"))

                quants = request.env["stock.quant"].sudo().search(quant_domain)
                stock_locations = [
                    {
                        "location_id":   q.location_id.id,
                        "location_name": q.location_id.complete_name,
                        "qty":           q.quantity,
                        "reserved_qty":  q.reserved_quantity,
                        "available_qty": q.quantity - q.reserved_quantity,
                    }
                    for q in quants
                ]

                results.append({
                    "rfid_tag":        lot.name,
                    "lot_id":          lot.id,
                    "lot_name":        lot.name,
                    "product_id":      product.id,
                    "product_name":    product.display_name,
                    "default_code":    product.default_code or "",
                    "barcode":         product.barcode or "",
                    "tracking":        product.tracking,
                    "uom":             product.uom_id.name,
                    "uom_id":          product.uom_id.id,
                    "expiration_date": lot.expiration_date.strftime("%Y-%m-%d") if lot.expiration_date else "",
                    "total_qty":       lot.product_qty,
                    "stock_locations": stock_locations,
                })

            return valid_response({"data": results})
        except json.JSONDecodeError:
            return invalid_response("invalid_json", "Request body is not valid JSON", 400)
        except Exception as e:
            _logger.exception("Error scanning RFID tag")
            return invalid_response("server_error", str(e), 500)
