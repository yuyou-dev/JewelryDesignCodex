"""Late-bound namespace shared with the jewelry image-2 runner entry point.

The runner historically lived in one flat module, and its tests monkeypatch
attributes (for example ``run_generation_job`` or ``codex_generate_command``)
on the loaded ``jewelry_image2_tool`` module. The entry point registers its
own globals here so internal call sites keep resolving through that same
namespace and the patches keep working after the package split.
"""

from __future__ import annotations

from typing import Any


TOOL_GLOBALS: dict[str, Any] = {}


def resolve(name: str, fallback: Any) -> Any:
    """Return the entry-point binding for name, falling back to the local one."""
    if TOOL_GLOBALS:
        resolved = TOOL_GLOBALS.get(name)
        if resolved is not None:
            return resolved
    return fallback
