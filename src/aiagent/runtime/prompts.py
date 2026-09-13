"""Instruction builder: system + user prompts with budgeted context (STEP 5).

Prompts are split into four layers so the runtime can assemble them independently
from agent definition changes (docs/plan/04 §4):

1. **Identity / system instructions** - loaded from the ``system_prompt_ref``
   file, per-agent, versioned by the prompt file itself.
2. **Runtime constraints** - safety/autonomy rules injected verbatim by the
   runtime (never come from the agent definition).
3. **User prompt** - project context + task context + the caller's raw input.
4. **Metadata** - correlation id, request id, used for observability only.

The raw input is sent as-is; ``input_context`` is a dict that gets pretty-
formatted into the user prompt so the model sees structured context without the
runtime interpreting it.
"""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from typing import Any, Protocol

from aiagent.core.errors import ConfigurationError
from aiagent.runtime.context import ExecutionContext

_SANITIZED_REF_RE = re.compile(r"^[a-zA-Z0-9._/-]+$")


class InstructionSource(Protocol):
    """Load prompt template files by agent reference id."""

    def system_instructions(self, ref: str | None) -> str | None: ...


class FileInstructionSource:
    """Load ``<root>/<ref>.md`` from disk (versioned by the file itself)."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def system_instructions(self, ref: str | None) -> str | None:
        if ref is None:
            return None
        if not _SANITIZED_REF_RE.fullmatch(ref):
            raise ConfigurationError(f"invalid instruction ref {ref!r} (path traversal?)")
        if ".." in ref:
            raise ConfigurationError(f"invalid instruction ref {ref!r} (path traversal?)")
        # Normalise: strip leading/trailing slashes, collapse multiples
        clean = ref.strip("/").replace("//", "/")
        path = (self._root / clean).with_suffix(".md")
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8").strip() or None

    def __repr__(self) -> str:
        return f"<FileInstructionSource root={self._root!r}>"


_CONSTRAINTS_TEMPLATE = textwrap.dedent("""\
    ## Runtime constraints (DO NOT edit)
    - Autonomy level: {autonomy_level}
    - Allowed tools: {allowed_tools}
    - No secrets or credentials are present in this prompt.
    """)


def _format_list(items: list[str]) -> str:
    if not items:
        return "(none)"
    return ", ".join(items)


def build_system_prompt(
    *,
    agent_identity: str,
    agent_description: str | None,
    system_instructions: str | None,
    context: ExecutionContext,
    allowed_tool_ids: list[str] | None = None,
) -> str:
    """Assemble the system prompt from agent identity + runtime constraints."""
    parts: list[str] = []
    parts.append(f"You are **{agent_identity}**.")
    if agent_description:
        parts.append(agent_description)
    if system_instructions:
        parts.append(system_instructions)
    parts.append(
        _CONSTRAINTS_TEMPLATE.format(
            autonomy_level=context.autonomy_level,
            allowed_tools=_format_list(allowed_tool_ids or []),
        )
    )
    return "\n\n".join(parts)


def build_user_prompt(
    *,
    context: ExecutionContext,
    project_summary: str | None = None,
    task_summary: str | None = None,
    inline_max_chars: int = 16000,
) -> str:
    """Assemble the user prompt with budgeted project/task context + input."""
    parts: list[str] = []
    if project_summary:
        parts.append(f"## Project context\n{project_summary[:inline_max_chars]}")
    if task_summary:
        parts.append(f"## Task\n{task_summary[:inline_max_chars]}")
    if context.relevant_context:
        ctx_preview = _format_dict_preview(context.relevant_context, inline_max_chars // 2)
        parts.append(f"## Context\n{ctx_preview}")
    parts.append(f"## Input\n{context.input}")
    return "\n\n".join(parts)


def _format_dict_preview(d: dict[str, Any], max_chars: int) -> str:
    """Best-effort pretty-format a dict, truncated to *max_chars*."""
    try:
        text = json.dumps(d, indent=2, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        text = str(d)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[...truncated]"
    return text
