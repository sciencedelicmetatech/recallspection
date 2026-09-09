import os
import json
import logging
import sqlite3
import secrets
import hashlib
import time
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# -----------------------------------------------------------------------------
# 1. Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recallspection-api")

# -----------------------------------------------------------------------------
# 2. Environment variables
# -----------------------------------------------------------------------------
MEMORY_FILE = os.getenv("RECALLSPECTION_MEMORY_FILE", "memory.json")
DB_FILE = os.getenv("RECALLSPECTION_DB_FILE", "keys.db")
SWSTM_MODE = os.getenv("SWSTM_MODE", "flat")
# AUDIT FIX: no default -- admin endpoints refuse to serve if this is unset,
# instead of comparing against an empty string (which could be satisfied by
# an empty/missing header, i.e. fail-open).
ADMIN_KEY = os.getenv("RECALLSPECTION_ADMIN_KEY")

# -----------------------------------------------------------------------------
# 3. Database: multiple API keys with usage tracking
# -----------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    # AUDIT FIX: renamed `limit` -> `quota_limit`. LIMIT is meaningful in
    # SQLite's SELECT ... LIMIT clause; using it as a bare column name is a
    # foot-gun even where it happens to parse.
    conn.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            plan TEXT NOT NULL,
            usage INTEGER DEFAULT 0,
            quota_limit INTEGER DEFAULT 1000,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_used TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_key_id ON api_keys(key_id)')
    # AUDIT ADD: minimal signup throttling table (fixes unlimited free-key minting).
    conn.execute('''
        CREATE TABLE IF NOT EXISTS signup_log (
            ip TEXT NOT NULL,
            day TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (ip, day)
        )
    ''')
    conn.commit()
    conn.close()


LIMIT_MAP = {
    "free": 1000, "pro": 100000, "enterprise": 1000000,
    "agent_free": 5000, "agent_pro": 500000, "agent_enterprise": 5000000,
}

# AUDIT FIX (severe, plaintext key storage): API keys are now stored and
# looked up by SHA-256 hash, never as plaintext. The plaintext key is
# returned to the caller exactly once, at creation time, and never stored.
def _hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def create_api_key(owner: str, plan: str = "free") -> str:
    key = f"rk_{secrets.token_urlsafe(24)}"
    key_hash = _hash_api_key(key)
    limit = LIMIT_MAP.get(plan, 1000)
    conn = get_db()
    conn.execute(
        "INSERT INTO api_keys (key_id, owner, plan, quota_limit) VALUES (?, ?, ?, ?)",
        (key_hash, owner, plan, limit)
    )
    conn.commit()
    conn.close()
    return key  # plaintext returned ONCE to the caller only


