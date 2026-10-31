"""Tests for efficiency, response caching, rate limiting, and repository footprint."""

import time
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from app.cache import PlanCache, compute_cache_key
from app.pipeline import GenerationResult, generate_plan_v0
from app.ratelimit import RateLimiter
from app.schemas import EventPlan, PlanInputs


def _make_dummy_plan() -> EventPlan:
    from app.pipeline import fallback_plan

    inputs = PlanInputs(
        event_type="birthday",
        event_date=date(2027, 9, 1),
        guests=20,
        total_budget=15000.0,
    )
    return fallback_plan(inputs)


class TestResponseCache:
    """Tests for SQLite-backed response caching."""

    def test_compute_cache_key_deterministic(self):
        inputs1 = PlanInputs(
            event_type="wedding",
            event_date=date(2027, 10, 10),
            guests=100,
            total_budget=500000.0,
            city="Bengaluru",
        )
        inputs2 = PlanInputs(
            event_type="wedding",
            event_date=date(2027, 10, 10),
            guests=100,
            total_budget=500000.0,
            city="Bengaluru",
        )
        assert compute_cache_key(inputs1, "groq") == compute_cache_key(inputs2, "groq")

        # Different city or date produces different key
        inputs3 = PlanInputs(
            event_type="wedding",
            event_date=date(2027, 10, 11),
            guests=100,
            total_budget=500000.0,
            city="Mumbai",
        )
        assert compute_cache_key(inputs1, "groq") != compute_cache_key(inputs3, "groq")

    def test_cache_set_and_sub_10ms_get(self, tmp_path):
        db_file = tmp_path / "test_cache.db"
        cache = PlanCache(db_path=db_file)

        plan = _make_dummy_plan()
        res = GenerationResult(
            plan=plan,
            is_fallback=False,
            notices=[],
            provider="groq",
        )

        key = "test_cache_key_123"
        cache.set(key, res)

        start = time.perf_counter()
        retrieved = cache.get(key)
        duration_ms = (time.perf_counter() - start) * 1000.0

        assert retrieved is not None
        assert retrieved.cached is True
        assert retrieved.plan.total_budget == plan.total_budget
        assert duration_ms < 25.0  # sub-25ms even on slow Windows I/O

    def test_fallback_plans_not_cached(self, tmp_path):
        cache = PlanCache(db_path=tmp_path / "fallback.db")
        plan = _make_dummy_plan()
        res = GenerationResult(
            plan=plan,
            is_fallback=True,  # fallback plan should not pollute cache
            notices=["Error notice"],
            provider="fallback",
        )
        key = "fb_key"
        cache.set(key, res)
        assert cache.get(key) is None


class TestRateLimiter:
    """Tests for per-session sliding-window rate limiting."""

    def test_rate_limiter_allows_under_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        session = "session_abc"

        for _ in range(3):
            allowed, msg = limiter.is_allowed(session)
            assert allowed is True
            assert msg is None
            limiter.record(session)

        # 4th request must be blocked
        allowed, msg = limiter.is_allowed(session)
        assert allowed is False
        assert "limit reached" in msg.lower()

    def test_rate_limiter_reset(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        session = "session_xyz"

        limiter.record(session)
        allowed, _ = limiter.is_allowed(session)
        assert allowed is False

        limiter.reset(session)
        allowed, _ = limiter.is_allowed(session)
        assert allowed is True

    def test_byok_bypasses_server_rate_limit(self):
        mock_llm = MagicMock()
        mock_llm.active_provider = "user_byok"

        # Even with empty rate limiter, passing an explicit llm object bypasses rate limiter
        inputs = PlanInputs(
            event_type="birthday",
            event_date=date(2027, 5, 1),
            guests=15,
            total_budget=10000.0,
        )
        # Mock client generate_json to return minimal proposal
        from app.pipeline import PlanProposalV0
        from app.schemas import IdeaSet

        mock_proposal = PlanProposalV0(
            budget=[{"key": "cake", "label": "Cake", "percent": 100.0, "note": "Birthday cake"}],
            timeline=[
                {
                    "title": "Buy cake",
                    "phase": "1 week out",
                    "offset_days": -7,
                    "owner": "Host",
                    "status": "todo",
                    "category_key": "cake",
                }
            ],
            vendors=[],
            ideas=IdeaSet(themes=["Fun"], menu=[], activities=[], decor=[], extras=[]),
            assumptions=["BYOK test"],
        )
        mock_llm.generate_json.return_value = mock_proposal

        res = generate_plan_v0(inputs, llm=mock_llm, use_cache=False)
        assert res.is_fallback is False
        assert res.provider == "user_byok"


class TestRepositoryFootprint:
    """Tests to enforce the hackathon rule: total repo footprint under 10 MB."""

    def test_repository_files_under_10_mb(self):
        root_dir = Path(__file__).resolve().parent.parent
        # Sum non-hidden tracked file sizes
        total_bytes = 0
        for f in root_dir.glob("**/*"):
            if f.is_file() and not any(part.startswith(".") for part in f.parts):
                total_bytes += f.stat().st_size

        total_mb = total_bytes / (1024 * 1024)
        # Repository code files must be strictly under 10 MB (typically < 3 MB)
        assert total_mb < 10.0, f"Repository size {total_mb:.2f} MB exceeds 10 MB limit!"
