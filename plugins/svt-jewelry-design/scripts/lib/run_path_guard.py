"""Active jewelry production run path guards.

Guarded mode is opt-in through ``--active-task-id`` or ``SVT_ACTIVE_TASK_ID``.
When no active id is present, legacy CLI behavior is preserved.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class TaskPathGuardError(ValueError):
    pass


def active_task_id_from_args(args: object | None = None) -> str:
    explicit = ""
    if args is not None:
        explicit = str(getattr(args, "active_task_id", "") or "")
    return (explicit or os.environ.get("SVT_ACTIVE_TASK_ID") or "").strip()


def assert_valid_task_id(task_id: str) -> None:
    if not task_id or task_id in {".", ".."} or not TASK_ID_RE.fullmatch(task_id):
        raise TaskPathGuardError("Active task id must use only letters, numbers, dot, underscore, or hyphen.")


def _nearest_existing_parent(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def canonical_for_write(path: Path | str) -> Path:
    absolute = Path(path).expanduser().resolve(strict=False)
    if absolute.exists():
        return absolute.resolve(strict=True)
    parent = _nearest_existing_parent(absolute.parent)
    remaining = absolute.relative_to(parent)
    real_parent = parent.resolve(strict=True) if parent.exists() else parent.resolve(strict=False)
    return (real_parent / remaining).resolve(strict=False)


def canonical_for_read(path: Path | str) -> Path:
    absolute = Path(path).expanduser().resolve(strict=False)
    if not absolute.exists():
        raise TaskPathGuardError(f"Current-task read path does not exist: {absolute}")
    return absolute.resolve(strict=True)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def current_task_roots(task_id: str, repo_root: Path | str | None = None) -> list[Path]:
    assert_valid_task_id(task_id)
    root = Path(repo_root or Path.cwd()).resolve(strict=True)
    media_root = root / "artifacts" / "runs"
    artifacts_root = media_root.parent
    if artifacts_root.exists() and artifacts_root.is_symlink():
        raise TaskPathGuardError("artifacts must be repository-local")
    media_root.mkdir(parents=True, exist_ok=True)
    if media_root.is_symlink() or media_root.resolve(strict=True) != root / "artifacts" / "runs":
        raise TaskPathGuardError("artifacts/runs must be a repository-local directory")
    task_root = media_root / task_id
    if task_root.is_symlink():
        raise TaskPathGuardError("task media workspace must not be a symlink")
    resolved = canonical_for_write(task_root)
    if resolved.parent != media_root:
        raise TaskPathGuardError("task media workspace escapes artifacts/runs")
    return [resolved]


def assert_current_task_write_path(
    path: Path | str,
    task_id: str,
    label: str = "Path",
    repo_root: Path | str | None = None,
) -> Path:
    if not task_id:
        return Path(path).expanduser().resolve(strict=False)
    candidate = canonical_for_write(path)
    roots = current_task_roots(task_id, repo_root)
    if not any(_is_relative_to(candidate, root) for root in roots):
        raise TaskPathGuardError(
            f"{label} must stay inside the active task media workspace ({task_id}): {Path(path).expanduser().resolve(strict=False)}"
        )
    return candidate


def assert_current_task_read_path(
    path: Path | str,
    task_id: str,
    label: str = "Path",
    repo_root: Path | str | None = None,
) -> Path:
    if not task_id:
        return Path(path).expanduser().resolve(strict=False)
    candidate = canonical_for_read(path)
    roots = current_task_roots(task_id, repo_root)
    if not any(_is_relative_to(candidate, root) for root in roots):
        raise TaskPathGuardError(
            f"{label} must stay inside the active task media workspace ({task_id}): {Path(path).expanduser().resolve(strict=False)}"
        )
    return candidate
