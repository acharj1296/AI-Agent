"""Audit-log helper used by the service layer.

Every write that mutates a core entity goes through
:meth:`AuditLogger.record` so the ``audit_logs`` collection maintains
an immutable ``before`` / ``after`` history with a ``trace_id`` for
full request tracing.
"""

from __future__ import annotations

from typing import Any

from aiagent.db.base import BaseDocument
from aiagent.db.models import AuditLog
from aiagent.db.repositories import AuditLogRepository

_EXCLUDED_MANAGED_FIELDS = {"id", "created_at", "updated_at"}


def snapshot(document: BaseDocument) -> dict[str, Any]:
    """Serialize a model for audit ``before``/``after`` payloads.

    ``id`` and the managed timestamps are excluded (they are carried by the
    payload's own ``resource_id``), keeping the diff focused on domain state.
    """
    return document.model_dump(exclude_none=True, exclude=_EXCLUDED_MANAGED_FIELDS)


class AuditLogger:
    """Append-only audit trail writer backed by the ``audit_logs`` collection."""

    def __init__(self, repository: AuditLogRepository) -> None:
        self._repo = repository

    async def record(
        self,
        *,
        action: str,
        subject: str | None = None,
        project_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            subject=subject,
            project_id=project_id,
            resource_type=resource_type,
            resource_id=resource_id,
            before=before,
            after=after,
        )
        return await self._repo.create(entry)
