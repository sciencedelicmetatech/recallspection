import os
import logging
import secrets
import hashlib
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any, Literal

from fastapi import FastAPI, HTTPException, Header, Depends, Request, Query
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from recallspection import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recallspection-api")

SWSTM_MODE = os.getenv("SWSTM_MODE", "flat")
ADMIN_KEY = os.getenv("RECALLSPECTION_ADMIN_KEY")
SELF_SIGNUP_PLANS = {"free", "agent_free"}
MAX_VALUE_LENGTH = 100_000

RATE_WINDOW_SECONDS = 60
RATE_MAX_REQUESTS = 120

def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"

LIMIT_MAP = {
    "free": 1000, "pro": 100000, "enterprise": 1000000,
    "agent_free": 5000, "agent_pro": 500000, "agent_enterprise": 5000000,
}

def create_api_key(owner: str, plan: str = "free") -> str:
    key = f"rk_{secrets.token_urlsafe(24)}"
    limit = LIMIT_MAP.get(plan, 1000)
    db.insert_api_key(db.hash_api_key(key), owner, plan, limit)
    return key

def get_key_info(key: str) -> Optional[Dict[str, Any]]:
    return db.fetch_key_info(db.hash_api_key(key))

def get_remaining_usage(key: str) -> int:
    return db.fetch_remaining(db.hash_api_key(key))

def check_and_log_signup(ip: str, max_per_day: int = 3) -> bool:
    return db.check_and_log_signup(ip, max_per_day)

swstm = None
exact = None

def get_exact_memory():
    global exact
    if exact is None:
        try:
            from exactmemory_recallspection import ExactMemory
        except ImportError:
            from recallspection.exact import ExactMemory
        try:
            exact = ExactMemory()
        except TypeError:
            keys = {
                "agent_key": hashlib.sha256(b"recallspection-agent").digest(),
                "container": hashlib.sha256(b"recallspection-container").digest(),
            }
            exact = ExactMemory(
                keys=keys, container_key_id="container", require_log=False
            )
        logger.info(f"ExactMemory initialized: {type(exact).__name__}")
    return exact

def get_swstm():
    global swstm
    if swstm is None:
        from recallspection.swstm import SWSTMEngine
        swstm = SWSTMEngine(mode=SWSTM_MODE, flat_num_slots=200)
        logger.info(f"SWSTMEngine initialized (mode={SWSTM_MODE})")
    return swstm

def save_memory():
    data = {}
    try:
        if exact is not None:
            if hasattr(exact, "export_state"):
                data["exact"] = exact.export_state()
            elif hasattr(exact, "_storage"):
                data["exact"] = {
                    k: (
                        v[0].hex() if isinstance(v[0], (bytes, bytearray)) else v[0],
                        v[1].hex() if isinstance(v[1], (bytes, bytearray)) else v[1],
                    )
                    for k, v in exact._storage.items()
                }
        if swstm is not None:
            data["swstm_key_to_value"] = getattr(swstm, "key_to_value", {})
            data["swstm_entity_of"] = getattr(swstm, "_entity_of", {})
            data["swstm_timestamp_of"] = getattr(swstm, "_timestamp_of", {})
        db.save_memory_snapshot(data)
        logger.info("Memory snapshot saved")
    except Exception:
        logger.exception("Failed to save memory")

def load_memory():
    global exact, swstm
    try:
        data = db.load_memory_snapshot()
        if not data:
            logger.info("No memory snapshot found, starting fresh.")
            return
        if "exact" in data:
            exact = get_exact_memory()
            if hasattr(exact, "load_state"):
                exact.load_state(data["exact"])
        if "swstm_key_to_value" in data:
            swstm = get_swstm()
            swstm.key_to_value = data["swstm_key_to_value"]
            swstm._entity_of = data.get("swstm_entity_of", {})
            swstm._timestamp_of = data.get("swstm_timestamp_of", {})
        logger.info("Memory snapshot loaded")
    except Exception:
        logger.exception("Failed to load memory")

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    load_memory()
    logger.info("Recallspection API started")
    yield
    save_memory()
    db.close_db()
    logger.info("Recallspection API shutting down")

