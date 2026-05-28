# RFID & Lot/Serial Numbers

RFID tags are used directly as **serial numbers** — there is no separate RFID field.  
The `rfid_tag` value you submit becomes the `name` of the `stock.lot` record in Odoo.

---

## How It Works

```
RFID Reader scans tag  →  rfid_tag = "SN-RFID-0001"
                       →  Odoo lot.name = "SN-RFID-0001"
                       →  qty_done = 1  (always)
```

> ⚠️ **One RFID tag = one physical item.** Each tag is globally unique.  
> `qty_done` **must always be `1`** when using `rfid_tag`.  
> To receive, transfer, or ship multiple units as a batch lot, use `lot_name` or `lot_id` with the full quantity.

| Field in API | Odoo field | `qty_done` | Use case |
|---|---|---|---|
| `rfid_tag` | `stock.lot.name` | **Must be `1`** | 1 physical item with unique RFID tag |
| `lot_name` | `stock.lot.name` | Any quantity | Multiple units under one batch/lot name |
| `lot_id` | `stock.lot.id` | Any quantity | Same as `lot_name` but using DB id |

The lot record is **auto-created** if it does not yet exist when `rfid_tag` or `lot_name` is submitted during a validate operation.

---

## Prerequisites

```python
import requests, json

BASE_URL = "http://localhost:8069"
HEADERS  = {
    "access_token": "xK9mT2pL...",
    "Content-Type": "application/json",
}
```

---

## 1. Lookup RFID Tag

**`GET /api/stock/rfid/lookup`**

Resolve an RFID tag to its lot/serial record.

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `rfid_tag` | string | ✅ | The RFID tag value to look up |
| `product_id` | int | ❌ | Narrow search to a specific product |

### cURL

```bash
curl -X GET "http://localhost:8069/api/stock/rfid/lookup?rfid_tag=SN-RFID-0001" \
  -H "access_token: xK9mT2pL..."

# Narrow to a product
curl -X GET "http://localhost:8069/api/stock/rfid/lookup?rfid_tag=SN-RFID-0001&product_id=42" \
  -H "access_token: xK9mT2pL..."
```

### Python

```python
resp = requests.get(
    f"{BASE_URL}/api/stock/rfid/lookup",
    headers=HEADERS,
    params={"rfid_tag": "SN-RFID-0001"},
)
data = resp.json()
if "data" in data:
    lot = data["data"][0]
    print(f"Lot: {lot['lot_name']} | Product: {lot['product_name']} | Qty: {lot['qty_available']}")
```

### Success Response `200`

```json
{
  "data": [
    {
      "id": 88,
      "name": "SN-RFID-0001",
      "rfid_tag": "SN-RFID-0001",
      "product_id": 42,
      "product_name": "Laptop ASUS VivoBook [BLK]",
      "default_code": "LAP-001",
      "barcode": "8991234567890",
      "tracking": "serial",
      "qty_available": 1.0,
      "expiration_date": ""
    }
  ]
}
```

### Error Response `404`

```json
{"type": "not_found", "message": "No lot/serial found for rfid_tag 'SN-RFID-XXXX'"}
```

---

## 2. Scan RFID Tag (Full Stock Context)

**`POST /api/stock/rfid/scan`**

The primary endpoint for handheld RFID readers during warehouse operations.  
Returns the product details, lot info, and stock quantities per location.

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `rfid_tag` | string | ✅ | RFID tag scanned by reader |
| `location_id` | int | ❌ | Show qty at a specific location only |

### cURL

```bash
# Scan tag — all locations
curl -X POST "http://localhost:8069/api/stock/rfid/scan" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{"rfid_tag": "SN-RFID-0001"}'

# Scan tag at a specific location
curl -X POST "http://localhost:8069/api/stock/rfid/scan" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{"rfid_tag": "LOT-RFID-BB01", "location_id": 8}'
```

### Python

```python
scan_payload = {"rfid_tag": "LOT-RFID-BB01", "location_id": 8}
resp = requests.post(f"{BASE_URL}/api/stock/rfid/scan", headers=HEADERS, data=json.dumps(scan_payload))
for item in resp.json()["data"]:
    print(f"Product: {item['product_name']} | Lot: {item['lot_name']} | Total: {item['total_qty']}")
    for loc in item["stock_locations"]:
        print(f"  {loc['location_name']}: available={loc['available_qty']}, reserved={loc['reserved_qty']}")
```

