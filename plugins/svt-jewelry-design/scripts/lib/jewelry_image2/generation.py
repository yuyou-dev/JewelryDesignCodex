from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from lib.jewelry_image2 import _runtime
from lib.jewelry_image2.policy import detect_disallowed_processing
from lib.run_path_guard import TaskPathGuardError
from lib.jewelry_image2.common import (
    BATCH_CIRCUIT_BREAKER_FAILURE_CLASSES,
    DEFAULT_EARLY_STOP_GRACE,
    DEFAULT_MONITOR_INTERVAL,
    DEFAULT_TIMEOUT,
    IMAGE_SUFFIXES,
    NON_RETRYABLE_FAILURE_CLASSES,
    ProviderRouteError,
    WORKER_CONTRACT_VERSION,
    build_executed_prompt,
    classify_codex_transport_failure,
    classify_provider_auth_failure,
    classify_provider_network_failure,
    duration_seconds,
    ensure_image2_provider_route_allowed,
    ensure_imagegen_prompt_contract,
    file_hash,
    guard_read_path,
    guard_write_path,
    has_complete_legacy_worker_contract,
    is_relative_to,
    iso_to_timestamp,
    normalize_ratio_value,
    now_iso,
    recursive_worker_output_flags,
    rel_to_workspace,
    safe_id,
    text_sha256,
)
from lib.jewelry_image2.jobs import (
    collect_image_inputs,
    executed_prompt_path_for_job,
    job_launch_record,
    job_record_path,
    prepare_worker_codex_home,
    set_job_status,
    workspace_file,
    write_job_record,
)


def codex_generate_command(
    workspace: Path,
    prompt_path: Path,
    image_paths: list[Path],
    output_message: Path,
) -> list[str]:
    command = [
        "codex",
        "-a",
        "never",
        "exec",
        "-C",
        str(workspace),
        "--skip-git-repo-check",
        "-s",
        "workspace-write",
        "-o",
        str(output_message),
    ]
    for image_path in image_paths:
        command.extend(["-i", str(image_path)])
    command.append("-")
    return command


def image_paths_from_text(text: str, workspace: Path) -> list[Path]:
    if not text:
        return []
    pattern = re.compile(r"(?P<path>(?:/|\.{0,2}/|[A-Za-z0-9_.-]+/)[^\s'\"<>]+?\.(?:png|jpg|jpeg|webp))", re.I)
    paths: dict[str, Path] = {}
    for match in pattern.finditer(text):
        raw = match.group("path").rstrip(").,;:")
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = workspace / path
        if path.exists() and path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            paths[str(path.resolve())] = path
    return sorted(paths.values(), key=lambda path: path.stat().st_mtime, reverse=True)


