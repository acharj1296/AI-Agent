"""FastAPI application factory and module-level ``app`` instance.

Use ``uvicorn aiagent.api.app:app`` to start the server. For tests, call
``create_app(settings)`` to inject a test configuration.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from aiagent import __version__
from aiagent.api.envelope import ok
from aiagent.api.errors import register_exception_handlers
from aiagent.api.routers.agents import router as agents_router
from aiagent.api.routers.health import router as health_router
from aiagent.api.routers.runtime import router as runtime_router
from aiagent.core.config import Settings, load_settings
from aiagent.core.context import clear_request_context, get_request_context, set_request_context
from aiagent.core.errors import AiAgentError
from aiagent.core.logging import get_logger, setup_logging
from aiagent.db.session import close_db, init_db


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the FastAPI application.

    When *settings* is ``None`` the process-wide cached settings are loaded via
    the YAML config merge chain (see :mod:`aiagent.core.config`).
    """
    resolved = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        setup_logging(level=resolved.app.log_level, json=not resolved.app.debug)
        logger = get_logger("api")
        try:
            await init_db(resolved)
        except AiAgentError:
            logger.critical(
                "startup failed: database unavailable",
                extra={"env": resolved.app.env, "version": __version__},
            )
            raise
        logger.info(
            "application started",
            extra={"env": resolved.app.env, "version": __version__},
        )
        yield
        logger.info("application stopped")
        await close_db()

    docs_url = "/docs" if resolved.app.env != "prod" else None
    openapi_url = "/openapi.json" if resolved.app.env != "prod" else None

    app = FastAPI(
        title="AI-Agent Control Plane",
        version=__version__,
        lifespan=lifespan,
        docs_url=docs_url,
        openapi_url=openapi_url,
        redoc_url=None,
    )

    register_exception_handlers(app)

    @app.middleware("http")
    async def _request_context_middleware(request: Request, call_next) -> JSONResponse:
        # Honour incoming correlation ids when provided by a caller
        set_request_context(
            request_id=request.headers.get("X-Request-ID"),
            trace_id=request.headers.get("X-Trace-ID"),
        )

        access_logger = get_logger("api.access")
        start = time.monotonic()
        response = None
        try:
            response = await call_next(request)
        except Exception:
            access_logger.exception("request failed during processing")
            raise
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            current_rid, current_tid = get_request_context()
            status_code = getattr(response, "status_code", 0) if response is not None else 0
            access_logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status_code,
                    "elapsed_ms": round(elapsed_ms, 1),
                },
            )
            clear_request_context()

        response.headers["X-Request-ID"] = current_rid
        response.headers["X-Trace-ID"] = current_tid
        return response

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return ok(
            data={
                "service": "aiagent",
                "version": __version__,
                "env": resolved.app.env,
                "docs": docs_url,
            }
        )

    app.include_router(health_router)
    app.include_router(agents_router)
    app.include_router(runtime_router)

    return app


app = create_app()
