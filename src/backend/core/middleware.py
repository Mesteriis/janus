from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .context import set_correlation_id, reset_correlation_id
from ..auth import auth_enabled, is_session_token_valid
from .. import settings

logger = logging.getLogger("backend.request")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, header_name: str = "X-Correlation-Id") -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get(self.header_name) or str(uuid.uuid4())
        token = set_correlation_id(correlation_id)
        request.state.correlation_id = correlation_id
        start = time.perf_counter()

        logger.info(
            "request.start",
            extra={
                "event": "request.start",
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
            },
        )

        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "request.error",
                extra={
                    "event": "request.error",
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error": str(exc),
                },
            )
            reset_correlation_id(token)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[self.header_name] = correlation_id
        logger.info(
            "request.end",
            extra={
                "event": "request.end",
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        reset_correlation_id(token)
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, header_name: str = "X-Auth-Token") -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next):
        if not auth_enabled():
            return await call_next(request)

        path = request.url.path
        if path == "/" or path.startswith("/static") or path.startswith("/api/auth") or path.startswith("/favicon"):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        token = request.cookies.get(settings.AUTH_COOKIE_NAME) or request.headers.get(self.header_name) or ""
        if is_session_token_valid(token):
            return await call_next(request)

        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
