"""
Storage backend for Recallspection API.

Uses Postgres when DATABASE_URL is set.
Falls back to SQLite ONLY when DATABASE_URL is absent (local dev).

IMPORTANT: if DATABASE_URL is set but Postgres cannot be initialized,
the module raises at import. It does NOT silently fall back to SQLite.
"""

import os
import json
import sqlite3
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

logger = logging.getLogger("recallspection-db")

DATABASE_URL = os.getenv("DATABASE_URL")
DB_FILE = os.getenv("RECALLSPECTION_DB_FILE", "keys.db")
USE_POSTGRES = bool(DATABASE_URL)

_pg_pool = None

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    from psycopg2.pool import SimpleConnectionPool
    # Fail loudly on init error -- do not fall back.
    _pg_pool = SimpleConnectionPool(1, 5, dsn=DATABASE_URL)
    logger.info("Storage backend: Postgres")
else:
    logger.info("Storage backend: SQLite (DATABASE_URL not set)")


# =============================================================================
# Connection helpers
# =============================================================================
def _pg_conn():
    return _pg_pool.getconn()


def _pg_release(conn):
    _pg_pool.putconn(conn)


def _sqlite_conn():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def close_db():
    """Called at app shutdown. Closes the PG pool if in use."""
    if USE_POSTGRES and _pg_pool is not None:
        try:
            _pg_pool.closeall()
        except Exception:
            logger.exception("Failed to close Postgres pool")


# =============================================================================
# Schema init + migrations
# =============================================================================
SCHEMA_VERSION = 1


