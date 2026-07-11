"""
Minimal in-memory sliding-window rate limiter, keyed by client IP.

This is intentionally simple (no Redis dependency) since the app is
stateless/session-less and single-instance for the hackathon deployment
target (Render free tier). For multi-instance production use, swap the
in-memory store for Redis.
"""
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rejects requests once a client exceeds N requests/minute."""

    def __init__(self, app):
        super().__init__(app)
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._window_seconds = 60

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        limit = settings.rate_limit_per_minute

        # Only rate-limit API routes; let health checks and static pass through.
        if request.url.path.startswith("/api/"):
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            hits = self._hits[client_ip]

            while hits and now - hits[0] > self._window_seconds:
                hits.popleft()

            if len(hits) >= limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limited",
                        "detail": f"Too many requests. Limit is {limit} per minute.",
                    },
                )
            hits.append(now)

        return await call_next(request)
