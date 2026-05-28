# Receiving (Incoming Shipments)

Use these endpoints to create and manage incoming stock receipts from vendors.  
For lot/serial tracked products (including RFID-tagged items), pass `rfid_tag`, `lot_name`, or `lot_id` in the validate payload.

> ⚠️ **RFID Rule:** Each physical item has **one unique RFID tag**. When using `rfid_tag`, `qty_done` must always be `1`. To receive multiple units as a batch lot, use `lot_name` or `lot_id` with the full quantity instead.

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

> **Lot / RFID resolution priority:** `lot_id` → `rfid_tag` → `lot_name`  
> The server auto-creates the lot/serial if it does not yet exist.

---

## 1. List Receipts

**`GET /api/stock/receiving`**

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `warehouse_id` | int | — | Filter by warehouse |
| `state` | string | — | `draft` \| `confirmed` \| `assigned` \| `done` \| `cancel` |
| `origin` | string | — | Filter by source document (partial match) |
| `limit` | int | 50 | Max records |
| `offset` | int | 0 | Pagination offset |

### cURL

```bash
curl -X GET "http://localhost:8069/api/stock/receiving?warehouse_id=1&state=assigned" \
  -H "access_token: xK9mT2pL..."
```

### Python

```python
params = {"warehouse_id": 1, "state": "assigned", "limit": 20}
resp = requests.get(f"{BASE_URL}/api/stock/receiving", headers=HEADERS, params=params)
for r in resp.json()["data"]:
    print(f"  {r['name']} — {r['state']} — origin: {r['origin']}")
```

### move_lines — lot/serial/RFID fields

```json
{
  "move_id": 201,
  "product_id": 42,
  "product_name": "Laptop ASUS VivoBook [BLK]",
  "tracking": "serial",
  "uom": "Unit(s)",
  "product_qty": 3.0,
  "quantity_done": 0.0,
  "state": "assigned",
  "lots": [
    {
      "move_line_id": 301,
      "lot_id": 88,
      "lot_name": "SN-RFID-0001",
      "rfid_tag": "SN-RFID-0001",
      "qty_reserved": 1.0,
      "qty_done": 0.0
    }
  ]
}
```

---

## 2. Get Receipt Detail

**`GET /api/stock/receiving/<id>`**

```bash
curl -X GET "http://localhost:8069/api/stock/receiving/101" \
  -H "access_token: xK9mT2pL..."
```

---

## 3. Create Receipt

**`POST /api/stock/receiving`**

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `warehouse_id` | int | ✅ | Determines receiving picking type |
| `lines` | array | ✅ | Products to receive |
| `lines[].product_id` | int | ✅ | Product ID |
| `lines[].qty` | float | ✅ | Expected quantity |
| `lines[].uom_id` | int | ❌ | Unit of measure |
| `location_dest_id` | int | ❌ | Override destination location |
| `partner_id` | int | ❌ | Vendor partner ID |
| `origin` | string | ❌ | Source document (e.g. PO number) |
| `scheduled_date` | string | ❌ | `YYYY-MM-DD` |
| `note` | string | ❌ | Internal note |

> Lot/serial numbers are assigned during **validate**, not during create.

### cURL

```bash
curl -X POST "http://localhost:8069/api/stock/receiving" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{
    "warehouse_id": 1,
    "partner_id": 12,
    "origin": "PO/2026/002",
    "lines": [
      {"product_id": 42, "qty": 5},
      {"product_id": 55, "qty": 3}
    ]
  }'
```

### Success Response `201`

```json
{"id": 105, "name": "WH/IN/00005", "state": "assigned"}
```

---

## 4. Validate Receipt

**`POST /api/stock/receiving/<id>/validate`**

### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `lines` | array | Per-line actual quantities and lot/RFID. Omit to auto-fill demand qty. |
| `lines[].move_id` | int | **Required** — move ID from receipt detail |
| `lines[].qty_done` | float | **Required** — actual quantity received |
| `lines[].rfid_tag` | string | Unique RFID tag for **1 physical item** — `qty_done` must be `1`. Auto-created if not registered. |
| `lines[].lot_name` | string | Batch/lot name — use when receiving multiple units under a single lot number |
| `lines[].lot_id` | int | Use an existing lot by ID |
| `backorder` | bool | `true` = create backorder for remaining (default). `false` = cancel. |

