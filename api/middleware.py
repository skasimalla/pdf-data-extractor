from __future__ import annotations

import asyncio
import time
import uuid
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .database import AsyncSessionLocal, _ensure_db
from .models import ActivityLog

logger = logging.getLogger("medorders.activity")

# Paths that are too noisy to log (health checks, docs)
_SKIP_PATHS = {"/v1/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}


async def _persist_log(
    action: str,
    path: str,
    method: str,
    status_code: int,
    duration_ms: float,
    ip: str | None,
    user_agent: str | None,
) -> None:
    """Write one activity log row. Runs as a fire-and-forget background task
    so it never blocks the HTTP response and runs after the route handler's
    DB session is fully closed (avoiding SQLite write-lock conflicts)."""
    # Yield to the event loop once so any pending session.close() calls in
    # the route handler's get_db() dependency can complete first.
    await asyncio.sleep(0)
    try:
        await _ensure_db()
        async with AsyncSessionLocal() as session:
            session.add(ActivityLog(
                id=str(uuid.uuid4()),
                action=action,
                request_path=path,
                request_method=method,
                status_code=status_code,
                duration_ms=duration_ms,
                ip_address=ip,
                user_agent=user_agent,
            ))
            await session.commit()
    except Exception as exc:
        logger.warning("Activity log write failed: %s", exc)


class ActivityLoggingMiddleware(BaseHTTPMiddleware):
    """Persists a log entry for every meaningful API request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        path = request.url.path
        if path not in _SKIP_PATHS and not path.startswith("/static"):
            ip = (
                request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                or (request.client.host if request.client else None)
            )
            asyncio.ensure_future(_persist_log(
                action=f"{request.method} {path}",
                path=path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms,
                ip=ip,
                user_agent=request.headers.get("user-agent"),
            ))

        return response
