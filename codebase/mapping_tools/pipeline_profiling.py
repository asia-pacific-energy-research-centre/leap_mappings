#%%
"""Lightweight shared hooks for nested mapping-pipeline resource profiling."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


_ACTIVE_PROFILER: Any | None = None


def set_pipeline_profiler(profiler: Any | None) -> None:
    """Register the active profiler without coupling helpers to the runner."""
    global _ACTIVE_PROFILER
    _ACTIVE_PROFILER = profiler


@contextmanager
def profile_pipeline_section(section_name: str) -> Iterator[None]:
    """Measure a nested section when a pipeline profiler is active."""
    if _ACTIVE_PROFILER is None:
        yield
        return
    with _ACTIVE_PROFILER.measure(section_name):
        yield


#%%
