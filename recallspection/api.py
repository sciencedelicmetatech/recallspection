"""
Recallspection v3.2.0 Production API
- Dual-engine: ExactMemory + SWSTM Legendary
- SQLite key management + usage quotas
- Stripe billing (checkout, portal, webhook) -> pays Sciencedelic Metatech
- One-click deploy ready (Render/Railway/Fly)
- Fail-closed admin, constant-time compare, payload limits, atomic saves
- Customer dashboard at /dashboard (Memory, Timeline, Shadow, Export)
- Eigengrau-themed API docs at /docs
- External anchor: file backend by default, gates T9 rollback on load
"""
import os
import hmac
import hashlib
import sqlite3
import time
import json
import tempfile
import threading
from pathlib import Path
from typing import Optional, Literal, Dict, Any
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from starlette.background import BackgroundTask
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

ANCHOR_BACKEND = os.getenv("RECALLSPECTION_ANCHOR_BACKEND", "file").strip().lower()
ANCHOR_FILE = os.getenv("RECALLSPECTION_ANCHOR_FILE", "./anchor.json")
ANCHOR_BUCKET = os.getenv("RECALLSPECTION_ANCHOR_BUCKET", "")
ANCHOR_PREFIX = os.getenv("RECALLSPECTION_ANCHOR_PREFIX", "recallspection/")

STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "price_pro_20")
STRIPE_PRICE_TEAM = os.getenv("STRIPE_PRICE_TEAM", "price_team_99")
STRIPE_PRICE_ENTERPRISE = os.getenv("STRIPE_PRICE_ENTERPRISE", "price_ent_249")

if STRIPE_AVAILABLE and STRIPE_SECRET:
    stripe.api_key = STRIPE_SECRET

# --- Landing page path ---
_THIS_FILE = Path(__file__).resolve()
_CANDIDATE_ROOTS = [
    _THIS_FILE.parent.parent,
    _THIS_FILE.parent.parent.parent,
]
INDEX_HTML = next(
    (root / "index.html" for root in _CANDIDATE_ROOTS if (root / "index.html").exists()),
    _CANDIDATE_ROOTS[0] / "index.html",
)

# --- Dashboard static dir (co-located with this file) ---
STATIC_DIR = _THIS_FILE.parent / "static"

# =====================================================================
# Eigengrau-themed Swagger UI
# =====================================================================
# CSS is written without f-string braces so no escaping is needed.
# The OpenAPI URL is injected below via .replace().
DOCS_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Recallspection API - Reference</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
<style>
:root {
    --bg: #16161D;
    --bg-panel: #1E1E28;
    --bg-code: #0F0F14;
    --fg: #E8F4FF;
    --fg-dim: #A0A8B4;
    --accent: #A8D8F0;
    --accent-dim: #6E90A8;
    --border: #2A2A36;
    --green: #4AE08A;
    --yellow: #F0C84A;
    --red: #FF5A5A;
}

html, body {
    background: var(--bg) !important;
    color: var(--fg);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 0;
}

