"""Content storage helpers for the runtime (docs/plan/28 §2.5)."""

from __future__ import annotations

from aiagent.runtime.content import (
    KIND_INPUT,
    MemoryContentStore,
    preview_text,
)


def test_memory_store_small_content_inline() -> None:
    store = MemoryContentStore()
    ref = store.store(KIND_INPUT, "run1", "short", max_preview_chars=4000)
    assert ref.uri == "memory://run1/input"
    assert ref.preview == "short"
    assert ref.truncated is False


def test_memory_store_large_content_truncated() -> None:
    store = MemoryContentStore()
    blob = "Z" * 100
    ref = store.store(KIND_INPUT, "run2", blob, max_preview_chars=10)
    assert ref.truncated is True
    assert ref.preview.startswith("Z" * 10)
    assert ref.preview.endswith("[...truncated]")


def test_preview_text_helpers() -> None:
    short, t_short = preview_text("abc", 5)
    assert short == "abc" and t_short is False

    long, t_long = preview_text("a" * 20, 5)
    assert t_long is True
    assert long.startswith("a" * 5)
    assert long.endswith("[...truncated]")
