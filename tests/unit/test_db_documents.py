"""Unit tests for the MongoDB document models and error translation."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError, OperationFailure

from aiagent.core.errors import ConflictError
from aiagent.db.base import utcnow
from aiagent.db.constants import (
    AgentRunStatus,
    ApprovalTier,
    ModelProvider,
    ProjectStage,
    ProjectStatus,
    TaskStatus,
)
from aiagent.db.models import (
    AgentRun,
    Approval,
    Model,
    Organization,
    Project,
    Task,
    User,
)
from aiagent.db.repositories import _duplicate_field, _translate

# ----------------------------------------------------------------------
# pymongo exception construction used by error-translation tests
# ----------------------------------------------------------------------


def _make_duplicate() -> DuplicateKeyError:
    return DuplicateKeyError(
        11000,
        "E11000 duplicate key error index: test.users.$uq_users_email",
        {"code": 11000, "keyPattern": {"email": 1}, "keyValue": {"email": "a@b.c"}},
    )


def test_translate_duplicate_maps_to_conflict() -> None:
    translated = _translate("users", _make_duplicate())
    assert isinstance(translated, ConflictError)
    assert translated.error_code == "conflict"
    assert translated.details["field"] == "email"
    assert translated.details["collection"] == "users"


def test_translate_duplicate_field_queries_key_pattern() -> None:
    assert _duplicate_field(_make_duplicate()) == "email"


def test_translate_operation_failure_maps_to_database_error() -> None:
    exc = OperationFailure("collection dropped", 47)
    translated = _translate("projects", exc)
    from aiagent.core.errors import DatabaseError

    assert isinstance(translated, DatabaseError)
    assert translated.error_code == "database_error"


def test_base_document_ids_and_timestamps() -> None:
    doc = Organization(name="Acme")
    assert len(doc.id) == 32
    assert isinstance(doc.created_at, datetime)
    assert isinstance(doc.updated_at, datetime)
    assert doc.collection == "organizations"


def test_to_doc_maps_id_to_mongo_id() -> None:
    doc = Organization(name="Acme")
    stored = doc.to_doc()
    assert stored["_id"] == doc.id
    assert "id" not in stored
    assert stored["name"] == "Acme"
    # nullable unset fields are omitted
    assert "budgets" not in stored


def test_from_doc_roundtrip() -> None:
    original = Organization(name="Acme", budgets={"monthly_eur": 1000})
    stored = original.to_doc()
    restored = Organization.from_doc(stored)
    assert restored.id == original.id
    assert restored.budgets == {"monthly_eur": 1000}
    assert restored.created_at == original.created_at


def test_enums_reject_invalid_values() -> None:
    with pytest.raises(ValidationError):
        Organization(name="A", autonomy_default=9)
    with pytest.raises(ValidationError):
        User(org_id="o1", name="Ada", email="ada@acme.example", role="superadmin")
    with pytest.raises(ValidationError):
        Project(org_id="o1", name="P", stage="not_a_stage")
    with pytest.raises(ValidationError):
        Project(org_id="o1", name="P", status="bogus")
    with pytest.raises(ValidationError):
        Task(project_id="p1", type="dev", title="T", status="wat")
    with pytest.raises(ValidationError):
        AgentRun(agent_id="a1", status="hammering")

    # valid enum values pass
    assert Project(org_id="o1", name="P").stage == ProjectStage.IDEA
    assert Project(org_id="o1", name="P").status == ProjectStatus.ACTIVE
    assert AgentRun(agent_id="a1").status == AgentRunStatus.CREATED
    assert Task(project_id="p1", type="dev", title="T").status == TaskStatus.CREATED


def test_email_shape_validated() -> None:
    with pytest.raises(ValidationError):
        User(org_id="o1", name="Ada", email="not-an-email")
    with pytest.raises(ValidationError):
        User(org_id="o1", name="Ada", email="@acme.example")
    user = User(org_id="o1", name="Ada", email="ADA@Acme.Example")
    assert user.email == "ada@acme.example"  # normalized to lowercase


def test_required_fields_and_defaults() -> None:
    agent = Model(model_id="gpt-4o-mini", provider=ModelProvider.OPENAI)
    assert agent.enabled is True
    assert agent.cost_per_1k is None

    approval = Approval(project_id="p1", tier=ApprovalTier.T3, title="deploy")
    assert approval.tier == ApprovalTier.T3
    assert approval.decision is None


def test_embedding_field_shape() -> None:
    from aiagent.db.models import Memory

    mem = Memory(kind="project", content="remember", project_id="p1", confidence=0.5)
    assert mem.embedding is None
    with pytest.raises(ValidationError):
        Memory(kind="project", content="c", confidence=1.5)


def test_utcnow_is_timezone_aware() -> None:
    assert utcnow().tzinfo is not None


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Organization(name="Acme", unexpected_field=1)