/* Header */
.swagger-ui .topbar {
    background: var(--bg-panel);
    border-bottom: 1px solid var(--border);
    padding: 14px 0;
}
.swagger-ui .topbar .download-url-wrapper {
    display: none;
}
.swagger-ui .topbar-wrapper {
    padding: 0 32px;
    align-items: center;
}
.swagger-ui .topbar-wrapper .link {
    display: flex;
    align-items: center;
    text-decoration: none;
}
.swagger-ui .topbar-wrapper .link::before {
    content: "Recallspection";
    font-family: "Cinzel", serif;
    font-weight: 700;
    font-size: 22px;
    letter-spacing: 0.05em;
    background: linear-gradient(180deg, #FFFFFF 0%, #C8D8E8 35%, #8FA8C0 50%, #E8F4FF 65%, #FFFFFF 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-right: 12px;
}
.swagger-ui .topbar-wrapper img {
    display: none;
}

/* Info block */
.swagger-ui .info {
    margin: 32px 0 24px;
    padding: 0 32px;
}
.swagger-ui .info .title {
    color: var(--accent);
    font-family: "Cinzel", serif;
    font-weight: 700;
    letter-spacing: 0.03em;
}
.swagger-ui .info .title small {
    background: var(--bg-panel);
    color: var(--accent);
}
.swagger-ui .info .title small.version-stamp {
    background: var(--bg-panel);
    border: 1px solid var(--border);
}
.swagger-ui .info p, .swagger-ui .info li {
    color: var(--fg-dim);
}
.swagger-ui .info a {
    color: var(--accent);
}
.swagger-ui .info .base-url {
    color: var(--fg-dim);
}
.swagger-ui .info h1, .swagger-ui .info h2, .swagger-ui .info h3, .swagger-ui .info h4 {
    color: var(--accent);
}
.swagger-ui .info .markdown code {
    background: var(--bg-code);
    color: var(--accent);
}

/* Scheme container / servers */
.swagger-ui .scheme-container {
    background: var(--bg-panel);
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    box-shadow: none;
    padding: 16px 32px;
}
.swagger-ui .scheme-container .schemes > label {
    color: var(--fg-dim);
}
.swagger-ui select {
    background: var(--bg-code) !important;
    color: var(--fg) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px;
}
.swagger-ui .servers > label select {
    background: var(--bg-code) url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20' fill='%23A8D8F0'%3E%3Cpath d='M5 7l5 5 5-5z'/%3E%3C/svg%3E") no-repeat right 8px center !important;
    color: var(--fg) !important;
}

/* Tag headers */
.swagger-ui .opblock-tag {
    color: var(--accent);
    border-bottom: 1px solid var(--border);
    font-family: "Cinzel", serif;
    letter-spacing: 0.03em;
}
.swagger-ui .opblock-tag:hover {
    background: var(--bg-panel);
}
.swagger-ui .opblock-tag small {
    color: var(--fg-dim);
}
.swagger-ui .opblock-tag-section h3 {
    color: var(--accent);
}

/* Operation blocks */
.swagger-ui .opblock {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 4px;
    box-shadow: none;
    margin-bottom: 8px;
}
.swagger-ui .opblock .opblock-summary {
    border-bottom: 1px solid var(--border);
}
.swagger-ui .opblock .opblock-summary-method {
    color: var(--bg);
    font-weight: 700;
    letter-spacing: 0.03em;
    text-shadow: none;
}
.swagger-ui .opblock .opblock-summary-path,
.swagger-ui .opblock .opblock-summary-path__deprecated {
    color: var(--fg);
}
.swagger-ui .opblock .opblock-summary-description {
    color: var(--fg-dim);
}
.swagger-ui .opblock .opblock-summary-control svg {
    fill: var(--accent);
}
.swagger-ui .opblock-body {
    background: var(--bg-code);
}
.swagger-ui .opblock-body pre.microlight {
    background: var(--bg-code) !important;
    color: var(--fg) !important;
}

/* Method colors (kept distinct but toned down) */
.swagger-ui .opblock.opblock-get {
    border-color: rgba(168, 216, 240, 0.3);
    background: rgba(168, 216, 240, 0.05);
}
.swagger-ui .opblock.opblock-get .opblock-summary-method {
    background: var(--accent);
}
.swagger-ui .opblock.opblock-post {
    border-color: rgba(74, 224, 138, 0.3);
    background: rgba(74, 224, 138, 0.05);
}
.swagger-ui .opblock.opblock-post .opblock-summary-method {
    background: var(--green);
}
.swagger-ui .opblock.opblock-put {
    border-color: rgba(240, 200, 74, 0.3);
    background: rgba(240, 200, 74, 0.05);
}
.swagger-ui .opblock.opblock-put .opblock-summary-method {
    background: var(--yellow);
}
.swagger-ui .opblock.opblock-delete {
    border-color: rgba(255, 90, 90, 0.3);
    background: rgba(255, 90, 90, 0.05);
}
.swagger-ui .opblock.opblock-delete .opblock-summary-method {
    background: var(--red);
}

/* Tables and models */
.swagger-ui table thead tr th {
    color: var(--accent);
    border-bottom: 1px solid var(--border);
}
.swagger-ui table tbody tr td {
    color: var(--fg);
    border-bottom: 1px solid var(--border);
}
.swagger-ui .model-box {
    background: var(--bg-code);
    color: var(--fg);
}
.swagger-ui .model {
    color: var(--fg);
}
.swagger-ui .model-title {
    color: var(--accent);
}
.swagger-ui .prop-type {
    color: var(--accent-dim);
}
.swagger-ui .prop-format {
    color: var(--fg-dim);
}
.swagger-ui .parameter__name {
    color: var(--fg);
}
.swagger-ui .parameter__type {
    color: var(--accent-dim);
}
.swagger-ui .parameter__in {
    color: var(--fg-dim);
}
.swagger-ui .parameter__name.required::after {
    color: var(--red);
}
.swagger-ui .parameters-col_description input,
.swagger-ui .parameters-col_description textarea,
.swagger-ui .parameters-col_description select {
    background: var(--bg-code);
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 4px;
}
.swagger-ui input[type=text],
.swagger-ui input[type=password],
.swagger-ui input[type=search],
.swagger-ui textarea {
    background: var(--bg-code);
    color: var(--fg);
    border: 1px solid var(--border);
}
.swagger-ui input::placeholder,
.swagger-ui textarea::placeholder {
    color: var(--fg-dim);
    opacity: 0.6;
}

/* Buttons */
.swagger-ui .btn {
    background: transparent;
    color: var(--accent);
    border: 1px solid var(--accent);
    border-radius: 4px;
    font-weight: 500;
    letter-spacing: 0.02em;
}
.swagger-ui .btn:hover {
    background: rgba(168, 216, 240, 0.1);
}
.swagger-ui .btn.execute {
    background: var(--accent);
    color: var(--bg);
    border-color: var(--accent);
    font-weight: 700;
}
.swagger-ui .btn.execute:hover {
    background: var(--fg);
    border-color: var(--fg);
}
.swagger-ui .btn.cancel {
    background: transparent;
    color: var(--red);
    border-color: var(--red);
}
.swagger-ui .btn.authorize {
    background: transparent;
    color: var(--accent);
    border-color: var(--accent);
}
.swagger-ui .btn.authorize svg {
    fill: var(--accent);
}
.swagger-ui .btn.authorize.locked {
    background: transparent;
    color: var(--accent);
    border-color: var(--accent);
}

/* Response blocks */
.swagger-ui .responses-inner h4,
.swagger-ui .responses-inner h5 {
    color: var(--accent);
}
.swagger-ui .response-col_status {
    color: var(--fg);
}
.swagger-ui .response-col_description {
    color: var(--fg-dim);
}
.swagger-ui .response-col_links {
    color: var(--fg-dim);
}
.swagger-ui .highlight-code {
    background: var(--bg-code) !important;
}
.swagger-ui .highlight-code .microlight {
    background: var(--bg-code) !important;
}
.swagger-ui .copy-to-clipboard {
    background: var(--bg-panel);
    border: 1px solid var(--border);
}
.swagger-ui .copy-to-clipboard button {
    background: transparent;
    color: var(--accent);
}

/* Scrollbars */
.swagger-ui ::-webkit-scrollbar {
    width: 10px;
    height: 10px;
}
.swagger-ui ::-webkit-scrollbar-track {
    background: var(--bg-code);
}
.swagger-ui ::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 5px;
}
.swagger-ui ::-webkit-scrollbar-thumb:hover {
    background: var(--accent-dim);
}

