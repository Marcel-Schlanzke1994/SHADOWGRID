from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import jwt
import structlog
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import RequestResponseEndpoint

from shadowgrid.api import router
from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.models import RefreshSession, User
from shadowgrid.security import decode_access_token

settings = get_settings()
WEB_DIST = (settings.web_dist_path or Path(__file__).resolve().parents[1] / "web-dist").resolve()
logging.basicConfig(level=settings.log_level, format="%(message)s")
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

REQUESTS = Counter("shadowgrid_http_requests_total", "HTTP requests", ["method", "route", "status"])
DURATION = Histogram(
    "shadowgrid_http_request_seconds", "HTTP request duration", ["method", "route"]
)

app = FastAPI(
    title="SHADOWGRID API",
    version="0.1.0",
    description="Server-authoritative API for a fictional seasonal strategy MMO.",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.web_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-World-Id",
        "X-Client-Kind",
    ],
)


@app.middleware("http")
async def security_and_observability(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    request_id = request.headers.get("x-request-id", str(uuid4()))[:60]
    request.state.request_id = request_id
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 1_048_576:
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "request.too_large",
                    "message": "Request body exceeds 1 MiB",
                    "request_id": request_id,
                },
                "server_time": datetime.now(UTC).isoformat(),
            },
        )
    started = time.perf_counter()
    response = await call_next(request)
    route = getattr(request.scope.get("route"), "path", request.url.path)
    elapsed = time.perf_counter() - started
    REQUESTS.labels(request.method, route, response.status_code).inc()
    DURATION.labels(request.method, route).observe(elapsed)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Server-Time"] = datetime.now(UTC).isoformat()
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if WEB_DIST.is_dir() and not request.url.path.startswith(settings.api_prefix):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self' ws: wss:; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self'; font-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
    logger.info(
        "http_request",
        request_id=request_id,
        method=request.method,
        route=route,
        status=response.status_code,
        duration_ms=round(elapsed * 1000, 2),
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail: dict[str, Any] = (
        exc.detail
        if isinstance(exc.detail, dict)
        else {"code": "request.error", "message": str(exc.detail)}
    )
    detail["request_id"] = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": detail, "server_time": datetime.now(UTC).isoformat()},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    fields = {".".join(str(part) for part in error["loc"]): error["msg"] for error in exc.errors()}
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "request.validation",
                "message": "Request validation failed",
                "request_id": getattr(request.state, "request_id", None),
                "fields": fields,
            },
            "server_time": datetime.now(UTC).isoformat(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_error",
        request_id=getattr(request.state, "request_id", None),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "server.unexpected",
                "message": "An unexpected server error occurred",
                "request_id": getattr(request.state, "request_id", None),
            },
            "server_time": datetime.now(UTC).isoformat(),
        },
    )


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(router, prefix=settings.api_prefix)


@app.websocket(f"{settings.api_prefix}/ws")
async def websocket_updates(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), timeout=8)
        message = json.loads(first)
        token = str(message.get("access_token", ""))
        payload = decode_access_token(token, settings)
        db = SessionLocal()
        try:
            user = db.get(User, payload.get("sub"))
            session = db.get(RefreshSession, payload.get("sid"))
            if user is None or session is None or session.revoked_at is not None:
                await websocket.close(code=4401)
                return
        finally:
            db.close()
        event_id = str(uuid4())
        await websocket.send_json(
            {
                "event_id": event_id,
                "type": "connected",
                "server_time": datetime.now(UTC).isoformat(),
            }
        )
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                incoming = json.loads(raw)
                if incoming.get("type") == "ping":
                    await websocket.send_json(
                        {
                            "event_id": str(uuid4()),
                            "type": "pong",
                            "server_time": datetime.now(UTC).isoformat(),
                        }
                    )
            except TimeoutError:
                await websocket.send_json(
                    {
                        "event_id": str(uuid4()),
                        "type": "heartbeat",
                        "server_time": datetime.now(UTC).isoformat(),
                    }
                )
    except (WebSocketDisconnect, json.JSONDecodeError, jwt.PyJWTError, TimeoutError):
        if websocket.client_state.name != "DISCONNECTED":
            await websocket.close(code=4401)


if WEB_DIST.is_dir():

    @app.get("/", include_in_schema=False)
    def web_index() -> FileResponse:
        return FileResponse(WEB_DIST / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/{spa_path:path}", include_in_schema=False)
    def web_spa(spa_path: str) -> FileResponse:
        candidate = (WEB_DIST / spa_path).resolve()
        if candidate.is_relative_to(WEB_DIST) and candidate.is_file():
            cache_control = (
                "public, max-age=31536000, immutable"
                if spa_path.startswith("assets/")
                else "no-cache"
            )
            return FileResponse(candidate, headers={"Cache-Control": cache_control})
        return FileResponse(WEB_DIST / "index.html", headers={"Cache-Control": "no-cache"})