app = FastAPI(
    title="Recallspection API",
    description="Dual-core exact memory with API keys, usage tracking, and agent detection",
    version="18.2.0",
    lifespan=lifespan,
)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static", html=False), name="static")

_rate_buckets: Dict[str, deque] = defaultdict(deque)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    ip = _client_ip(request)
    now = time.time()
    bucket = _rate_buckets[ip]
    while bucket and bucket[0] < now - RATE_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= RATE_MAX_REQUESTS:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again shortly."},
        )
    bucket.append(now)
    return await call_next(request)

@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        with open("index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return {"error": "index.html not found"}

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def is_agent_request(request: Request) -> bool:
    user_agent = request.headers.get("user-agent", "").lower()
    for pattern in [
        "python", "curl", "wget", "requests", "langchain",
        "llamaindex", "openai", "anthropic", "cohere",
        "transformers", "jupyter", "colab", "bot", "spider",
    ]:
        if pattern in user_agent:
            return True
    return "colab" in request.headers.get("referer", "").lower()

async def _validate_key(request: Request, api_key: str, increment: bool):
    if api_key is None:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")
    key_hash = db.hash_api_key(api_key)
    key_info = db.fetch_key_info(key_hash)
    if key_info is None:
        raise HTTPException(
            status_code=403, detail="Invalid API Key or key deactivated."
        )
    if increment:
        new_usage = db.consume_usage(key_hash)
        if new_usage is None:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"Usage limit exceeded. Plan: {key_info['plan']}, "
                    f"Limit: {key_info['quota_limit']}."
                ),
            )
        key_info["usage"] = new_usage
    request.state.key_info = key_info
    request.state.api_key = api_key
    request.state.is_agent = is_agent_request(request)
    return key_info

async def validate_api_key(
    request: Request,
    api_key: str = Depends(api_key_header),
):
    return await _validate_key(request, api_key, increment=True)

async def validate_api_key_no_count(
    request: Request,
    api_key: str = Depends(api_key_header),
):
    return await _validate_key(request, api_key, increment=False)

BackendName = Literal["exact", "swstm"]

class AddRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=512)
    value: str = Field(..., min_length=1, max_length=MAX_VALUE_LENGTH)
    entity_id: Optional[str] = Field(None, max_length=128)

class ProvisionRequest(BaseModel):
    owner: str = Field(..., min_length=1, max_length=128)
    plan: str = Field(..., min_length=1, max_length=32)

class SignupRequest(BaseModel):
    owner: str = Field(..., min_length=1, max_length=128)
    plan: str = Field(default="free", pattern="^(free|agent_free)$")

class AddResponse(BaseModel):
    status: str
    message: str
    backend: str
    remaining: int

class GetResponse(BaseModel):
    answers: List[str]
    backend: str
    remaining: int
    status: Optional[str] = None
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

class VerifyResponse(BaseModel):
    key: str
    status: str
    value: Optional[str]
    verified: bool
    remaining: int

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "18.2.0",
        "backend": "ExactMemory v3 + SWSTM v7.0",
        "storage": "Postgres" if db.USE_POSTGRES else "SQLite",
        "swstm_loaded": swstm is not None,
        "exact_loaded": exact is not None,
        "facts_swstm": getattr(swstm, "fact_count", 0) if swstm else 0,
        "facts_exact": len(exact) if exact else 0,
    }

