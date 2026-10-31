"""Per-session rate limiting for EventGenie.

Protects free-tier API quotas on public deployments by restricting rapid requests.
Configurable via environment variables RATE_LIMIT_MAX_REQUESTS and RATE_LIMIT_WINDOW_SECONDS.
"""

import os
import threading
import time
from collections import defaultdict


class RateLimiter:
    """Thread-safe sliding-window rate limiter per session identifier."""

    def __init__(
        self,
        max_requests: int | None = None,
        window_seconds: float | None = None,
    ):
        env_max = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "10"))
        env_window = float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "3600.0"))

        self.max_requests = max_requests if max_requests is not None else env_max
        self.window_seconds = window_seconds if window_seconds is not None else env_window
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _prune(self, session_id: str, now: float) -> None:
        """Remove timestamps outside the current sliding window."""
        cutoff = now - self.window_seconds
        self._history[session_id] = [t for t in self._history[session_id] if t > cutoff]

    def is_allowed(self, session_id: str = "default") -> tuple[bool, str | None]:
        """Check if session is permitted to make another request.

        Returns:
            (True, None) if permitted.
            (False, friendly_message) if limit has been reached.
        """
        now = time.time()
        with self._lock:
            self._prune(session_id, now)
            count = len(self._history[session_id])

            if count >= self.max_requests:
                msg = (
                    f"Notice: Generation limit reached ({self.max_requests} plans / "
                    f"{int(self.window_seconds // 60)} min). To continue exploring, "
                    "please wait a few minutes or enter your free API key in the sidebar."
                )
                return False, msg

            return True, None

    def record(self, session_id: str = "default") -> None:
        """Record an executed request timestamp for the session."""
        now = time.time()
        with self._lock:
            self._prune(session_id, now)
            self._history[session_id].append(now)

    def get_remaining(self, session_id: str = "default") -> int:
        """Get remaining allowed requests in current window."""
        now = time.time()
        with self._lock:
            self._prune(session_id, now)
            return max(0, self.max_requests - len(self._history[session_id]))

    def reset(self, session_id: str | None = None) -> None:
        """Clear rate limit history for a specific session or all sessions."""
        with self._lock:
            if session_id:
                self._history.pop(session_id, None)
            else:
                self._history.clear()


# Module-level shared rate limiter instance
default_rate_limiter = RateLimiter()