def generated_images_after(root: Path, timestamp: float) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        [
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in IMAGE_SUFFIXES
            and path.stat().st_mtime >= timestamp
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def looks_like_image_file(path: Path) -> bool:
    try:
        header = path.read_bytes()[:32]
    except OSError:
        return False
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if header.startswith(b"\xff\xd8\xff"):
        return True
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return True
    return False


def stable_generated_image(
    root: Path,
    timestamp: float,
    existing_hashes: set[str],
    seen: dict[str, dict[str, Any]],
    stable_for: float,
) -> Path | None:
    if not root.exists():
        return None
    now = time.monotonic()
    candidates: list[tuple[float, Path, os.stat_result]] = []
    for path in root.rglob("*"):
        try:
            stat = path.stat()
        except OSError:
            continue
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if stat.st_size <= 0 or stat.st_mtime < timestamp:
            continue
        if not looks_like_image_file(path):
            continue
        try:
            if file_hash(path) in existing_hashes:
                continue
        except OSError:
            continue
        candidates.append((stat.st_mtime, path, stat))
    if len(candidates) != 1:
        return None
    for _, path, stat in sorted(candidates, key=lambda item: item[0], reverse=True):
        key = str(path.resolve())
        previous = seen.get(key)
        if not previous or previous.get("size") != stat.st_size or previous.get("mtime") != stat.st_mtime:
            seen[key] = {"size": stat.st_size, "mtime": stat.st_mtime, "stable_since": now}
            if stable_for <= 0:
                return path
            continue
        if now - float(previous.get("stable_since") or now) >= stable_for:
            return path
    return None


def terminate_generation_process(process: subprocess.Popen[str], *, reason: str, wait_seconds: float) -> dict[str, Any]:
    if process.poll() is not None:
        return {"reason": reason, "terminated": False, "killed": False, "returncode": process.returncode}
    process.terminate()
    try:
        process.wait(timeout=max(0.5, min(5.0, wait_seconds)))
        return {"reason": reason, "terminated": True, "killed": False, "returncode": process.returncode}
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        return {"reason": reason, "terminated": True, "killed": True, "returncode": process.returncode}


def run_monitored_generation_attempt(
    *,
    command: list[str],
    prompt_text: str,
    workspace: Path,
    env: dict[str, str],
    worker_home: Path,
    output_path: Path,
    stdout_log: Path,
    stderr_log: Path,
    start_time: float,
    timeout: int,
    allow_latest_recovery: bool,
    early_stop: bool,
    monitor_interval: float,
    early_stop_grace: float,
    existing_hashes: set[str],
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    details: dict[str, Any] = {
        "early_stopped": False,
        "early_stop_reason": None,
        "recovered_from": None,
        "termination": None,
        "timed_out": False,
    }
    poll_interval = max(0.05, float(monitor_interval or DEFAULT_MONITOR_INTERVAL))
    stable_for = max(0.0, float(early_stop_grace or 0.0))
    attempt_started = time.monotonic()
    seen_candidates: dict[str, dict[str, Any]] = {}
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    stderr_log.parent.mkdir(parents=True, exist_ok=True)
    with stdout_log.open("a", encoding="utf-8") as stdout_handle, stderr_log.open("a", encoding="utf-8") as stderr_handle:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            cwd=workspace,
            env=env,
        )
        if process.stdin:
            try:
                process.stdin.write(prompt_text)
                process.stdin.close()
            except BrokenPipeError:
                pass
        while True:
            returncode = process.poll()
            if returncode is not None:
                break
            if timeout and time.monotonic() - attempt_started >= timeout:
                details["timed_out"] = True
                details["termination"] = terminate_generation_process(process, reason="timeout", wait_seconds=early_stop_grace)
                stderr_handle.write(f"\nTimed out after {timeout} seconds.\n")
                stderr_handle.flush()
                returncode = 124
                break
            live_text = ""
            for live_path in (stdout_log, stderr_log):
                if live_path.exists():
                    live_text += live_path.read_text(encoding="utf-8", errors="replace")[-8192:].lower()
            auth_failure = classify_provider_auth_failure(live_text)
            if auth_failure:
                details["fast_failed"] = True
                details["fast_fail_class"] = "provider_auth_failed"
                details["fast_fail_signal"] = auth_failure["signal"]
                details["termination"] = terminate_generation_process(process, reason="provider_auth_fast_fail", wait_seconds=early_stop_grace)
                returncode = process.returncode
                break
            network_failure = classify_provider_network_failure(live_text)
            if network_failure:
                details["fast_failed"] = True
                details["fast_fail_class"] = "provider_network_error"
                details["fast_fail_signal"] = network_failure["signal"]
                details["termination"] = terminate_generation_process(process, reason="network_fast_fail", wait_seconds=early_stop_grace)
                returncode = process.returncode
                break
            if early_stop and allow_latest_recovery:
                candidate = stable_generated_image(
                    worker_home / "generated_images",
                    start_time,
                    existing_hashes,
                    seen_candidates,
                    stable_for,
                )
                if candidate:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(candidate, output_path)
                    details["early_stopped"] = True
                    details["early_stop_reason"] = "stable_worker_generated_image"
                    details["recovered_from"] = str(candidate)
                    details["termination"] = terminate_generation_process(process, reason="early_stop", wait_seconds=early_stop_grace)
                    stderr_handle.write(f"\nEarly stopped after recovering {candidate}.\n")
                    stderr_handle.flush()
                    returncode = process.returncode
                    break
            try:
                process.wait(timeout=poll_interval)
            except subprocess.TimeoutExpired:
                pass
    stdout = stdout_log.read_text(encoding="utf-8", errors="replace") if stdout_log.exists() else ""
    stderr = stderr_log.read_text(encoding="utf-8", errors="replace") if stderr_log.exists() else ""
    if details["timed_out"]:
        returncode = 124
    else:
        returncode = process.returncode
    return subprocess.CompletedProcess(command, int(returncode or 0), stdout, stderr), details


def classify_generation_failure(
    result: subprocess.CompletedProcess[str],
    worker_home: Path,
    start_time: float,
    output_path: Path,
    combined_text: str,
) -> dict[str, Any]:
    generated_root = worker_home / "generated_images"
    candidates = generated_images_after(generated_root, start_time)
    text = (combined_text or "").lower()
    if candidates:
        return {
            "class": "recovery_failed",
            "message": "Worker generated_images contains new images, but none could be recovered to the target output.",
            "generated_candidates": [str(path) for path in candidates[:5]],
        }
    auth_failure = classify_provider_auth_failure(combined_text)
    if auth_failure:
        return {**auth_failure, "generated_candidates": []}
    network_failure = classify_provider_network_failure(combined_text)
    if network_failure:
        return {**network_failure, "generated_candidates": []}
    if re.search(r"(permission denied|operation not permitted|read-only file system|outside the active task|not writable|sandbox (denied|violation)|landlock)", text):
        return {
            "class": "sandbox_path_failure",
            "message": "Generation failed with a sandbox, permission, or path write/read error.",
            "generated_candidates": [],
        }
    transport_failure = classify_codex_transport_failure(text)
    if transport_failure:
        return {**transport_failure, "generated_candidates": []}
    if result.returncode == 124 or re.search(r"\btimed out after \d+(?:\.\d+)? seconds\b", text):
        return {
            "class": "provider_timeout",
            "message": "Codex image generation timed out before producing the target output.",
            "generated_candidates": [],
        }
    if result.returncode != 0:
        return {
            "class": "provider_failure",
            "message": "Codex image generation exited non-zero and produced no recoverable output.",
            "generated_candidates": [],
        }
    return {
        "class": "provider_no_output",
        "message": f"Codex exited successfully but did not produce the expected output file: {output_path}",
        "generated_candidates": [],
    }


def classify_generation_exception(error: BaseException) -> str:
    text = str(error).lower()
    if isinstance(error, ProviderRouteError) or "provider_route_forbidden" in text:
        return "provider_route_forbidden"
    if isinstance(error, FileNotFoundError) or "prompt" in text or "reference" in text:
        return "missing_prompt_or_reference"
    if isinstance(error, TaskPathGuardError) or "active task workspace" in text:
        return "sandbox_path_failure"
    if isinstance(error, PermissionError):
        return "sandbox_path_failure"
    return "runner_exception"


def existing_output_hashes(workspace: Path, output_path: Path) -> set[str]:
    hashes: set[str] = set()
    outputs_root = workspace / "outputs"
    if not outputs_root.exists():
        return hashes
    for path in outputs_root.rglob("*"):
        if path == output_path:
            continue
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            hashes.add(file_hash(path))
    return hashes


def quarantine_output(workspace: Path, output_path: Path, suffix: str = ".rejected") -> str | None:
    if not output_path.exists():
        return None
    rel = rel_to_workspace(workspace, output_path)
    target = output_path.with_name(output_path.name + suffix)
    counter = 1
    while target.exists():
        target = output_path.with_name(f"{output_path.name}{suffix}.{counter}")
        counter += 1
    shutil.move(str(output_path), str(target))
    return rel_to_workspace(workspace, target)


def recover_generated_image(
    workspace: Path,
    output_path: Path,
    result: subprocess.CompletedProcess[str],
    output_message: Path,
    codex_home: Path,
    start_time: float,
    allow_latest_recovery: bool,
    existing_hashes: set[str] | None = None,
    candidate_text: str | None = None,
) -> str | None:
    if output_path.exists() and output_path.stat().st_size > 0:
        return None
    message = output_message.read_text(encoding="utf-8", errors="replace") if output_message.exists() else ""
    text = candidate_text if candidate_text is not None else "\n".join([result.stdout or "", result.stderr or "", message])
    generated_root = codex_home / "generated_images"
    hashes = existing_hashes or set()
    candidates: dict[str, Path] = {}
    for candidate in image_paths_from_text(text, workspace):
        if candidate.resolve() == output_path.resolve():
            continue
        if not is_relative_to(candidate, generated_root):
            continue
        if not candidate.exists() or not looks_like_image_file(candidate):
            continue
        if file_hash(candidate) in hashes:
            continue
        candidates[str(candidate.resolve())] = candidate
    if allow_latest_recovery:
        for candidate in generated_images_after(generated_root, start_time):
            if looks_like_image_file(candidate) and file_hash(candidate) not in hashes:
                candidates[str(candidate.resolve())] = candidate
    if len(candidates) > 1:
        raise RuntimeError("ambiguous_recovery: multiple new worker images; refusing to guess")
    if len(candidates) == 1:
        candidate = next(iter(candidates.values()))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate, output_path)
        return str(candidate)
    return None