# FIXED: Use JSON body instead of query params for POST
@app.post("/signup", response_model=KeyResponse)
async def signup(
    request: Request,
    body: SignupRequest,
):
    owner = body.owner
    plan = body.plan
    if plan not in SELF_SIGNUP_PLANS:
        raise HTTPException(
            status_code=403,
            detail=f"Plan '{plan}' requires admin provisioning. "
                   f"Self-signup available: {sorted(SELF_SIGNUP_PLANS)}",
        )
    client_ip = _client_ip(request)
    if not check_and_log_signup(client_ip):
        raise HTTPException(status_code=429, detail="Too many signups today.")
    key = create_api_key(owner, plan)
    key_info = get_key_info(key)
    return KeyResponse(
        api_key=key,
        owner=key_info["owner"],
        plan=key_info["plan"],
        limit=key_info["quota_limit"],
        remaining=key_info["quota_limit"] - key_info["usage"],
    )

# Keep backward compat for old clients that send ?owner=&plan=
@app.get("/signup", response_model=KeyResponse)
async def signup_get(
    request: Request,
    owner: str = Query(..., min_length=1, max_length=128),
    plan: str = Query(default="free", pattern="^(free|agent_free)$"),
):
    return await signup(request, SignupRequest(owner=owner, plan=plan))

@app.get("/usage", response_model=UsageResponse)
async def usage(key_info: dict = Depends(validate_api_key_no_count)):
    return UsageResponse(
        owner=key_info["owner"],
        plan=key_info["plan"],
        used=key_info["usage"],
        limit=key_info["quota_limit"],
        remaining=key_info["quota_limit"] - key_info["usage"],
    )

def _exact_add(mem, key, value):
    if hasattr(mem, "put"):
        try:
            import inspect
            if "key_id" in inspect.signature(mem.put).parameters:
                return mem.put(key, value, key_id="agent_key")
        except (ValueError, TypeError):
            pass
        return mem.put(key, value)
    if hasattr(mem, "add"):
        return mem.add(key, value)
    raise RuntimeError("ExactMemory has neither put() nor add()")

def _exact_get(mem, key):
    if hasattr(mem, "get_with_status"):
        return mem.get_with_status(key)
    if hasattr(mem, "get"):
        val = mem.get(key)
        return val, ("ok" if val is not None else "missing")
    raise RuntimeError("ExactMemory has no get()")

@app.post("/add", response_model=AddResponse)
async def add_fact(
    add_req: AddRequest,
    backend: BackendName = Query(default="exact"),
    key_info: dict = Depends(validate_api_key),
):
    try:
        if backend == "exact":
            mem = get_exact_memory()
            _exact_add(mem, add_req.key, add_req.value)
            return AddResponse(
                status="ok",
                message="Added to ExactMemory",
                backend="exact",
                remaining=get_remaining_usage(key_info["key_id"]),
            )
        mem = get_swstm()
        result = mem.add(add_req.key, add_req.value, entity_id=add_req.entity_id)
        return AddResponse(
            status="ok",
            message=str(result),
            backend="swstm",
            remaining=get_remaining_usage(key_info["key_id"]),
        )
    except ImportError as e:
        raise HTTPException(
            status_code=503, detail=f"Backend '{backend}' unavailable: {e}"
        )
    except Exception:
        logger.exception("Error in /add")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/get", response_model=GetResponse)
async def get_fact(
    key: str = Query(..., min_length=1, max_length=512),
    top_k: int = Query(default=1, ge=1, le=100),
    backend: BackendName = Query(default="exact"),
    key_info: dict = Depends(validate_api_key),
):
    try:
        if backend == "exact":
            mem = get_exact_memory()
            value, status = _exact_get(mem, key)
            remaining = get_remaining_usage(key_info["key_id"])
            if status == "ok":
                return GetResponse(
                    answers=[str(value)],
                    backend="exact",
                    remaining=remaining,
                    status="ok",
                )
            if status == "tampered":
                raise HTTPException(
                    status_code=409, detail="Tamper detected on stored value."
                )
            return GetResponse(
                answers=[],
                backend="exact",
                remaining=remaining,
                status="missing",
                message="Not found",
            )
        mem = get_swstm()
        results = mem.get(key, top_k=top_k)
        remaining = get_remaining_usage(key_info["key_id"])
        if results:
            return GetResponse(
                answers=list(results), backend="swstm", remaining=remaining
            )
        return GetResponse(
            answers=[], backend="swstm", remaining=remaining, message="No match"
        )
    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(
            status_code=503, detail=f"Backend '{backend}' unavailable: {e}"
        )
    except Exception:
        logger.exception("Error in /get")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/verify", response_model=VerifyResponse)
