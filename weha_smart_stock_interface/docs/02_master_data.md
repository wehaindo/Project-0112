# Master Data — Products, Warehouses & Locations

Use these endpoints to sync the product catalogue and discover available warehouses and storage locations before creating stock operations.

---

## Prerequisites

Obtain a token first. See [Authentication](./01_authentication.md).

```python
# Shared setup used in all examples below
import requests

BASE_URL = "http://localhost:8069"
TOKEN    = "xK9mT2pL..."   # replace with your token

HEADERS = {
    "access_token": TOKEN,
    "Content-Type": "application/json",
}
```

---

## 1. List Products

**`GET /api/stock/product`**

Returns active storable/consumable products with current stock quantities.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Max records to return |
| `offset` | int | 0 | Pagination offset |
| `search` | string | — | Search by name, barcode, or internal reference |
| `category_id` | int | — | Filter by product category ID |

### cURL

```bash
# All products
curl -X GET "http://localhost:8069/api/stock/product" \
  -H "access_token: xK9mT2pL..."

# Search by name with pagination
curl -X GET "http://localhost:8069/api/stock/product?search=laptop&limit=20&offset=0" \
  -H "access_token: xK9mT2pL..."

# Filter by category
curl -X GET "http://localhost:8069/api/stock/product?category_id=5" \
  -H "access_token: xK9mT2pL..."
```

### Python

```python
# List all products
resp = requests.get(f"{BASE_URL}/api/stock/product", headers=HEADERS)
data = resp.json()
print(f"Total products: {data['total']}")
for product in data["data"]:
    print(f"  [{product['default_code']}] {product['name']} — qty: {product['qty_available']}")

# Search with pagination
params = {"search": "laptop", "limit": 20, "offset": 0}
resp = requests.get(f"{BASE_URL}/api/stock/product", headers=HEADERS, params=params)
products = resp.json()["data"]
```

### Success Response `200`

```json
{
  "total": 250,
  "limit": 100,
  "offset": 0,
  "data": [
    {
      "id": 42,
      "product_tmpl_id": 38,
      "name": "Laptop ASUS VivoBook [BLK]",
      "default_code": "LAP-001",
      "barcode": "8991234567890",
      "uom": "Unit(s)",
      "uom_id": 1,
      "uom_po_id": 1,
      "category": "All / Saleable / Electronics",
      "category_id": 5,
      "type": "product",
      "tracking": "none",
      "active": true,
      "qty_available": 15.0,
      "virtual_available": 10.0,
      "image_url": "/web/image/product.product/42/image_128"
    }
  ]
}
```

---

## 2. Get Single Product

**`GET /api/stock/product/<id>`**

Returns full product details including supplier pricelists.

### cURL

```bash
curl -X GET "http://localhost:8069/api/stock/product/42" \
  -H "access_token: xK9mT2pL..."
```

### Python

```python
product_id = 42
resp = requests.get(f"{BASE_URL}/api/stock/product/{product_id}", headers=HEADERS)
product = resp.json()
print(product["name"], product["qty_available"])
print("Suppliers:", product["suppliers"])
```

### Success Response `200`

```json
{
  "id": 42,
  "product_tmpl_id": 38,
  "name": "Laptop ASUS VivoBook [BLK]",
  "default_code": "LAP-001",
  "barcode": "8991234567890",
  "description": "High performance laptop",
  "uom": "Unit(s)",
  "uom_id": 1,
  "uom_po_id": 1,
  "category": "All / Saleable / Electronics",
  "category_id": 5,
  "type": "product",
  "tracking": "none",
  "active": true,
  "qty_available": 15.0,
  "virtual_available": 10.0,
  "suppliers": [
    {
      "partner_id": 12,
      "partner_name": "PT Supplier ABC",
      "price": 8500000.0,
      "currency": "IDR",
      "min_qty": 1.0
    }
  ],
  "image_url": "/web/image/product.product/42/image_128"
}
```

### Error Response `404`

```json
{
  "type": "not_found",
  "message": "Product not found"
}
```

---

## 3. List Warehouses

**`GET /api/stock/warehouse`**

Returns all warehouses in the current company. Use the `id` and location IDs when creating stock operations.

### cURL

```bash
curl -X GET "http://localhost:8069/api/stock/warehouse" \
  -H "access_token: xK9mT2pL..."
```

### Python

```python
resp = requests.get(f"{BASE_URL}/api/stock/warehouse", headers=HEADERS)
warehouses = resp.json()["data"]
for wh in warehouses:
    print(f"[{wh['id']}] {wh['name']} ({wh['code']}) — stock loc: {wh['lot_stock_name']}")
```

### Success Response `200`

```json
{
  "total": 2,
  "data": [
    {
      "id": 1,
      "name": "Main Warehouse",
      "code": "WH",
      "company_id": 1,
      "company_name": "My Company",
      "lot_stock_id": 8,
      "lot_stock_name": "WH/Stock",
      "view_location_id": 7,
      "view_location_name": "WH",
      "wh_input_stock_loc_id": 9,
      "wh_output_stock_loc_id": 10,
      "reception_steps": "one_step",
      "delivery_steps": "one_step"
    },
    {
      "id": 2,
      "name": "Jakarta Warehouse",
      "code": "JKT",
      "company_id": 1,
      "company_name": "My Company",
      "lot_stock_id": 15,
      "lot_stock_name": "JKT/Stock",
      "view_location_id": 14,
      "view_location_name": "JKT",
      "wh_input_stock_loc_id": 16,
      "wh_output_stock_loc_id": 17,
      "reception_steps": "two_steps",
      "delivery_steps": "one_step"
    }
  ]
}
```

---

## 4. List Locations

**`GET /api/stock/location`**

Returns stock locations. Useful for choosing `location_id` / `location_dest_id` in transfer/delivery requests.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `usage` | string | `internal` | `internal` \| `supplier` \| `customer` \| `inventory` \| `transit` |
| `warehouse_id` | int | — | Filter locations belonging to a warehouse |
| `search` | string | — | Filter by complete location name |

### cURL

```bash
# All internal locations
curl -X GET "http://localhost:8069/api/stock/location" \
  -H "access_token: xK9mT2pL..."

# Supplier locations (vendor source for receipts)
curl -X GET "http://localhost:8069/api/stock/location?usage=supplier" \
  -H "access_token: xK9mT2pL..."

# Locations inside a specific warehouse
curl -X GET "http://localhost:8069/api/stock/location?warehouse_id=2" \
  -H "access_token: xK9mT2pL..."
```

### Python

```python
# Get internal locations for warehouse 1
params = {"usage": "internal", "warehouse_id": 1}
resp = requests.get(f"{BASE_URL}/api/stock/location", headers=HEADERS, params=params)
locations = resp.json()["data"]
for loc in locations:
    print(f"[{loc['id']}] {loc['complete_name']}")
```

### Success Response `200`

```json
{
  "total": 4,
  "data": [
    {
      "id": 8,
      "name": "Stock",
      "complete_name": "WH/Stock",
      "usage": "internal",
      "location_id": 7,
      "parent_name": "WH",
      "barcode": "",
      "active": true
    },
    {
      "id": 11,
      "name": "Shelf A",
      "complete_name": "WH/Stock/Shelf A",
      "usage": "internal",
      "location_id": 8,
      "parent_name": "WH/Stock",
      "barcode": "LOC-SHELF-A",
      "active": true
    }
  ]
}
```
