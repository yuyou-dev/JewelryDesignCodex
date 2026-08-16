from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

from .contract import DOCUMENTS, safe_task_id


_ZIP_DATE_TIME = (2020, 1, 1, 0, 0, 0)


def _is_private_worker_runtime(parts: tuple[str, ...]) -> bool:
    return any(part.startswith(".codex-home") for part in parts)


def _roots(root: Path, task_id: str) -> tuple[Path, Path, Path]:
    root = root.resolve()
    task_id = safe_task_id(task_id)
    tasks_root = root / "artifacts" / "design-tasks"
    media_root = root / "artifacts" / "runs"
    if tasks_root.is_symlink() or tasks_root.resolve() != root / "artifacts" / "design-tasks":
        raise ValueError("artifacts/design-tasks must be a repository-local directory")
    if media_root.is_symlink() or media_root.resolve() != root / "artifacts" / "runs":
        raise ValueError("artifacts/runs must be a repository-local directory")
    task_root = tasks_root / task_id
    task_media = media_root / task_id
    if task_root.is_symlink() or task_root.resolve().parent != tasks_root.resolve():
        raise ValueError("design task directory escapes task root")
    if task_media.is_symlink() or task_media.resolve().parent != media_root.resolve():
        raise ValueError("task media workspace escapes artifacts/runs")
    return task_root, task_media, media_root


def build_task_zip(root: Path, task_id: str) -> bytes:
    task_root, task_media, _ = _roots(root, task_id)
    if not task_root.is_dir() or any(not (task_root / name).is_file() or (task_root / name).is_symlink() for name in DOCUMENTS):
        raise FileNotFoundError(task_id)
    if any((task_root / name).resolve().parent != task_root.resolve() for name in DOCUMENTS):
        raise ValueError("design task documents must be regular task-local files")
    if sorted(item.name for item in task_root.iterdir()) != sorted(DOCUMENTS):
        raise ValueError("design task directory must contain exactly four Markdown documents")

    entries: list[tuple[str, bytes]] = [(name, (task_root / name).read_bytes()) for name in DOCUMENTS]
    if task_media.is_dir():
        for path in sorted(task_media.rglob("*"), key=lambda item: item.relative_to(task_media).as_posix()):
            relative = path.relative_to(task_media).as_posix()
            if (
                relative.startswith("export/")
                or _is_private_worker_runtime(path.relative_to(task_media).parts)
                or path.is_symlink()
                or not path.is_file()
            ):
                continue
            resolved = path.resolve()
            if task_media.resolve() not in resolved.parents:
                continue
            entries.append((f"media/{relative}", resolved.read_bytes()))

    entries.sort(key=lambda item: item[0])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            info = zipfile.ZipInfo(filename=name, date_time=_ZIP_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return buffer.getvalue()


def export_task_zip(root: Path, task_id: str) -> Path:
    root = root.resolve()
    task_id = safe_task_id(task_id)
    data = build_task_zip(root, task_id)
    destination = root / "artifacts" / "runs" / task_id / "export" / f"design-task-{task_id}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination


def zip_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
