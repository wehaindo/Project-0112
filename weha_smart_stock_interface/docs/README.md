# WEHA Smart Stock Interface — API Documentation

Welcome to the **WEHA Smart Stock Interface** REST API docs.

## Table of Contents

1. [Authentication](./01_authentication.md)
2. [Master Data — Products, Warehouses & Locations](./02_master_data.md)
3. [Receiving (Incoming Shipments)](./03_receiving.md)
4. [Internal Transfer](./04_transfer.md)
5. [Delivery Orders](./05_delivery.md)
6. [RFID & Lot/Serial Numbers](./06_rfid.md)

---

## Base URL

```
http://<your-odoo-host>:<port>
```

## Common Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Content-Type` | For POST | `application/json` |
| `access_token` | All protected endpoints | Bearer token obtained from `/api/auth/token` |

## Lot / Serial & RFID

`rfid_tag` is treated as the **lot or serial number** directly — no separate field.
Whenever a validate or create payload accepts `rfid_tag`, `lot_name`, or `lot_id`, all three resolve the same way:

| Field | Meaning |
|-------|---------|
| `rfid_tag` | RFID tag value — used directly as the lot/serial name |
| `lot_name` | Alias — identical behaviour to `rfid_tag` |
| `lot_id` | Use an existing lot by its Odoo database ID |

The server **auto-creates** the lot record when `rfid_tag` or `lot_name` is given and the lot does not yet exist.

## Response Format

All endpoints return JSON. Successful list responses follow:

```json
{
  "total": 100,
  "limit": 50,
  "offset": 0,
  "data": [ ... ]
}
```

Successful single-record responses return the object directly.

Error responses:

```json
{
  "type": "error_code",
  "message": "Human readable description"
}
```

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | OK |
| `201` | Created |
| `400` | Bad Request (missing/invalid fields) |
| `401` | Unauthorized (missing or expired token) |
| `403` | Forbidden |
| `404` | Not Found |
| `500` | Internal Server Error |
