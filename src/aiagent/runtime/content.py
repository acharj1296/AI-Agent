"""Output/input content storage with inline previews (docs/plan/28 §2.5, STEP 5).

The runtime must not store huge raw prompts/responses in the Mongo
:class:`AgentRun` document.  The :class:`ContentStore` writes full content to
artifacts and returns a reference; callers embed only a bounded *preview* (plus
the reference URI) in the run row.  ``input`` is stored with the same policy so
a run is always reproducible without bloating the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

KIND_INPUT = "input"
KIND_OUTPUT = "output"


@dataclass(frozen=True)
class ContentRef:
    """Reference to possibly-large run content.

    * ``called`` uri (``file://``) when the content was externalized,
    * ``preview`` first ``max_preview_chars`` chars for quick display, always set,
    * ``truncated`` true when the full content exceeded the preview window.
    """

    uri: str | None
    preview: str
    truncated: bool


class ContentStore(Protocol):
    """:class:`Path`-backed store writing one file per (run, kind)."""

    def store(
        self, kind: str, run_id: str, content: str, *, max_preview_chars: int
    ) -> ContentRef: ...


class FileContentStore:
    """Persist run content under ``root/runs/<run_id>/<kind>.txt`` (file:// URIs)."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def store(self, kind: str, run_id: str, content: str, *, max_preview_chars: int) -> ContentRef:
        run_dir = self._root / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / f"{kind}.txt"
        path.write_text(content, encoding="utf-8")
        preview = content[:max_preview_chars] + (
            "" if len(content) <= max_preview_chars else "\n[...truncated]"
        )
        return ContentRef(
            uri=path.as_uri(), preview=preview, truncated=len(content) > max_preview_chars
        )

    def __repr__(self) -> str:
        return f"<FileContentStore root={self._root!r}>"


class MemoryContentStore:
    """In-memory content store for unit tests (never touches the filesystem)."""

    def __init__(self) -> None:
        self._blobs: dict[tuple[str, str], str] = {}

    def store(self, kind: str, run_id: str, content: str, *, max_preview_chars: int) -> ContentRef:
        self._blobs[(kind, run_id)] = content
        truncated = len(content) > max_preview_chars
        preview = content[:max_preview_chars] + ("\n[...truncated]" if truncated else "")
        return ContentRef(uri=f"memory://{run_id}/{kind}", preview=preview, truncated=truncated)


def preview_text(content: str, max_preview_chars: int) -> tuple[str, bool]:
    """Return ``(preview, truncated)`` for *content* (shared by the service)."""
    truncated = len(content) > max_preview_chars
    if truncated:
        return content[:max_preview_chars] + "\n[...truncated]", True
    return content, False