def retry_delay_seconds(attempt: int, base: float, maximum: float) -> float:
    if base <= 0 or maximum <= 0:
        return 0
    return min(maximum, base * (2 ** max(0, attempt - 1)))


def resolved_job_timeout(job: dict[str, Any], batch_timeout: int) -> int:
    value = job.get("timeout")
    if isinstance(value, bool):
        value = None
    if isinstance(value, int):
        return value
    return int(batch_timeout or DEFAULT_TIMEOUT)


def run_generation_job(
    workspace: Path,
    job: dict[str, Any],
    base_codex_home: Path,
    retries: int,
    timeout: int,
    retry_base: float,
    retry_max: float,
    allow_latest_recovery: bool,
    dry_run: bool = False,
    active_task_id: str = "",
    early_stop: bool = True,
    monitor_interval: float = DEFAULT_MONITOR_INTERVAL,
    early_stop_grace: float = DEFAULT_EARLY_STOP_GRACE,
) -> dict[str, Any]:
    job_started_monotonic = time.monotonic()
    job_id = str(job.get("id"))
    ensure_image2_provider_route_allowed(job, label=f"job {job_id}")
    queued_at = now_iso()
    prompt_path = workspace_file(workspace, str(job.get("prompt") or ""))
    executed_prompt_path = executed_prompt_path_for_job(workspace, job_id)
    output_path = workspace_file(workspace, str(job.get("output") or f"outputs/{job_id}.png"))
    output_message = workspace / "logs" / f"codex_{safe_id(job_id)}.last-message.txt"
    ratio = normalize_ratio_value(job.get("ratio"))
    ratio_source = str(job.get("ratio_source") or "")
    guard_read_path(prompt_path, active_task_id, "image2 prompt file")
    guard_write_path(executed_prompt_path, active_task_id, "image2 executed prompt evidence")
    guard_write_path(output_path, active_task_id, "image2 output")
    guard_write_path(output_message, active_task_id, "image2 message log")
    image_paths = collect_image_inputs(workspace, job, active_task_id)
    command = _runtime.resolve("codex_generate_command", codex_generate_command)(workspace, prompt_path, image_paths, output_message)
    timeout = resolved_job_timeout(job, timeout)
    logs = workspace / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    cmd_log = logs / f"codex_{safe_id(job_id)}.cmd.txt"
    stdout_log = logs / f"codex_{safe_id(job_id)}.stdout.txt"
    stderr_log = logs / f"codex_{safe_id(job_id)}.stderr.txt"
    guard_write_path(cmd_log, active_task_id, "image2 command log")
    guard_write_path(stdout_log, active_task_id, "image2 stdout log")
    guard_write_path(stderr_log, active_task_id, "image2 stderr log")
    guard_write_path(job_record_path(workspace, job_id), active_task_id, "image2 job record")
    if not prompt_path.exists():
        raise FileNotFoundError(f"prompt not found: {prompt_path}")
    prompt_text = prompt_path.read_text(encoding="utf-8")
    ensure_imagegen_prompt_contract(prompt_text, label=f"prompt for {job_id}")
    source_prompt_sha256 = text_sha256(prompt_text)
    prompt_text_for_generation = build_executed_prompt(prompt_text, ratio, ratio_source)
    executed_prompt_sha256 = text_sha256(prompt_text_for_generation)
    executed_prompt_path.parent.mkdir(parents=True, exist_ok=True)
    executed_prompt_path.write_text(prompt_text_for_generation, encoding="utf-8")
    prompt_contract = {
        "ratio": ratio,
        "ratio_source": ratio_source,
        "applied_to_stdin": bool(ratio),
        "source_kind": "legacy_complete" if has_complete_legacy_worker_contract(prompt_text) else "creative_only",
        "worker_contract_version": WORKER_CONTRACT_VERSION,
    }
    if dry_run:
        worker_home = prepare_worker_codex_home(base_codex_home, job_id)
        worker_prepared_at = now_iso()
        launch_started_at = now_iso()
        cmd_log.write_text(" ".join(command) + f"\n< {executed_prompt_path}\n", encoding="utf-8")
        stdout_log.write_text("", encoding="utf-8")
        stderr_log.write_text("dry run; provider command was not executed\n", encoding="utf-8")
        record = job_launch_record(
            workspace,
            job_id,
            status="dry_run",
            command=command,
            prompt_path=prompt_path,
            output_path=output_path,
            image_paths=image_paths,
            worker_home=worker_home,
            cmd_log=cmd_log,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
            output_message=output_message,
            queued_at=queued_at,
            worker_prepared_at=worker_prepared_at,
            launch_started_at=launch_started_at,
            launch_kind="dry_run",
            dry_run=True,
            attempts=[],
        )
        record["ratio"] = ratio
        record["ratio_source"] = ratio_source
        record["prompt_sha256"] = source_prompt_sha256
        record["executed_prompt"] = rel_to_workspace(workspace, executed_prompt_path)
        record["executed_prompt_sha256"] = executed_prompt_sha256
        record["executed_prompt_bytes"] = len(prompt_text_for_generation.encode("utf-8"))
        record["worker_contract_version"] = WORKER_CONTRACT_VERSION
        record["prompt_contract"] = prompt_contract
        record["finished_at"] = now_iso()
        record["duration_seconds"] = duration_seconds(job_started_monotonic)
        record["early_stopped"] = False
        record["early_stop_reason"] = None
        record["references"] = [str(path) for path in image_paths]
        write_job_record(workspace, job_id, record)
        set_job_status(
            workspace,
            job_id,
            {
                "status": "dry_run",
                "output": rel_to_workspace(workspace, output_path),
                "job_record": rel_to_workspace(workspace, job_record_path(workspace, job_id)),
                "executed_prompt_sha256": executed_prompt_sha256,
                "worker_contract_version": WORKER_CONTRACT_VERSION,
            },
        )
        return record
    started_timestamp = dt.datetime.now().timestamp()
    previous_output = None
    if output_path.exists() and output_path.stat().st_size > 0:
        previous_output = quarantine_output(workspace, output_path, ".previous")
    worker_home = prepare_worker_codex_home(base_codex_home, job_id)
    worker_prepared_at = now_iso()
    env = os.environ.copy()
    env["CODEX_HOME"] = str(worker_home)
    env["JDC_IMAGE2_JOB_ID"] = job_id
    cmd_log.write_text(" ".join(command) + f"\n< {executed_prompt_path}\n", encoding="utf-8")
    stdout_log.write_text("", encoding="utf-8")
    stderr_log.write_text("", encoding="utf-8")
    launch_started_at = now_iso()
    attempts: list[dict[str, Any]] = []
    last_combined_text = ""
    record = job_launch_record(
        workspace,
        job_id,
        status="running",
        command=command,
        prompt_path=prompt_path,
        output_path=output_path,
        image_paths=image_paths,
        worker_home=worker_home,
        cmd_log=cmd_log,
        stdout_log=stdout_log,
        stderr_log=stderr_log,
        output_message=output_message,
        queued_at=queued_at,
        worker_prepared_at=worker_prepared_at,
        launch_started_at=launch_started_at,
        launch_kind="subprocess_popen_monitor",
        dry_run=False,
        attempts=attempts,
    )
    record["ratio"] = ratio
    record["ratio_source"] = ratio_source
    record["prompt_sha256"] = source_prompt_sha256
    record["executed_prompt"] = rel_to_workspace(workspace, executed_prompt_path)
    record["executed_prompt_sha256"] = executed_prompt_sha256
    record["executed_prompt_bytes"] = len(prompt_text_for_generation.encode("utf-8"))
    record["worker_contract_version"] = WORKER_CONTRACT_VERSION
    record["prompt_contract"] = prompt_contract
    record["finished_at"] = None
    record["duration_seconds"] = None
    record["early_stopped"] = False
    record["early_stop_reason"] = None
    write_job_record(workspace, job_id, record)
    set_job_status(
        workspace,
        job_id,
        {
            "status": "running",
            "output": rel_to_workspace(workspace, output_path),
            "job_record": rel_to_workspace(workspace, job_record_path(workspace, job_id)),
            "executed_prompt_sha256": executed_prompt_sha256,
            "worker_contract_version": WORKER_CONTRACT_VERSION,
        },
    )
    result: subprocess.CompletedProcess[str] | None = None
    max_attempts = max(1, retries + 1)
    retry_skipped_reason = None
    for attempt in range(1, max_attempts + 1):
        attempt_started_monotonic = time.monotonic()
        attempt_started_timestamp = time.time()
        attempt_record: dict[str, Any] = {
            "attempt": attempt,
            "prompt_sha256": source_prompt_sha256,
            "executed_prompt_sha256": executed_prompt_sha256,
            "worker_contract_version": WORKER_CONTRACT_VERSION,
            "started_at": now_iso(),
            "finished_at": None,
            "duration_seconds": None,
            "returncode": None,
            "early_stopped": False,
            "early_stop_reason": None,
        }
        attempts.append(attempt_record)
        record["attempts"] = attempts
        write_job_record(workspace, job_id, record)
        result, monitor_details = _runtime.resolve("run_monitored_generation_attempt", run_monitored_generation_attempt)(
            command=command,
            prompt_text=prompt_text_for_generation,
            workspace=workspace,
            env=env,
            worker_home=worker_home,
            output_path=output_path,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
            start_time=started_timestamp,
            timeout=timeout,
            allow_latest_recovery=allow_latest_recovery,
            early_stop=early_stop,
            monitor_interval=monitor_interval,
            early_stop_grace=early_stop_grace,
            existing_hashes=existing_output_hashes(workspace, output_path),
        )
        attempt_record["finished_at"] = now_iso()
        attempt_record["duration_seconds"] = duration_seconds(attempt_started_monotonic)
        attempt_record["returncode"] = result.returncode
        attempt_record["early_stopped"] = bool(monitor_details.get("early_stopped"))
        attempt_record["early_stop_reason"] = monitor_details.get("early_stop_reason")
        attempt_record["route"] = "user-codex-home"
        attempt_record["trigger"] = "initial"
        if monitor_details.get("fast_failed"):
            attempt_record["fast_failed"] = True
            attempt_record["fast_fail_signal"] = monitor_details.get("fast_fail_signal")
        if monitor_details.get("termination"):
            attempt_record["termination"] = monitor_details["termination"]
        if monitor_details.get("timed_out"):
            attempt_record["timed_out"] = True
        combined = "\n".join(
            [
                result.stdout or "",
                result.stderr or "",
                output_message.read_text(encoding="utf-8", errors="replace") if output_message.exists() else "",
            ]
        )
        last_combined_text = combined
        processing_rejection = detect_disallowed_processing(combined)
        recursive_flags = recursive_worker_output_flags(combined)
        if recursive_flags:
            processing_rejection = "recursive worker output detected: Codex worker attempted task orchestration instead of direct image generation"
        rejected_output = None
        if processing_rejection and output_path.exists() and output_path.stat().st_size > 0:
            rejected_output = quarantine_output(workspace, output_path, ".rejected")
        recovered_from = str(monitor_details.get("recovered_from") or "") or None
        ambiguous_recovery = False
        if not processing_rejection and not recovered_from:
            try:
                recovered_from = recover_generated_image(
                    workspace,
                    output_path,
                    result,
                    output_message,
                    worker_home,
                    started_timestamp,
                    allow_latest_recovery,
                    existing_output_hashes(workspace, output_path),
                )
            except RuntimeError as error:
                if not str(error).startswith("ambiguous_recovery:"):
                    raise
                ambiguous_recovery = True
                attempt_record["failure_class"] = "ambiguous_recovery"
                attempt_record["failure_message"] = str(error)
        attempt_record["recovered_from"] = recovered_from
        attempt_record["recovered"] = bool(recovered_from)
        if attempt_record["early_stopped"]:
            record["early_stopped"] = True
            record["early_stop_reason"] = attempt_record["early_stop_reason"]
        if processing_rejection:
            attempt_record["processing_rejection"] = processing_rejection
        if recursive_flags:
            attempt_record["recursive_worker_output"] = recursive_flags
        if rejected_output:
            attempt_record["rejected_output"] = rejected_output
        write_job_record(workspace, job_id, record)
        if ambiguous_recovery:
            record["failure_class"] = "ambiguous_recovery"
            record["failure_message"] = "Multiple new worker images were found; deterministic recovery refused to guess."
            retry_skipped_reason = "ambiguous_recovery requires a fresh batch requeue"
            write_job_record(workspace, job_id, record)
            break
        if processing_rejection:
            break
        if output_path.exists() and output_path.stat().st_size > 0:
            break
        failure = (
            {"class": "provider_network_error", "message": "Image provider reported a whitelisted network failure.", "generated_candidates": []}
            if monitor_details.get("fast_failed")
            else classify_generation_failure(result, worker_home, attempt_started_timestamp, output_path, combined)
        )
        attempt_record["failure_class"] = failure["class"]
        if failure["class"] in NON_RETRYABLE_FAILURE_CLASSES:
            retry_skipped_reason = f"{failure['class']} is non-retryable"
            record["retry_skipped_reason"] = retry_skipped_reason
            record["failure_class"] = failure["class"]
            record["failure_message"] = failure["message"]
            record["generated_candidates"] = failure.get("generated_candidates", [])
            write_job_record(workspace, job_id, record)
            break
        if attempt < max_attempts:
            delay = retry_delay_seconds(attempt, retry_base, retry_max)
            if delay:
                time.sleep(delay)
    assert result is not None
    logs = workspace / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout_log.write_text(result.stdout or "", encoding="utf-8")
    stderr_log.write_text(result.stderr or "", encoding="utf-8")
    recursive_attempts = [
        attempt for attempt in attempts
        if isinstance(attempt, dict) and attempt.get("recursive_worker_output")
    ]
    processing_attempts = [
        attempt for attempt in attempts
        if isinstance(attempt, dict) and attempt.get("processing_rejection")
    ]
    if recursive_attempts or processing_attempts:
        status = "blocked_non_retryable"
    else:
        status = "done" if output_path.exists() and output_path.stat().st_size > 0 else "failed"
    record["status"] = status
    record["returncode"] = result.returncode
    record["finished_at"] = now_iso()
    record["duration_seconds"] = duration_seconds(job_started_monotonic)
    if previous_output:
        record["previous_output"] = previous_output
    if status == "done":
        record["bytes"] = output_path.stat().st_size
        output_sha256 = file_hash(output_path)
        record["output_sha256"] = output_sha256
        if attempts:
            attempts[-1]["output_sha256"] = output_sha256
            attempts[-1]["binding"] = {
                "job_id": job_id,
                "prompt_sha256": record["prompt_sha256"],
                "executed_prompt_sha256": record["executed_prompt_sha256"],
                "worker_contract_version": record["worker_contract_version"],
                "output_sha256": output_sha256,
                "worker_home": "user-codex-home",
                "attempt": attempts[-1].get("attempt"),
            }
    else:
        if recursive_attempts:
            failure = {
                "class": "recursive_worker_output",
                "message": "Codex worker attempted task orchestration instead of direct image generation.",
                "generated_candidates": [],
            }
        elif processing_attempts:
            failure = {
                "class": "post_processing_rejected",
                "message": "Codex worker reported or attempted post-generation processing; regenerate directly with image-2.",
                "generated_candidates": [],
            }
        elif retry_skipped_reason and record.get("failure_class"):
            failure = {
                "class": str(record.get("failure_class")),
                "message": str(record.get("failure_message") or "Generation failed with a non-retryable class."),
                "generated_candidates": record.get("generated_candidates", []),
            }
        else:
            failure = classify_generation_failure(result, worker_home, started_timestamp, output_path, last_combined_text)
            if attempts and attempts[-1].get("fast_failed"):
                failure = {"class": "provider_network_error", "message": "Image provider reported a whitelisted network failure.", "generated_candidates": []}
        record["failure_class"] = failure["class"]
        record["failure_message"] = failure["message"]
        record["generated_candidates"] = failure.get("generated_candidates", [])
        if retry_skipped_reason:
            record["retry_skipped_reason"] = retry_skipped_reason
        if attempts:
            attempts[-1]["failure_class"] = failure["class"]
        record["error"] = result.stderr or result.stdout or "Codex generation did not produce the expected output file."
    write_job_record(workspace, job_id, record)
    set_job_status(workspace, job_id, {
        "status": status,
        "output": rel_to_workspace(workspace, output_path),
        "job_record": rel_to_workspace(workspace, job_record_path(workspace, job_id)),
        **({"error": record.get("error")} if status != "done" else {}),
    })
    return record