def get_key_info(key: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM api_keys WHERE key_id = ? AND is_active = 1",
        (_hash_api_key(key),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def increment_usage(key: str) -> int:
    key_hash = _hash_api_key(key)
    conn = get_db()
    conn.execute(
        "UPDATE api_keys SET usage = usage + 1, last_used = CURRENT_TIMESTAMP WHERE key_id = ?",
        (key_hash,)
    )
    conn.commit()
    row = conn.execute("SELECT usage, quota_limit FROM api_keys WHERE key_id = ?", (key_hash,)).fetchone()
    conn.close()
    return row[0] if row else 0


def get_remaining_usage(key: str) -> int:
    conn = get_db()
    row = conn.execute(
        "SELECT quota_limit, usage FROM api_keys WHERE key_id = ?", (_hash_api_key(key),)
    ).fetchone()
    conn.close()
    if row:
        return row[0] - row[1]
    return 0


def check_and_log_signup(ip: str, max_per_day: int = 3) -> bool:
    """AUDIT ADD: basic per-IP signup rate limit. Returns True if allowed."""
    day = time.strftime("%Y-%m-%d")
    conn = get_db()
    row = conn.execute("SELECT count FROM signup_log WHERE ip = ? AND day = ?", (ip, day)).fetchone()
    if row and row[0] >= max_per_day:
        conn.close()
        return False
    if row:
        conn.execute("UPDATE signup_log SET count = count + 1 WHERE ip = ? AND day = ?", (ip, day))
    else:
        conn.execute("INSERT INTO signup_log (ip, day, count) VALUES (?, ?, 1)", (ip, day))
    conn.commit()
    conn.close()
    return True


# -----------------------------------------------------------------------------
# 4. Lazy imports (SWSTM/ExactMemory)
#    AUDIT FIX: renamed the ExactMemory helper away from `get_exact` -- a
#    route handler further down in this file was ALSO named `get_exact`,
#    which silently shadowed this function at module load time and caused
#    every call site (this helper, /add, /get, load_memory) to instead call
#    the async route handler with zero arguments, raising TypeError on every
#    request. Confirmed with a minimal repro before this fix was written.
# -----------------------------------------------------------------------------
swstm = None
exact = None


def get_exact_memory():
    global exact
    if exact is None:
        from recallspection.exact import ExactMemory
        exact = ExactMemory()
        logger.info("ExactMemory initialized")
    return exact


def get_swstm():
    global swstm
    if swstm is None:
        from recallspection.swstm import SWSTMEngine
        # AUDIT FIX: this call now matches SWSTMEngine's real constructor
        # (mode=/flat_num_slots= are accepted; previously they were not,
        # guaranteeing a TypeError the first time this ran).
        # AUDIT FIX: use_direct_mapping explicitly set to False -- the
        # library's prior default (True) silently bypasses the neural model
        # for exact-key queries and its own docstring said this "masks
        # neural performance." Flip to True only if you understand that
        # any resulting accuracy number does not reflect neural retrieval.
        swstm = SWSTMEngine(mode=SWSTM_MODE, flat_num_slots=200, use_direct_mapping=False)
        logger.info(f"SWSTMEngine initialized (mode={SWSTM_MODE}, use_direct_mapping=False)")
    return swstm


# -----------------------------------------------------------------------------
# 5. Persistent storage (load/save memory to JSON)
#    NOTE (unresolved, flagged not fixed): this is a single dump on clean
#    shutdown, not durable/incremental persistence. An OOM kill or forced
#    redeploy on a PaaS loses everything written since the last clean
#    shutdown. This directly conflicts with "audit trail / compliance"
#    positioning -- fixing it properly means incremental writes (e.g. an
#    append-only log or real DB), which is a bigger change than this patch
#    covers. Do not claim compliance-grade durability until this is fixed.
# -----------------------------------------------------------------------------
def save_memory():
    data = {}
    try:
        if exact is not None:
            # AUDIT FIX: use the public export_state() API instead of
            # reaching into exact._storage directly -- decouples api.py
            # from ExactMemory's internal representation.
            data['exact'] = exact.export_state()
        if swstm is not None:
            data['swstm_key_to_value'] = swstm.key_to_value
            data['swstm_entity_of'] = swstm._entity_of
            data['swstm_timestamp_of'] = swstm._timestamp_of
        with open(MEMORY_FILE, 'w') as f:
            json.dump(data, f)
        logger.info(f"Memory saved to {MEMORY_FILE}")
    except Exception as e:
        logger.error(f"Failed to save memory: {e}")


def load_memory():
    global exact, swstm
    if not os.path.exists(MEMORY_FILE):
        logger.info("No existing memory file, starting fresh.")
        return
    try:
        with open(MEMORY_FILE, 'r') as f:
            data = json.load(f)

        if 'exact' in data:
            exact = get_exact_memory()
            exact.load_state(data['exact'])
            logger.info(f"Loaded ExactMemory with {len(exact)} facts.")

        if 'swstm_key_to_value' in data:
            swstm = get_swstm()
            swstm.key_to_value = data['swstm_key_to_value']
            swstm._entity_of = data.get('swstm_entity_of', {})
            swstm._timestamp_of = data.get('swstm_timestamp_of', {})
            logger.info(f"Loaded SWSTM with {swstm.fact_count} facts.")
    except Exception as e:
        logger.error(f"Failed to load memory: {e}")


# -----------------------------------------------------------------------------
# 6. FastAPI app with lifespan and static file mount
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_memory()
    logger.info("Recallspection API started")
    yield
    save_memory()
    logger.info("Recallspection API shutting down")


app = FastAPI(
    title="Recallspection API",
    description="Dual-core exact memory with API keys, usage tracking, and agent detection",
    version="18.0.1",
    lifespan=lifespan,
)

# AUDIT FIX (severe): the entire working directory was previously mounted
# at "/" as static files, meaning keys.db and memory.json (containing every
# API key and every stored fact) were directly downloadable by anyone over
# HTTP. Now only a dedicated ./static/ directory -- containing solely
# public assets like banner.svg -- is exposed. Put ONLY files meant to be
# public into ./static/.
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static", html=False), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        with open("index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return {"error": "index.html not found"}


# -----------------------------------------------------------------------------
# 7. API Key security with agent detection
# -----------------------------------------------------------------------------
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def is_agent_request(request: Request) -> bool:
    user_agent = request.headers.get("user-agent", "").lower()
    agent_patterns = [
        "python", "curl", "wget", "requests", "langchain", "llamaindex",
        "openai", "anthropic", "cohere", "mistral", "transformers",
        "pytorch", "tensorflow", "jupyter", "colab", "bot", "spider"
    ]
    for pattern in agent_patterns:
        if pattern in user_agent:
            return True
    referer = request.headers.get("referer", "").lower()
    if "colab" in referer or "notebook" in referer:
        return True
    return False
    # NOTE (flagged, not fixed): trivially spoofable via User-Agent header.
    # Fine as a marketing nudge (see /agent-info); do not use for anything
    # that gates pricing or access decisions.


async def validate_api_key(request: Request, api_key: str = Depends(api_key_header)):
    if api_key is None:
        raise HTTPException(status_code=401, detail="Missing API Key. Please provide X-API-Key header.")
    key_info = get_key_info(api_key)
    if key_info is None:
        raise HTTPException(status_code=403, detail="Invalid API Key or key deactivated.")
    remaining = get_remaining_usage(api_key)
    if remaining <= 0:
        raise HTTPException(
            status_code=402,
            detail=f"Usage limit exceeded. Plan: {key_info['plan']}, Used: {key_info['usage']}, "
                   f"Limit: {key_info['quota_limit']}. Please upgrade."
        )
    increment_usage(api_key)
    request.state.key_info = key_info
    request.state.is_agent = is_agent_request(request)
    return key_info


# -----------------------------------------------------------------------------
# 8. Pydantic models
# -----------------------------------------------------------------------------
class AddRequest(BaseModel):
    key: str
    value: str
    entity_id: Optional[str] = None   # AUDIT ADD: supports recency versioning


class AddResponse(BaseModel):
    status: str
    message: str
    backend: str = "swstm"
    remaining: int


class GetResponse(BaseModel):
    answers: List[str]
    backend: str = "swstm"
    remaining: int
    message: Optional[str] = None


class KeyResponse(BaseModel):
    api_key: str
    owner: str
    plan: str
    limit: int
    remaining: int


class UsageResponse(BaseModel):
    owner: str
    plan: str
    used: int
    limit: int
    remaining: int


# -----------------------------------------------------------------------------
# 9. Public endpoints (no auth required)
# -----------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "backend": "SWSTM v7.0 + ExactMemory",
        "swstm_loaded": swstm is not None,
        "exact_loaded": exact is not None,
        "facts_swstm": swstm.fact_count if swstm else 0,
        "facts_exact": len(exact) if exact else 0,
        "db_connected": os.path.exists(DB_FILE),
    }


@app.post("/signup")
async def signup(request: Request, owner: str, plan: str = "free"):
    valid_plans = list(LIMIT_MAP.keys())
    if plan not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Choose from: {valid_plans}")

    # AUDIT ADD: throttle unauthenticated key creation (previously
    # unlimited -- a script could mint unbounded free-tier keys).
    client_ip = request.client.host if request.client else "unknown"
    if not check_and_log_signup(client_ip):
        raise HTTPException(status_code=429, detail="Too many signups from this address today. Try again tomorrow.")

    key = create_api_key(owner, plan)
    key_info = get_key_info(key)
    return KeyResponse(
        api_key=key,
        owner=key_info["owner"],
        plan=key_info["plan"],
        limit=key_info["quota_limit"],
        remaining=key_info["quota_limit"] - key_info["usage"],
    )


# -----------------------------------------------------------------------------
# 10. Protected endpoints (require API key)
# -----------------------------------------------------------------------------
@app.get("/usage")
async def usage(key_info: dict = Depends(validate_api_key)):
    return UsageResponse(
        owner=key_info["owner"], plan=key_info["plan"], used=key_info["usage"],
        limit=key_info["quota_limit"], remaining=key_info["quota_limit"] - key_info["usage"],
    )


@app.post("/add", response_model=AddResponse)
async def add_fact(add_req: AddRequest, backend: str = "swstm", key_info: dict = Depends(validate_api_key)):
    try:
        if backend == "exact":
            mem = get_exact_memory()
            mem.add(add_req.key, add_req.value)
            remaining = get_remaining_usage(key_info["key_id"])
            return AddResponse(status="ok", message="Added to ExactMemory", backend="exact", remaining=remaining)
        else:
            mem = get_swstm()
            result = mem.add(add_req.key, add_req.value, entity_id=add_req.entity_id)
            remaining = get_remaining_usage(key_info["key_id"])
            return AddResponse(status="ok", message=result, backend="swstm", remaining=remaining)
    except Exception as e:
        logger.exception("Error in /add")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get", response_model=GetResponse)
async def get_fact(key: str, top_k: int = 1, backend: str = "swstm", key_info: dict = Depends(validate_api_key)):
    try:
        if backend == "exact":
            mem = get_exact_memory()
            remaining = get_remaining_usage(key_info["key_id"])
            try:
                result = mem.get(key)
            except Exception as tamper_err:
                # ExactMemory now raises on real tamper detection rather than
                # returning None indistinguishably from "not found" -- surface
                # that distinction to the caller instead of masking it.
                logger.warning(f"Tamper detected on /get: {tamper_err}")
                raise HTTPException(status_code=409, detail="Tamper detected on stored value.")
            if result is not None:
                return GetResponse(answers=[str(result)], backend="exact", remaining=remaining)
            return GetResponse(answers=[], backend="exact", remaining=remaining, message="Not found")
        else:
            mem = get_swstm()
            results = mem.get(key, top_k=top_k)
            remaining = get_remaining_usage(key_info["key_id"])
            if results:
                return GetResponse(answers=results, backend="swstm", remaining=remaining)
            return GetResponse(answers=[], backend="swstm", remaining=remaining, message="No match")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in /get")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/exact/add")
