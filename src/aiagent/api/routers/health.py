"""Health endpoints (docs/plan/29 section 3).

``GET /healthz`` - liveness probe (no DB, always 200 when process is up)
``GET /readyz``  - readiness probe (checks MongoDB; 503 when the DB is down)

The responses never expose credentials, URIs, or internal details.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from aiagent import __version__
from aiagent.api.envelope import error, ok
from aiagent.db.session import ping

router = APIRouter(tags=["health"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@router.get(
    "/healthz",
    summary="Liveness probe",
    description="Returns 200 when the process is alive (no DB dependency).",
)
async def healthz() -> dict:
    return ok(
        data={
            "status": "ok",
            "service": "aiagent",
            "version": __version__,
            "timestamp": _now_iso(),
        }
    )


@router.get(
    "/readyz",
    summary="Readiness probe",
    description="Returns 200 only when the database is reachable.",
    response_model=None,
)
async def readyz() -> JSONResponse:
    db_ok = await ping()
    if db_ok:
        return JSONResponse(
            status_code=200,
            content=ok(
                data={
                    "status": "ready",
                    "checks": {"database": "ok"},
                    "timestamp": _now_iso(),
                }
            ),
        )
    return JSONResponse(
        status_code=503,
        content=error(
            code="not_ready",
            message="service not ready",
            details={"checks": {"database": "unavailable"}},
        ),
    )
