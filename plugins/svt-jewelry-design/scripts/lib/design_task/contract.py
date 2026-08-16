from __future__ import annotations

import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9._-]+$")
DOCUMENTS = ("proposal.md", "progress.md", "result.md", "handoff.md")
REQUIRED_SECTIONS = {
    "proposal.md": ("Goal", "Deliverables", "Design Direction", "Constraints"),
    "progress.md": ("Current", "Checklist", "Blocked", "Next"),
    "result.md": ("Summary", "Deliverables", "Missing"),
    "handoff.md": ("Current State", "Continue From", "Open Items", "Key Paths"),
}


def safe_task_id(value: object) -> str:
    task_id = str(value or "").strip()
    if not task_id or task_id in {".", ".."} or not SAFE_TASK_ID.fullmatch(task_id):
        raise ValueError("invalid task_id")
    return task_id


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean(value: object, fallback: str = "") -> str:
    text = " ".join(str(value or "").split()).strip()
    return text or fallback


class DesignTasksService:
    """Filesystem-only contract for the four task documents."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.tasks_root = self.root / "artifacts" / "design-tasks"
        self.media_root = self.root / "artifacts" / "runs"

    def safe_id(self, value: object) -> str:
        return safe_task_id(value)

    def _task_dir(self, task_id: str) -> Path:
        expected_root = self.root / "artifacts" / "design-tasks"
        if self.tasks_root.is_symlink() or self.tasks_root.resolve() != expected_root:
            raise ValueError("artifacts/design-tasks must be a repository-local directory")
        task_dir = self.tasks_root / safe_task_id(task_id)
        if task_dir.is_symlink():
            raise ValueError("design task directory must not be a symlink")
        if task_dir.resolve().parent != self.tasks_root.resolve():
            raise ValueError("design task directory escapes task root")
        return task_dir

    def list_design_tasks(self) -> list[dict[str, Any]]:
        if not self.tasks_root.exists():
            return []
        tasks: list[dict[str, Any]] = []
        for entry in self.tasks_root.iterdir():
            try:
                task = self.read_design_task(entry.name) if entry.is_dir() else None
            except (OSError, ValueError):
                task = None
            if task is not None:
                tasks.append(task)
        return sorted(tasks, key=lambda task: (float(task["updated_at"]), str(task["task_id"])), reverse=True)

    def read_design_task(self, task_id: str) -> dict[str, Any] | None:
        task_id = safe_task_id(task_id)
        task_dir = self._task_dir(task_id)
        if not task_dir.is_dir():
            return None
        if any(not (task_dir / name).is_file() or (task_dir / name).is_symlink() for name in DOCUMENTS):
            return None
        real_task_dir = task_dir.resolve()
        if any((task_dir / name).resolve().parent != real_task_dir for name in DOCUMENTS):
            return None
        if sorted(item.name for item in task_dir.iterdir()) != sorted(DOCUMENTS):
            return None
        documents = {
            name.removesuffix(".md"): (task_dir / name).read_text(encoding="utf-8", errors="replace")
            for name in DOCUMENTS
        }
        if any(not self._valid_sections(f"{name}.md", content) for name, content in documents.items()):
            return None
        updated_at = max((task_dir / name).stat().st_mtime for name in DOCUMENTS)
        return {
            "task_id": task_id,
            "title": self._title(documents["proposal"], task_id),
            "updated_at": updated_at,
            "documents": documents,
            "media_root": (self.media_root / task_id).relative_to(self.root).as_posix(),
        }

    def create_design_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("design task payload must be an object")
        task_id = safe_task_id(payload.get("task_id") or payload.get("id"))
        goal = _clean(payload.get("goal"), "Untitled jewelry design task")
        title = _clean(payload.get("title") or payload.get("name"), goal)[:120]
        task_dir = self._task_dir(task_id)
        if task_dir.exists():
            raise ValueError("design task already exists")
        self.tasks_root.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix=f".{task_id}.", dir=self.tasks_root))
        try:
            documents = self._initial_documents(task_id, title, goal, payload)
            for name in DOCUMENTS:
                self._atomic_write(temp_dir / name, documents[name])
            if sorted(item.name for item in temp_dir.iterdir()) != sorted(DOCUMENTS):
                raise RuntimeError("design task creation produced an invalid document set")
            os.replace(temp_dir, task_dir)
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        task = self.read_design_task(task_id)
        if task is None:
            shutil.rmtree(task_dir, ignore_errors=True)
            raise RuntimeError("design task could not be read after creation")
        return task

    def update_document(self, task_id: str, document: str, content: str) -> dict[str, Any]:
        task_id = safe_task_id(task_id)
        filename = f"{str(document).removesuffix('.md')}.md"
        if filename not in DOCUMENTS:
            raise ValueError("document must be proposal, progress, result, or handoff")
        task_dir = self._task_dir(task_id)
        if self.read_design_task(task_id) is None:
            raise FileNotFoundError(task_id)
        if not isinstance(content, str) or not content.strip():
            raise ValueError("document content is required")
        normalized = content.rstrip() + "\n"
        if not self._valid_sections(filename, normalized):
            raise ValueError(f"{filename} must contain only its fixed sections in order")
        self._atomic_write(task_dir / filename, normalized)
        task = self.read_design_task(task_id)
        if task is None:
            raise RuntimeError("updated design task no longer satisfies the four-document contract")
        return task

    def _initial_documents(self, task_id: str, title: str, goal: str, payload: dict[str, Any]) -> dict[str, str]:
        deliverables = _clean(payload.get("deliverables"), "- Confirm the requested deliverables with the designer.")
        direction = _clean(payload.get("design_direction"), "- To be developed from the active brief and references.")
        constraints = _clean(payload.get("constraints"), "- Keep work and uploads scoped to this task.")
        deliverables = deliverables if deliverables.startswith("-") else f"- {deliverables}"
        direction = direction if direction.startswith("-") else f"- {direction}"
        constraints = constraints if constraints.startswith("-") else f"- {constraints}"
        now = _utc_now()
        return {
            "proposal.md": f"# {title}\n\nTask: {task_id}\n\n## Goal\n\n{goal}\n\n## Deliverables\n\n{deliverables}\n\n## Design Direction\n\n{direction}\n\n## Constraints\n\n{constraints}\n",
            "progress.md": f"# Progress\n\nTask: {task_id}\nUpdated: {now}\n\n## Current\n\nWork has started.\n\n## Checklist\n\n- [ ] Confirm the proposal.\n- [ ] Produce the requested deliverables.\n- [ ] Present the actual results.\n\n## Blocked\n\n- None.\n\n## Next\n\n- Continue from the proposal.\n",
            "result.md": f"# Result\n\nTask: {task_id}\n\n## Summary\n\nNo result has been delivered yet.\n\n## Deliverables\n\n- Pending.\n\n## Missing\n\n- Requested deliverables are still in progress.\n",
            "handoff.md": f"# Handoff\n\nTask: {task_id}\nUpdated: {now}\n\n## Current State\n\nThe task has been created.\n\n## Continue From\n\n- Read proposal.md and progress.md.\n\n## Open Items\n\n- Complete the requested deliverables.\n\n## Key Paths\n\n- Task documents: artifacts/design-tasks/{task_id}/\n- Provider workspace: artifacts/runs/{task_id}/\n",
        }

    def _atomic_write(self, target: Path, content: str) -> None:
        temp = target.with_name(f".{target.name}.tmp")
        temp.write_text(content, encoding="utf-8")
        os.replace(temp, target)

    def _title(self, proposal: str, fallback: str) -> str:
        for line in proposal.splitlines():
            if line.startswith("# "):
                return line[2:].strip() or fallback
        return fallback

    def _valid_sections(self, filename: str, content: str) -> bool:
        headings = tuple(line[3:].strip() for line in content.splitlines() if line.startswith("## "))
        return headings == REQUIRED_SECTIONS[filename]