async def verify(
    key: str = Query(..., min_length=1, max_length=512),
    key_info: dict = Depends(validate_api_key),
):
    try:
        mem = get_exact_memory()
        value, status = _exact_get(mem, key)
        remaining = get_remaining_usage(key_info["key_id"])
        return VerifyResponse(
            key=key,
            status=status,
            value=str(value) if value is not None else None,
            verified=(status == "ok"),
            remaining=remaining,
        )
    except Exception:
        logger.exception("Error in /verify")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/exact/add")
async def add_exact(
    add_req: AddRequest,
    key_info: dict = Depends(validate_api_key),
):
    mem = get_exact_memory()
    _exact_add(mem, add_req.key, add_req.value)
    return {"status": "ok", "remaining": get_remaining_usage(key_info["key_id"])}

@app.get("/exact/get")
async def exact_get_endpoint(
    key: str = Query(..., min_length=1, max_length=512),
    key_info: dict = Depends(validate_api_key),
):
    mem = get_exact_memory()
    value, status = _exact_get(mem, key)
    remaining = get_remaining_usage(key_info["key_id"])
    if status == "tampered":
        raise HTTPException(
            status_code=409, detail="Tamper detected on stored value."
        )
    return {"answer": value, "status": status, "remaining": remaining}

@app.get("/agent-info")
async def agent_info(
    request: Request,
    key_info: dict = Depends(validate_api_key_no_count),
):
    return {
        "is_agent": request.state.is_agent,
        "plan": key_info["plan"],
        "remaining": get_remaining_usage(key_info["key_id"]),
        "suggestion": "Consider an agent plan for higher limits."
        if request.state.is_agent and key_info["plan"].startswith("free")
        else None,
    }

def _require_admin(admin_key: str) -> None:
    if not ADMIN_KEY:
        raise HTTPException(
            status_code=503, detail="Admin endpoints not configured"
        )
    if not secrets.compare_digest(admin_key, ADMIN_KEY):
        logger.warning("Failed admin auth attempt")
        raise HTTPException(status_code=403, detail="Invalid admin key")

@app.get("/admin/keys")
async def list_keys(admin_key: str = Header(..., alias="admin-key")):
    _require_admin(admin_key)
    logger.info("Admin: list_keys")
    return db.list_all_keys()

@app.post("/admin/provision", response_model=KeyResponse)
async def admin_provision(
    req: ProvisionRequest,
    admin_key: str = Header(..., alias="admin-key"),
):
    _require_admin(admin_key)
    if req.plan not in LIMIT_MAP:
        raise HTTPException(
            status_code=400, detail=f"Unknown plan: {req.plan}"
        )
    logger.info(f"Admin: provision owner={req.owner} plan={req.plan}")
    key = create_api_key(req.owner, req.plan)
    key_info = get_key_info(key)
    return KeyResponse(
        api_key=key,
        owner=key_info["owner"],
        plan=key_info["plan"],
        limit=key_info["quota_limit"],
        remaining=key_info["quota_limit"] - key_info["usage"],
    )

@app.post("/admin/revoke/{key_id}")
async def revoke_key(
    key_id: str,
    admin_key: str = Header(..., alias="admin-key"),
):
    _require_admin(admin_key)
    logger.info(f"Admin: revoke key_id={key_id[:16]}...")
    ok = db.deactivate_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="No such key_id")
    return {"status": "ok", "message": f"Key {key_id} revoked"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)
