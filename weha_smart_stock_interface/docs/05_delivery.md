# Delivery Orders

Use these endpoints to create and manage outgoing deliveries to customers.  
For lot/serial tracked products (including RFID-tagged items), pass `rfid_tag`, `lot_name`, or `lot_id` in the validate payload.

> ⚠️ **RFID Rule:** Each physical item has **one unique RFID tag**. When using `rfid_tag`, `qty_done` must always be `1`. To ship multiple units as a batch lot, use `lot_name` or `lot_id` with the full quantity instead.

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

---

## 1. List Delivery Orders

**`GET /api/stock/delivery`**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `warehouse_id` | int | — | Filter by warehouse |
| `state` | string | — | `draft` \| `assigned` \| `done` \| `cancel` |
| `partner_id` | int | — | Filter by customer |
| `origin` | string | — | Filter by source document |
| `limit` | int | 50 | Max records |
| `offset` | int | 0 | Pagination offset |

```bash
curl -X GET "http://localhost:8069/api/stock/delivery?warehouse_id=1&state=assigned" \
  -H "access_token: xK9mT2pL..."
```

### move_lines — lot/serial/RFID fields

```json
{
  "move_id": 401,
  "product_id": 42,
  "tracking": "serial",
  "product_qty": 2.0,
  "lots": [
    {"lot_id": 88, "lot_name": "SN-RFID-0001", "rfid_tag": "SN-RFID-0001", "qty_reserved": 1.0}
  ]
}
```

---

## 2. Get Delivery Detail

**`GET /api/stock/delivery/<id>`**

```bash
curl -X GET "http://localhost:8069/api/stock/delivery/301" \
  -H "access_token: xK9mT2pL..."
```

---

## 3. Create Delivery Order

**`POST /api/stock/delivery`**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `warehouse_id` | int | ✅ | Determines delivery picking type |
| `lines` | array | ✅ | Products to ship |
| `lines[].product_id` | int | ✅ | Product ID |
| `lines[].qty` | float | ✅ | Quantity |
| `partner_id` | int | ❌ | Customer partner ID |
| `location_id` | int | ❌ | Override source location |
| `location_dest_id` | int | ❌ | Override destination |
| `origin` | string | ❌ | Source document (e.g. SO number) |
| `scheduled_date` | string | ❌ | `YYYY-MM-DD` |
| `note` | string | ❌ | Internal note |

```bash
curl -X POST "http://localhost:8069/api/stock/delivery" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{
    "warehouse_id": 1,
    "partner_id": 25,
    "origin": "SO/2026/0046",
    "lines": [
      {"product_id": 42, "qty": 2},
      {"product_id": 55, "qty": 5}
    ]
  }'
```

### Success Response `201`

```json
{"id": 305, "name": "WH/OUT/00005", "state": "assigned"}
```

---

## 4. Validate (Ship) Delivery

**`POST /api/stock/delivery/<id>/validate`**

| Field | Type | Description |
|-------|------|-------------|
| `lines` | array | Per-line actual quantities and lot/RFID. Omit to auto-fill. |
| `lines[].move_id` | int | **Required** — move ID |
| `lines[].qty_done` | float | **Required** — actual qty shipped |
| `lines[].rfid_tag` | string | Unique RFID tag for **1 physical item** — `qty_done` must be `1`. |
| `lines[].lot_name` | string | Batch/lot name — use when shipping multiple units under a single lot number |
| `lines[].lot_id` | int | Use an existing lot by ID |
| `backorder` | bool | `true` = create backorder (default). `false` = cancel. |

---

### Example A — No lot/serial tracking (auto-complete)

```bash
curl -X POST "http://localhost:8069/api/stock/delivery/305/validate" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### Example B — Lot-tracked product (multiple units in one batch)

For products tracked by lot number, use `lot_name` with the full batch quantity.  
`rfid_tag` cannot be used here because it always represents exactly **1 physical item**.

```bash
curl -X POST "http://localhost:8069/api/stock/delivery/305/validate" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{
    "backorder": false,
    "lines": [
      {"move_id": 401, "qty_done": 5, "lot_name": "BATCH-BB01"}
    ]
  }'