async def add_exact(add_req: AddRequest, key_info: dict = Depends(validate_api_key)):
    mem = get_exact_memory()
    mem.add(add_req.key, add_req.value)
    remaining = get_remaining_usage(key_info["key_id"])
    return {"status": "ok", "remaining": remaining}


# AUDIT FIX: renamed from `get_exact` to `exact_get_endpoint`. The previous
# name collided with the module-level helper of the same name, so this
# handler called ITSELF recursively with zero arguments (missing the
# required request/key/key_info params) on every single invocation, and
# every OTHER caller of the real helper (/add, /get, load_memory) was
# broken the same way after this definition executed at import time.
@app.get("/exact/get")
async def exact_get_endpoint(key: str, key_info: dict = Depends(validate_api_key)):
    mem = get_exact_memory()
    remaining = get_remaining_usage(key_info["key_id"])
    try:
        result = mem.get(key)
    except Exception as tamper_err:
        logger.warning(f"Tamper detected on /exact/get: {tamper_err}")
        raise HTTPException(status_code=409, detail="Tamper detected on stored value.")
    if result is not None:
        return {"answer": result, "remaining": remaining}
    return {"answer": None, "remaining": remaining, "message": "Not found"}


@app.get("/agent-info")
async def agent_info(request: Request, key_info: dict = Depends(validate_api_key)):
    is_agent = request.state.is_agent
    return {
        "is_agent": is_agent,
        "plan": key_info["plan"],
        "remaining": get_remaining_usage(key_info["key_id"]),
        "suggestion": "Consider upgrading to agent plan for higher limits."
                      if is_agent and key_info["plan"].startswith("free") else None,
    }


