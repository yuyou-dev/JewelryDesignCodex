from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from lib.jewelry_image2 import _runtime
from lib.design_task import DesignTasksService
from lib.jewelry_image2.preflight import validate_request_readiness
from lib.jewelry_image2.workspace import (
    prepare_codex_home as prepare_codex_home_dir,
    prepare_worker_codex_home as prepare_worker_codex_home_dir,
)
from lib.jewelry_image2.common import (
    EXECUTED_JOB_CONTRACT_FIELDS,
    IMAGE_SUFFIXES,
    JOBS_LOCK,
    PROVIDER_ROUTE_FIELDS,
    WORKER_CONTRACT_VERSION,
    build_executed_prompt,
    declares_executed_prompt_contract,
    ensure_image2_provider_route_allowed,
    ensure_imagegen_prompt_contract,
    file_hash,
    guard_read_path,
    guard_write_path,
    image2_provider_route_issues,
    is_relative_to,
    normalize_ratio_value,
    now_iso,
    read_json,
    rel_to_workspace,
    resolve_job_ratio,
    safe_id,
    text_sha256,
    validate_imagegen_prompt_contract,
    write_json,
)


SCRIPT_DIR = Path(__file__).resolve().parents[2]


def workspace_file(workspace: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = workspace / path
    return path


def ensure_workspace(workspace: Path) -> None:
    for child in [
        "prompts",
        "references",
        "outputs",
        "logs",
        "jobs",
        "output",
    ]:
        (workspace / child).mkdir(parents=True, exist_ok=True)


def state_path(workspace: Path) -> Path:
    return workspace / "state.json"


def jobs_path(workspace: Path) -> Path:
    return workspace / "jobs.json"


def load_state(workspace: Path) -> dict[str, Any]:
    data = read_json(state_path(workspace), {})
    return data if isinstance(data, dict) else {}


def save_state(workspace: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json(state_path(workspace), state)


def load_jobs(workspace: Path) -> dict[str, Any]:
    data = read_json(jobs_path(workspace), {"version": 1, "jobs": []})
    if not isinstance(data, dict):
        data = {"version": 1, "jobs": []}
    if not isinstance(data.get("jobs"), list):
        data["jobs"] = []
    data.setdefault("version", 1)
    return data


def save_jobs(workspace: Path, data: dict[str, Any]) -> None:
    write_json(jobs_path(workspace), data)


def find_job(jobs: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    for job in jobs.get("jobs", []):
        if isinstance(job, dict) and str(job.get("id")) == job_id:
            return job
    return None


def prompt_path_for_job(workspace: Path, job_id: str) -> Path:
    return workspace / "prompts" / f"{safe_id(job_id)}.prompt.txt"


def canonicalize_prompt_file_for_job(
    workspace: Path,
    job_id: str,
    source_path: Path,
    *,
    active_task_id: str,
) -> Path:
    """Bind prompt-file content to the one path owned by job_id before registration."""
    canonical_path = prompt_path_for_job(workspace, job_id).resolve()
    source_path = source_path.resolve()
    if source_path == canonical_path:
        return canonical_path
    guard_write_path(canonical_path, active_task_id, "image2 canonical prompt file")
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    source_text = source_path.read_text(encoding="utf-8")
    try:
        with canonical_path.open("x", encoding="utf-8") as handle:
            handle.write(source_text)
    except FileExistsError:
        if not canonical_path.is_file() or canonical_path.read_text(encoding="utf-8") != source_text:
            raise ValueError(
                f"canonical prompt already exists with different content for job {safe_id(job_id)}: "
                f"{rel_to_workspace(workspace, canonical_path)}"
            )
    return canonical_path


def executed_prompt_path_for_job(workspace: Path, job_id: str) -> Path:
    return workspace / "logs" / "executed-prompts" / f"{safe_id(job_id)}.prompt.txt"


def job_record_path(workspace: Path, job_id: str) -> Path:
    return workspace / "jobs" / f"{safe_id(job_id)}.json"


def write_job_record(workspace: Path, job_id: str, record: dict[str, Any]) -> None:
    write_json(job_record_path(workspace, job_id), record)


def job_launch_record(
    workspace: Path,
    job_id: str,
    *,
    status: str,
    command: list[str],
    prompt_path: Path,
    output_path: Path,
    image_paths: list[Path],
    worker_home: Path,
    cmd_log: Path,
    stdout_log: Path,
    stderr_log: Path,
    output_message: Path,
    queued_at: str,
    worker_prepared_at: str,
    launch_started_at: str,
    launch_kind: str,
    dry_run: bool,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "id": job_id,
        "status": status,
        "dry_run": dry_run,
        "command": command,
        "prompt": rel_to_workspace(workspace, prompt_path),
        "output": rel_to_workspace(workspace, output_path),
        "references": [rel_to_workspace(workspace, path) for path in image_paths],
        "worker_codex_home": "user-codex-home",
        "queued_at": queued_at,
        "worker_prepared_at": worker_prepared_at,
        "launch_started_at": launch_started_at,
        "launch_evidence": {
            "kind": launch_kind,
            "cwd": ".",
            "codex_home": "user-codex-home",
            "cmd_log": rel_to_workspace(workspace, cmd_log),
        },
        "cmd_log": rel_to_workspace(workspace, cmd_log),
        "stdout_log": rel_to_workspace(workspace, stdout_log),
        "stderr_log": rel_to_workspace(workspace, stderr_log),
        "message_log": rel_to_workspace(workspace, output_message),
        "attempts": attempts,
    }


def prepare_codex_home(workspace: Path, source_home: Path | None = None) -> Path:
    selected = source_home or Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    return prepare_codex_home_dir(workspace, ensure_workspace, source_home=selected)


def prepare_worker_codex_home(base_codex_home: Path, job_id: str) -> Path:
    return prepare_worker_codex_home_dir(base_codex_home, job_id, safe_id)


def collect_image_inputs(workspace: Path, job: dict[str, Any], active_task_id: str = "") -> list[Path]:
    images: list[Path] = []
    for raw in job.get("references", []) or []:
        path = workspace_file(workspace, str(raw))
        guard_read_path(path, active_task_id, "image2 reference")
        if path.exists() and path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            images.append(path)
        else:
            raise FileNotFoundError(f"reference image not found or unsupported: {raw}")
    return images


def runner_hashes() -> dict[str, str]:
    paths = [(SCRIPT_DIR / "jewelry_image2_tool.py").resolve(), *sorted((SCRIPT_DIR / "lib" / "jewelry_image2").glob("**/*.py"))]
    return {str(path.relative_to(SCRIPT_DIR.parent)): file_hash(path) for path in paths if path.is_file()}


def check_runner_snapshot(workspace: Path) -> list[str]:
    snapshot_path = workspace / "logs" / "runner-snapshot.json"
    current = _runtime.resolve("runner_hashes", runner_hashes)()
    try:
        previous = read_json(snapshot_path, {})
    except json.JSONDecodeError:
        previous = {}
    warnings: list[str] = []
    if isinstance(previous, dict) and previous.get("hashes") and previous.get("hashes") != current:
        warnings.append("runner files changed after this design run started")
        changes_path = workspace / "logs" / "runner-change-warnings.jsonl"
        changes_path.parent.mkdir(parents=True, exist_ok=True)
        with changes_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"detected_at": now_iso(), "before": previous.get("hashes"), "after": current}, ensure_ascii=False) + "\n")
    if not previous:
        write_json(snapshot_path, {"recorded_at": now_iso(), "hashes": current})
    return warnings