### Success Response `200`

```json
{
  "data": [
    {
      "rfid_tag": "LOT-RFID-BB01",
      "lot_id": 91,
      "lot_name": "LOT-RFID-BB01",
      "product_id": 55,
      "product_name": "Cable UTP Cat6 [500m]",
      "default_code": "CBL-002",
      "barcode": "8991234500001",
      "tracking": "lot",
      "uom": "Roll(s)",
      "uom_id": 3,
      "expiration_date": "2027-12-31",
      "total_qty": 20.0,
      "stock_locations": [
        {
          "location_id": 8,
          "location_name": "WH/Stock",
          "qty": 15.0,
          "reserved_qty": 5.0,
          "available_qty": 10.0
        },
        {
          "location_id": 11,
          "location_name": "WH/Stock/Shelf A",
          "qty": 5.0,
          "reserved_qty": 0.0,
          "available_qty": 5.0
        }
      ]
    }
  ]
}
```

---

## 3. List Lots / Serials

**`GET /api/stock/rfid/lots`**

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `product_id` | int | — | Filter by product |
| `search` | string | — | Partial match on lot name / rfid_tag |
| `limit` | int | 100 | Max records |
| `offset` | int | 0 | Pagination offset |

### cURL

```bash
# All lots
curl -X GET "http://localhost:8069/api/stock/rfid/lots" \
  -H "access_token: xK9mT2pL..."

# All serials for product 42
curl -X GET "http://localhost:8069/api/stock/rfid/lots?product_id=42" \
  -H "access_token: xK9mT2pL..."

# Search by RFID prefix
curl -X GET "http://localhost:8069/api/stock/rfid/lots?search=SN-RFID" \
  -H "access_token: xK9mT2pL..."
```

### Python

```python
params = {"product_id": 42, "search": "SN-RFID", "limit": 50}
resp = requests.get(f"{BASE_URL}/api/stock/rfid/lots", headers=HEADERS, params=params)
data = resp.json()
print(f"Found {data['total']} lots")
for lot in data["data"]:
    print(f"  [{lot['id']}] {lot['rfid_tag']} — qty: {lot['qty_available']}")
```

---

## 4. Register RFID Tag

**`POST /api/stock/rfid/register`**

Pre-register an RFID tag as a lot/serial before it enters the warehouse (e.g. during goods labelling).

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `rfid_tag` | string | ✅ | RFID tag value — becomes lot/serial name |
| `product_id` | int | ✅ | Product this tag belongs to |
| `expiration_date` | string | ❌ | `YYYY-MM-DD` — for lots with expiry tracking |

> Returns the existing lot record if the tag is already registered (idempotent).

### cURL

```bash
# Register a serial number
curl -X POST "http://localhost:8069/api/stock/rfid/register" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{
    "rfid_tag": "SN-RFID-0099",
    "product_id": 42
  }'

# Register a lot with expiry date
curl -X POST "http://localhost:8069/api/stock/rfid/register" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{
    "rfid_tag": "LOT-RFID-EXP01",
    "product_id": 55,
    "expiration_date": "2027-06-30"
  }'
```

### Python

```python
payload = {
    "rfid_tag": "SN-RFID-0099",
    "product_id": 42,
}
resp = requests.post(f"{BASE_URL}/api/stock/rfid/register", headers=HEADERS, data=json.dumps(payload))
lot = resp.json()
print(f"Registered: lot_id={lot['id']} rfid_tag={lot['rfid_tag']}")
```

### Success Response `201` (new) / `200` (already exists)

```json
{
  "id": 120,
  "name": "SN-RFID-0099",
  "rfid_tag": "SN-RFID-0099",
  "product_id": 42,
  "product_name": "Laptop ASUS VivoBook [BLK]",
  "tracking": "serial",
  "qty_available": 0.0,
  "expiration_date": ""
}
```

### Error — tracking not enabled