# -----------------------------------------------------------------------------
# 11. Admin endpoints
#     AUDIT FIX: fail CLOSED if RECALLSPECTION_ADMIN_KEY is unset, instead of
#     comparing against "" (which an empty/missing header could satisfy).
#     Also switched to a constant-time comparison.
# -----------------------------------------------------------------------------
@app.get("/admin/keys")
async def list_keys(admin_key: str = Header(...)):
    if not ADMIN_KEY:
        raise HTTPException(status_code=503, detail="Admin endpoints not configured")
    if not secrets.compare_digest(admin_key, ADMIN_KEY):
        raise HTTPException(status_code=403, detail="Invalid admin key")
    conn = get_db()
    rows = conn.execute(
        "SELECT key_id, owner, plan, usage, quota_limit, created_at, last_used, is_active FROM api_keys"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/admin/revoke/{key_id}")
async def revoke_key(key_id: str, admin_key: str = Header(...)):
    if not ADMIN_KEY:
        raise HTTPException(status_code=503, detail="Admin endpoints not configured")
    if not secrets.compare_digest(admin_key, ADMIN_KEY):
        raise HTTPException(status_code=403, detail="Invalid admin key")
    conn = get_db()
    conn.execute("UPDATE api_keys SET is_active = 0 WHERE key_id = ?", (key_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"Key {key_id} revoked"}


# -----------------------------------------------------------------------------
# 12. Run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
