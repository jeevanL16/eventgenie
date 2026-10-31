"""Pytest global configuration and fixtures for EventGenie test suite."""

import pytest

from app.cache import default_cache
from app.ratelimit import default_rate_limiter


@pytest.fixture(autouse=True)
def reset_global_test_state():
    """Ensure clean cache and rate limit history before every test run."""
    default_cache.clear()
    default_rate_limiter.reset()
    yield
    default_cache.clear()
    default_rate_limiter.reset()