/* Hide the default error wrapper text so it doesn't break theme */
.swagger-ui .errors-wrapper {
    background: rgba(255, 90, 90, 0.08);
    border-color: var(--red);
}
.swagger-ui .errors-wrapper .errors h4 {
    color: var(--red);
}
.swagger-ui .errors-wrapper .errors small {
    color: var(--fg-dim);
}

/* Dialogs / modals */
.swagger-ui .dialog-ux .modal-ux {
    background: var(--bg-panel);
    border: 1px solid var(--border);
}
.swagger-ui .dialog-ux .modal-ux-header h3 {
    color: var(--accent);
    font-family: "Cinzel", serif;
}
.swagger-ui .dialog-ux .modal-ux-content h4 {
    color: var(--accent);
}
.swagger-ui .dialog-ux .modal-ux-content p {
    color: var(--fg-dim);
}
.swagger-ui .dialog-ux .modal-ux-header .close-modal svg {
    fill: var(--fg);
}
.swagger-ui .auth-container .errors {
    color: var(--red);
}

/* Inline links and marks */
.swagger-ui a {
    color: var(--accent);
}
.swagger-ui code {
    background: var(--bg-code);
    color: var(--accent);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 1px 5px;
}
.swagger-ui .renderedMarkdown p {
    color: var(--fg-dim);
}
.swagger-ui .renderedMarkdown code {
    background: var(--bg-code);
    color: var(--accent);
}
</style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
<script>
window.onload = function() {
    window.ui = SwaggerUIBundle({
        url: "__OPENAPI_URL__",
        dom_id: "#swagger-ui",
        deepLinking: true,
        docExpansion: "list",
        defaultModelsExpandDepth: 1,
        defaultModelExpandDepth: 1,
        displayRequestDuration: true,
        filter: true,
        tryItOutEnabled: true,
        presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout",
        syntaxHighlight: {
            activate: true,
            theme: "obsidian"
        }
    });
};
</script>
</body>
</html>
"""


app = FastAPI(
    title="Recallspection API v3.2.0",
    description="Tamper-evident exact memory + collision-resistant SWSTM. TL;DR get(k)=v_set or Err(Tamper)",
    version="3.2.0",
    docs_url=None,       # replaced by custom route below
    redoc_url=None,      # disable default ReDoc
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Payload size guard ---
MAX_PAYLOAD = 1024 * 1024
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

# --- Anchor backends ---
class FileAnchor:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def anchor(self, chain_hash, max_version, container_hash):
        with self._lock:
            try:
                cur = self._read()
                if cur and max_version <= cur.get("max_version", 0):
                    return
                self.path.parent.mkdir(parents=True, exist_ok=True)
                data = {
                    "max_version": max_version,
                    "chain_hash": chain_hash,
                    "container_hash": container_hash,
                    "anchored_at": int(time.time()),
                }
                tmp = str(self.path) + ".tmp"
                with open(tmp, "w") as f:
                    f.write(json.dumps(data, sort_keys=True))
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.path)
            except Exception as e:
                print("[anchor] write failed: " + str(e)[:200])

    def get_latest(self):
        return self._read()

    def verify(self, chain_hash):
        cur = self._read()
        return cur is not None and cur.get("chain_hash") == chain_hash

    def _read(self):
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return None


def _build_anchor():
    if ANCHOR_BACKEND == "file":
        print("[Anchor] file backend -> " + ANCHOR_FILE)
        return FileAnchor(ANCHOR_FILE)
    if ANCHOR_BACKEND == "s3":
        try:
            from recallspection.anchor import RemoteAnchorS3
            a = RemoteAnchorS3(bucket=ANCHOR_BUCKET, prefix=ANCHOR_PREFIX)
            print("[Anchor] s3 backend -> s3://" + ANCHOR_BUCKET + "/" + ANCHOR_PREFIX)
            return a
        except Exception as e:
            print("[Anchor] s3 init failed: " + str(e) + " - falling back to file")
            return FileAnchor(ANCHOR_FILE)
    if ANCHOR_BACKEND == "none":
        print("[Anchor] disabled - T9 (snapshot rollback) will be accepted")
        return None
    print("[Anchor] unknown backend '" + ANCHOR_BACKEND + "' - disabled")
    return None


# --- ExactMemory ---
exact_memory = None
exact_keys = None
_anchor = None
try:
    from exactmemory.recallspection import (
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
    _anchor = _build_anchor()
    exact_memory = ExactMemory(
        keys=exact_keys,
        container_key_id="container",
        require_log=True,
        remote_anchor=_anchor,
    )
    if Path(MEMORY_FILE).exists():
        try:
            exact_memory.load(MEMORY_FILE)
        except FormatVersionError as e:
            print("[FATAL] Format version mismatch: " + str(e))
            raise SystemExit(2)
        except (TamperError, RollbackError, LogCompromisedError) as e:
            print("[FATAL] Integrity failure on load: " + str(e))
            raise SystemExit(3)
        except Exception as e:
            print("[FATAL] Unexpected load failure: " + str(e))
            raise SystemExit(4)
    print("[ExactMemory] initialized")
except SystemExit:
    raise
except Exception as e:
    print("[ExactMemory] init failed: " + str(e) + " - running in mock mode")
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
            print("[SWSTM] load failed: " + str(e))
    print("[SWSTM] initialized")
except Exception as e:
    print("[SWSTM] init failed: " + str(e))

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
            print("[autosave] " + str(e))

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

# --- Anchor helpers ---
def _anchor_snapshot():
    if _anchor is None:
        return None
    try:
        latest = _anchor.get_latest()
    except Exception as e:
        return {"error": str(e)[:200]}
    if latest is None:
        return None
    if isinstance(latest, dict):
        return latest
    return {
        "max_version": getattr(latest, "max_version", None),
        "chain_hash": getattr(latest, "chain_hash", None),
        "anchored_at": getattr(latest, "anchored_at", None),
        "container_hash": getattr(latest, "container_hash", None),
    }

# =====================================================================
# Custom themed docs
# =====================================================================
@app.get("/docs", include_in_schema=False)
def custom_docs():
    html = DOCS_HTML_TEMPLATE.replace("__OPENAPI_URL__", app.openapi_url or "/openapi.json")
    return HTMLResponse(content=html)

# =====================================================================
# Endpoints
# =====================================================================
@app.get("/health")
def health():
    anchor_state = _anchor_snapshot()
    return {
        "status": "ok",
        "version": "3.2.0",
        "exact_loaded": exact_memory is not None,
        "swstm_loaded": hybrid is not None,
        "store_format": exact_memory.VERSION if exact_memory else None,
        "store_max_version": exact_memory.max_version if exact_memory else None,
        "memory_file": MEMORY_FILE,
        "swstm_file": SWSTM_FILE,
        "db_file": DB_FILE,
        "exact_log": EXACT_LOG,
        "anchor_backend": ANCHOR_BACKEND,
        "anchor_file": ANCHOR_FILE if ANCHOR_BACKEND == "file" else None,
        "anchor_configured": _anchor is not None,
        "anchor_max_version": anchor_state.get("max_version") if isinstance(anchor_state, dict) else None,
        "stripe_enabled": STRIPE_AVAILABLE and bool(STRIPE_SECRET),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/signup")
def signup(req: SignupRequest):
    if SIGNUP_SECRET:
        if not req.signup_secret or not const_eq(req.signup_secret, SIGNUP_SECRET):
            raise HTTPException(403, "Invalid signup secret")
    import secrets
    raw_key = "rsc_" + secrets.token_urlsafe(32)
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
            print("[stripe] customer create failed: " + str(e))

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
        raise HTTPException(429, "Quota exceeded " + str(auth["quota_used"]) + "/" + str(auth["quota_limit"]))
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
            put_status = exact_memory.put(req.key, req.value, key_id="agent_key", source="admin")
            result["exact"] = put_status
        if backend in ("swstm", "hybrid"):
            if hybrid:
                hybrid.add(req.key, req.value)
                result["swstm"] = "ok"
        if exact_memory:
            exact_memory.save(MEMORY_FILE)
        if hybrid:
            hybrid.save(SWSTM_FILE)
        return {"key": req.key, "backend": backend, "result": result, "status": "stored"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, "Add failed: " + str(e)[:500])

@app.get("/get")
def get_fact(key: str, top_k: int = 1, auth=Depends(verify_api_key)):
    check_quota(auth)
    try:
        if exact_memory:
            if hasattr(exact_memory, "get_with_status"):
                val, status = exact_memory.get_with_status(key)
            else:
                val, status = exact_memory.get(key), "ok"

            if status == "ok" and val is not None:
                return {"key": key, "value": val, "source": "exact", "status": status, "tamper": False}

            if status == "tampered":
                return {"key": key, "value": None, "source": "exact", "status": "tampered",
                        "tamper": True,
                        "detail": "Previously known key missing or HMAC mismatch - deletion/corruption attack detected"}
            if status == "revoked":
                return {"key": key, "value": None, "source": "exact", "status": "revoked",
                        "tamper": False,
                        "detail": "Record revoked. Not eligible for fuzzy fallback."}
            if status == "tombstoned":
                return {"key": key, "value": None, "source": "exact", "status": "tombstoned",
                        "tamper": False,
                        "detail": "Record deleted. Not eligible for fuzzy fallback."}
            if status == "expired":
                return {"key": key, "value": None, "source": "exact", "status": "expired",
                        "tamper": False,
                        "detail": "Record expired (TTL). Not eligible for fuzzy fallback."}

        if hybrid:
            res = hybrid.get(key, top_k=top_k)
            if res:
                return {"key": key, "value": res, "source": "swstm", "status": "ok", "tamper": False}

        return {"key": key, "value": None, "source": "none", "status": "missing"}
    except Exception as e:
        print("[get] error " + str(e))
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
        if hasattr(exact_memory, "get_with_status"):
            val, status = exact_memory.get_with_status(key)
        else:
            val, status = exact_memory.get(key), "ok"
        return {
            "key": key,
            "value": val,
            "status": status,
            "tamper": status == "tampered",
            "terminal": status in ("tampered", "revoked", "tombstoned", "expired"),
        }
    except Exception as e:
        raise HTTPException(500, str(e)[:500])

# --- Billing ---
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
    if not price_id or not price_id.startswith("price_"):
        price_id = None

    try:
        session = stripe.checkout.Session.create(
            customer_email=req.email,
            line_items=[{"price": price_id, "quantity": 1}] if price_id else [{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Recallspection " + req.tier.title()},
                    "unit_amount": {"pro": 2000, "team": 9900, "enterprise": 24900}[req.tier],
                },
                "quantity": 1
            }],
            mode="subscription",
            success_url=FRONTEND_URL + "/billing/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=FRONTEND_URL + "/billing/cancel",
            metadata={"tier": req.tier, "email": req.email}
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        raise HTTPException(500, "Stripe checkout failed: " + str(e))

@app.get("/billing/portal")
def billing_portal(customer_id: str = None, auth=Depends(verify_api_key)):
    if not (STRIPE_AVAILABLE and STRIPE_SECRET):
        raise HTTPException(500, "Stripe not configured")
    cid = customer_id or auth.get("stripe_customer_id")
    if not cid:
        raise HTTPException(400, "No stripe_customer_id found - signup with email first")
    try:
        portal = stripe.billing_portal.Session.create(customer=cid, return_url=FRONTEND_URL + "/usage")
        return {"portal_url": portal.url}
    except Exception as e:
        raise HTTPException(500, "Portal failed: " + str(e))

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    if not (STRIPE_AVAILABLE and STRIPE_SECRET and STRIPE_WEBHOOK_SECRET):
        raise HTTPException(500, "Stripe webhook not configured")
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(400, "Webhook error: " + str(e))

    if event["type"] in ("checkout.session.completed", "customer.subscription.created", "customer.subscription.updated"):
        obj = event["data"]["object"]
        customer_id = obj.get("customer") or obj.get("customer_id")
        tier = obj.get("metadata", {}).get("tier", "pro")
        try:
            conn = get_conn()
            if customer_id:
                conn.execute(
                    "UPDATE api_keys SET tier=?, status='active', quota_limit=? WHERE stripe_customer_id=?",
                    (tier, {"pro": 50000, "team": 500000, "enterprise": 10000000}[tier], customer_id)
                )
            conn.commit()
            conn.close()
            print("[stripe] upgraded " + str(customer_id) + " to " + tier)
        except Exception as e:
            print("[stripe] DB update failed " + str(e))

    return {"status": "ok"}

# --- Admin ---
@app.get("/admin/keys")
def admin_list_keys(_=Depends(verify_admin)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT key_id, api_key_prefix, created_at, quota_limit, quota_used, tier, status, stripe_customer_id "
        "FROM api_keys ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
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

@app.get("/admin/anchor")
def admin_anchor(_=Depends(verify_admin)):
    if exact_memory and _anchor:
        try:
            exact_memory.save(MEMORY_FILE)
        except Exception as e:
            raise HTTPException(500, "save failed: " + str(e))
    return {
        "backend": ANCHOR_BACKEND,
        "file": ANCHOR_FILE if ANCHOR_BACKEND == "file" else None,
        "state": _anchor_snapshot(),
    }

# --- Root: landing page ---
@app.get("/", response_class=HTMLResponse)
def root():
    if INDEX_HTML.exists():
        return INDEX_HTML.read_text(encoding="utf-8")

    return JSONResponse(
        status_code=200,
        content={
            "name": "Recallspection API v3.2.0",
            "docs": "/docs",
            "health": "/health",
            "dashboard": FRONTEND_URL,
            "message": "index.html not found - serving JSON fallback.",
            "expected_path": str(INDEX_HTML),
        },
    )

# =====================================================================
# Customer-facing dashboard
# =====================================================================
_STATUS_TO_BADGE: Dict[str, str] = {
    "ok": "green",
    "missing": "yellow",
    "tampered": "red",
    "tombstoned": "red",
    "revoked": "red",
    "expired": "red",
}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    html_path = STATIC_DIR / "dashboard.html"
    if not html_path.exists():
        raise HTTPException(404, "Dashboard asset missing from deploy")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.get("/dashboard/memory")
def dashboard_memory(auth=Depends(verify_api_key)):
    if not exact_memory:
        return {"keys": [], "exact_loaded": False}
    out = []
    for k in list(exact_memory.store.keys()):
        rec, tag = exact_memory.store[k]
        if hasattr(exact_memory, "verify_record"):
            valid = exact_memory.verify_record(k)
        else:
            valid = hmac.compare_digest(tag, exact_memory._make_tag(rec["key_id"], rec))
        out.append({
            "key": k,
            "value": rec.get("value"),
            "version": rec.get("version"),
            "hmac_status": "valid" if valid else "invalid",
            "anchor_time": rec.get("timestamp"),
            "source": rec.get("source"),
            "trusted": rec.get("trusted", False),
            "revoked": rec.get("revoked", False),
            "shadow_count": len(rec.get("shadow", [])),
        })
    return {"keys": out, "exact_loaded": True, "store_format": exact_memory.VERSION}

@app.get("/dashboard/memory/{key}/history")
def dashboard_history(key: str, auth=Depends(verify_api_key)):
    if not exact_memory:
        raise HTTPException(503, "ExactMemory not loaded")
    if key not in exact_memory.store:
        return {"key": key, "versions": []}
    rec, _tag = exact_memory.store[key]
    if hasattr(exact_memory, "verify_record"):
        valid = exact_memory.verify_record(key)
    else:
        valid = hmac.compare_digest(_tag, exact_memory._make_tag(rec["key_id"], rec))
    tip = exact_memory.log.get_tip() if exact_memory.log else None
    return {
        "key": key,
        "versions": [{
            "version": rec.get("version"),
            "timestamp": rec.get("timestamp"),
            "hmac_valid": valid,
            "anchor_status": "anchored" if tip else "unanchored",
            "prev_hash": tip.get("prev_hash") if tip else None,
            "root": tip.get("chain_hash") if tip else None,
            "is_rollback": False,
        }],
        "note": "ExactMemory v3.2.0 retains one record per key. Per-key version history is not persisted.",
    }

@app.get("/dashboard/memory/{key}/verify")
def dashboard_verify(key: str, auth=Depends(verify_api_key)):
    if not exact_memory:
        raise HTTPException(503, "ExactMemory not loaded")
    if hasattr(exact_memory, "get_with_status"):
        _val, status = exact_memory.get_with_status(key)
    else:
        v = exact_memory.get(key)
        status = "ok" if v is not None else "missing"
    state = _STATUS_TO_BADGE.get(status, "yellow")

    snapshot = _anchor_snapshot()
    anchor_time = None
    anchor_chain_hash = None
    if isinstance(snapshot, dict):
        anchor_time = snapshot.get("anchored_at")
        anchor_chain_hash = snapshot.get("chain_hash")

    return {
        "key": key,
        "state": state,
        "status": status,
        "anchor_time": anchor_time,
        "anchor_chain_hash": anchor_chain_hash,
        "hmac_status": "valid" if status == "ok" else status,
    }

@app.get("/dashboard/memory/{key}/shadow")
def dashboard_shadow(key: str, auth=Depends(verify_api_key)):
    if not exact_memory:
        raise HTTPException(503, "ExactMemory not loaded")
    if not hasattr(exact_memory, "get_shadow"):
        return {"key": key, "shadow": [], "note": "Loaded core predates CP1; shadow not available."}
    return {"key": key, "shadow": exact_memory.get_shadow(key)}

@app.get("/dashboard/anchor")
def dashboard_anchor(auth=Depends(verify_api_key)):
    if not exact_memory:
        raise HTTPException(503, "ExactMemory not loaded")
    return {
        "backend": ANCHOR_BACKEND,
        "configured": _anchor is not None,
        "file": ANCHOR_FILE if ANCHOR_BACKEND == "file" else None,
        "latest": _anchor_snapshot(),
        "store_max_version": exact_memory.max_version,
    }

@app.get("/dashboard/export")
def dashboard_export(auth=Depends(verify_api_key)):
    try:
        from recallspection.anchor import audit_export
    except ImportError as e:
        raise HTTPException(500, "Export unavailable: " + str(e))
    fd, tmp = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    try:
        audit_export(EXACT_LOG, tmp)
    except Exception as e:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise HTTPException(500, "Export failed: " + str(e)[:300])
    return FileResponse(
        tmp,
        media_type="application/zip",
        filename="recallspection-evidence.zip",
        background=BackgroundTask(lambda p=tmp: os.path.exists(p) and os.unlink(p)),
    )
