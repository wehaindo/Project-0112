import json
import logging

from odoo import http
from odoo.http import request
from odoo.addons.weha_base_api.libs.common import invalid_response, valid_response
from odoo.addons.weha_base_api.contollers.main import validate_token

_logger = logging.getLogger(__name__)


class StockProductAPI(http.Controller):
    """
    Product master sync endpoints.

    GET  /api/stock/product          - list products (with optional filters)
    GET  /api/stock/product/<int:id> - single product detail
    GET  /api/stock/warehouse        - list warehouses
    GET  /api/stock/location         - list stock locations
    """

    # -------------------------------------------------------------------------
    # Products
    # -------------------------------------------------------------------------

    @validate_token
    @http.route("/api/stock/product", methods=["GET"], type="http", auth="none", csrf=False)
    def list_products(self, **params):
        """
        List active storable/consumable products.

        Query params (all optional):
          - limit        (int, default 100)
          - offset       (int, default 0)
          - search       (str) – searches name / barcode / internal reference
          - category_id  (int) – filter by product category id
          - warehouse_id (int) – include qty_available per warehouse location
        """
        try:
            limit  = int(params.get("limit",  100))
            offset = int(params.get("offset", 0))
            search = params.get("search", "")
            category_id = params.get("category_id")

            domain = [("active", "=", True), ("type", "in", ["consu", "product"])]
            if search:
                domain += [
                    "|", "|",
                    ("name",            "ilike", search),
                    ("default_code",    "ilike", search),
                    ("barcode",         "ilike", search),
                ]
            if category_id:
                domain.append(("categ_id", "=", int(category_id)))

            products = request.env["product.product"].sudo().search(
                domain, limit=limit, offset=offset, order="name asc"
            )
            total = request.env["product.product"].sudo().search_count(domain)

            data = []
            for p in products:
                data.append({
                    "id":              p.id,
                    "product_tmpl_id": p.product_tmpl_id.id,
                    "name":            p.display_name,
                    "default_code":    p.default_code or "",
                    "barcode":         p.barcode or "",
                    "uom":             p.uom_id.name,
                    "uom_id":          p.uom_id.id,
                    "uom_po_id":       p.uom_po_id.id,
                    "category":        p.categ_id.complete_name,
                    "category_id":     p.categ_id.id,
                    "type":            p.type,
                    "tracking":        p.tracking,
                    "active":          p.active,
                    "qty_available":   p.qty_available,
                    "virtual_available": p.virtual_available,
                    "image_url":       "/web/image/product.product/%d/image_128" % p.id,
                })

            return valid_response({
                "total":   total,
                "limit":   limit,
                "offset":  offset,
                "data":    data,
            })
        except Exception as e:
            _logger.exception("Error fetching products")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route("/api/stock/product/<int:product_id>", methods=["GET"], type="http", auth="none", csrf=False)
    def get_product(self, product_id, **params):
        """Return a single product.product record by id."""
        try:
            product = request.env["product.product"].sudo().browse(product_id)
            if not product.exists():
                return invalid_response("not_found", "Product not found", 404)

            suppliers = []
            for s in product.seller_ids:
                suppliers.append({
                    "partner_id":   s.partner_id.id,
                    "partner_name": s.partner_id.name,
                    "price":        s.price,
                    "currency":     s.currency_id.name,
                    "min_qty":      s.min_qty,
                })

            data = {
                "id":              product.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "name":            product.display_name,
                "default_code":    product.default_code or "",
                "barcode":         product.barcode or "",
                "description":     product.description or "",
                "uom":             product.uom_id.name,
                "uom_id":          product.uom_id.id,
                "uom_po_id":       product.uom_po_id.id,
                "category":        product.categ_id.complete_name,
                "category_id":     product.categ_id.id,
                "type":            product.type,
                "tracking":        product.tracking,
                "active":          product.active,
                "qty_available":   product.qty_available,
                "virtual_available": product.virtual_available,
                "suppliers":       suppliers,
                "image_url":       "/web/image/product.product/%d/image_128" % product.id,
            }
            return valid_response(data)
        except Exception as e:
            _logger.exception("Error fetching product %s", product_id)
            return invalid_response("server_error", str(e), 500)

    # -------------------------------------------------------------------------
    # Warehouses
    # -------------------------------------------------------------------------

    @validate_token
    @http.route("/api/stock/warehouse", methods=["GET"], type="http", auth="none", csrf=False)
    def list_warehouses(self, **params):
        """Return all warehouses accessible by the current company."""
        try:
            warehouses = request.env["stock.warehouse"].sudo().search([
                ("company_id", "in", request.env.user.company_ids.ids)
            ])
            data = []
            for w in warehouses:
                data.append({
                    "id":                    w.id,
                    "name":                  w.name,
                    "code":                  w.code,
                    "company_id":            w.company_id.id,
                    "company_name":          w.company_id.name,
                    "lot_stock_id":          w.lot_stock_id.id,
                    "lot_stock_name":        w.lot_stock_id.complete_name,
                    "view_location_id":      w.view_location_id.id,
                    "view_location_name":    w.view_location_id.complete_name,
                    "wh_input_stock_loc_id": w.wh_input_stock_loc_id.id,
                    "wh_output_stock_loc_id": w.wh_output_stock_loc_id.id,
                    "reception_steps":       w.reception_steps,
                    "delivery_steps":        w.delivery_steps,
                })
            return valid_response({"total": len(data), "data": data})
        except Exception as e:
            _logger.exception("Error fetching warehouses")
            return invalid_response("server_error", str(e), 500)

    # -------------------------------------------------------------------------
    # Locations
    # -------------------------------------------------------------------------

    @validate_token
    @http.route("/api/stock/location", methods=["GET"], type="http", auth="none", csrf=False)
    def list_locations(self, **params):
        """
        Return stock locations.

        Query params (all optional):
          - warehouse_id (int)  – filter by warehouse view location
          - usage        (str)  – internal | supplier | customer | inventory | transit
          - search       (str)  – filter by name
        """
        try:
            usage       = params.get("usage", "internal")
            search      = params.get("search", "")
            warehouse_id = params.get("warehouse_id")

            domain = [("active", "=", True), ("usage", "=", usage)]
            if search:
                domain.append(("complete_name", "ilike", search))
            if warehouse_id:
                warehouse = request.env["stock.warehouse"].sudo().browse(int(warehouse_id))
                if warehouse.exists():
                    domain.append(
                        ("complete_name", "ilike", warehouse.code)
                    )

            locations = request.env["stock.location"].sudo().search(domain, order="complete_name asc")
            data = []
            for loc in locations:
                data.append({
                    "id":            loc.id,
                    "name":          loc.name,
                    "complete_name": loc.complete_name,
                    "usage":         loc.usage,
                    "location_id":   loc.location_id.id,
                    "parent_name":   loc.location_id.complete_name,
                    "barcode":       loc.barcode or "",
                    "active":        loc.active,
                })
            return valid_response({"total": len(data), "data": data})
        except Exception as e:
            _logger.exception("Error fetching locations")
            return invalid_response("server_error", str(e), 500)