def build_timing_summary(
    *,
    results: list[dict[str, Any]],
    batch_started_at: str,
    batch_finished_at: str,
    batch_duration_seconds: float,
    parallel_requested: int,
    parallel_effective: int,
) -> dict[str, Any]:
    jobs_summary: list[dict[str, Any]] = []
    failure_classes: dict[str, int] = {}
    recovered_count = 0
    early_stopped_count = 0
    slowest_job: dict[str, Any] | None = None
    launch_timestamps: list[float] = []
    launch_by_timestamp: dict[float, str] = {}
    for result in results:
        attempts = result.get("attempts") if isinstance(result.get("attempts"), list) else []
        recovered = any(bool(attempt.get("recovered_from")) for attempt in attempts if isinstance(attempt, dict))
        early_stopped = bool(result.get("early_stopped")) or any(
            bool(attempt.get("early_stopped")) for attempt in attempts if isinstance(attempt, dict)
        )
        if recovered:
            recovered_count += 1
        if early_stopped:
            early_stopped_count += 1
        failure_class = result.get("failure_class")
        if failure_class:
            key = str(failure_class)
            failure_classes[key] = failure_classes.get(key, 0) + 1
        duration = result.get("duration_seconds")
        job_summary = {
            "id": str(result.get("id") or ""),
            "status": str(result.get("status") or ""),
            "duration_seconds": duration if isinstance(duration, (int, float)) else None,
            "attempt_count": len(attempts),
            "early_stopped": early_stopped,
            "early_stop_reason": result.get("early_stop_reason") if early_stopped else None,
            "recovered": recovered,
            "failure_class": failure_class,
            "returncode": result.get("returncode"),
        }
        jobs_summary.append(job_summary)
        if isinstance(job_summary["duration_seconds"], (int, float)):
            if slowest_job is None or float(job_summary["duration_seconds"]) > float(slowest_job.get("duration_seconds") or 0):
                slowest_job = dict(job_summary)
        launch_timestamp = iso_to_timestamp(result.get("launch_started_at"))
        if launch_timestamp is not None:
            launch_timestamps.append(launch_timestamp)
            launch_by_timestamp[launch_timestamp] = str(result.get("id") or "")
    first_launch = min(launch_timestamps) if launch_timestamps else None
    last_launch = max(launch_timestamps) if launch_timestamps else None
    fanout_window = {
        "first_job_started_at": dt.datetime.fromtimestamp(first_launch, dt.timezone.utc).isoformat().replace("+00:00", "Z") if first_launch else None,
        "last_job_started_at": dt.datetime.fromtimestamp(last_launch, dt.timezone.utc).isoformat().replace("+00:00", "Z") if last_launch else None,
        "duration_seconds": round(max(0.0, last_launch - first_launch), 3) if first_launch is not None and last_launch is not None else 0.0,
        "first_job_id": launch_by_timestamp.get(first_launch) if first_launch is not None else None,
        "last_job_id": launch_by_timestamp.get(last_launch) if last_launch is not None else None,
    }
    return {
        "batch": {
            "started_at": batch_started_at,
            "finished_at": batch_finished_at,
            "duration_seconds": batch_duration_seconds,
        },
        "fanout_window": fanout_window,
        "parallel": {
            "requested": parallel_requested,
            "effective": parallel_effective,
        },
        "slowest_job": slowest_job,
        "recovered_jobs": recovered_count,
        "early_stopped_jobs": early_stopped_count,
        "failure_classes": failure_classes,
        "jobs": jobs_summary,
    }