```json
{"type": "tracking_disabled", "message": "Product 'Widget X' has no lot/serial tracking enabled"}
```

---

## 5. Delete Lot / RFID Tag

**`DELETE /api/stock/rfid/<lot_id>`**

Remove a lot/serial registration. Only permitted when the lot has **zero** on-hand stock.

### cURL

```bash
curl -X DELETE "http://localhost:8069/api/stock/rfid/120" \
  -H "access_token: xK9mT2pL..."
```

### Python

```python
lot_id = 120
resp = requests.delete(f"{BASE_URL}/api/stock/rfid/{lot_id}", headers=HEADERS)
print(resp.json())  # {"deleted": true, "rfid_tag": "SN-RFID-0099"}
```

### Success Response `200`

```json
{"deleted": true, "rfid_tag": "SN-RFID-0099"}
```

### Error — stock still exists

```json
{"type": "stock_exists", "message": "Cannot delete lot 'SN-RFID-0099': it still has 1.00 units on hand"}
```

---

## Typical RFID Warehouse Workflow

### 1 — Receiving with RFID scanner

```python
# Step 1: Create the receipt
receipt = requests.post(f"{BASE_URL}/api/stock/receiving", headers=HEADERS, data=json.dumps({
    "warehouse_id": 1, "origin": "PO/2026/020",
    "lines": [{"product_id": 42, "qty": 3}],
})).json()
receipt_id = receipt["id"]
move_id = requests.get(f"{BASE_URL}/api/stock/receiving/{receipt_id}", headers=HEADERS) \
    .json()["move_lines"][0]["move_id"]

# Step 2: Operator scans RFID tags one by one at receiving dock
scanned = ["SN-RFID-AA10", "SN-RFID-AA11", "SN-RFID-AA12"]

requests.post(f"{BASE_URL}/api/stock/receiving/{receipt_id}/validate", headers=HEADERS,
    data=json.dumps({
        "backorder": False,
        "lines": [{"move_id": move_id, "qty_done": 1, "rfid_tag": tag} for tag in scanned],
    })
)
```

### 2 — Transfer with RFID scanner

```python
# Create transfer, get move_id, then validate with RFID tags
transfer = requests.post(f"{BASE_URL}/api/stock/transfer", headers=HEADERS, data=json.dumps({
    "warehouse_id": 1, "location_id": 8, "location_dest_id": 11,
    "lines": [{"product_id": 42, "qty": 2}],
})).json()
transfer_id = transfer["id"]
move_id = requests.get(f"{BASE_URL}/api/stock/transfer/{transfer_id}", headers=HEADERS) \
    .json()["move_lines"][0]["move_id"]

requests.post(f"{BASE_URL}/api/stock/transfer/{transfer_id}/validate", headers=HEADERS,
    data=json.dumps({
        "lines": [
            {"move_id": move_id, "qty_done": 1, "rfid_tag": "SN-RFID-AA10"},
            {"move_id": move_id, "qty_done": 1, "rfid_tag": "SN-RFID-AA11"},
        ],
    })
)
```

### 3 — Delivery with RFID gate scanner

```python
# Check RFID tag before shipping
scan = requests.post(f"{BASE_URL}/api/stock/rfid/scan", headers=HEADERS,
    data=json.dumps({"rfid_tag": "SN-RFID-AA10", "location_id": 8})).json()
available = scan["data"][0]["stock_locations"][0]["available_qty"]

if available >= 1:
    delivery = requests.post(f"{BASE_URL}/api/stock/delivery", headers=HEADERS, data=json.dumps({
        "warehouse_id": 1, "partner_id": 25,
        "lines": [{"product_id": 42, "qty": 1}],
    })).json()
    delivery_id = delivery["id"]
    move_id = requests.get(f"{BASE_URL}/api/stock/delivery/{delivery_id}", headers=HEADERS) \
        .json()["move_lines"][0]["move_id"]

    requests.post(f"{BASE_URL}/api/stock/delivery/{delivery_id}/validate", headers=HEADERS,
        data=json.dumps({
            "lines": [{"move_id": move_id, "qty_done": 1, "rfid_tag": "SN-RFID-AA10"}],
        })
    )
```