---

### Example A — Auto-complete (no lot tracking)

```bash
curl -X POST "http://localhost:8069/api/stock/receiving/105/validate" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### Example B — Lot-tracked product (multiple units in one batch)

For products tracked by lot number, use `lot_name` with the full batch quantity.  
`rfid_tag` cannot be used here because it always represents exactly **1 physical item**.

```bash
curl -X POST "http://localhost:8069/api/stock/receiving/105/validate" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{
    "backorder": false,
    "lines": [
      {"move_id": 210, "qty_done": 10, "lot_name": "BATCH-2026-A01"}
    ]
  }'
```

```python
validate_payload = {
    "backorder": False,
    "lines": [{"move_id": 210, "qty_done": 10, "lot_name": "BATCH-2026-A01"}],
}
resp = requests.post(
    f"{BASE_URL}/api/stock/receiving/105/validate",
    headers=HEADERS, data=json.dumps(validate_payload),
)
print(resp.json())
```

---

### Example C — Serial-tracked product (one RFID per unit)

```python
serials = ["SN-RFID-0001", "SN-RFID-0002", "SN-RFID-0003"]

validate_payload = {
    "backorder": False,
    "lines": [
        {"move_id": 211, "qty_done": 1, "rfid_tag": tag}
        for tag in serials
    ],
}
resp = requests.post(
    f"{BASE_URL}/api/stock/receiving/106/validate",
    headers=HEADERS, data=json.dumps(validate_payload),
)
print(resp.json())
```

---

### Example D — Mixed lines

```python
validate_payload = {
    "backorder": False,
    "lines": [
        {"move_id": 210, "qty_done": 5, "lot_name": "BATCH-2026-B01"},  # lot-tracked (5 units, 1 lot)
        {"move_id": 212, "qty_done": 3},                                 # not tracked
    ],
}
```

---

### Full End-to-End Flow (Python)

```python
import requests, json

BASE_URL = "http://localhost:8069"
HEADERS  = {"access_token": "xK9mT2pL...", "Content-Type": "application/json"}

# 1. Create receipt
payload = {
    "warehouse_id": 1, "origin": "PO/2026/010", "partner_id": 12,
    "lines": [
        {"product_id": 42, "qty": 3},   # serial-tracked
        {"product_id": 55, "qty": 10},  # lot-tracked
        {"product_id": 60, "qty": 6},   # not tracked
    ],
}
resp = requests.post(f"{BASE_URL}/api/stock/receiving", headers=HEADERS, data=json.dumps(payload))
receipt_id = resp.json()["id"]

# 2. Get move IDs
detail = requests.get(f"{BASE_URL}/api/stock/receiving/{receipt_id}", headers=HEADERS).json()
moves = {m["product_id"]: m["move_id"] for m in detail["move_lines"]}

# 3. Validate with RFID tags
validate_payload = {
    "backorder": False,
    "lines": [
        {"move_id": moves[42], "qty_done": 1, "rfid_tag": "SN-RFID-AA01"},
        {"move_id": moves[42], "qty_done": 1, "rfid_tag": "SN-RFID-AA02"},
        {"move_id": moves[42], "qty_done": 1, "rfid_tag": "SN-RFID-AA03"},
        {"move_id": moves[55], "qty_done": 10, "lot_name": "BATCH-BB01"},   # lot: use lot_name for batch qty
        {"move_id": moves[60], "qty_done": 6},                              # no tracking: qty only
    ],
}
result = requests.post(
    f"{BASE_URL}/api/stock/receiving/{receipt_id}/validate",
    headers=HEADERS, data=json.dumps(validate_payload),
).json()
print(result)  # {"id": ..., "name": "WH/IN/...", "state": "done"}
```

### Success Response `200`

```json
{"id": 105, "name": "WH/IN/00005", "state": "done"}
```
