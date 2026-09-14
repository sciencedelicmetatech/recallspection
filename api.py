import os
import json
import logging
import sqlite3
import secrets
import hmac
import base64
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# -----------------------------------------------------------------------------
# 1. Logging & Environment Variables
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recallspection-api")

MEMORY_FILE = os.getenv("RECALLSPECTION_MEMORY_FILE", "memory.json")
SWSTM_FILE = os.getenv("RECALLSPECTION_SWSTM_FILE", "swstm.pt")
DB_FILE = os.getenv("RECALLSPECTION_DB_FILE", "keys.db")
SWSTM_MODE = os.getenv("SWSTM_MODE", "flat")

ADMIN_KEY_ENV = "RECALLSPECTION_ADMIN_KEY"
SIGNUP_SECRET_ENV = "RECALLSPECTION_SIGNUP_SECRET"
EXACT_SECRET_ENV = "RECALLSPECTION_EXACT_SECRET"

# -----------------------------------------------------------------------------
# 2. Database: API Keys & Usage Tracking
# -----------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            plan TEXT NOT NULL,
            usage INTEGER DEFAULT 0,
            limit INTEGER DEFAULT 1000,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_used TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_key_id ON api_keys(key_id)')
    conn.commit()
    conn.close()

def create_api_key(owner: str, plan: str = "free") -> str:
    key = f"rk_{secrets.token_urlsafe(24)}"
    limit_map = {
        "free": 1000,
        "pro": 100000,
        "enterprise": 1000000,
        "agent_free": 5000,
        "agent_pro": 500000,
        "agent_enterprise": 5000000,
    }
    limit = limit_map.get(plan, 1000)
    
    conn = get_db()
    conn.execute(
        "INSERT INTO api_keys (key_id, owner, plan, limit) VALUES (?, ?, ?, ?)",
        (key, owner, plan, limit)
    )
    conn.commit()
    conn.close()
    return key