```

```python
validate_payload = {
    "backorder": False,
    "lines": [{"move_id": 401, "qty_done": 5, "lot_name": "BATCH-BB01"}],
}
resp = requests.post(
    f"{BASE_URL}/api/stock/delivery/305/validate",
    headers=HEADERS, data=json.dumps(validate_payload),
)
print(resp.json())
```

---

### Example C — Serial-tracked product (RFID gate scanner)

```python
scanned_tags = ["SN-RFID-0001", "SN-RFID-0002"]

validate_payload = {
    "backorder": False,
    "lines": [
        {"move_id": 402, "qty_done": 1, "rfid_tag": tag}
        for tag in scanned_tags
    ],
}
resp = requests.post(
    f"{BASE_URL}/api/stock/delivery/306/validate",
    headers=HEADERS, data=json.dumps(validate_payload),
)
print(resp.json())
```

---

### Example D — Use existing lot by ID

```python
# Step 1: resolve RFID tag to lot_id
lookup = requests.get(
    f"{BASE_URL}/api/stock/rfid/lookup",
    headers=HEADERS,
    params={"rfid_tag": "SN-RFID-0001", "product_id": 42},
).json()
lot_id = lookup["data"][0]["id"]

# Step 2: validate using lot_id
validate_payload = {
    "lines": [{"move_id": 402, "qty_done": 1, "lot_id": lot_id}],
}
resp = requests.post(
    f"{BASE_URL}/api/stock/delivery/306/validate",
    headers=HEADERS, data=json.dumps(validate_payload),
)
```

---

### Full End-to-End Flow (Python)

```python
import requests, json

BASE_URL = "http://localhost:8069"
HEADERS  = {"access_token": "xK9mT2pL...", "Content-Type": "application/json"}

# 1. Create delivery
payload = {
    "warehouse_id": 1, "partner_id": 25, "origin": "SO/2026/0055",
    "lines": [
        {"product_id": 42, "qty": 2},   # serial-tracked
        {"product_id": 55, "qty": 10},  # lot-tracked
        {"product_id": 60, "qty": 4},   # not tracked
    ],
}
resp = requests.post(f"{BASE_URL}/api/stock/delivery", headers=HEADERS, data=json.dumps(payload))
delivery_id = resp.json()["id"]

# 2. Get move IDs
detail = requests.get(f"{BASE_URL}/api/stock/delivery/{delivery_id}", headers=HEADERS).json()
moves = {m["product_id"]: m["move_id"] for m in detail["move_lines"]}

# 3. Validate with RFID tags
validate_payload = {
    "backorder": False,
    "lines": [
        {"move_id": moves[42], "qty_done": 1, "rfid_tag": "SN-RFID-AA01"},
        {"move_id": moves[42], "qty_done": 1, "rfid_tag": "SN-RFID-AA02"},
        {"move_id": moves[55], "qty_done": 10, "lot_name": "BATCH-CC01"},   # lot: use lot_name for batch qty
        {"move_id": moves[60], "qty_done": 4},                              # no tracking: qty only
    ],
}
result = requests.post(
    f"{BASE_URL}/api/stock/delivery/{delivery_id}/validate",
    headers=HEADERS, data=json.dumps(validate_payload),
).json()
print(result)  # {"id": ..., "name": "WH/OUT/...", "state": "done"}
```

### Success Response `200`

```json
{"id": 305, "name": "WH/OUT/00005", "state": "done"}
```

---

## Check Stock Before Creating Delivery

```python
scan_payload = {"rfid_tag": "LOT-RFID-BB01", "location_id": 8}
scan = requests.post(
    f"{BASE_URL}/api/stock/rfid/scan",
    headers=HEADERS, data=json.dumps(scan_payload),
).json()
for loc in scan["data"][0]["stock_locations"]:
    print(f"  {loc['location_name']}: available={loc['available_qty']}")
```
