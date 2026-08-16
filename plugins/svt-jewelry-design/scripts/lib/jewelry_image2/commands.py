from __future__ import annotations

import argparse
import concurrent.futures
import json
import shlex
import sys
import time
from pathlib import Path
from typing import Any

from lib.jewelry_image2 import _runtime
from lib.jewelry_image2.preflight import validate_request_readiness
from lib.run_path_guard import active_task_id_from_args
from lib.jewelry_image2.common import (
    DEFAULT_ASSETS,
    DEFAULT_REPORT,
    DEFAULT_VIDEO_ASSETS,
    FAST_FAIL_NETWORK_SIGNALS,
    IMAGE_SUFFIXES,
    duration_seconds,
    guard_read_path,
    guard_write_path,
    guarded_workspace,
    image2_provider_route_issues,
    now_iso,
    read_json,
    rel_to_workspace,
    safe_id,
    step_echo,
    write_json,
)
from lib.jewelry_image2.generation import (
    batch_circuit_breaker_trigger,
    block_jobs_for_circuit_breaker,
    build_timing_summary,
    classify_generation_exception,
    run_generation_job,
)
from lib.jewelry_image2.jobs import (
    check_runner_snapshot,
    enforce_registration_uniqueness,
    ensure_design_task_for_workspace,
    ensure_workspace,
    jobs_path,
    load_jobs,
    load_state,
    mark_abandoned_batch_artifacts,
    normalize_job_payload,
    prepare_codex_home,
    reject_known_registration_collisions,
    save_jobs,
    save_state,
    selected_jobs,
    set_job_status,
    state_path,
    upsert_job,
    validate_job_payloads_before_persist,
    validate_static_job_contract,
    workspace_file,
    write_job_record,
)
from lib.jewelry_image2.report import (
    asset_record,
    progress_line,
    unique_existing_references,
    video_assets_from_results,
    write_preview_html,
)


SCRIPT_DIR = Path(__file__).resolve().parents[2]
JDC_IMAGE2_COMMAND = f"node {json.dumps(str(SCRIPT_DIR / 'jdc.mjs'))} image2"


