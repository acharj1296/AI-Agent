"""Unit tests for the STEP 3 domain models and repository pagination helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aiagent.db.base import is_doc_id, validate_doc_id
from aiagent.db.constants import (
    TaskRunStatus,
    WorkflowRunStatus,
    WorkflowStatus,
)
from aiagent.db.models import TaskRun, Workflow, WorkflowRun


def test_task_run_defaults_and_enum() -> None:
    run = TaskRun(task_id="a" * 32, project_id="b" * 32)
    assert run.attempt == 1
    assert run.status == TaskRunStatus.CREATED
    assert run.started_at is None


def test_task_run_rejects_bad_attempt() -> None:
    with pytest.raises(ValidationError):
        TaskRun(task_id="a" * 32, project_id="b" * 32, attempt=0)


def test_task_run_rejects_non_doc_id_references() -> None:
    with pytest.raises(ValidationError):
        TaskRun(task_id="not-a-hex-id", project_id="b" * 32)
    with pytest.raises(ValidationError):
        TaskRun(task_id="a" * 32, project_id="short")


def test_task_run_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        TaskRun(task_id="a" * 32, project_id="b" * 32, status="hammering")


def test_workflow_defaults_and_enum() -> None:
    wf = Workflow(workflow_id="project_build", name="Project build")
    assert wf.version == 1
    assert wf.status == WorkflowStatus.DRAFT
    assert wf.entry is None
    assert wf.steps == []


def test_workflow_rejects_bad_version_and_id() -> None:
    with pytest.raises(ValidationError):
        Workflow(workflow_id="project_build", name="P", version=0)
    with pytest.raises(ValidationError):
        Workflow(workflow_id="", name="P")
    with pytest.raises(ValidationError):
        Workflow(workflow_id="project_build", name="P", status="bogus")


def test_workflow_run_defaults_to_created() -> None:
    run = WorkflowRun(project_id="a" * 32, workflow_id="project_build")
    assert run.status == WorkflowRunStatus.CREATED


def test_workflow_run_status_has_created() -> None:
    assert WorkflowRunStatus("created") is WorkflowRunStatus.CREATED


def test_task_run_status_values() -> None:
    assert TaskRunStatus("queued") is TaskRunStatus.QUEUED
    assert TaskRunStatus("succeeded") is TaskRunStatus.SUCCEEDED
    assert TaskRunStatus("timeout") is TaskRunStatus.TIMEOUT


def test_is_doc_id_shape_validation() -> None:
    assert is_doc_id("a" * 32) is True
    assert is_doc_id("A" * 32) is True
    assert is_doc_id("a" * 31) is False
    assert is_doc_id("a" * 32 + "!") is False
    assert is_doc_id("gg") is False
    assert is_doc_id(None) is False
    with pytest.raises(ValueError):
        validate_doc_id("nope", field="task_id")
