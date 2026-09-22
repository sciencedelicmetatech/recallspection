"""
Recallspection v3.2.0 Production API
- Dual-engine: ExactMemory + SWSTM Legendary
- SQLite key management + usage quotas
- Stripe billing (checkout, portal, webhook) -> pays Sciencedelic Metatech
- One-click deploy ready (Render/Railway/Fly)
- Fail-closed admin, constant-time compare, payload limits, atomic saves

v3.2.0 changes:
- Fail-loud on store load: FormatVersionError / TamperError / RollbackError /
  LogCompromisedError cause SystemExit. No silent empty-store fallback.

Env:
  RECALLSPECTION_EXACT_SECRET - master secret for ExactMemory keys (required prod)
  RECALLSPECTION_ADMIN_KEY - admin key (required prod, fail closed)
  RECALLSPECTION_SIGNUP_SECRET - optional signup gate
  RECALLSPECTION_MEMORY_FILE - /data/memory.db
  RECALLSPECTION_SWSTM_FILE - /data/swstm.pt
  RECALLSPECTION_DB_FILE - /data/keys.db
  RECALLSPECTION_EXACT_LOG - /data/transparency.log
  STRIPE_SECRET_KEY - sk_live_... (for billing)
  STRIPE_WEBHOOK_SECRET - whsec_...
  STRIPE_PRICE_PRO - price_... ($20/mo)
  STRIPE_PRICE_TEAM - price_... ($99/mo)
  FRONTEND_URL - https://your-dashboard.com for redirect after checkout
"""
import os
import hmac
import hashlib
import sqlite3
import time
import json
import threading
from pathlib import Path
from typing import Optional, Literal, Dict, Any
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# --- Optional Stripe ---
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

# --- Config ---
EXACT_SECRET = os.getenv("RECALLSPECTION_EXACT_SECRET", "dev-secret-change-me")
ADMIN_KEY = os.getenv("RECALLSPECTION_ADMIN_KEY", "")
SIGNUP_SECRET = os.getenv("RECALLSPECTION_SIGNUP_SECRET", "")
MEMORY_FILE = os.getenv("RECALLSPECTION_MEMORY_FILE", "./memory.db")
SWSTM_FILE = os.getenv("RECALLSPECTION_SWSTM_FILE", "./swstm.pt")
DB_FILE = os.getenv("RECALLSPECTION_DB_FILE", "./keys.db")
EXACT_LOG = os.getenv("RECALLSPECTION_EXACT_LOG", "./transparency.log")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "price_pro_20")
STRIPE_PRICE_TEAM = os.getenv("STRIPE_PRICE_TEAM", "price_team_99")
STRIPE_PRICE_ENTERPRISE = os.getenv("STRIPE_PRICE_ENTERPRISE", "price_ent_249")

if STRIPE_AVAILABLE and STRIPE_SECRET:
    stripe.api_key = STRIPE_SECRET

