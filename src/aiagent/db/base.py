"""Pydantic base for MongoDB document models.

Repositories map the domain ``id`` field to the stored ``_id`` field so model
code always works with ``id`` while stored documents use ``_id`` (see
:meth:`BaseDocument.to_doc` / :meth:`BaseDocument.from_doc`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T", bound="BaseDocument")


def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


class BaseDocument(BaseModel):
    """Shared id + timestamp fields for every collection.

    ``collection`` is a ``ClassVar`` so the repository layer can map a model
    class to its MongoDB collection name without an extra registration step.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True, populate_by_name=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    collection: ClassVar[str]

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def to_doc(self) -> dict[str, Any]:
        """Convert the model to a dict suitable for ``insert_one`` / ``replace_one``.

        ``exclude_none`` removes nullable fields that are unset, keeping
        documents lean.  Datetime objects are stored as native BSON dates.
        """
        doc = self.model_dump(exclude_none=True)
        doc["_id"] = doc.pop("id")
        return doc

    @classmethod
    def from_doc(cls: type[T], doc: dict[str, Any]) -> T:
        """Reconstruct a document model from a raw MongoDB document."""
        data: dict[str, Any] = dict(doc)
        if "_id" in data:
            data["id"] = str(data.pop("_id"))
        return cls.model_validate(data)