def command_validate_request(args: argparse.Namespace) -> int:
    result = validate_request_readiness(
        requested_count=args.requested_count,
        output_shape=args.output_shape,
        outputs=args.output or [],
        references=args.reference or [],
        reference_base=Path.cwd(),
        provider=args.provider,
        explicit_provider_request=bool(args.explicit_provider_request),
        provider_status=args.provider_status,
        codex_home=Path(args.codex_home).expanduser(),
    )
    step_echo(
        "image2.prepare",
        "done" if result["ok"] else "blocked",
        "Validate design request readiness",
        f"status={result['status']} requested_count={result['requested_count']}",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def command_init(args: argparse.Namespace) -> int:
    workspace = guarded_workspace(args)
    step_echo("image2.prepare", "running", "Prepare image-2 workspace", f"workspace={workspace}")
    task = ensure_design_task_for_workspace(workspace, args)
    ensure_workspace(workspace)
    state = {
        "version": 1,
        "title": args.title or "Jewelry Image-2 Task",
        "status": "initialized",
        "provider": "codex-cli",
        "image_model": "gpt-image-2",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    if not state_path(workspace).exists() or args.force:
        save_state(workspace, state)
    if not jobs_path(workspace).exists() or args.force:
        save_jobs(workspace, {"version": 1, "jobs": []})
    step_echo("image2.prepare", "done", "Prepare image-2 workspace", f"workspace={workspace}")
    print(json.dumps({
        "task_id": task.get("task_id") if task else None,
        "task_documents": str(SCRIPT_DIR.parent / "artifacts" / "design-tasks" / task["task_id"]) if task else None,
        "workspace": str(workspace),
        "state": str(state_path(workspace)),
    }, ensure_ascii=False))
    return 0


def command_add_job(args: argparse.Namespace) -> int:
    workspace = guarded_workspace(args)
    active_task_id = active_task_id_from_args(args)
    payload = {
        "id": args.job_id,
        "title": args.title,
        "kind": args.kind,
        "ratio": args.ratio,
        "prompt": args.prompt,
        "prompt_file": args.prompt_file,
        "output": args.output,
        "references": args.reference or [],
        "allow_duplicate_prompt": bool(args.allow_duplicate_prompt),
    }
    if args.timeout is not None:
        payload["timeout"] = args.timeout
    validate_job_payloads_before_persist(workspace, [payload])
    reject_known_registration_collisions(workspace, [payload])
    step_echo("image2.prepare", "running", "Prepare image-2 job", f"job_id={safe_id(args.job_id)} workspace={workspace}")
    ensure_workspace(workspace)
    job = normalize_job_payload(workspace, payload, active_task_id)
    enforce_registration_uniqueness(workspace, [job])
    upsert_job(workspace, job)
    step_echo("image2.prepare", "done", "Prepare image-2 job", f"job_id={job['id']} workspace={workspace}")
    print(json.dumps(job, ensure_ascii=False))
    return 0


def command_add_jobs(args: argparse.Namespace) -> int:
    workspace = guarded_workspace(args)
    active_task_id = active_task_id_from_args(args)
    input_path = Path(args.input).expanduser()
    guard_read_path(input_path, active_task_id, "image2 jobs input")
    payload = read_json(input_path, [])
    jobs = payload.get("jobs") if isinstance(payload, dict) else payload
    if not isinstance(jobs, list):
        raise ValueError("input must be a JSON list or an object with jobs")
    if not all(isinstance(item, dict) for item in jobs):
        raise ValueError("every job must be an object")
    validate_job_payloads_before_persist(workspace, jobs)
    reject_known_registration_collisions(workspace, jobs)
    step_echo("image2.prepare", "running", "Prepare image-2 jobs", f"input={args.input} workspace={workspace}")
    ensure_workspace(workspace)
    normalized_jobs = []
    for item in jobs:
        if not isinstance(item, dict):
            raise ValueError("every job must be an object")
        job = normalize_job_payload(workspace, item, active_task_id)
        normalized_jobs.append(job)
    enforce_registration_uniqueness(workspace, normalized_jobs)
    added = []
    for job in normalized_jobs:
        upsert_job(workspace, job)
        added.append(job["id"])
    step_echo("image2.prepare", "done", "Prepare image-2 jobs", f"count={len(added)} workspace={workspace}")
    print(json.dumps({"added": added}, ensure_ascii=False))
    return 0


def command_validate_jobs(args: argparse.Namespace) -> int:
    workspace = guarded_workspace(args, write=False)
    active_task_id = active_task_id_from_args(args)
    ensure_workspace(workspace)
    jobs = selected_jobs(workspace, args.job_id, args.only or "", args.job_prefix, args.job_manifest)
    seen_outputs: dict[str, str] = {}
    items = [
        validate_static_job_contract(workspace, job, active_task_id=active_task_id, seen_outputs=seen_outputs)
        for job in jobs
    ]
    issues: list[str] = []
    if args.requested_count is not None and len(items) != int(args.requested_count):
        issues.append(f"requested_count_mismatch: expected {int(args.requested_count)} selected {len(items)}")
    if not items:
        issues.append("no_jobs_selected")
    for item in items:
        for issue in item["issues"]:
            issues.append(f"{item['job_id']}:{issue}")
    status = "passed" if not issues else "failed"
    selector = ""
    if args.job_manifest:
        selector = f" --job-manifest {shlex.quote(args.job_manifest)}"
    elif args.job_prefix:
        selector = f" --job-prefix {shlex.quote(args.job_prefix)}"
    elif args.job_id:
        selector = f" --job-id {shlex.quote(args.job_id)}"
    payload = {
        "schema_version": 1,
        "kind": "jewelry_image_static_job_validation",
        "status": status,
        "workspace": str(workspace),
        "selected_count": len(items),
        "requested_count": args.requested_count,
        "issues": issues,
        "items": items,
        "recommended_next_command": (
            f"{JDC_IMAGE2_COMMAND} generate --workspace "
            f"{json.dumps(rel_to_workspace(Path.cwd(), workspace))}"
            f"{selector} --only pending,failed --parallel {max(1, min(4, len(items)))}"
        ),
    }
    step_echo("image2.prepare", "done" if not issues else "blocked", "Validate image-2 jobs", f"status={status} count={len(items)}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


def command_generate(args: argparse.Namespace) -> int:
    workspace = guarded_workspace(args)
    active_task_id = active_task_id_from_args(args)
    batch_started_at = now_iso()
    batch_started_monotonic = time.monotonic()
    jobs = selected_jobs(workspace, args.job_id, args.only, args.job_prefix, args.job_manifest)
    if not jobs:
        step_echo("image2.generate", "skipped", "Generate image-2 jobs", "no matching jobs")
        print(json.dumps({"status": "noop", "message": "no matching jobs"}, ensure_ascii=False))
        return 0
    has_external_route = any(image2_provider_route_issues(job) for job in jobs)
    request_readiness = validate_request_readiness(
        requested_count=len(jobs),
        output_shape="independent_images",
        outputs=[str(job.get("output") or f"outputs/{safe_id(str(job.get('id') or 'job'))}.png") for job in jobs],
        references=[str(item) for job in jobs for item in job.get("references", []) or []],
        reference_base=workspace,
        provider="codex-cli",
        provider_status="auto",
        codex_home=Path(args.codex_home).expanduser(),
        check_provider=not args.dry_run and not has_external_route,
    )
    if not request_readiness["ok"]:
        step_echo("image2.generate", "blocked", "Validate generation readiness", "request readiness failed before workspace writes")
        print(json.dumps(request_readiness, ensure_ascii=False, indent=2))
        return 1
    step_echo("image2.generate", "running", "Generate image-2 jobs", f"workspace={workspace}")
    ensure_workspace(workspace)
    snapshot_warnings = check_runner_snapshot(workspace)
    for warning in snapshot_warnings:
        step_echo("image2.generate", "warning", "Runner changed", warning)
    preview_path = _runtime.resolve("write_preview_html", write_preview_html)(workspace)
    if not load_state(workspace).get("last_generation"):
        step_echo("image2.preview", "ready", "Live design preview", str(preview_path))
    initial_job_ids = {
        str(job.get("id") or "")
        for job in load_jobs(workspace).get("jobs", [])
        if isinstance(job, dict) and job.get("id")
    }
    selected_job_ids = {str(job.get("id") or "") for job in jobs if job.get("id")}
    route_blocks: list[dict[str, Any]] = []
    for job in jobs:
        job_id = str(job.get("id") or "")
        issues = image2_provider_route_issues(job)
        if not issues:
            continue
        message = "Job declares an explicit external provider/plugin route and cannot be generated by the local image-2 runner."
        record = {
            "id": job_id,
            "status": "blocked",
            "failure_class": "provider_route_forbidden",
            "failure_message": message,
            "issues": issues,
            "finished_at": now_iso(),
            "duration_seconds": None,
            "attempts": [],
            "early_stopped": False,
            "early_stop_reason": None,
        }
        set_job_status(workspace, job_id, {"status": "blocked", "failure_class": "provider_route_forbidden", "error": message, "provider_route_issues": issues})
        write_job_record(workspace, job_id, record)
        route_blocks.append({"job_id": job_id, "issues": issues})
    if route_blocks:
        state = load_state(workspace)
        state["status"] = "blocked"
        state["last_generation"] = {
            "status": "blocked",
            "failure_class": "provider_route_forbidden",
            "blocked_jobs": route_blocks,
            "updated_at": now_iso(),
        }
        save_state(workspace, state)
        step_echo("image2.generate", "blocked", "Generate image-2 jobs", f"provider_route_forbidden count={len(route_blocks)}")
        print(json.dumps({"status": "blocked", "failure_class": "provider_route_forbidden", "blocked_jobs": route_blocks}, ensure_ascii=False, indent=2))
        return 1
    base_codex_home = _runtime.resolve("prepare_codex_home", prepare_codex_home)(workspace, source_home=Path(args.codex_home).expanduser())
    results = []
    failures = 0
    state = load_state(workspace)
    generation_warnings: list[str] = []
    execution_plan = state.get("execution_plan") if isinstance(state.get("execution_plan"), dict) else {}
    planned_jobs = int(execution_plan.get("planned_jobs") or 0) if isinstance(execution_plan, dict) else 0
    last_generation = state.get("last_generation") if isinstance(state.get("last_generation"), dict) else {}
    previous_real_generation = bool(last_generation) and not bool(last_generation.get("dry_run"))
    first_real_generation = not args.dry_run and not previous_real_generation
    if first_real_generation and planned_jobs > 0 and len(jobs) < planned_jobs:
        warning = (
            f"generating {len(jobs)} of {planned_jobs} planned jobs - "
            "queue all independent jobs before the first generate"
        )
        generation_warnings.append(warning)
        step_echo("image2.generate", "running", "Generate image-2 jobs", warning)
    state["status"] = "generating" if not args.dry_run else "dry_run"
    save_state(workspace, state)
    parallel_requested = max(1, int(args.parallel or 1))
    parallel_effective = min(parallel_requested, len(jobs))
    circuit_threshold = 0 if args.no_circuit_breaker or args.dry_run else max(1, int(args.circuit_breaker or 0))
    completed_results: list[dict[str, Any]] = []
    circuit_breaker = {"tripped": False}
    if parallel_effective == 1:
        for index, job in enumerate(jobs):
            try:
                result = _runtime.resolve("run_generation_job", run_generation_job)(
                    workspace=workspace,
                    job=job,
                    base_codex_home=base_codex_home,
                    retries=0,
                    timeout=args.timeout,
                    retry_base=args.retry_base,
                    retry_max=args.retry_max,
                    allow_latest_recovery=args.allow_latest_recovery,
                    dry_run=args.dry_run,
                    active_task_id=active_task_id,
                    early_stop=bool(getattr(args, "early_stop", True)),
                    monitor_interval=args.monitor_interval,
                    early_stop_grace=args.early_stop_grace,
                )
            except Exception as error:
                job_id = str(job.get("id"))
                failure_class = classify_generation_exception(error)
                result = {
                    "id": job_id,
                    "status": "failed",
                    "failure_class": failure_class,
                    "error": str(error),
                    "finished_at": now_iso(),
                    "duration_seconds": None,
                    "attempts": [],
                    "early_stopped": False,
                    "early_stop_reason": None,
                }
                set_job_status(workspace, job_id, {"status": "failed", "failure_class": failure_class, "error": str(error)})
                write_job_record(workspace, job_id, result)
            results.append(result)
            completed_results.append(result)
            progress_line(workspace, result, len(completed_results), len(jobs), requeued=result.get("status") != "done" and not args.dry_run, event_command=args.job_event_command)
            _runtime.resolve("write_preview_html", write_preview_html)(workspace)
            if result.get("status") != "done" and not args.dry_run:
                failures += 1
            trigger_class = batch_circuit_breaker_trigger(completed_results, circuit_threshold)
            if trigger_class:
                remaining_jobs = jobs[index + 1:]
                blocked_records = block_jobs_for_circuit_breaker(workspace, remaining_jobs, trigger_class)
                results.extend(blocked_records)
                failures += len(blocked_records)
                circuit_breaker = {
                    "tripped": True,
                    "trigger_class": trigger_class,
                    "completed_failures": circuit_threshold,
                    "blocked_jobs": [str(record.get("id") or "") for record in blocked_records],
                    "note": "In-flight jobs are allowed to finish naturally; thread cancellation of running jobs is out of scope.",
                }
                break
    else:
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=parallel_effective,
            thread_name_prefix="jewelry-image2-fanout",
        )
        pending_iter = iter(jobs)
        future_to_job: dict[concurrent.futures.Future[dict[str, Any]], dict[str, Any]] = {}
        started_job_ids: set[str] = set()

        def submit_next_job() -> bool:
            try:
                job = next(pending_iter)
            except StopIteration:
                return False
            future = executor.submit(
                _runtime.resolve("run_generation_job", run_generation_job),
                workspace=workspace,
                job=job,
                base_codex_home=base_codex_home,
                retries=0,
                timeout=args.timeout,
                retry_base=args.retry_base,
                retry_max=args.retry_max,
                allow_latest_recovery=args.allow_latest_recovery,
                dry_run=args.dry_run,
                active_task_id=active_task_id,
                early_stop=bool(getattr(args, "early_stop", True)),
                monitor_interval=args.monitor_interval,
                early_stop_grace=args.early_stop_grace,
            )
            future_to_job[future] = job
            started_job_ids.add(str(job.get("id") or ""))
            return True

        try:
            for _ in range(parallel_effective):
                submit_next_job()
            while future_to_job:
                done, _ = concurrent.futures.wait(future_to_job, return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    job = future_to_job.pop(future)
                    try:
                        result = future.result()
                    except Exception as error:
                        job_id = str(job.get("id"))
                        failure_class = classify_generation_exception(error)
                        result = {
                            "id": job_id,
                            "status": "failed",
                            "failure_class": failure_class,
                            "error": str(error),
                            "finished_at": now_iso(),
                            "duration_seconds": None,
                            "attempts": [],
                            "early_stopped": False,
                            "early_stop_reason": None,
                        }
                        set_job_status(workspace, job_id, {"status": "failed", "failure_class": failure_class, "error": str(error)})
                        write_job_record(workspace, job_id, result)
                    results.append(result)
                    completed_results.append(result)
                    progress_line(workspace, result, len(completed_results), len(jobs), requeued=result.get("status") != "done" and not args.dry_run, event_command=args.job_event_command)
                    _runtime.resolve("write_preview_html", write_preview_html)(workspace)
                    if result.get("status") != "done" and not args.dry_run:
                        failures += 1
                if not circuit_breaker["tripped"]:
                    trigger_class = batch_circuit_breaker_trigger(completed_results, circuit_threshold)
                    if trigger_class:
                        not_started_jobs = [job for job in jobs if str(job.get("id") or "") not in started_job_ids]
                        blocked_records = block_jobs_for_circuit_breaker(workspace, not_started_jobs, trigger_class)
                        results.extend(blocked_records)
                        failures += len(blocked_records)
                        circuit_breaker = {
                            "tripped": True,
                            "trigger_class": trigger_class,
                            "completed_failures": circuit_threshold,
                            "blocked_jobs": [str(record.get("id") or "") for record in blocked_records],
                            "note": "In-flight jobs are allowed to finish naturally; thread cancellation of running jobs is out of scope.",
                        }
                if not circuit_breaker["tripped"]:
                    while len(future_to_job) < parallel_effective and submit_next_job():
                        pass
        finally:
            executor.shutdown(wait=True, cancel_futures=True)
    if not args.dry_run and not circuit_breaker.get("tripped"):
        result_by_id = {str(result.get("id") or ""): result for result in results}
        jobs_by_id = {str(job.get("id") or ""): job for job in jobs}
        for job_id, initial in list(result_by_id.items()):
            if initial.get("status") == "done" or initial.get("status") == "blocked_non_retryable" or initial.get("failure_class") not in {"provider_no_output", "provider_timeout", "provider_failure", "provider_network_error"}:
                continue
            combined_attempts = list(initial.get("attempts") or [])
            latest = initial
            for round_number in range(1, max(1, int(args.attempt_budget))):
                fresh_home = workspace / ".codex-home-requeue" / f"{safe_id(job_id)}-{round_number}"
                latest = _runtime.resolve("run_generation_job", run_generation_job)(
                    workspace=workspace, job=jobs_by_id[job_id], base_codex_home=fresh_home,
                    retries=0, timeout=args.timeout, retry_base=args.retry_base, retry_max=args.retry_max,
                    allow_latest_recovery=args.allow_latest_recovery, dry_run=False,
                    active_task_id=active_task_id,
                    early_stop=bool(getattr(args, "early_stop", True)), monitor_interval=args.monitor_interval,
                    early_stop_grace=args.early_stop_grace,
                )
                new_attempts = list(latest.get("attempts") or [])
                for attempt in new_attempts:
                    attempt["attempt"] = len(combined_attempts) + 1
                    attempt["trigger"] = "batch_requeue"
                    attempt["requeued"] = True
                combined_attempts.extend(new_attempts)
                latest["attempts"] = combined_attempts
                latest["requeued"] = True
                latest["requeue_round"] = round_number
                write_job_record(workspace, job_id, latest)
                progress_line(workspace, latest, len(completed_results), len(jobs), requeued=latest.get("status") != "done", event_command=args.job_event_command)
                _runtime.resolve("write_preview_html", write_preview_html)(workspace)
                if latest.get("status") == "done":
                    break
            results[results.index(initial)] = latest
        failures = sum(1 for result in results if result.get("status") != "done")
    state = load_state(workspace)
    state["status"] = "failed" if failures else ("ready" if not args.dry_run else "dry_run")
    batch_finished_at = now_iso()
    cleanup_summary = mark_abandoned_batch_artifacts(
        workspace,
        selected_job_ids=selected_job_ids,
        initial_job_ids=initial_job_ids,
    )
    timing_summary = build_timing_summary(
        results=results,
        batch_started_at=batch_started_at,
        batch_finished_at=batch_finished_at,
        batch_duration_seconds=duration_seconds(batch_started_monotonic),
        parallel_requested=parallel_requested,
        parallel_effective=parallel_effective,
    )
    state["last_generation"] = {
        "updated_at": batch_finished_at,
        "count": len(results),
        "failures": failures,
        "parallel": parallel_requested,
        "parallel_effective": parallel_effective,
        "dry_run": bool(args.dry_run),
        "retries": 0,
        "attempt_budget": args.attempt_budget,
        "retry_policy": {"initial_attempts": 1, "requeue": "batch_end_fresh_worker", "network_fast_fail_signals": list(FAST_FAIL_NETWORK_SIGNALS)},
        "retry_base": args.retry_base,
        "retry_max": args.retry_max,
        "latest_recovery": bool(args.allow_latest_recovery),
        "early_stop": bool(getattr(args, "early_stop", True)),
        "monitor_interval": args.monitor_interval,
        "early_stop_grace": args.early_stop_grace,
        "circuit_breaker": circuit_breaker,
        "warnings": generation_warnings + snapshot_warnings,
        "timing_summary": timing_summary,
        "cleanup": cleanup_summary,
    }
    save_state(workspace, state)
    generate_status = "blocked" if circuit_breaker.get("tripped") else ("failed" if failures else "done")
    detail = f"count={len(results)} failures={failures} parallel={parallel_requested}/{parallel_effective}"
    if circuit_breaker.get("tripped"):
        detail = f"batch_circuit_breaker trigger={circuit_breaker.get('trigger_class')} blocked={len(circuit_breaker.get('blocked_jobs') or [])}"
    step_echo(
        "image2.generate",
        generate_status,
        "Generate image-2 jobs",
        detail,
    )
    print(json.dumps({"results": results, "failures": failures, "circuit_breaker": circuit_breaker, "timing_summary": timing_summary, "cleanup": cleanup_summary}, ensure_ascii=False, indent=2))
    sys.stdout.flush()
    sys.stderr.flush()
    return 1 if failures else 0


def command_assemble_markdown(args: argparse.Namespace) -> int:
    workspace = guarded_workspace(args)
    active_task_id = active_task_id_from_args(args)
    step_echo("image2.assemble", "running", "Assemble image-2 report", f"workspace={workspace}")
    ensure_workspace(workspace)
    output_rel = args.output or DEFAULT_REPORT
    output_path = workspace_file(workspace, output_rel)
    assets_path = workspace_file(workspace, args.assets or DEFAULT_ASSETS)
    video_assets_path = workspace_file(workspace, args.video_assets or DEFAULT_VIDEO_ASSETS)
    guard_write_path(output_path, active_task_id, "image2 report")
    guard_write_path(assets_path, active_task_id, "image2 assets manifest")
    guard_write_path(video_assets_path, active_task_id, "image2 video assets manifest")
    data = load_jobs(workspace)
    state = load_state(workspace)
    title = args.title or state.get("title") or "Jewelry Image-2 Report"
    generated_at = now_iso()
    jobs = [job for job in data.get("jobs", []) if isinstance(job, dict)]
    lines = [
        f"# {title}",
        "",
        "## 给设计师的快速导览",
        "",
        f"本报告整理本轮珠宝视觉提案，包含 {len(jobs)} 个静态设计方向。主石、材质和结构约束以每张图对应的生成提示为准；展示顺序按方案编号排列，便于和客户沟通取舍。",
        "",
    ]
    assets = []

    cover_path = workspace_file(workspace, args.cover) if args.cover else None
    if cover_path:
        guard_read_path(cover_path, active_task_id, "image2 cover")
    if cover_path and cover_path.exists() and cover_path.is_file() and cover_path.suffix.lower() in IMAGE_SUFFIXES:
        cover_title = args.cover_title or "封面设计"
        cover_anchor = "SVT_JEWELRY_COVER"
        lines += [f"## {cover_title}", "", cover_anchor, "", f"![{cover_title}]({rel_to_workspace(workspace, cover_path)})", ""]
        assets.append(asset_record(
            workspace,
            job_id="cover",
            title=cover_title,
            path=cover_path,
            anchor=cover_anchor,
            role="cover",
        ))

    references = unique_existing_references(workspace, jobs, active_task_id)
    if references:
        lines += [
            "## 参考图",
            "",
            "下列图片为本轮设计的来源参考，用于说明造型、色彩和结构延展关系；最终设计不复制其中的品牌、文字或海报信息。",
            "",
        ]
        for index, reference_path in enumerate(references, start=1):
            reference_title = f"参考图 {index}"
            reference_anchor = f"SVT_JEWELRY_REFERENCE_{index:02d}"
            lines += [
                f"### {reference_title}",
                "",
                reference_anchor,
                "",
                f"![{reference_title}]({rel_to_workspace(workspace, reference_path)})",
                "",
            ]
            assets.append(asset_record(
                workspace,
                job_id=f"reference-{index:02d}",
                title=reference_title,
                path=reference_path,
                anchor=reference_anchor,
                role="reference",
            ))

    lines += ["## 设计方向", ""]
    for job in jobs:
        job_id = str(job.get("id"))
        image_rel = str(job.get("output") or "")
        image_path = workspace_file(workspace, image_rel)
        anchor = f"SVT_JEWELRY_IMAGE_{safe_id(job_id).upper()}"
        title_text = str(job.get("title") or job_id)
        lines += [f"### {title_text}", "", anchor, ""]
        if image_path.exists() and image_path.is_file():
            rel = rel_to_workspace(workspace, image_path)
            lines += [f"![{title_text}]({rel})", ""]
            exists = True
        else:
            lines += [f"> Image pending: `{image_rel}`", ""]
            exists = False
        status = str(job.get("status") or "")
        if status and status != "done":
            lines += [f"- 当前状态：`{status}`", ""]
        elif job.get("kind"):
            lines += [f"- 类型：{job.get('kind')}", ""]
        asset = asset_record(workspace, job_id=job_id, title=title_text, path=image_path, anchor=anchor)
        asset["exists"] = exists
        assets.append(asset)
    video_assets = video_assets_from_results(workspace)
    if video_assets:
        lines += ["## 视频成片", ""]
        for asset in video_assets:
            lines += [
                f"### {asset.get('title') or asset.get('job_id')}",
                "",
                str(asset.get("anchor") or ""),
                "",
            ]
            if asset.get("exists"):
                lines += [
                    f"- 本地视频：`{asset.get('path')}`",
                    f"- 规格：`{asset.get('width')}x{asset.get('height')}`，`{asset.get('fps')}fps`，`{asset.get('duration')}s`，`{asset.get('format')}`",
                ]
            if asset.get("video_url"):
                lines += [f"- 备用链接：{asset.get('video_url')}"]
            lines += [""]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    write_json(assets_path, {"version": 1, "created_at": generated_at, "markdown": rel_to_workspace(workspace, output_path), "assets": assets})
    write_json(video_assets_path, {"version": 1, "created_at": generated_at, "markdown": rel_to_workspace(workspace, output_path), "assets": video_assets})
    state["report"] = rel_to_workspace(workspace, output_path)
    state["assets"] = rel_to_workspace(workspace, assets_path)
    state["video_assets"] = rel_to_workspace(workspace, video_assets_path)
    state["status"] = "assembled"
    save_state(workspace, state)
    step_echo(
        "image2.assemble",
        "done",
        "Assemble image-2 report",
        f"images={len(assets)} videos={len(video_assets)} markdown={rel_to_workspace(workspace, output_path)}",
    )
    print(json.dumps({
        "markdown": str(output_path),
        "assets": str(assets_path),
        "video_assets": str(video_assets_path),
        "image_count": len(assets),
        "video_count": len(video_assets),
    }, ensure_ascii=False))
    return 0


def command_status(args: argparse.Namespace) -> int:
    workspace = guarded_workspace(args, write=False)
    state = load_state(workspace)
    jobs = load_jobs(workspace)
    summary = {
        "workspace": str(workspace),
        "state": state,
        "jobs": {
            "total": len(jobs.get("jobs", [])),
            "by_status": {},
        },
    }
    for job in jobs.get("jobs", []):
        if not isinstance(job, dict):
            continue
        status = str(job.get("status") or "unknown")
        summary["jobs"]["by_status"][status] = summary["jobs"]["by_status"].get(status, 0) + 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0
