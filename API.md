# API Reference

Base URL (local): http://localhost:8000
Interactive docs: http://localhost:8000/docs (Swagger UI)

---

## Authentication

| Header | Used by | Required |
|---|---|---|
| X-API-Key | Authenticated endpoints | Yes |
| X-Admin-Key | Admin endpoints | Yes (fails closed if unconfigured) |

Public endpoints require no header.

---

## Public Endpoints

### GET /health

Health check, engine status, anchor status.

Response:
{"status": "ok", "swstm_loaded": true, "exact_loaded": true, "anchor_configured": true, "anchor_locked": true}

### POST /signup

Create an API key. Requires RECALLSPECTION_SIGNUP_SECRET if configured.

Request:
{"signup_secret": "your-signup-secret", "label": "my-agent"}

Response:
{"api_key": "rsp_xxxxxxxxxxxxxxxx", "label": "my-agent", "quota": 100000}

### GET /verify?root=0x...

Verify a Merkle root against local chain and S3 Object Lock retention. Third-party verifiable.

Response:
{"local_valid": true, "s3_locked": true, "compliance": "COMPLIANCE", "retain_until": "2027-01-28T00:00:00Z"}

---

## Authenticated Endpoints

All require X-API-Key header.

### POST /add

Request: {"key": "agent:mission", "value": "Secure memory for AI agents", "backend": "exact"}
Response: {"status": "ok", "key": "agent:mission", "backend": "exact"}

### GET /get?key=...

Response: {"status": "ok", "key": "agent:mission", "value": "Secure memory for AI agents", "source": "exact"}
Status values: ok, missing, tampered.

### POST /exact/add

Request: {"key": "user:color", "value": "blue"}
Response: {"status": "ok", "key": "user:color"}

### GET /exact/get?key=...

Response: {"status": "ok", "key": "user:color", "value": "blue"}

### GET /usage

Response: {"key": "rsp_xxx", "label": "my-agent", "calls_used": 1234, "quota": 100000, "anchors_created": 12}

### POST /anchor

Response: {"root": "0x4a2f...1291", "anchored_at": "2026-10-02T12:34:56Z", "retain_until": "2027-01-28T00:00:00Z", "s3_key": "anchors/0x4a2f...1291.json"}

### GET /audit/export

Returns application/zip binary stream.

---

## Admin Endpoints

All require X-Admin-Key header. Fails closed if unset.

### GET /admin/keys
Response: {"keys": [{"key_id": "abc123", "label": "my-agent", "calls_used": 1234, "active": true}]}

### POST /admin/revoke/{key_id}
Response: {"status": "revoked", "key_id": "abc123"}

### POST /admin/save
Response: {"status": "saved", "files": ["memory.db", "transparency.log", "swstm.pt", "keys.db"]}

### POST /admin/consolidate
Response: {"status": "consolidated", "slots_before": 2000, "slots_after": 2000, "evictions": 0}

---

## Error Responses

{"detail": "human-readable message", "status": 400}

| Status | Meaning |
|---|---|
| 400 | Malformed request |
| 401 | Missing or invalid API key |
| 403 | Admin route without valid key |
| 404 | Key not found |
| 409 | Tampered record detected |
| 413 | Payload too large |
| 429 | Quota exceeded |
| 500 | Internal error (masked) |

---

## Rate Limits

Default quota: 100,000 calls per API key.

## Payload Limits

| Field | Max size |
|---|---|
| key | 512 bytes |
| value | 64 KB |
| Request body | 128 KB |