def request_readiness_error(result: dict[str, Any]) -> ValueError:
    messages = [str(item.get("message") or item.get("code") or "request is not ready") for item in result.get("issues", [])]
    return ValueError("request_readiness_blocked: " + "; ".join(messages))


def validate_job_payloads_before_persist(workspace: Path, payloads: list[dict[str, Any]]) -> dict[str, Any]:
    outputs: list[str] = []
    references: list[str] = []
    for payload in payloads:
        job_id = safe_id(str(payload.get("id") or payload.get("job_id") or payload.get("title") or "job"))
        outputs.append(str(payload.get("output") or f"outputs/{job_id}.png"))
        references.extend(str(item) for item in payload.get("references", []) or [])
        ensure_image2_provider_route_allowed(payload, label=f"job {job_id}")
    result = validate_request_readiness(
        requested_count=len(payloads),
        output_shape="independent_images",
        outputs=outputs,
        references=references,
        reference_base=workspace,
        check_provider=False,
    )
    if not result["ok"]:
        raise request_readiness_error(result)
    return result


def ensure_design_task_for_workspace(workspace: Path, args: argparse.Namespace) -> dict[str, Any] | None:
    repo_root = SCRIPT_DIR.parent.resolve()
    media_root = (repo_root / "artifacts" / "runs").resolve()
    if workspace.parent.resolve() != media_root:
        return None
    task_id = str(getattr(args, "task_id", "") or getattr(args, "active_task_id", "") or workspace.name)
    service = DesignTasksService(repo_root)
    existing = service.read_design_task(task_id)
    if existing is not None:
        return existing
    return service.create_design_task({
        "task_id": task_id,
        "title": args.title,
        "goal": getattr(args, "goal", "") or args.title,
        "deliverables": getattr(args, "deliverables", ""),
        "design_direction": getattr(args, "design_direction", ""),
        "constraints": getattr(args, "constraints", ""),
    })


