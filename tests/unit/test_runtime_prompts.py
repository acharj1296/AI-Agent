"""Prompt/instruction assembly for the runtime (docs/plan/04 §4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aiagent.core.errors import ConfigurationError
from aiagent.runtime.context import ExecutionContext, ExecutionLimits
from aiagent.runtime.prompts import (
    FileInstructionSource,
    build_system_prompt,
    build_user_prompt,
)


@pytest.fixture
def prompt_dir(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    root.mkdir()
    (root / "engineer.md").write_text(
        "You write backend services.\n- Careful about typing.", encoding="utf-8"
    )
    return root


def _context(**kw):
    defaults = ExecutionLimits()
    data = {
        "agent_id": "a",
        "input": "please implement",
        "autonomy_level": 2,
    }
    data.update(kw)
    data.setdefault("limits", defaults)
    return ExecutionContext(**data)


def test_file_source_loads_ref(prompt_dir: Path) -> None:
    source = FileInstructionSource(prompt_dir)
    text = source.system_instructions("engineer")
    assert text is not None
    assert "backend services" in text


def test_file_source_returns_none_when_missing(prompt_dir: Path) -> None:
    source = FileInstructionSource(prompt_dir)
    assert source.system_instructions("missing") is None
    assert source.system_instructions(None) is None


def test_file_source_rejects_path_traversal(prompt_dir: Path) -> None:
    source = FileInstructionSource(prompt_dir)
    with pytest.raises(ConfigurationError):
        source.system_instructions("../secret")
    with pytest.raises(ConfigurationError):
        source.system_instructions("/../etc/passwd")


def test_build_system_prompt_layers() -> None:
    prompt = build_system_prompt(
        agent_identity="Backend Engineer",
        agent_description="Builds services.",
        system_instructions="You write backend services.",
        context=_context(),
        allowed_tool_ids=["fs.read"],
    )
    assert "Backend Engineer" in prompt
    assert "Builds services." in prompt
    assert "You write backend services." in prompt
    assert "Autonomy level: 2" in prompt
    assert "fs.read" in prompt


def test_build_user_prompt_layers() -> None:
    prompt = build_user_prompt(
        context=_context(),
        project_summary='{"id": "p1", "name": "Plat"}',
        task_summary='{"title": "Auth"}',
    )
    assert "## Project context" in prompt
    assert "## Task" in prompt
    assert "## Input" in prompt
    assert "please implement" in prompt
