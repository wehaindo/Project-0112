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

Pass the token in all subsequent requests via the `access_token` header:

```bash
curl -X GET "http://localhost:8069/api/stock/product" \
  -H "access_token: xK9mT2pL..."
```

```python
headers = {
    "access_token": access_token
}
response = requests.get("http://localhost:8069/api/stock/product", headers=headers)
```

---

## 3. Revoke / Logout

**`DELETE /api/auth/token`**

Revoke the current token (logout).

```bash
curl -X DELETE "http://localhost:8069/api/auth/token" \
  -H "access_token: xK9mT2pL..."
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
