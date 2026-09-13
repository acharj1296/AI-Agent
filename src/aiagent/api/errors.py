"""Exception handlers translating failures into the error envelope."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from aiagent.api.envelope import error
from aiagent.core.errors import AiAgentError
from aiagent.core.logging import get_logger

logger = get_logger("api.errors")


async def _aiagent_error_handler(request: Request, exc: AiAgentError) -> JSONResponse:
    message = exc.message or str(exc)
    if exc.status_code >= 500:
        logger.error(f"application error: {message}", extra={"code": exc.error_code})
    else:
        logger.debug(f"handled error: {message}", extra={"code": exc.error_code})
    return JSONResponse(
        status_code=exc.status_code,
        content=error(code=exc.error_code, message=message, details=exc.details),
    )


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "loc": list(err.get("loc", [])),
            "msg": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error(
            code="validation_error", message="request validation failed", details=details
        ),
    )


async def _pydantic_error_handler(request: Request, exc: PydanticValidationError) -> JSONResponse:
    """Map domain-level validation failures (e.g. invalid slug/version) to 422."""
    details = [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error(code="validation_error", message="agent definition invalid", details=details),
    )


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error(code="http_error", message=str(exc.detail)),
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled error",
        exc_info=exc,
        extra={"route": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content=error(code="internal_error", message="an unexpected error occurred"),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all handlers to the application.

    Order matters: the generic ``Exception`` handler must be registered last so
    FastAPI's priority logic routes matching exceptions correctly.
    """
    app.add_exception_handler(AiAgentError, _aiagent_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(PydanticValidationError, _pydantic_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_exception_handler)
