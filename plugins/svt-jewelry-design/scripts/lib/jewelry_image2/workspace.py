from __future__ import annotations

from pathlib import Path
from typing import Callable


def prepare_codex_home(
    workspace: Path,
    ensure_workspace: Callable[[Path], None],
    *,
    source_home: Path,
) -> Path:
    """Return the user's existing Codex home without copying identity or configuration files."""
    ensure_workspace(workspace)
    return source_home.expanduser().resolve()


def prepare_worker_codex_home(base_codex_home: Path, job_id: str, safe_id: Callable[[str], str]) -> Path:
    """Workers share the authenticated Codex home; no credential-bearing worker copy is created."""
    del job_id, safe_id
    return base_codex_home