app = FastAPI(
    title="Recallspection API v3.2.0",
    description="Tamper-evident exact memory + collision-resistant SWSTM. TL;DR get(k)=v_set ∨ Err(Tamper)",
    version="3.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Payload size guard ---
MAX_PAYLOAD = 1024 * 1024  # 1MB
@app.middleware("http")
async def check_payload_size(request: Request, call_next):
    if request.headers.get("content-length"):
        if int(request.headers["content-length"]) > MAX_PAYLOAD:
            return JSONResponse(status_code=413, content={"detail": "Payload too large"})
    return await call_next(request)

# --- SQLite keys.db ---
def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    Path(DB_FILE).parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS api_keys (
        key_id TEXT PRIMARY KEY,
        api_key_hash TEXT NOT NULL,
        api_key_prefix TEXT,
        created_at REAL,
        quota_limit INTEGER DEFAULT 1000,
        quota_used INTEGER DEFAULT 0,
        tier TEXT DEFAULT 'free',
        stripe_customer_id TEXT,
        stripe_subscription_id TEXT,
        status TEXT DEFAULT 'active'
    );
    """)
    conn.commit()
    conn.close()

init_db()

def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def const_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)

# --- ExactMemory ---
exact_memory = None
exact_keys = None
try:
    from exactmemory import (
        ExactMemory,
        FormatVersionError,
        TamperError,
        RollbackError,
        LogCompromisedError,
    )

    master = EXACT_SECRET.encode()
    exact_keys = {
        "agent_key": hashlib.sha256(master).digest(),
        "container": hashlib.sha256(b"container-salt-" + hashlib.sha256(master).digest()).digest(),
    }
    exact_memory = ExactMemory(keys=exact_keys, container_key_id="container", require_log=True)
    # Load if exists
    if Path(MEMORY_FILE).exists():
        try:
            exact_memory.load(MEMORY_FILE)
        except FormatVersionError as e:
            print(f"[FATAL] Format version mismatch: {e}")
            print("[FATAL] Refusing to start with incompatible store. Re-ingest data or downgrade.")
            raise SystemExit(2)
        except (TamperError, RollbackError, LogCompromisedError) as e:
            print(f"[FATAL] Integrity failure on load: {e}")
            print("[FATAL] Refusing to serve from a compromised or rolled-back store.")
            raise SystemExit(3)
        except Exception as e:
            print(f"[FATAL] Unexpected load failure: {e}")
            raise SystemExit(4)
    print("[ExactMemory] initialized")
except SystemExit:
    raise
except Exception as e:
    print(f"[ExactMemory] init failed: {e} - running in mock mode")
    exact_memory = None

# --- SWSTM Hybrid ---
hybrid = None
try:
    from recallspection.swstm import HybridEngine
    hybrid = HybridEngine(num_slots=2000, mode="flat", device="cpu")
    if Path(SWSTM_FILE).exists():
        try:
            hybrid.load(SWSTM_FILE)
        except Exception as e:
            print(f"[SWSTM] load failed: {e}")
    print("[SWSTM] initialized")
except Exception as e:
    print(f"[SWSTM] init failed: {e}")

# --- Auto-save ---
def autosave_loop():
    while True:
        time.sleep(60)
        try:
            if exact_memory:
                exact_memory.save(MEMORY_FILE)
            if hybrid:
                hybrid.save(SWSTM_FILE)
        except Exception as e:
            print(f"[autosave] {e}")

threading.Thread(target=autosave_loop, daemon=True).start()

# --- Models ---
class AddRequest(BaseModel):
    key: str = Field(..., max_length=256)
    value: str = Field(..., max_length=10000)
    backend: Literal["exact", "swstm", "hybrid"] = "hybrid"

class GetRequest(BaseModel):
    key: str

class SignupRequest(BaseModel):
    signup_secret: Optional[str] = None
    email: Optional[str] = None
    tier: Literal["free", "pro", "team", "enterprise"] = "free"

class CheckoutRequest(BaseModel):
    tier: Literal["pro", "team", "enterprise"]
    email: str

# --- Auth helpers ---
def verify_api_key(x_api_key: str = Header(None)) -> Dict[str, Any]:
    if not x_api_key:
        raise HTTPException(401, "Missing X-API-Key")
    conn = get_conn()
    h = hash_key(x_api_key)
    row = conn.execute("SELECT * FROM api_keys WHERE api_key_hash=? AND status='active'", (h,)).fetchone()
    conn.close()
    if not row:
        const_eq(h, "0"*64)
        raise HTTPException(401, "Invalid API key")
    return dict(row)

def verify_admin(x_admin_key: str = Header(None)):
    if not ADMIN_KEY:
        raise HTTPException(403, "Admin disabled - set RECALLSPECTION_ADMIN_KEY (fail closed)")
    if not x_admin_key or not const_eq(x_admin_key, ADMIN_KEY):
        raise HTTPException(403, "Invalid admin key")
    return True

# --- Endpoints ---
@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "3.2.0",
        "exact_loaded": exact_memory is not None,
        "swstm_loaded": hybrid is not None,
        "store_format": exact_memory.VERSION if exact_memory else None,
        "memory_file": MEMORY_FILE,
        "swstm_file": SWSTM_FILE,
        "db_file": DB_FILE,
        "exact_log": EXACT_LOG,
        "stripe_enabled": STRIPE_AVAILABLE and bool(STRIPE_SECRET),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/signup")
def signup(req: SignupRequest):
    if SIGNUP_SECRET:
        if not req.signup_secret or not const_eq(req.signup_secret, SIGNUP_SECRET):
            raise HTTPException(403, "Invalid signup secret")
    import secrets
    raw_key = f"rsc_{secrets.token_urlsafe(32)}"
    key_hash = hash_key(raw_key)
    prefix = raw_key[:12]
    quota = {"free": 1000, "pro": 50000, "team": 500000, "enterprise": 10_000_000}[req.tier]

    conn = get_conn()
    conn.execute(
        "INSERT INTO api_keys (key_id, api_key_hash, api_key_prefix, created_at, quota_limit, quota_used, tier) VALUES (?,?,?,?,?,?,?)",
        (prefix, key_hash, prefix, time.time(), quota, 0, req.tier)
    )
    conn.commit()
    conn.close()

    stripe_customer = None
    if STRIPE_AVAILABLE and STRIPE_SECRET and req.email and req.tier != "free":
        try:
            cust = stripe.Customer.create(email=req.email, metadata={"key_prefix": prefix})
            stripe_customer = cust.id
            conn = get_conn()
            conn.execute("UPDATE api_keys SET stripe_customer_id=? WHERE key_id=?", (stripe_customer, prefix))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[stripe] customer create failed: {e}")

    return {
        "api_key": raw_key,
        "key_id": prefix,
        "tier": req.tier,
        "quota_limit": quota,
        "message": "Save this key - it will not be shown again. Use X-API-Key header.",
        "stripe_customer_id": stripe_customer
    }

@app.get("/usage")
def usage(auth=Depends(verify_api_key)):
    return {
        "key_id": auth["key_id"],
        "tier": auth["tier"],
        "quota_limit": auth["quota_limit"],
        "quota_used": auth["quota_used"],
        "remaining": auth["quota_limit"] - auth["quota_used"],
        "status": auth["status"]
    }

def check_quota(auth):
    if auth["quota_used"] >= auth["quota_limit"]:
        raise HTTPException(429, f"Quota exceeded {auth['quota_used']}/{auth['quota_limit']} - upgrade at /billing/checkout")
    conn = get_conn()
    conn.execute("UPDATE api_keys SET quota_used=quota_used+1 WHERE key_id=?", (auth["key_id"],))
    conn.commit()
    conn.close()

@app.post("/add")
def add_fact(req: AddRequest, auth=Depends(verify_api_key)):
    check_quota(auth)
    backend = req.backend
    result = {}
    try:
        if backend in ("exact", "hybrid"):
            if not exact_memory:
                raise HTTPException(500, "ExactMemory not loaded")
            exact_memory.put(req.key, req.value, key_id="agent_key")
            result["exact"] = "ok"
        if backend in ("swstm", "hybrid"):
            if hybrid:
                hybrid.add(req.key, req.value)
                result["swstm"] = "ok"
        if exact_memory:
            exact_memory.save(MEMORY_FILE)
        if hybrid:
            hybrid.save(SWSTM_FILE)
        return {"key": req.key, "backend": backend, "result": result, "status": "stored"}
    except Exception as e:
        raise HTTPException(500, f"Add failed: {str(e)[:500]}")

@app.get("/get")
def get_fact(key: str, top_k: int = 1, auth=Depends(verify_api_key)):
    check_quota(auth)
    try:
        if exact_memory:
            val, status = exact_memory.get_with_status(key) if hasattr(exact_memory, "get_with_status") else (exact_memory.get(key), "ok")
            if status == "ok" and val is not None:
                return {"key": key, "value": val, "source": "exact", "status": status, "tamper": False}
            if status == "tampered":
                return {"key": key, "value": None, "source": "exact", "status": "tampered", "tamper": True, "detail": "Previously known key missing or HMAC mismatch - deletion/corruption attack detected"}

        if hybrid:
            res = hybrid.get(key, top_k=top_k)
            if res:
                return {"key": key, "value": res, "source": "swstm", "status": "ok", "tamper": False}

        return {"key": key, "value": None, "source": "none", "status": "missing"}
    except Exception as e:
        print(f"[get] error {e}")
        raise HTTPException(500, "Internal retrieval error")

@app.post("/exact/add")
def exact_add(req: AddRequest, auth=Depends(verify_api_key)):
    req.backend = "exact"
    return add_fact(req, auth)

@app.get("/exact/get")
def exact_get(key: str, auth=Depends(verify_api_key)):
    check_quota(auth)
    if not exact_memory:
        raise HTTPException(500, "ExactMemory not loaded")
    try:
        val, status = exact_memory.get_with_status(key) if hasattr(exact_memory, "get_with_status") else (exact_memory.get(key), "ok")
        return {"key": key, "value": val, "status": status, "tamper": status == "tampered"}
    except Exception as e:
        raise HTTPException(500, str(e)[:500])

# --- Billing: pays Sciencedelic Metatech ---
@app.post("/billing/checkout")
def billing_checkout(req: CheckoutRequest):
    if not (STRIPE_AVAILABLE and STRIPE_SECRET):
        raise HTTPException(500, "Stripe not configured - set STRIPE_SECRET_KEY")
    price_map = {
        "pro": STRIPE_PRICE_PRO,
        "team": STRIPE_PRICE_TEAM,
        "enterprise": STRIPE_PRICE_ENTERPRISE
    }
    price_id = price_map.get(req.tier)
    if not price_id or price_id.startswith("price_") == False:
        price_id = None

    try:
        session = stripe.checkout.Session.create(
            customer_email=req.email,
            line_items=[{"price": price_id, "quantity": 1}] if price_id else [{"price_data": {"currency": "usd", "product_data": {"name": f"Recallspection {req.tier.title()}"}, "unit_amount": {"pro":2000,"team":9900,"enterprise":24900}[req.tier]}, "quantity": 1}],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/billing/cancel",
            metadata={"tier": req.tier, "email": req.email}
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        raise HTTPException(500, f"Stripe checkout failed: {e}")

@app.get("/billing/portal")
def billing_portal(customer_id: str = None, auth=Depends(verify_api_key)):
    if not (STRIPE_AVAILABLE and STRIPE_SECRET):
        raise HTTPException(500, "Stripe not configured")
    cid = customer_id or auth.get("stripe_customer_id")
    if not cid:
        raise HTTPException(400, "No stripe_customer_id found - signup with email first")
    try:
        portal = stripe.billing_portal.Session.create(customer=cid, return_url=f"{FRONTEND_URL}/usage")
        return {"portal_url": portal.url}
    except Exception as e:
        raise HTTPException(500, f"Portal failed: {e}")

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    if not (STRIPE_AVAILABLE and STRIPE_SECRET and STRIPE_WEBHOOK_SECRET):
        raise HTTPException(500, "Stripe webhook not configured")
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(400, f"Webhook error: {e}")

    if event["type"] in ("checkout.session.completed", "customer.subscription.created", "customer.subscription.updated"):
        obj = event["data"]["object"]
        email = obj.get("customer_email") or obj.get("customer_details", {}).get("email")
        customer_id = obj.get("customer") or obj.get("customer_id")
        tier = obj.get("metadata", {}).get("tier", "pro")
        try:
            conn = get_conn()
            if customer_id:
                conn.execute("UPDATE api_keys SET tier=?, status='active', quota_limit=? WHERE stripe_customer_id=?",
                             (tier, {"pro":50000,"team":500000,"enterprise":10000000}[tier], customer_id))
            conn.commit()
            conn.close()
            print(f"[stripe] upgraded {customer_id} to {tier}")
        except Exception as e:
            print(f"[stripe] DB update failed {e}")

    return {"status": "ok"}

# --- Admin ---
@app.get("/admin/keys")
def admin_list_keys(_=Depends(verify_admin)):
    conn = get_conn()
    rows = conn.execute("SELECT key_id, api_key_prefix, created_at, quota_limit, quota_used, tier, status, stripe_customer_id FROM api_keys ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()
    return {"keys": [dict(r) for r in rows]}

@app.post("/admin/revoke/{key_id}")
def admin_revoke(key_id: str, _=Depends(verify_admin)):
    conn = get_conn()
    conn.execute("UPDATE api_keys SET status='revoked' WHERE key_id=?", (key_id,))
    conn.commit()
    conn.close()
    return {"key_id": key_id, "status": "revoked"}

@app.post("/admin/save")
def admin_save(_=Depends(verify_admin)):
    try:
        if exact_memory:
            exact_memory.save(MEMORY_FILE)
        if hybrid:
            hybrid.save(SWSTM_FILE)
        return {"status": "saved", "memory": MEMORY_FILE, "swstm": SWSTM_FILE}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/admin/consolidate")
def admin_consolidate(_=Depends(verify_admin)):
    try:
        if hybrid and hasattr(hybrid, "consolidate"):
            hybrid.consolidate()
            hybrid.save(SWSTM_FILE)
        return {"status": "consolidated"}
    except Exception as e:
        raise HTTPException(500, str(e))

# --- Root ---
@app.get("/")
def root():
    return {
        "name": "Recallspection API v3.2.0",
        "docs": "/docs",
        "health": "/health",
        "dashboard": FRONTEND_URL,
        "message": "Tamper-evident exact memory + collision-resistant SWSTM. get(k)=v_set ∨ Err(Tamper)"
    }