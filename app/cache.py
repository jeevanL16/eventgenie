"""Response caching for EventGenie.

Caches validated EventPlan generation results using SQLite with TTL support.
Keyed by SHA256 of canonical plan inputs and active model/provider.
"""

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from app.llm.base import LLMMetadata
from app.schemas import EventPlan, PlanInputs

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_CACHE_DB = DEFAULT_CACHE_DIR / "cache.db"
DEFAULT_TTL_SECONDS = 86400.0  # 24 hours


def compute_cache_key(inputs: PlanInputs, provider_or_model: str = "") -> str:
    """Generate a deterministic SHA-256 hash key from inputs and model identifier."""
    engine_val = provider_or_model.strip().lower() if isinstance(provider_or_model, str) else ""
    canonical = {
        "event_type": inputs.event_type,
        "event_date": inputs.event_date.isoformat(),
        "guests": inputs.guests,
        "total_budget": inputs.total_budget,
        "currency": inputs.currency.upper(),
        "city": inputs.city.strip().lower(),
        "lang": inputs.lang,
        "vibe": inputs.vibe.strip().lower(),
        "notes": inputs.notes.strip().lower(),
        "engine": engine_val,
    }
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class PlanCache:
    """Thread-safe SQLite-backed response cache for EventPlan results."""

    def __init__(self, db_path: Path | str = DEFAULT_CACHE_DB):
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS plan_cache (
                        cache_key TEXT PRIMARY KEY,
                        plan_json TEXT NOT NULL,
                        is_fallback INTEGER NOT NULL,
                        notices_json TEXT NOT NULL,
                        provider TEXT,
                        latency_ms REAL,
                        model TEXT,
                        prompt_tokens INTEGER,
                        completion_tokens INTEGER,
                        created_at REAL NOT NULL
                    )
                    """
                )
                conn.commit()
        except Exception as e:
            logger.warning("Failed to initialize SQLite cache table: %s", e)

    def get(self, cache_key: str, max_age_seconds: float = DEFAULT_TTL_SECONDS) -> Any | None:
        """Retrieve a cached GenerationResult if present and within max_age_seconds."""
        try:
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    SELECT plan_json, is_fallback, notices_json, provider, latency_ms,
                           model, prompt_tokens, completion_tokens, created_at
                    FROM plan_cache
                    WHERE cache_key = ?
                    """,
                    (cache_key,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                age = time.time() - float(row["created_at"])
                if age > max_age_seconds:
                    conn.execute("DELETE FROM plan_cache WHERE cache_key = ?", (cache_key,))
                    conn.commit()
                    return None

                from app.pipeline import GenerationResult

                plan_data = json.loads(row["plan_json"])
                plan = EventPlan.model_validate(plan_data)
                notices = json.loads(row["notices_json"])

                metadata = None
                if row["model"]:
                    metadata = LLMMetadata(
                        model=row["model"],
                        latency_ms=row["latency_ms"] or 0.0,
                        prompt_tokens=row["prompt_tokens"] or 0,
                        completion_tokens=row["completion_tokens"] or 0,
                        total_tokens=(row["prompt_tokens"] or 0) + (row["completion_tokens"] or 0),
                    )

                return GenerationResult(
                    plan=plan,
                    is_fallback=bool(row["is_fallback"]),
                    notices=notices,
                    metadata=metadata,
                    provider=row["provider"],
                    cached=True,
                )
        except Exception as e:
            logger.warning("Cache read failed for key %s: %s", cache_key, e)
            return None

    def set(self, cache_key: str, result: Any) -> None:
        """Store a GenerationResult in cache. Does not cache fallback error plans."""
        if getattr(result, "is_fallback", False):
            return  # Do not cache fallback benchmark plans

        try:
            plan = result.plan
            plan_json = plan.model_dump_json()
            notices_json = json.dumps(result.notices or [])
            meta = result.metadata

            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO plan_cache
                    (cache_key, plan_json, is_fallback, notices_json, provider,
                     latency_ms, model, prompt_tokens, completion_tokens, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cache_key,
                        plan_json,
                        int(result.is_fallback),
                        notices_json,
                        result.provider,
                        meta.latency_ms if meta else 0.0,
                        meta.model if meta else None,
                        meta.prompt_tokens if meta else 0,
                        meta.completion_tokens if meta else 0,
                        time.time(),
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.warning("Cache write failed for key %s: %s", cache_key, e)

    def clear(self) -> None:
        """Clear all entries from the cache table."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM plan_cache")
                conn.commit()
        except Exception as e:
            logger.warning("Cache clear failed: %s", e)


# Module-level shared singleton cache
default_cache = PlanCache()
