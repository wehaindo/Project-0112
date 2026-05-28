# Internal Transfer

Use these endpoints to move stock between locations within the same or different warehouses.  
For lot/serial tracked products (including RFID-tagged items), pass `rfid_tag`, `lot_name`, or `lot_id` in the validate payload.

> ⚠️ **RFID Rule:** Each physical item has **one unique RFID tag**. When using `rfid_tag`, `qty_done` must always be `1`. To move multiple units as a batch lot, use `lot_name` or `lot_id` with the full quantity instead.

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

## 1. List Internal Transfers

**`GET /api/stock/transfer`**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `warehouse_id` | int | — | Filter by warehouse |
| `state` | string | — | `draft` \| `assigned` \| `done` \| `cancel` |
| `origin` | string | — | Filter by source document |
| `limit` | int | 50 | Max records |
| `offset` | int | 0 | Pagination offset |

```bash
curl -X GET "http://localhost:8069/api/stock/transfer?warehouse_id=1&state=assigned" \
  -H "access_token: xK9mT2pL..."
```

```python
params = {"warehouse_id": 1, "state": "assigned"}
resp = requests.get(f"{BASE_URL}/api/stock/transfer", headers=HEADERS, params=params)
for t in resp.json()["data"]:
    print(f"  {t['name']} | {t['location_name']} → {t['location_dest_name']}")
```

### move_lines — lot/serial/RFID fields

```json
{
  "move_id": 301,
  "product_id": 42,
  "tracking": "serial",
  "product_qty": 2.0,
  "lots": [
    {"lot_id": 88, "lot_name": "SN-RFID-0001", "rfid_tag": "SN-RFID-0001", "qty_reserved": 1.0},
    {"lot_id": 89, "lot_name": "SN-RFID-0002", "rfid_tag": "SN-RFID-0002", "qty_reserved": 1.0}
  ]
}
```

---

## 2. Get Transfer Detail

**`GET /api/stock/transfer/<id>`**

```bash
curl -X GET "http://localhost:8069/api/stock/transfer/200" \
  -H "access_token: xK9mT2pL..."
```

---

## 3. Create Internal Transfer

**`POST /api/stock/transfer`**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `warehouse_id` | int | ✅ | Determines internal picking type |
| `location_id` | int | ✅ | Source location ID |
| `location_dest_id` | int | ✅ | Destination location ID |
| `lines` | array | ✅ | Products to move |
| `lines[].product_id` | int | ✅ | Product ID |
| `lines[].qty` | float | ✅ | Quantity |
| `origin` | string | ❌ | Source reference |
| `scheduled_date` | string | ❌ | `YYYY-MM-DD` |
| `note` | string | ❌ | Internal note |

```bash
curl -X POST "http://localhost:8069/api/stock/transfer" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{
    "warehouse_id": 1,
    "location_id": 8,
    "location_dest_id": 11,
    "origin": "REPLENISH-002",
    "lines": [
      {"product_id": 42, "qty": 2},
      {"product_id": 55, "qty": 10}
    ]
  }'
```

### Success Response `201`

```json
{"id": 205, "name": "WH/INT/00005", "state": "assigned"}
```

---

## 4. Validate Transfer

**`POST /api/stock/transfer/<id>/validate`**

| Field | Type | Description |
|-------|------|-------------|
| `lines` | array | Per-line actual quantities and lot/RFID. Omit to auto-fill. |
| `lines[].move_id` | int | **Required** — move ID |
| `lines[].qty_done` | float | **Required** — actual qty moved |
| `lines[].rfid_tag` | string | Unique RFID tag for **1 physical item** — `qty_done` must be `1`. |
| `lines[].lot_name` | string | Batch/lot name — use when moving multiple units under a single lot number |
| `lines[].lot_id` | int | Use an existing lot by ID |
| `backorder` | bool | `true` = create backorder (default). `false` = cancel. |

---

### Example A — No lot/serial tracking (auto-complete)

```bash
curl -X POST "http://localhost:8069/api/stock/transfer/205/validate" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### Example B — Lot-tracked product (multiple units in one batch)

For products tracked by lot number, use `lot_name` with the full batch quantity.  
`rfid_tag` cannot be used here because it always represents exactly **1 physical item**.

```bash
curl -X POST "http://localhost:8069/api/stock/transfer/205/validate" \
  -H "access_token: xK9mT2pL..." \
  -H "Content-Type: application/json" \
  -d '{
    "backorder": false,
    "lines": [
      {"move_id": 301, "qty_done": 10, "lot_name": "BATCH-BB01"}
    ]
  }'
```

```python
validate_payload = {
    "backorder": False,
    "lines": [{"move_id": 301, "qty_done": 10, "lot_name": "BATCH-BB01"}],
}
resp = requests.post(
    f"{BASE_URL}/api/stock/transfer/205/validate",
    headers=HEADERS, data=json.dumps(validate_payload),
)
print(resp.json())
```

---

### Example C — Serial-tracked product (one RFID per unit)

```python
scanned_tags = ["SN-RFID-0001", "SN-RFID-0002", "SN-RFID-0003"]

validate_payload = {
    "backorder": False,
    "lines": [
        {"move_id": 302, "qty_done": 1, "rfid_tag": tag}
        for tag in scanned_tags
    ],
}
resp = requests.post(
    f"{BASE_URL}/api/stock/transfer/206/validate",
    headers=HEADERS, data=json.dumps(validate_payload),
)
print(resp.json())
```

---

### Full End-to-End Flow (Python)

```python
import requests, json

BASE_URL = "http://localhost:8069"
HEADERS  = {"access_token": "xK9mT2pL...", "Content-Type": "application/json"}

# 1. Create transfer
payload = {
    "warehouse_id": 1, "location_id": 8, "location_dest_id": 11,
    "origin": "REPLENISH-RFID",
    "lines": [
        {"product_id": 42, "qty": 2},   # serial-tracked
        {"product_id": 55, "qty": 20},  # lot-tracked
    ],
}
resp = requests.post(f"{BASE_URL}/api/stock/transfer", headers=HEADERS, data=json.dumps(payload))
transfer_id = resp.json()["id"]

# 2. Get move IDs
detail = requests.get(f"{BASE_URL}/api/stock/transfer/{transfer_id}", headers=HEADERS).json()
moves = {m["product_id"]: m["move_id"] for m in detail["move_lines"]}

# 3. Validate with RFID tags
validate_payload = {
    "backorder": False,
    "lines": [
        {"move_id": moves[42], "qty_done": 1, "rfid_tag": "SN-RFID-AA01"},
        {"move_id": moves[42], "qty_done": 1, "rfid_tag": "SN-RFID-AA02"},
        {"move_id": moves[55], "qty_done": 20, "lot_name": "BATCH-CC01"},   # lot: use lot_name for batch qty
    ],
}
result = requests.post(
    f"{BASE_URL}/api/stock/transfer/{transfer_id}/validate",
    headers=HEADERS, data=json.dumps(validate_payload),
).json()
print(result)  # {"id": ..., "name": "WH/INT/...", "state": "done"}
```

### Success Response `200`

```json
{"id": 205, "name": "WH/INT/00005", "state": "done"}
```
