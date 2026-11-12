"""SQLite persistence layer for StyleDNA, swipe idempotency, ADK sessions, media cache, search cache, and telemetry.

Uses Python's built-in sqlite3 (WAL mode + RLock) so state survives server restarts and multi-worker processes
without requiring external database infrastructure.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.adk.events.event import Event
from google.adk.sessions import BaseSessionService, InMemorySessionService, Session
from google.adk.sessions.base_session_service import GetSessionConfig, ListSessionsResponse

from app import config
from stylist_agent.schemas import StyleDNA


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuraDatabase:
    """Thread-safe SQLite store backing profiles, swipe events, media blobs, search cache, ADK sessions, and telemetry."""

    def __init__(self, db_path: Path | str | None = None):
        raw = db_path if db_path is not None else config.AURA_DB_PATH
        self.db_path = str(raw)
        self._lock = threading.RLock()
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            if self.db_path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY,
                    owner_token_hash TEXT NOT NULL DEFAULT '',
                    dna_json TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS swipe_events (
                    user_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    action TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, idempotency_key)
                );

                CREATE TABLE IF NOT EXISTS adk_sessions (
                    app_name TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    session_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (app_name, user_id, session_id)
                );

                CREATE TABLE IF NOT EXISTS media_cache (
                    media_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT '',
                    mime_type TEXT NOT NULL,
                    image_source TEXT NOT NULL DEFAULT 'none',
                    data BLOB NOT NULL,
                    last_accessed REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS search_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    expires_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telemetry_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------- Auth & User Scoping ----------

    def issue_session_token(self, user_id: str) -> str:
        """Issue or rotate an opaque user token bound to user_id via SHA-256 hash."""
        uid = user_id or "default"
        token = secrets.token_urlsafe(32)
        tok_hash = _hash_token(token)
        with self._lock, self._conn:
            row = self._conn.execute("SELECT dna_json FROM profiles WHERE user_id = ?", (uid,)).fetchone()
            if row is None:
                dna = StyleDNA(user_id=uid).model_dump_json()
                self._conn.execute(
                    "INSERT INTO profiles (user_id, owner_token_hash, dna_json, version, updated_at) VALUES (?, ?, ?, 1, ?)",
                    (uid, tok_hash, dna, _now_iso()),
                )
            else:
                self._conn.execute(
                    "UPDATE profiles SET owner_token_hash = ?, updated_at = ? WHERE user_id = ?",
                    (tok_hash, _now_iso(), uid),
                )
        return token

    def verify_user_token(self, user_id: str, provided_token: str | None, *, strict: bool = False) -> bool:
        """Verify token against stored owner hash.

        If a user_id already has an owner_token_hash, missing or mismatched tokens return False.
        If `strict=True` (AURA_STRICT_AUTH=1), even unbound user_ids require a valid token.
        If `provided_token` is supplied for an unbound user_id in non-strict mode, bind it lazily.
        """
        uid = user_id or "default"
        with self._lock, self._conn:
            row = self._conn.execute("SELECT owner_token_hash FROM profiles WHERE user_id = ?", (uid,)).fetchone()
            stored_hash = (row["owner_token_hash"] if row else "") or ""
            if stored_hash:
                if not provided_token:
                    return False
                return hmac.compare_digest(stored_hash, _hash_token(provided_token))
            if strict and not provided_token:
                return False
            if provided_token:
                dna = StyleDNA(user_id=uid).model_dump_json()
                self._conn.execute(
                    """
                    INSERT INTO profiles (user_id, owner_token_hash, dna_json, version, updated_at)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(user_id) DO UPDATE SET owner_token_hash = excluded.owner_token_hash
                    """,
                    (uid, _hash_token(provided_token), dna, _now_iso()),
                )
            return True

    # ---------- Profile CRUD ----------

    def get_profile(self, user_id: str) -> StyleDNA:
        uid = user_id or "default"
        with self._lock:
            row = self._conn.execute("SELECT dna_json FROM profiles WHERE user_id = ?", (uid,)).fetchone()
            if row:
                try:
                    return StyleDNA.model_validate_json(row["dna_json"])
                except Exception:
                    pass
            return StyleDNA(user_id=uid)

    def save_profile(self, dna: StyleDNA) -> StyleDNA:
        uid = dna.user_id or "default"
        copy = dna.model_copy(deep=True)
        payload = copy.model_dump_json()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO profiles (user_id, owner_token_hash, dna_json, version, updated_at)
                VALUES (?, '', ?, 1, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    dna_json = excluded.dna_json,
                    version = version + 1,
                    updated_at = excluded.updated_at
                """,
                (uid, payload, _now_iso()),
            )
        return copy

    def forget_user(self, user_id: str) -> StyleDNA:
        """Cascade delete across profiles, swipe events, user media, telemetry, and ADK sessions."""
        uid = user_id or "default"
        fresh = StyleDNA(user_id=uid)
        with self._lock, self._conn:
            # Keep owner_token_hash zeroed or cleared, delete everything user-related
            self._conn.execute("DELETE FROM profiles WHERE user_id = ?", (uid,))
            self._conn.execute("DELETE FROM swipe_events WHERE user_id = ?", (uid,))
            self._conn.execute("DELETE FROM adk_sessions WHERE user_id = ?", (uid,))
            self._conn.execute("DELETE FROM media_cache WHERE user_id = ?", (uid,))
            self._conn.execute("DELETE FROM telemetry_events WHERE user_id = ?", (uid,))
        return fresh

    # ---------- Swipe Idempotency ----------

    def get_idempotent_swipe(self, user_id: str, idempotency_key: str) -> dict[str, Any] | None:
        if not idempotency_key:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT response_json FROM swipe_events WHERE user_id = ? AND idempotency_key = ?",
                (user_id or "default", idempotency_key),
            ).fetchone()
            if row:
                try:
                    return json.loads(row["response_json"])
                except Exception:
                    return None
        return None

    def record_idempotent_swipe(
        self, user_id: str, idempotency_key: str, action: str, response_payload: dict[str, Any]
    ) -> None:
        if not idempotency_key:
            return
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO swipe_events (user_id, idempotency_key, action, response_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id or "default", idempotency_key, action, json.dumps(response_payload), _now_iso()),
            )

    # ---------- Media Cache ----------

    def put_media(
        self,
        media_id: str,
        data: bytes,
        mime_type: str,
        *,
        user_id: str = "",
        image_source: str = "none",
        max_entries: int = 250,
    ) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO media_cache (media_id, user_id, mime_type, image_source, data, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(media_id) DO UPDATE SET
                    data = excluded.data,
                    mime_type = excluded.mime_type,
                    image_source = excluded.image_source,
                    last_accessed = excluded.last_accessed
                """,
                (media_id, user_id, mime_type, image_source, sqlite3.Binary(data), now),
            )
            self._conn.execute(
                """
                DELETE FROM media_cache WHERE media_id IN (
                    SELECT media_id FROM media_cache ORDER BY last_accessed DESC LIMIT -1 OFFSET ?
                )
                """,
                (max_entries,),
            )

    def get_media(self, media_id: str) -> tuple[bytes, str] | None:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT data, mime_type FROM media_cache WHERE media_id = ?", (media_id,)
            ).fetchone()
            if row is None:
                return None
            self._conn.execute(
                "UPDATE media_cache SET last_accessed = ? WHERE media_id = ?", (time.time(), media_id)
            )
            return bytes(row["data"]), str(row["mime_type"])

    def delete_user_media(self, user_id: str) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM media_cache WHERE user_id = ?", (user_id or "default",))
            return cur.rowcount

    # ---------- Search Cache ----------

    def get_search_cache(self, cache_key: str) -> dict[str, Any] | None:
        now = time.time()
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT payload_json, expires_at FROM search_cache WHERE cache_key = ?", (cache_key,)
            ).fetchone()
            if row is None:
                return None
            if float(row["expires_at"]) <= now:
                self._conn.execute("DELETE FROM search_cache WHERE cache_key = ?", (cache_key,))
                return None
            try:
                return json.loads(row["payload_json"])
            except Exception:
                return None

    def set_search_cache(self, cache_key: str, payload: dict[str, Any], ttl_sec: int = 900) -> None:
        if ttl_sec <= 0:
            return
        expires = time.time() + ttl_sec
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO search_cache (cache_key, payload_json, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    expires_at = excluded.expires_at
                """,
                (cache_key, json.dumps(payload, ensure_ascii=False), expires),
            )
            self._conn.execute("DELETE FROM search_cache WHERE expires_at <= ?", (time.time(),))

    # ---------- Telemetry ----------

    def record_telemetry(
        self,
        *,
        request_id: str,
        user_id: str,
        session_id: str,
        event_type: str,
        name: str,
        duration_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
        meta: dict[str, Any] | None = None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO telemetry_events
                (request_id, user_id, session_id, event_type, name, duration_ms, input_tokens, output_tokens, estimated_cost_usd, meta_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    user_id,
                    session_id,
                    event_type,
                    name,
                    round(duration_ms, 2),
                    int(input_tokens),
                    int(output_tokens),
                    round(estimated_cost_usd, 6),
                    json.dumps(meta or {}),
                    _now_iso(),
                ),
            )

    def telemetry_summary(self, limit: int = 25) -> dict[str, Any]:
        with self._lock:
            agg = self._conn.execute(
                """
                SELECT
                    COUNT(*) AS count,
                    COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                    COALESCE(SUM(estimated_cost_usd), 0.0) AS total_cost_usd,
                    COALESCE(AVG(duration_ms), 0.0) AS avg_duration_ms
                FROM telemetry_events
                """
            ).fetchone()
            rows = self._conn.execute(
                """
                SELECT request_id, user_id, event_type, name, duration_ms, input_tokens, output_tokens, estimated_cost_usd, created_at
                FROM telemetry_events ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return {
            "totals": dict(agg) if agg else {},
            "recent": [dict(r) for r in rows],
        }


_DEFAULT_DB: AuraDatabase | None = None
_DB_LOCK = threading.RLock()


def get_db() -> AuraDatabase:
    global _DEFAULT_DB
    with _DB_LOCK:
        if _DEFAULT_DB is None:
            _DEFAULT_DB = AuraDatabase(config.AURA_DB_PATH)
        return _DEFAULT_DB


def set_db(db: AuraDatabase | None) -> None:
    global _DEFAULT_DB
    with _DB_LOCK:
        _DEFAULT_DB = db


class SqliteSessionService(BaseSessionService):
    """ADK BaseSessionService persisted atomically to AuraDatabase SQLite."""

    def __init__(self, db: AuraDatabase | None = None):
        self._db = db
        self._mem = InMemorySessionService()

    def _active_db(self) -> AuraDatabase:
        return self._db or get_db()

    def _save_session(self, session: Session) -> None:
        db = self._active_db()
        with db._lock, db._conn:
            db._conn.execute(
                """
                INSERT INTO adk_sessions (app_name, user_id, session_id, session_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(app_name, user_id, session_id) DO UPDATE SET
                    session_json = excluded.session_json,
                    updated_at = excluded.updated_at
                """,
                (session.app_name, session.user_id, session.id, session.model_dump_json(), _now_iso()),
            )

    def _load_session(self, app_name: str, user_id: str, session_id: str) -> Session | None:
        db = self._active_db()
        with db._lock:
            row = db._conn.execute(
                "SELECT session_json FROM adk_sessions WHERE app_name = ? AND user_id = ? AND session_id = ?",
                (app_name, user_id, session_id),
            ).fetchone()
        if not row:
            return None
        try:
            return Session.model_validate_json(row["session_json"])
        except Exception:
            return None

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> Session:
        session = await self._mem.create_session(
            app_name=app_name, user_id=user_id, state=state, session_id=session_id
        )
        self._save_session(session)
        return session

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: GetSessionConfig | None = None,
    ) -> Session | None:
        mem_session = await self._mem.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id, config=config
        )
        if mem_session is not None:
            return mem_session
        loaded = self._load_session(app_name, user_id, session_id)
        if loaded is None:
            return None
        # Hydrate in-memory cache so Runner can mutate/append cleanly
        restored = await self._mem.create_session(
            app_name=loaded.app_name,
            user_id=loaded.user_id,
            state=loaded.state,
            session_id=loaded.id,
        )
        restored.events = list(loaded.events)
        restored.last_update_time = loaded.last_update_time
        return await self._mem.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id, config=config
        )

    async def list_sessions(
        self, *, app_name: str, user_id: str | None = None
    ) -> ListSessionsResponse:
        db = self._active_db()
        with db._lock:
            if user_id is None:
                rows = db._conn.execute(
                    "SELECT session_json FROM adk_sessions WHERE app_name = ?", (app_name,)
                ).fetchall()
            else:
                rows = db._conn.execute(
                    "SELECT session_json FROM adk_sessions WHERE app_name = ? AND user_id = ?",
                    (app_name, user_id),
                ).fetchall()
        sessions = []
        for r in rows:
            try:
                sessions.append(Session.model_validate_json(r["session_json"]))
            except Exception:
                continue
        return ListSessionsResponse(sessions=sessions)

    async def delete_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> None:
        await self._mem.delete_session(app_name=app_name, user_id=user_id, session_id=session_id)
        db = self._active_db()
        with db._lock, db._conn:
            db._conn.execute(
                "DELETE FROM adk_sessions WHERE app_name = ? AND user_id = ? AND session_id = ?",
                (app_name, user_id, session_id),
            )

    async def delete_user_sessions(self, user_id: str) -> None:
        db = self._active_db()
        with db._lock:
            rows = db._conn.execute(
                "SELECT app_name, session_id FROM adk_sessions WHERE user_id = ?", (user_id,)
            ).fetchall()
        for r in rows:
            await self._mem.delete_session(
                app_name=r["app_name"], user_id=user_id, session_id=r["session_id"]
            )
        with db._lock, db._conn:
            db._conn.execute("DELETE FROM adk_sessions WHERE user_id = ?", (user_id,))

    async def append_event(self, session: Session, event: Event) -> Event:
        saved = await self._mem.append_event(session=session, event=event)
        self._save_session(session)
        return saved
