"""Security middleware: correlation IDs, HTTP security headers, secret redaction, rate limiting."""
from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

SENSITIVE_KEYS = {
    "password",
    "secret",
    "token",
    "authorization",
    "razorpay_key_secret",
    "razorpay_webhook_secret",
    "clerk_secret",
    "card_number",
    "cvv",
    "upi_pin",
    "pin",
    "api_key",
}


def redact_sensitive(data: Any) -> Any:
    """Recursively mask any sensitive key before storing in logs or audit snapshots."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            low = str(k).lower()
            if any(bad in low for bad in SENSITIVE_KEYS):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = redact_sensitive(v)
        return cleaned
    if isinstance(data, list):
        return [redact_sensitive(x) for x in data]
    return data


class CorrelationAndHeadersMiddleware(BaseHTTPMiddleware):
    """Attach X-Correlation-ID and defensive HTTP security headers to every response."""

    def __init__(self, app, *, allow_dev_iframe: bool = False, is_production: bool = False) -> None:
        super().__init__(app)
        self.allow_dev_iframe = allow_dev_iframe
        self.is_production = is_production

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if not self.allow_dev_iframe:
            response.headers["X-Frame-Options"] = "DENY"
        frame_ancestors = "'self'" if self.allow_dev_iframe else "'none'"
        response.headers["Content-Security-Policy"] = (
            f"default-src 'none'; frame-ancestors {frame_ancestors}; base-uri 'none'; form-action 'none'"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Cache-Control"] = "no-store"
        if self.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding-window rate limiter (use Redis in multi-worker prod)."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                retry_after = max(1, int(bucket[0] + self.window_seconds - now))
                return False, retry_after
            bucket.append(now)
            return True, 0
