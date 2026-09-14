import os
import json
import logging
import sqlite3
import secrets
import hmac
import hashlib
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
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

AUTO_SAVE_INTERVAL = int(os.getenv("AUTO_SAVE_INTERVAL", "100"))
write_counter = 0

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
            `limit` INTEGER DEFAULT 1000,
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
        "free": 1000, "pro": 100000, "enterprise": 1000000,
        "agent_free": 5000, "agent_pro": 500000, "agent_enterprise": 5000000,
    }
    limit = limit_map.get(plan, 1000)
    
    conn = get_db()
    conn.execute(
        "INSERT INTO api_keys (key_id, owner, plan, `limit`) VALUES (?, ?, ?, ?)",
        (key, owner, plan, limit)
    )
    conn.commit()
    conn.close()
    return key

def get_key_info(key: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM api_keys WHERE key_id = ? AND is_active = 1", (key,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def increment_usage(key: str) -> int:
    conn = get_db()
    conn.execute(
        "UPDATE api_keys SET usage = usage + 1, last_used = CURRENT_TIMESTAMP WHERE key_id = ?", (key,)
    )
    conn.commit()
    row = conn.execute("SELECT usage, `limit` FROM api_keys WHERE key_id = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else 0

def get_remaining_usage(key: str) -> int:
    conn = get_db()
    row = conn.execute("SELECT `limit`, usage FROM api_keys WHERE key_id = ?", (key,)).fetchone()
    conn.close()
    return (row[0] - row[1]) if row else 0

# -----------------------------------------------------------------------------
# 3. Memory Engine Initialization & Persistence (v3.0.0 Integration)
# -----------------------------------------------------------------------------
swstm = None
exact = None
EXACT_LOG_FILE = os.getenv("RECALLSPECTION_EXACT_LOG", "transparency.log")

def get_exact_keys() -> Dict[str, bytes]:
    """Derives the required key dictionary from a single environment secret."""
    raw = os.getenv(EXACT_SECRET_ENV)
    if not raw:
        logger.warning(f"{EXACT_SECRET_ENV} not set. Using ephemeral keys. Persistence will break on restart.")
        raw = secrets.token_hex(32)
    
    # Deterministically derive the agent key and container key from the master secret
    base = hashlib.sha256(raw.encode()).digest()
    return {
        'agent_key': base,
        'container': hashlib.sha256(b"container-salt-" + base).digest()
    }

def get_exact_memory():
    global exact
    if exact is None:
        # Import from the standalone package
        from exactmemory import ExactMemory 
        
        keys = get_exact_keys()
        exact = ExactMemory(
            keys=keys, 
            container_key_id='container',
            require_log=True, 
            log_path=EXACT_LOG_FILE
        )
        logger.info("ExactMemory v3.0.0 initialized with transparency log")
    return exact

def get_swstm():
    global swstm
    if swstm is None:
        from recallspection.swstm import SWSTMEngine
        swstm = SWSTMEngine(mode=SWSTM_MODE, flat_num_slots=2000)
        logger.info(f"SWSTMEngine initialized (mode={SWSTM_MODE})")
    return swstm

def save_memory():
    try:
        if exact is not None:
            exact.save(MEMORY_FILE) # v3.0.0 handles atomic writes and logging internally
            logger.info(f"ExactMemory saved to {MEMORY_FILE}")
            
        if swstm is not None:
            tmp_swstm = SWSTM_FILE + ".tmp"
            swstm.save(tmp_swstm)
            os.replace(tmp_swstm, SWSTM_FILE)
            logger.info(f"SWSTM saved to {SWSTM_FILE}")
            
    except Exception as e:
        logger.error(f"Failed to save memory: {e}")

def load_memory():
    global exact, swstm
    try:
        if os.path.exists(MEMORY_FILE):
            mem = get_exact_memory()
            keys = get_exact_keys()
            mem.load(MEMORY_FILE, keys) # v3.0.0 verifies MAC, log chain, and rollbacks
            logger.info(f"Loaded ExactMemory with {len(mem)} active facts.")
                
        if os.path.exists(SWSTM_FILE):
            mem = get_swstm()
            mem.load(SWSTM_FILE)
            logger.info(f"Loaded SWSTM with {mem.fact_count} facts.")
            
    except Exception as e:
        logger.critical(f"Failed to load memory (Possible Tampering/Rollback): {e}")

# -----------------------------------------------------------------------------
# 4. FastAPI App Lifecycle
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_exact_memory() 
    get_swstm()        
    load_memory()
    logger.info("Recallspection API started")
    yield
    save_memory()
    logger.info("Recallspection API shutting down")

app = FastAPI(
    title="Recallspection API",
    description="Legendary Dual-core exact memory with API keys, usage tracking, and agent detection",
    version="18.1.0-legendary",
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
    return any(pattern in user_agent for pattern in agent_patterns)

def validate_api_key(request: Request, api_key: str = Depends(api_key_header)):
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
    key: str = Field(..., max_length=2048, description="Max 2KB key")
    value: str = Field(..., max_length=65536, description="Max 64KB value")

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
def root():
    try:
        with open("index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return {"message": "Recallspection API is running. Legend mode active."}

app.mount("/static", StaticFiles(directory=".", html=True), name="static")

@app.get("/health")
def health():
    exact_mem = get_exact_memory() if exact is not None else None
    swstm_mem = get_swstm() if swstm is not None else None
    
    return {
        "status": "healthy",
        "version": "18.1.0-legendary",
        "backend": "SWSTM Legendary + ExactMemory",
        "swstm_loaded": swstm_mem is not None,
        "exact_loaded": exact_mem is not None,
        "facts_swstm": swstm_mem.fact_count if swstm_mem else 0,
        "facts_exact": len(exact_mem) if exact_mem else 0,
        "db_connected": os.path.exists(DB_FILE),
    }

@app.post("/signup")
def signup(
    owner: str = Field(..., max_length=256), 
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
def usage(key_info: dict = Depends(validate_api_key)):
    return UsageResponse(
        owner=key_info["owner"],
        plan=key_info["plan"],
        used=key_info["usage"],
        limit=key_info["limit"],
        remaining=key_info["limit"] - key_info["usage"],
    )

@app.post("/add", response_model=AddResponse)
def add_fact(
    request: Request,
    add_req: AddRequest,
    backend: str = "swstm",
    key_info: dict = Depends(validate_api_key),
):
    global write_counter
    try:
        remaining = get_remaining_usage(key_info["key_id"])
        
        if backend == "exact":
            from exactmemory import TamperError
            mem = get_exact_memory()
            try:
                mem.put(add_req.key, add_req.value, key_id='agent_key')
            except TamperError:
                 raise HTTPException(status_code=409, detail="Tamper detected during write.")
            msg = "Added to ExactMemory (Tamper-Evident)"
            b_end = "exact"
        else:
            mem = get_swstm()
            slot_idx = mem.add(add_req.key, add_req.value)
            msg = f"Added to SWSTM slot {slot_idx}"
            b_end = "swstm"
            
        write_counter += 1
        if write_counter >= AUTO_SAVE_INTERVAL:
            save_memory()
            write_counter = 0
            
        return AddResponse(status="ok", message=msg, backend=b_end, remaining=remaining)
            
    except Exception as e:
        logger.exception("Error in /add")
        raise HTTPException(status_code=500, detail="Internal server error during memory write.")

@app.get("/get", response_model=GetResponse)
def get_fact(
    request: Request,
    key: str,
    top_k: int = 1,
    backend: str = "swstm",
    key_info: dict = Depends(validate_api_key),
):
    try:
        remaining = get_remaining_usage(key_info["key_id"])
        
        if backend == "exact":
            from exactmemory import TamperError
            mem = get_exact_memory()
            try:
                result = mem.get(key, raise_on_tampered=True)
            except TamperError:
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
        raise HTTPException(status_code=500, detail="Internal server error during memory retrieval.")

# -----------------------------------------------------------------------------
# 9. Exact Memory Dedicated Routes
# -----------------------------------------------------------------------------
@app.post("/exact/add")
def add_exact_endpoint(
    request: Request,
    add_req: AddRequest,
    key_info: dict = Depends(validate_api_key),
):
    global write_counter
    from exactmemory import TamperError
    mem = get_exact_memory()
    try:
        mem.put(add_req.key, add_req.value, key_id='agent_key')
    except TamperError:
        raise HTTPException(status_code=409, detail="Tamper detected during write.")
        
    remaining = get_remaining_usage(key_info["key_id"])
    
    write_counter += 1
    if write_counter >= AUTO_SAVE_INTERVAL:
        save_memory()
        write_counter = 0
        
    return {"status": "ok", "remaining": remaining}

@app.get("/exact/get")
def get_exact_endpoint(
    request: Request,
    key: str,
    key_info: dict = Depends(validate_api_key),
):
    from exactmemory import TamperError
    mem = get_exact_memory()
    remaining = get_remaining_usage(key_info["key_id"])
    
    try:
        result = mem.get(key, raise_on_tampered=True)
    except TamperError:
        raise HTTPException(status_code=409, detail="Tamper detected: record integrity compromised.")
        
    if result is not None:
        return {"answer": result, "remaining": remaining}
    return {"answer": None, "remaining": remaining, "message": "Not found"}

@app.get("/agent-info")
def agent_info(request: Request, key_info: dict = Depends(validate_api_key)):
    is_agent = request.state.is_agent
    return {
        "is_agent": is_agent,
        "plan": key_info["plan"],
        "remaining": get_remaining_usage(key_info["key_id"]),
        "suggestion": "Consider upgrading to agent plan for higher limits." if is_agent and key_info["plan"].startswith("free") else None,
    }

# -----------------------------------------------------------------------------
# 10. Admin Routes
# -----------------------------------------------------------------------------
@app.get("/admin/keys")
def list_keys(admin: dict = Depends(require_admin)):
    conn = get_db()
    rows = conn.execute("SELECT key_id, owner, plan, usage, `limit`, created_at, last_used, is_active FROM api_keys").fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/admin/revoke/{key_id}")
def revoke_key(key_id: str, admin: dict = Depends(require_admin)):
    conn = get_db()
    conn.execute("UPDATE api_keys SET is_active = 0 WHERE key_id = ?", (key_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"Key {key_id} revoked"}

@app.post("/admin/save")
def admin_save(admin: dict = Depends(require_admin)):
    save_memory()
    return {"status": "ok", "message": "Memory manually flushed to disk."}

@app.post("/admin/consolidate")
def admin_consolidate(admin: dict = Depends(require_admin)):
    mem = get_swstm()
    mem.consolidate()
    save_memory()
    return {"status": "ok", "message": "SWSTM consolidated and saved."}

# -----------------------------------------------------------------------------
# 11. Run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