def get_key_info(key: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM api_keys WHERE key_id = ? AND is_active = 1",
        (key,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def increment_usage(key: str) -> int:
    conn = get_db()
    conn.execute(
        "UPDATE api_keys SET usage = usage + 1, last_used = CURRENT_TIMESTAMP WHERE key_id = ?",
        (key,)
    )
    conn.commit()
    row = conn.execute("SELECT usage, limit FROM api_keys WHERE key_id = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else 0

def get_remaining_usage(key: str) -> int:
    conn = get_db()
    row = conn.execute("SELECT limit, usage FROM api_keys WHERE key_id = ?", (key,)).fetchone()
    conn.close()
    if row:
        return row[0] - row[1]
    return 0

# -----------------------------------------------------------------------------
# 3. Memory Engine Initialization & Persistence
# -----------------------------------------------------------------------------
swstm = None
exact = None

def get_exact_secret() -> bytes:
    raw = os.getenv(EXACT_SECRET_ENV)
    if not raw:
        logger.warning(f"{EXACT_SECRET_ENV} not set. Generating ephemeral key. Persistence will break on restart.")
        return os.urandom(32)
    return base64.urlsafe_b64decode(raw.encode())

def get_exact_memory():
    global exact
    if exact is None:
        from recallspection.exact import ExactMemory
        exact = ExactMemory(secret_key=get_exact_secret())
        logger.info("ExactMemory initialized")
    return exact

def get_swstm():
    global swstm
    if swstm is None:
        from recallspection.swstm import SWSTMEngine
        # Legendary SWSTM accepts mode and flat_num_slots for API compatibility
        swstm = SWSTMEngine(mode=SWSTM_MODE, flat_num_slots=200)
        logger.info(f"SWSTMEngine initialized (mode={SWSTM_MODE})")
    return swstm

def save_memory():
    try:
        if exact is not None:
            data = {"exact": exact.export_state()}
            with open(MEMORY_FILE, 'w') as f:
                json.dump(data, f)
            logger.info(f"ExactMemory saved to {MEMORY_FILE}")
            
        if swstm is not None:
            swstm.save(SWSTM_FILE)
            logger.info(f"SWSTM saved to {SWSTM_FILE}")
            
    except Exception as e:
        logger.error(f"Failed to save memory: {e}")

def load_memory():
    global exact, swstm
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r') as f:
                data = json.load(f)
            if 'exact' in data:
                mem = get_exact_memory()
                mem.load_state(data['exact'])
                logger.info(f"Loaded ExactMemory with {len(mem)} facts.")
                
        if os.path.exists(SWSTM_FILE):
            mem = get_swstm()
            mem.load(SWSTM_FILE)
            logger.info(f"Loaded SWSTM with {mem.fact_count} facts.")
            
    except Exception as e:
        logger.error(f"Failed to load memory: {e}")

# -----------------------------------------------------------------------------
# 4. FastAPI App Lifecycle
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_exact_memory() # Pre-initialize
    get_swstm()        # Pre-initialize
    load_memory()
    logger.info("Recallspection API started")
    yield
    save_memory()
    logger.info("Recallspection API shutting down")

app = FastAPI(
    title="Recallspection API",
    description="Legendary Dual-core exact memory with API keys, usage tracking, and agent detection",
    version="18.1.0",
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------
# 5. Auth & Security
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
            detail=f"Usage limit exceeded. Plan: {key_info['plan']}, Used: {key_info['usage']}, Limit: {key_info['limit']}."
        )
        
    increment_usage(api_key)
    request.state.key_info = key_info
    request.state.is_agent = is_agent_request(request)
    return key_info

def require_admin(admin_key: str = Header(None, alias="X-Admin-Key")):
    expected = os.getenv(ADMIN_KEY_ENV)
    if not expected:
        raise HTTPException(status_code=503, detail="Admin API disabled: Admin key not configured on server.")
        
    if admin_key is None or not hmac.compare_digest(admin_key, expected):
        raise HTTPException(status_code=403, detail="Invalid admin key")
        
    return {"admin": True}

# -----------------------------------------------------------------------------
# 6. Pydantic Models
# -----------------------------------------------------------------------------
class AddRequest(BaseModel):
    key: str
    value: str

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
# 7. Public Routes & Static Files
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        with open("index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return {"message": "Recallspection API is running. Legend mode active."}

# Mount static files AFTER routes so it doesn't block API endpoints
app.mount("/static", StaticFiles(directory=".", html=True), name="static")

@app.get("/health")
async def health():
    exact_mem = get_exact_memory() if exact is not None else None
    swstm_mem = get_swstm() if swstm is not None else None
    
    return {
        "status": "healthy",
        "backend": "SWSTM Legendary + ExactMemory",
        "swstm_loaded": swstm_mem is not None,
        "exact_loaded": exact_mem is not None,
        "facts_swstm": swstm_mem.fact_count if swstm_mem else 0,
        "facts_exact": len(exact_mem) if exact_mem else 0,
        "db_connected": os.path.exists(DB_FILE),
    }

@app.post("/signup")
async def signup(
    owner: str, 
    plan: str = "free", 
    signup_secret: str = Header(None, alias="X-Signup-Secret")
):
    expected_secret = os.getenv(SIGNUP_SECRET_ENV)
    if expected_secret:
        if signup_secret is None or not hmac.compare_digest(signup_secret, expected_secret):
            raise HTTPException(status_code=403, detail="Signup requires a valid invite secret.")
            
    valid_plans = ["free", "pro", "enterprise", "agent_free", "agent_pro", "agent_enterprise"]
    if plan not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Choose from: {valid_plans}")
        
    key = create_api_key(owner, plan)
    key_info = get_key_info(key)
    
    return KeyResponse(
        api_key=key,
        owner=key_info["owner"],
        plan=key_info["plan"],
        limit=key_info["limit"],
        remaining=key_info["limit"] - key_info["usage"],
    )

# -----------------------------------------------------------------------------
# 8. Protected Memory Routes
# -----------------------------------------------------------------------------
@app.get("/usage")
async def usage(key_info: dict = Depends(validate_api_key)):
    # FIXED: Removed illegal "await api_key"
    return UsageResponse(
        owner=key_info["owner"],
        plan=key_info["plan"],
        used=key_info["usage"],
        limit=key_info["limit"],
        remaining=key_info["limit"] - key_info["usage"],
    )

@app.post("/add", response_model=AddResponse)
async def add_fact(
    request: Request,
    add_req: AddRequest,
    backend: str = "swstm",
    key_info: dict = Depends(validate_api_key),
):
    try:
        remaining = get_remaining_usage(key_info["key_id"])
        
        if backend == "exact":
            mem = get_exact_memory()
            mem.add(add_req.key, add_req.value)
            return AddResponse(
                status="ok",
                message="Added to ExactMemory",
                backend="exact",
                remaining=remaining,
            )
        else:
            mem = get_swstm()
            slot_idx = mem.add(add_req.key, add_req.value)
            return AddResponse(
                status="ok",
                message=f"Added to SWSTM slot {slot_idx}",
                backend="swstm",
                remaining=remaining,
            )
            
    except Exception as e:
        logger.exception("Error in /add")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get", response_model=GetResponse)
async def get_fact(
    request: Request,
    key: str,
    top_k: int = 1,
    backend: str = "swstm",
    key_info: dict = Depends(validate_api_key),
):
    try:
        remaining = get_remaining_usage(key_info["key_id"])
        
        if backend == "exact":
            from recallspection.exact import TamperDetectedError
            mem = get_exact_memory()
            
            try:
                result = mem.get(key, raise_on_tamper=True)
            except TamperDetectedError:
                raise HTTPException(status_code=409, detail="Tamper detected: record integrity compromised.")
                
            if result is not None:
                return GetResponse(answers=[str(result)], backend="exact", remaining=remaining)
            return GetResponse(answers=[], backend="exact", remaining=remaining, message="Not found")
            
        else:
            mem = get_swstm()
            results = mem.get(key, top_k=top_k)
            
            if results:
                return GetResponse(answers=results, backend="swstm", remaining=remaining)
            return GetResponse(answers=[], backend="swstm", remaining=remaining, message="No match")
            
    except Exception as e:
        logger.exception("Error in /get")
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# 9. Exact Memory Dedicated Routes (FIXED NAME COLLISION)
# -----------------------------------------------------------------------------
@app.post("/exact/add")
async def add_exact_endpoint(
    request: Request,
    add_req: AddRequest,
    key_info: dict = Depends(validate_api_key),
):
    mem = get_exact_memory()
    mem.add(add_req.key, add_req.value)
    remaining = get_remaining_usage(key_info["key_id"])
    return {"status": "ok", "remaining": remaining}

@app.get("/exact/get")
async def get_exact_endpoint(
    request: Request,
    key: str,
    key_info: dict = Depends(validate_api_key),
):
    from recallspection.exact import TamperDetectedError
    mem = get_exact_memory()
    remaining = get_remaining_usage(key_info["key_id"])
    
    try:
        result = mem.get(key, raise_on_tamper=True)
    except TamperDetectedError:
        raise HTTPException(status_code=409, detail="Tamper detected: record integrity compromised.")
        
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
        "suggestion": "Consider upgrading to agent plan for higher limits." if is_agent and key_info["plan"].startswith("free") else None,
    }

# -----------------------------------------------------------------------------
# 10. Admin Routes (FIXED SECURITY)
# -----------------------------------------------------------------------------
@app.get("/admin/keys")
async def list_keys(admin: dict = Depends(require_admin)):
    conn = get_db()
    rows = conn.execute("SELECT key_id, owner, plan, usage, limit, created_at, last_used, is_active FROM api_keys").fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/admin/revoke/{key_id}")
async def revoke_key(key_id: str, admin: dict = Depends(require_admin)):
    conn = get_db()
    conn.execute("UPDATE api_keys SET is_active = 0 WHERE key_id = ?", (key_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"Key {key_id} revoked"}

# -----------------------------------------------------------------------------
# 11. Run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
