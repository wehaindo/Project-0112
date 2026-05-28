# Authentication

All API endpoints (except `/api/auth/token`) require a valid `access_token` in the request header.

---

## 1. Obtain Access Token

**`GET /api/auth/token`**

Authenticate with Odoo credentials to receive an access token.

### Request — via Query Params or Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `db` | string | ✅ | Odoo database name |
| `login` | string | ✅ | Odoo username |
| `password` | string | ✅ | Odoo password |

Credentials can be passed as **form body** or **request headers**.

### Example — cURL (form body)

```bash
curl -X GET "http://localhost:8069/api/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "db=mydb&login=admin&password=admin"
```

### Example — Python (requests)

```python
import requests

url = "http://localhost:8069/api/auth/token"
data = {
    "db": "mydb",
    "login": "admin",
    "password": "admin"
}

response = requests.get(url, data=data)
result = response.json()

access_token = result["access_token"]
print("Token:", access_token)
```

### Success Response `200`

```json
{
  "uid": 2,
  "company_id": 1,
  "company_ids": [1],
  "partner_id": 3,
  "access_token": "xK9mT2pL...",
  "expires_in": 3600
}
```

### Error Response `403`

```json
{
  "type": "missing error",
  "message": "either of the following are missing [db, username,password]"
}
```

---

## 2. Use the Token

Pass the token in any of the following ways — all are accepted:

```bash
# Option 1 — access_token header (recommended)
curl -X GET "http://localhost:8069/api/stock/product" \
  -H "access_token: xK9mT2pL..."

# Option 2 — access-token header (hyphen, proxy-safe)
curl -X GET "http://localhost:8069/api/stock/product" \
  -H "access-token: xK9mT2pL..."

# Option 3 — Authorization: Bearer
curl -X GET "http://localhost:8069/api/stock/product" \
  -H "Authorization: Bearer xK9mT2pL..."

# Option 4 — query parameter fallback
curl -X GET "http://localhost:8069/api/stock/product?access_token=xK9mT2pL..."
```

```python
token = "xK9mT2pL..."

# Option 1 — access_token header
headers = {"access_token": token}

# Option 2 — access-token header (use this if behind nginx/proxy)
headers = {"access-token": token}

# Option 3 — Authorization Bearer
headers = {"Authorization": f"Bearer {token}"}

response = requests.get("http://localhost:8069/api/stock/product", headers=headers)
```

> **Nginx / proxy users:** If you are behind nginx with default settings, headers containing underscores are silently dropped (`underscores_in_headers off` is nginx's default). Use the **`access-token`** (hyphen) header or **`Authorization: Bearer`** instead, or add `underscores_in_headers on;` to your nginx config.

---

## 3. Revoke / Logout

**`DELETE /api/auth/token`**

Revoke the current token (logout).

```bash
curl -X DELETE "http://localhost:8069/api/auth/token" \
  -H "access_token: xK9mT2pL..."
```

---

## 4. Troubleshooting

### `access_token_not_found` — missing access token in request header

```json
{"type": "access_token_not_found", "message": "missing access token in request header"}
```

**Cause:** The `access_token` header was not included in the request.

**Fix:** Every request (except `GET /api/auth/token`) must include the header:

```bash
# ✅ Correct
curl -X GET "http://localhost:8069/api/stock/product" \
  -H "access_token: xK9mT2pL..."

# ❌ Wrong — header name typo or missing entirely
curl -X GET "http://localhost:8069/api/stock/product" \
  -H "Authorization: Bearer xK9mT2pL..."
```

```python
# ✅ Correct
headers = {"access_token": access_token}          # key must be exactly 'access_token'
requests.get(url, headers=headers)

# ❌ Wrong — common mistakes
headers = {"Authorization": f"Bearer {access_token}"}  # wrong header name
headers = {"Access-Token": access_token}               # wrong capitalisation
```

### `access_token` — token seems to have expired or invalid

```json
{"type": "access_token", "message": "token seems to have expired or invalid"}
```

**Cause:** Token has expired (default TTL = 1 hour) or was revoked.

**Fix:** Re-authenticate to get a fresh token:

```python
resp = requests.get(
    "http://localhost:8069/api/auth/token",
    data={"db": "mydb", "login": "admin", "password": "admin"},
)
access_token = resp.json()["access_token"]
```

### Success Response `200`

```json
[{"desc": "access token successfully deleted", "delete": true}]
```

---

## 4. Token Expiry

Tokens expire after **3600 seconds (1 hour)** by default.  
The expiry can be changed in Odoo → Settings → Technical → System Parameters → `weha_base_api.access_token_expires_in`.

When a token expires, all protected endpoints return:

```json
{
  "type": "access_token",
  "message": "token seems to have expired or invalid"
}
```
Simply re-authenticate to get a new token.