def init_db():
    if USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute(
                    "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
                )
                row = cur.fetchone()
                current = row[0] if row else 0

                # --- v1: initial schema ---
                if current < 1:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS api_keys (
                            key_id TEXT PRIMARY KEY,
                            owner TEXT NOT NULL,
                            plan TEXT NOT NULL,
                            usage INTEGER DEFAULT 0,
                            quota_limit INTEGER DEFAULT 1000,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_used TIMESTAMP,
                            is_active INTEGER DEFAULT 1
                        )
                    """)
                    cur.execute(
                        "CREATE INDEX IF NOT EXISTS idx_key_id ON api_keys(key_id)"
                    )
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS signup_log (
                            ip TEXT NOT NULL,
                            day TEXT NOT NULL,
                            signup_count INTEGER DEFAULT 0,
                            PRIMARY KEY (ip, day)
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS memory_snapshots (
                            id INTEGER PRIMARY KEY,
                            data JSONB NOT NULL,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("INSERT INTO schema_version (version) VALUES (1)")

                # --- Future migrations: elif current < 2: ... ---

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            _pg_release(conn)
    else:
        conn = _sqlite_conn()
        try:
            # Lightweight legacy migration for local dev.
            try:
                cols = [
                    r[1]
                    for r in conn.execute("PRAGMA table_info(api_keys)").fetchall()
                ]
                if "limit" in cols and "quota_limit" not in cols:
                    conn.execute(
                        "ALTER TABLE api_keys RENAME COLUMN `limit` TO quota_limit"
                    )
                    logger.info("Migrated old api_keys.limit -> quota_limit")
            except Exception:
                logger.warning("Migration check skipped (table may not exist)")

            conn.execute("""
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
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_key_id ON api_keys(key_id)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signup_log (
                    ip TEXT NOT NULL,
                    day TEXT NOT NULL,
                    signup_count INTEGER DEFAULT 0,
                    PRIMARY KEY (ip, day)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_snapshots (
                    id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    logger.info(
        f"Database initialized ({'Postgres' if USE_POSTGRES else 'SQLite'})"
    )


# =============================================================================
# Hashing
# =============================================================================
def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# =============================================================================
# API key operations
# =============================================================================
def insert_api_key(key_hash: str, owner: str, plan: str, quota_limit: int) -> None:
    if USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO api_keys (key_id, owner, plan, quota_limit) "
                    "VALUES (%s, %s, %s, %s)",
                    (key_hash, owner, plan, quota_limit),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            _pg_release(conn)
    else:
        conn = _sqlite_conn()
        try:
            conn.execute(
                "INSERT INTO api_keys (key_id, owner, plan, quota_limit) "
                "VALUES (?, ?, ?, ?)",
                (key_hash, owner, plan, quota_limit),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def fetch_key_info(key_hash: str) -> Optional[Dict[str, Any]]:
    if USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM api_keys WHERE key_id = %s AND is_active = 1",
                    (key_hash,),
                )
                row = cur.fetchone()
            return dict(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            _pg_release(conn)
    else:
        conn = _sqlite_conn()
        try:
            row = conn.execute(
                "SELECT * FROM api_keys WHERE key_id = ? AND is_active = 1",
                (key_hash,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def consume_usage(key_hash: str) -> Optional[int]:
    """
    Atomically consume one unit of quota.
    Returns new usage count, or None if key is inactive/missing/exhausted.
    """
    if USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE api_keys
                    SET usage = usage + 1,
                        last_used = CURRENT_TIMESTAMP
                    WHERE key_id = %s
                      AND is_active = 1
                      AND usage < quota_limit
                    RETURNING usage
                    """,
                    (key_hash,),
                )
                row = cur.fetchone()
            conn.commit()
            return row[0] if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            _pg_release(conn)
    else:
        conn = _sqlite_conn()
        try:
            cur = conn.execute(
                """
                UPDATE api_keys
                SET usage = usage + 1,
                    last_used = CURRENT_TIMESTAMP
                WHERE key_id = ?
                  AND is_active = 1
                  AND usage < quota_limit
                """,
                (key_hash,),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT usage FROM api_keys WHERE key_id = ?",
                (key_hash,),
            ).fetchone()
            return row["usage"] if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def fetch_remaining(key_hash: str) -> int:
    if USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT quota_limit, usage FROM api_keys WHERE key_id = %s",
                    (key_hash,),
                )
                row = cur.fetchone()
            return (row[0] - row[1]) if row else 0
        except Exception:
            conn.rollback()
            raise
        finally:
            _pg_release(conn)
    else:
        conn = _sqlite_conn()
        try:
            row = conn.execute(
                "SELECT quota_limit, usage FROM api_keys WHERE key_id = ?",
                (key_hash,),
            ).fetchone()
            return (row["quota_limit"] - row["usage"]) if row else 0
        finally:
            conn.close()


def check_and_log_signup(ip: str, max_per_day: int = 3) -> bool:
    """Atomic check-and-increment of signup count. True if allowed."""
    day = datetime.now(timezone.utc).date().isoformat()

    if USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO signup_log (ip, day, signup_count)
                    VALUES (%s, %s, 1)
                    ON CONFLICT (ip, day)
                    DO UPDATE SET signup_count = signup_log.signup_count + 1
                    WHERE signup_log.signup_count < %s
                    RETURNING signup_count
                    """,
                    (ip, day, max_per_day),
                )
                row = cur.fetchone()
            conn.commit()
            return row is not None
        except Exception:
            conn.rollback()
            raise
        finally:
            _pg_release(conn)
    else:
        conn = _sqlite_conn()
        try:
            # SQLite 3.24+ supports ON CONFLICT DO UPDATE ... WHERE
            try:
                cur = conn.execute(
                    """
                    INSERT INTO signup_log (ip, day, signup_count)
                    VALUES (?, ?, 1)
                    ON CONFLICT (ip, day) DO UPDATE
                    SET signup_count = signup_count + 1
                    WHERE signup_count < ?
                    """,
                    (ip, day, max_per_day),
                )
                conn.commit()
                return cur.rowcount > 0
            except sqlite3.OperationalError:
                # Fallback for old SQLite: SELECT + write
                conn.rollback()
                row = conn.execute(
                    "SELECT signup_count FROM signup_log WHERE ip = ? AND day = ?",
                    (ip, day),
                ).fetchone()
                if row and row["signup_count"] >= max_per_day:
                    return False
                if row:
                    conn.execute(
                        "UPDATE signup_log SET signup_count = signup_count + 1 "
                        "WHERE ip = ? AND day = ?",
                        (ip, day),
                    )
                else:
                    conn.execute(
                        "INSERT INTO signup_log (ip, day, signup_count) "
                        "VALUES (?, ?, 1)",
                        (ip, day),
                    )
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def list_all_keys() -> List[Dict[str, Any]]:
    if USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT key_id, owner, plan, usage, quota_limit, created_at, "
                    "last_used, is_active FROM api_keys ORDER BY created_at DESC"
                )
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            conn.rollback()
            raise
        finally:
            _pg_release(conn)
    else:
        conn = _sqlite_conn()
        try:
            rows = conn.execute(
                "SELECT key_id, owner, plan, usage, quota_limit, created_at, "
                "last_used, is_active FROM api_keys ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def deactivate_key(key_id: str) -> bool:
    """Returns True if a row was updated, False if no such key."""
    if USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE api_keys SET is_active = 0 WHERE key_id = %s",
                    (key_id,),
                )
                updated = cur.rowcount
            conn.commit()
            return updated > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            _pg_release(conn)
    else:
        conn = _sqlite_conn()
        try:
            cur = conn.execute(
                "UPDATE api_keys SET is_active = 0 WHERE key_id = ?",
                (key_id,),
            )
            conn.commit()
            return cur.rowcount > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# =============================================================================
# Memory snapshot persistence
# =============================================================================
def save_memory_snapshot(data: Dict[str, Any]) -> None:
    if USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM memory_snapshots")
                cur.execute(
                    "INSERT INTO memory_snapshots (id, data) VALUES (1, %s)",
                    (json.dumps(data),),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            _pg_release(conn)
    else:
        conn = _sqlite_conn()
        try:
            conn.execute("DELETE FROM memory_snapshots")
            conn.execute(
                "INSERT INTO memory_snapshots (id, data) VALUES (1, ?)",
                (json.dumps(data),),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def load_memory_snapshot() -> Optional[Dict[str, Any]]:
    if USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM memory_snapshots WHERE id = 1")
                row = cur.fetchone()
            if not row:
                return None
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])
        except Exception:
            conn.rollback()
            raise
        finally:
            _pg_release(conn)
    else:
        conn = _sqlite_conn()
        try:
            row = conn.execute(
                "SELECT data FROM memory_snapshots WHERE id = 1"
            ).fetchone()
            if row:
                return json.loads(row[0])
            return None
        finally:
            conn.close()
