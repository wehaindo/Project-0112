{
    "name": "WEHA Smart Stock Interface",
    "version": "18.0.1.0",
    "category": "Inventory",
    "depends": ["stock", "weha_base_api"],
    "author": "WEHA",
    "summary": "REST API for Stock: Receiving, Transfer, Delivery, Product Sync & RFID",
    "description": "Provides REST API endpoints for stock operations (receiving, internal transfer, delivery) and master product synchronisation. RFID tags are used as lot/serial numbers for tracked products. Inherits token-based auth from weha_base_api.",
    "website": "https://www.weha-id.com",
    "email": "info@weha-id.com",
    "price": 0,
    "currency": "USD",
    "data": [
        "security/ir.model.access.csv",
    ],
    "auto_install": False,
    "installable": True,
    "license": "LGPL-3",
}