def batch_circuit_breaker_trigger(results: list[dict[str, Any]], threshold: int) -> str | None:
    if threshold <= 0 or len(results) < threshold:
        return None
    first_results = results[:threshold]
    if any(str(result.get("status") or "") == "done" for result in results):
        return None
    failure_classes = [str(result.get("failure_class") or "") for result in first_results]
    if not failure_classes or any(item not in BATCH_CIRCUIT_BREAKER_FAILURE_CLASSES for item in failure_classes):
        return None
    return failure_classes[0] if len(set(failure_classes)) == 1 else "codex_transport_failure"


def block_jobs_for_circuit_breaker(workspace: Path, jobs: list[dict[str, Any]], trigger_class: str) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    message = f"Batch circuit breaker tripped after uniform transport failures: {trigger_class}."
    for job in jobs:
        job_id = str(job.get("id") or "")
        record = {
            "id": job_id,
            "status": "blocked",
            "failure_class": "batch_circuit_breaker",
            "failure_message": message,
            "error": message,
            "finished_at": now_iso(),
            "duration_seconds": None,
            "attempts": [],
            "early_stopped": False,
            "early_stop_reason": None,
        }
        set_job_status(workspace, job_id, {"status": "blocked", "failure_class": "batch_circuit_breaker", "error": message})
        write_job_record(workspace, job_id, record)
        blocked.append(record)
    return blocked