def normalize_job_payload(workspace: Path, payload: dict[str, Any], active_task_id: str = "") -> dict[str, Any]:
    job_id = safe_id(str(payload.get("id") or payload.get("job_id") or payload.get("title") or f"job-{int(time.time() * 1000)}"))
    ensure_image2_provider_route_allowed(payload, label=f"job {job_id}")
    output = str(payload.get("output") or f"outputs/{job_id}.png")
    prompt_file = str(payload.get("prompt_file") or "")
    prompt_text = str(payload.get("prompt") or "")
    if prompt_file:
        prompt_path = workspace_file(workspace, prompt_file)
        guard_read_path(prompt_path, active_task_id, "image2 prompt file")
        if not prompt_path.exists():
            raise FileNotFoundError(f"prompt file not found: {prompt_file}")
        prompt_for_ratio = prompt_path.read_text(encoding="utf-8", errors="replace")
        ensure_imagegen_prompt_contract(prompt_for_ratio, label=f"prompt file {prompt_file}")
        prompt_path = canonicalize_prompt_file_for_job(
            workspace,
            job_id,
            prompt_path,
            active_task_id=active_task_id,
        )
    else:
        if not prompt_text.strip():
            raise ValueError("prompt or prompt_file is required")
        prompt_path = prompt_path_for_job(workspace, job_id)
        guard_write_path(prompt_path, active_task_id, "image2 generated prompt")
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_for_ratio = prompt_text
        ensure_imagegen_prompt_contract(prompt_for_ratio, label=f"inline prompt for {job_id}")
    ratio, ratio_source = resolve_job_ratio(payload, prompt_for_ratio)
    if not prompt_file:
        prompt_path.write_text(prompt_text, encoding="utf-8")
    source_prompt = prompt_path.read_text(encoding="utf-8")
    executed_prompt = build_executed_prompt(source_prompt, ratio, ratio_source)
    output_path = workspace_file(workspace, output)
    guard_write_path(output_path, active_task_id, "image2 output")
    references = [str(item) for item in payload.get("references", []) or []]
    for reference in references:
        guard_read_path(workspace_file(workspace, reference), active_task_id, "image2 reference")
    job = {
        "schema_version": int(payload.get("schema_version") or 1),
        "id": job_id,
        "title": str(payload.get("title") or job_id),
        "kind": str(payload.get("kind") or "jewelry-image"),
        "ratio": ratio,
        "ratio_source": ratio_source,
        "prompt": rel_to_workspace(workspace, prompt_path),
        "prompt_sha256": text_sha256(source_prompt),
        "executed_prompt_sha256": text_sha256(executed_prompt),
        "worker_contract_version": WORKER_CONTRACT_VERSION,
        "output": output,
        "references": references,
        "status": str(payload.get("status") or "pending"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    if payload.get("run_id"):
        job["run_id"] = str(payload["run_id"])
    if payload.get("batch_id"):
        job["batch_id"] = str(payload["batch_id"])
    if payload.get("stable_id"):
        job["stable_id"] = str(payload["stable_id"])
    if payload.get("source"):
        job["source"] = str(payload["source"])
    if payload.get("delivery_level") or payload.get("deliveryLevel"):
        job["delivery_level"] = str(payload.get("delivery_level") or payload.get("deliveryLevel"))
    if "timeout" in payload:
        job["timeout"] = payload["timeout"]
    if payload.get("allow_duplicate_prompt") or payload.get("allowDuplicatePrompt"):
        job["allow_duplicate_prompt"] = True
    for field in PROVIDER_ROUTE_FIELDS + ["provider_exception", "providerException", "allowed_fallbacks", "allowedFallbacks"]:
        if field in payload:
            job[field] = payload[field]
    return job


def upsert_job(workspace: Path, job: dict[str, Any]) -> None:
    data = load_jobs(workspace)
    existing = find_job(data, str(job["id"]))
    if existing:
        existing.update({**job, "created_at": existing.get("created_at") or job.get("created_at"), "updated_at": now_iso()})
    else:
        data["jobs"].append(job)
    save_jobs(workspace, data)


def enforce_registration_uniqueness(workspace: Path, jobs: list[dict[str, Any]]) -> None:
    existing = [item for item in load_jobs(workspace).get("jobs", []) if isinstance(item, dict)]
    seen_ids = {str(item.get("id") or ""): str(item.get("id") or "") for item in existing}
    seen_outputs = {str(item.get("output") or ""): str(item.get("id") or "") for item in existing}
    seen_prompts = {str(item.get("prompt_sha256") or ""): str(item.get("id") or "") for item in existing if item.get("prompt_sha256")}
    for job in jobs:
        job_id = str(job.get("id") or "")
        output = str(job.get("output") or "")
        prompt_hash = str(job.get("prompt_sha256") or "")
        if job_id in seen_ids:
            raise ValueError(f"duplicate job_id registration: {job_id}")
        if output in seen_outputs:
            raise ValueError(f"duplicate output registration: {output} (already owned by {seen_outputs[output]})")
        if prompt_hash in seen_prompts and not job.get("allow_duplicate_prompt"):
            raise ValueError(f"duplicate prompt registration: {job_id} matches {seen_prompts[prompt_hash]}; pass --allow-duplicate-prompt only when explicitly requested")
        seen_ids[job_id] = job_id
        seen_outputs[output] = job_id
        if prompt_hash and prompt_hash not in seen_prompts:
            seen_prompts[prompt_hash] = job_id


def reject_known_registration_collisions(workspace: Path, payloads: list[dict[str, Any]]) -> None:
    """Reject id/output collisions before normalization can write prompt files."""
    existing = [item for item in load_jobs(workspace).get("jobs", []) if isinstance(item, dict)]
    ids = {str(item.get("id") or "") for item in existing}
    outputs = {str(item.get("output") or "") for item in existing}
    for payload in payloads:
        job_id = safe_id(str(payload.get("id") or payload.get("job_id") or payload.get("title") or ""))
        output = str(payload.get("output") or f"outputs/{job_id}.png")
        if job_id in ids:
            raise ValueError(f"duplicate job_id registration: {job_id}")
        if output in outputs:
            raise ValueError(f"duplicate output registration: {output}")
        ids.add(job_id)
        outputs.add(output)


def job_ids_from_manifest(workspace: Path, manifest_arg: str | None) -> set[str] | None:
    if not manifest_arg:
        return None
    candidate = Path(manifest_arg).expanduser()
    resolved = (candidate if candidate.is_absolute() else workspace / candidate).resolve()
    if not resolved.is_relative_to(workspace.resolve()) or not resolved.is_file():
        raise ValueError("job manifest must be a readable file inside the workspace")
    payload = read_json(resolved, {})
    jobs = payload.get("jobs") if isinstance(payload, dict) else payload
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("job manifest must contain a non-empty jobs list")
    job_ids = {str(item.get("id") or "") for item in jobs if isinstance(item, dict)}
    if len(job_ids) != len(jobs) or "" in job_ids:
        raise ValueError("job manifest contains missing or duplicate job ids")
    return job_ids


def selected_jobs(
    workspace: Path,
    job_id: str | None,
    only: str,
    job_prefix: str | None = None,
    job_manifest: str | None = None,
) -> list[dict[str, Any]]:
    selectors = sum(bool(value) for value in (job_id, job_prefix, job_manifest))
    if selectors > 1:
        raise ValueError("use only one of --job-id, --job-prefix, or --job-manifest")
    data = load_jobs(workspace)
    statuses = {item.strip() for item in only.split(",") if item.strip()}
    jobs = [job for job in data.get("jobs", []) if isinstance(job, dict)]
    if job_id:
        jobs = [job for job in jobs if str(job.get("id")) == job_id]
    if job_prefix:
        jobs = [job for job in jobs if str(job.get("id") or "").startswith(job_prefix)]
    manifest_ids = job_ids_from_manifest(workspace, job_manifest)
    if manifest_ids is not None:
        jobs = [job for job in jobs if str(job.get("id") or "") in manifest_ids]
        matched_ids = {str(job.get("id") or "") for job in jobs}
        missing_ids = sorted(manifest_ids - matched_ids)
        if missing_ids:
            raise ValueError(f"job manifest references unregistered ids: {', '.join(missing_ids)}")
    if statuses:
        jobs = [job for job in jobs if str(job.get("status") or "pending") in statuses]
    return jobs


def validate_static_job_contract(workspace: Path, job: dict[str, Any], *, active_task_id: str, seen_outputs: dict[str, str]) -> dict[str, Any]:
    job_id = str(job.get("id") or "")
    issues: list[str] = []
    prompt_rel = str(job.get("prompt") or f"prompts/{safe_id(job_id)}.prompt.txt")
    output_rel = str(job.get("output") or f"outputs/{safe_id(job_id)}.png")
    prompt_path = workspace_file(workspace, prompt_rel)
    output_path = workspace_file(workspace, output_rel)
    issues.extend(image2_provider_route_issues(job))

    try:
        guard_read_path(prompt_path, active_task_id, "image2 static prompt")
    except Exception as error:
        issues.append(f"prompt_path_guard_failed:{error.__class__.__name__}")
    try:
        guard_write_path(output_path, active_task_id, "image2 static output")
    except Exception as error:
        issues.append(f"output_path_guard_failed:{error.__class__.__name__}")

    if not is_relative_to(prompt_path, workspace):
        issues.append("prompt_outside_workspace")
    if not prompt_path.exists() or not prompt_path.is_file():
        issues.append("prompt_missing")
        prompt_contract_issues: list[str] = []
    else:
        prompt_text = prompt_path.read_text(encoding="utf-8", errors="replace")
        if job.get("prompt_sha256") and job.get("prompt_sha256") != text_sha256(prompt_text):
            issues.append("prompt_hash_mismatch")
        prompt_contract_issues = validate_imagegen_prompt_contract(prompt_text, label=f"prompt for {job_id}")
        issues.extend(prompt_contract_issues)
        if declares_executed_prompt_contract(job, EXECUTED_JOB_CONTRACT_FIELDS):
            if not all(job.get(field) for field in EXECUTED_JOB_CONTRACT_FIELDS):
                issues.append("executed_prompt_contract_incomplete")
            elif str(job.get("worker_contract_version")) != WORKER_CONTRACT_VERSION:
                issues.append("worker_contract_version_mismatch")
            elif not prompt_contract_issues:
                expected_executed_hash = text_sha256(
                    build_executed_prompt(
                        prompt_text,
                        normalize_ratio_value(job.get("ratio")),
                        str(job.get("ratio_source") or ""),
                    )
                )
                if str(job.get("executed_prompt_sha256")) != expected_executed_hash:
                    issues.append("executed_prompt_hash_mismatch")

    if not is_relative_to(output_path, workspace):
        issues.append("output_outside_workspace")
    if output_path.suffix.lower() not in IMAGE_SUFFIXES:
        issues.append("output_suffix_not_image")
    output_key = rel_to_workspace(workspace, output_path)
    if output_key in seen_outputs:
        issues.append(f"duplicate_output:{seen_outputs[output_key]}")
    else:
        seen_outputs[output_key] = job_id

    normalized_ratio = normalize_ratio_value(job.get("ratio"))
    if job.get("ratio") and not re.fullmatch(r"\d{1,2}:\d{1,2}", normalized_ratio):
        issues.append("ratio_invalid")
    if "timeout" in job:
        timeout_value = job.get("timeout")
        if isinstance(timeout_value, bool) or not isinstance(timeout_value, int):
            issues.append("timeout_invalid")
        elif timeout_value < 60:
            issues.append("timeout_too_small")

    reference_issues: list[str] = []
    try:
        collect_image_inputs(workspace, job, active_task_id)
    except Exception as error:
        reference_issues.append(f"reference_invalid:{error.__class__.__name__}:{error}")
        issues.extend(reference_issues)

    return {
        "job_id": job_id,
        "status": str(job.get("status") or "pending"),
        "prompt": rel_to_workspace(workspace, prompt_path),
        "output": output_key,
        "ratio": str(job.get("ratio") or ""),
        "issues": issues,
        "prompt_contract_issues": prompt_contract_issues if prompt_path.exists() else [],
        "reference_issues": reference_issues,
    }


def set_job_status(workspace: Path, job_id: str, updates: dict[str, Any]) -> None:
    with JOBS_LOCK:
        data = load_jobs(workspace)
        job = find_job(data, job_id)
        if job is None:
            return
        job.update(updates)
        job["updated_at"] = now_iso()
        save_jobs(workspace, data)


def mark_abandoned_batch_artifacts(workspace: Path, *, selected_job_ids: set[str], initial_job_ids: set[str]) -> dict[str, Any]:
    abandoned_selected: list[str] = []
    abandoned_recursive: list[str] = []
    with JOBS_LOCK:
        data = load_jobs(workspace)
        changed = False
        for job in data.get("jobs", []):
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or "")
            status = str(job.get("status") or "pending")
            if job_id in selected_job_ids and status in {"running", "generating"}:
                job["status"] = "abandoned"
                job["failure_class"] = "stale_running_after_batch"
                job["error"] = "Job was left running after the generate batch finished."
                job["updated_at"] = now_iso()
                abandoned_selected.append(job_id)
                changed = True
            elif job_id not in initial_job_ids and re.search(r"\buser-[A-Za-z0-9_.-]+-v\d+\b", job_id):
                job["status"] = "abandoned"
                job["failure_class"] = "recursive_worker_output"
                job["error"] = "Job was created by a worker during image generation and is not part of the planned batch."
                job["updated_at"] = now_iso()
                abandoned_recursive.append(job_id)
                changed = True
        if changed:
            save_jobs(workspace, data)
    return {
        "abandoned_selected_job_ids": abandoned_selected,
        "abandoned_recursive_job_ids": abandoned_recursive,
    }
