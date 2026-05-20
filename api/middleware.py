import time
import uuid
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .database import AsyncSessionLocal
from .models import ActivityLog

logger = logging.getLogger("medorders.activity")

# Paths that are too noisy to log (health checks, docs)
_SKIP_PATHS = {"/v1/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}


class ActivityLoggingMiddleware(BaseHTTPMiddleware):
    """Persists a log entry for every meaningful API request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        path = request.url.path
        if path in _SKIP_PATHS or path.startswith("/static"):
            return response

        try:
            async with AsyncSessionLocal() as session:
                log = ActivityLog(
                    id=str(uuid.uuid4()),
                    action=f"{request.method} {path}",
                    request_path=path,
                    request_method=request.method,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    ip_address=(
                        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                        or (request.client.host if request.client else None)
                    ),
                    user_agent=request.headers.get("user-agent"),
                )
                session.add(log)
                await session.commit()
        except Exception as exc:
            # Never fail the request because logging failed
            logger.warning("Activity log write failed: %s", exc)

        return response
