from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

from lib.jewelry_image2.common import (
    IMAGE_SUFFIXES,
    file_hash,
    guard_read_path,
    image_header_metadata,
    is_relative_to,
    now_iso,
    read_json,
    rel_to_workspace,
    safe_id,
    step_echo,
)
from lib.jewelry_image2.jobs import (
    load_jobs,
    workspace_file,
)


def write_preview_html(workspace: Path) -> Path:
    preview = workspace / "preview.html"
    html = """<!doctype html><meta charset=\"utf-8\"><meta http-equiv=\"refresh\" content=\"5\"><title>Design preview</title>
<style>body{font:14px system-ui;margin:24px}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}figure{margin:0}img{width:100%;height:220px;object-fit:contain;background:#f4f4f4}figcaption{overflow-wrap:anywhere}</style><h1>Design preview</h1><main>__ITEMS__</main>"""
    items = []
    try:
        preview_jobs = load_jobs(workspace).get("jobs", [])
    except json.JSONDecodeError:
        preview_jobs = []
    for job in preview_jobs:
        output = str(job.get("output") or "")
        path = workspace_file(workspace, output) if output else workspace
        if path.is_file() and is_relative_to(path, workspace) and path.suffix.lower() in IMAGE_SUFFIXES:
            safe_output = output.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
            safe_id_text = str(job.get("id") or "").replace("&", "&amp;").replace("<", "&lt;")
            items.append(f'<figure><img loading="lazy" src="{safe_output}"><figcaption>{safe_id_text}</figcaption></figure>')
    preview.write_text(html.replace("__ITEMS__", "".join(items)), encoding="utf-8")
    return preview


def progress_line(workspace: Path, result: dict[str, Any], completed: int, total: int, *, requeued: bool = False, event_command: str = "") -> None:
    job_id = str(result.get("id") or "job")
    event = {
        "schema_version": 1,
        "event": "image_job_completed",
        "emitted_at": now_iso(),
        "job_id": job_id,
        "status": str(result.get("status") or "failed"),
        "output": str(result.get("output") or f"outputs/{safe_id(job_id)}.png"),
        "prompt": str(result.get("prompt") or f"prompts/{safe_id(job_id)}.prompt.txt"),
        "prompt_sha256": result.get("prompt_sha256"),
        "output_sha256": result.get("output_sha256"),
        "job_record": f"jobs/{safe_id(job_id)}.json",
        "requeue": bool(requeued),
        "failure_class": result.get("failure_class"),
    }
    if event["status"] == "done":
        output_path = workspace_file(workspace, event["output"])
        metadata = image_header_metadata(output_path)
        event.update({
            "media_type": "image",
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "size_bytes": output_path.stat().st_size if output_path.is_file() else 0,
            "output_sha256": event.get("output_sha256") or (file_hash(output_path) if output_path.is_file() else None),
        })
    event_path = workspace / "logs" / "image-job-events.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    if event_command:
        try:
            hook = subprocess.run(
                shlex.split(event_command), input=json.dumps(event, ensure_ascii=False), text=True,
                cwd=workspace, capture_output=True, check=False, timeout=30,
            )
            hook_warning = None if hook.returncode == 0 else {
                "returncode": hook.returncode, "stderr": (hook.stderr or "")[-2000:], "failure_class": "nonzero_exit"
            }
        except subprocess.TimeoutExpired as error:
            hook_warning = {"returncode": None, "stderr": str(error)[-2000:], "failure_class": "timeout"}
        except (OSError, subprocess.SubprocessError) as error:
            hook_warning = {"returncode": None, "stderr": str(error)[-2000:], "failure_class": "launch_or_subprocess_error"}
        if hook_warning:
            warning = {"emitted_at": now_iso(), "event": event, **hook_warning}
            warning_path = workspace / "logs" / "image-job-event-hook-warnings.jsonl"
            with warning_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(warning, ensure_ascii=False) + "\n")
            step_echo("image2.event-hook", "warning", job_id, f"command failed class={hook_warning['failure_class']}")
    if result.get("status") == "done":
        output = workspace_file(workspace, str(result.get("output") or f"outputs/{safe_id(job_id)}.png"))
        meta = image_header_metadata(output)
        size = output.stat().st_size if output.exists() else 0
        step_echo("image2.progress", "done", f"{completed}/{total}", f"{output.name} {meta.get('width') or '?'}x{meta.get('height') or '?'} {size}B")
    elif result.get("status") == "dry_run":
        step_echo("image2.progress", "done", f"{completed}/{total}", f"{job_id} dry_run provider_not_executed")
    else:
        suffix = " -> requeued" if requeued else ""
        step_echo("image2.progress", "failed", f"{completed}/{total}", f"{job_id} {result.get('failure_class') or 'provider_failure'}{suffix}")


def unique_existing_references(workspace: Path, jobs: list[dict[str, Any]], active_task_id: str = "") -> list[Path]:
    seen: dict[str, Path] = {}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        for raw in job.get("references", []) or []:
            path = workspace_file(workspace, str(raw))
            guard_read_path(path, active_task_id, "image2 report reference")
            if path.exists() and path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                seen[str(path.resolve())] = path
    return sorted(seen.values(), key=lambda path: path.name)


def asset_record(
    workspace: Path,
    *,
    job_id: str,
    title: str,
    path: Path,
    anchor: str,
    media_type: str = "image",
    role: str = "generated",
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "title": title,
        "path": rel_to_workspace(workspace, path),
        "anchor": anchor,
        "exists": path.exists() and path.is_file(),
        "media_type": media_type,
        "role": role,
    }


def video_assets_from_results(workspace: Path) -> list[dict[str, Any]]:
    results_root = workspace / "video" / "results"
    assets: list[dict[str, Any]] = []
    if not results_root.exists():
        return assets
    for path in sorted(results_root.glob("*.query-result.json")):
        data = read_json(path, {})
        if not isinstance(data, dict) or data.get("gen_status") != "success":
            continue
        job_id = str(data.get("job_id") or path.stem.replace(".query-result", ""))
        video = data.get("video") if isinstance(data.get("video"), dict) else {}
        local_path = str(video.get("local_path") or video.get("path") or "")
        video_path = workspace_file(workspace, local_path) if local_path else Path("")
        anchor = f"SVT_JEWELRY_VIDEO_{safe_id(job_id).upper()}"
        assets.append({
            "job_id": job_id,
            "title": str(data.get("title") or job_id),
            "path": rel_to_workspace(workspace, video_path) if local_path else "",
            "anchor": anchor,
            "exists": bool(local_path and video_path.exists() and video_path.is_file()),
            "media_type": "video",
            "submit_id": str(data.get("submit_id") or ""),
            "width": video.get("width"),
            "height": video.get("height"),
            "fps": video.get("fps"),
            "duration": video.get("duration"),
            "format": video.get("format") or "mp4",
            "video_url": video.get("video_url") or "",
        })
    return assets
