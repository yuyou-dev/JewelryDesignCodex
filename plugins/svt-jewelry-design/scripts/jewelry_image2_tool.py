#!/usr/bin/env python3
"""Jewelry Codex CLI image-2 runner.

This script is the executable counterpart to the jewelry skills' image-2
contract. It intentionally routes still-image generation through ``codex exec``
with prompt files, local image attachments, a run-local CODEX_HOME, and
recoverable generated image outputs.
"""

from __future__ import annotations

import argparse
import os
import shutil  # re-exported module surface; tests monkeypatch TOOL.shutil
import subprocess  # re-exported module surface; tests monkeypatch TOOL.subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from lib.design_task import DesignTasksService
from lib.jewelry_image2.policy import detect_disallowed_processing
from lib.jewelry_image2.workspace import (
    prepare_codex_home as prepare_codex_home_dir,
    prepare_worker_codex_home as prepare_worker_codex_home_dir,
)
from lib.jewelry_image2.preflight import (
    TINY_PNG_BYTES,
    validate_request_readiness,
)
from lib.run_path_guard import (
    TaskPathGuardError,
    active_task_id_from_args,
    assert_current_task_read_path,
    assert_current_task_write_path,
)
from lib.jewelry_image2 import _runtime
from lib.jewelry_image2.common import (
    IMAGE_SUFFIXES,
    MIN_REVIEW_IMAGE_BYTES,
    MIN_REVIEW_IMAGE_DIMENSION,
    DEFAULT_RETRIES,
    DEFAULT_ATTEMPT_BUDGET,
    FAST_FAIL_NETWORK_SIGNALS,
    DEFAULT_TIMEOUT,
    DEFAULT_MONITOR_INTERVAL,
    DEFAULT_EARLY_STOP_GRACE,
    NON_RETRYABLE_FAILURE_CLASSES,
    BATCH_CIRCUIT_BREAKER_FAILURE_CLASSES,
    PROVIDER_AUTH_FAILURE_PATTERN,
    DEFAULT_DESIGN_RATIO,
    DEFAULT_REPORT,
    DEFAULT_ASSETS,
    DEFAULT_VIDEO_ASSETS,
    JOBS_LOCK,
    IMAGEGEN_FIRST_LINE,
    WORKER_CONTRACT_VERSION,
    EXECUTED_JOB_CONTRACT_FIELDS,
    EXECUTED_RECORD_CONTRACT_FIELDS,
    LOCAL_IMAGE2_ROUTE_VALUES,
    PROVIDER_ROUTE_FIELDS,
    ProviderRouteError,
    DIRECT_IMAGE_WORKER_GUARD,
    DIRECT_IMAGE_WORKER_GUARD_PATTERNS,
    IMAGEGEN_NEGATION_MARKERS,
    DISALLOWED_IMAGEGEN_EXECUTION_PATTERNS,
    RECURSIVE_ORCHESTRATION_COMMAND,
    EXECUTION_LINE,
    EXECUTION_EVENT_KINDS,
    PRESET_RATIO_KIND_TOKENS,
    STEP_PHASE_BY_COMMAND,
    step_value,
    step_echo,
    now_iso,
    duration_seconds,
    normalize_ratio_value,
    infer_ratio_from_prompt,
    kind_uses_default_design_ratio,
    resolve_job_ratio,
    prompt_with_ratio_contract,
    first_nonempty_line,
    validate_imagegen_prompt_contract,
    ensure_imagegen_prompt_contract,
    has_complete_legacy_worker_contract,
    build_executed_prompt,
    declares_executed_prompt_contract,
    truthy_route_flag,
    normalize_route_value,
    image2_provider_route_issues,
    ensure_image2_provider_route_allowed,
    classify_codex_transport_failure,
    classify_provider_auth_failure,
    classify_provider_network_failure,
    recursive_worker_output_flags,
    iso_to_timestamp,
    read_json,
    write_json,
    safe_id,
    workspace_path,
    guarded_workspace,
    guard_write_path,
    guard_read_path,
    rel_to_workspace,
    is_relative_to,
    file_hash,
    text_sha256,
    image_header_metadata,
)
from lib.jewelry_image2.jobs import (
    workspace_file,
    ensure_workspace,
    state_path,
    jobs_path,
    load_state,
    save_state,
    load_jobs,
    save_jobs,
    find_job,
    prompt_path_for_job,
    canonicalize_prompt_file_for_job,
    executed_prompt_path_for_job,
    job_record_path,
    write_job_record,
    job_launch_record,
    prepare_codex_home,
    prepare_worker_codex_home,
    collect_image_inputs,
    runner_hashes,
    check_runner_snapshot,
    request_readiness_error,
    validate_job_payloads_before_persist,
    ensure_design_task_for_workspace,
    normalize_job_payload,
    upsert_job,
    enforce_registration_uniqueness,
    reject_known_registration_collisions,
    job_ids_from_manifest,
    selected_jobs,
    validate_static_job_contract,
    set_job_status,
    mark_abandoned_batch_artifacts,
)
from lib.jewelry_image2.generation import (
    codex_generate_command,
    image_paths_from_text,
    generated_images_after,
    looks_like_image_file,
    stable_generated_image,
    terminate_generation_process,
    run_monitored_generation_attempt,
    classify_generation_failure,
    classify_generation_exception,
    existing_output_hashes,
    quarantine_output,
    recover_generated_image,
    retry_delay_seconds,
    resolved_job_timeout,
    run_generation_job,
    build_timing_summary,
    batch_circuit_breaker_trigger,
    block_jobs_for_circuit_breaker,
)
from lib.jewelry_image2.report import (
    write_preview_html,
    progress_line,
    unique_existing_references,
    asset_record,
    video_assets_from_results,
)
from lib.jewelry_image2.commands import (
    command_validate_request,
    command_init,
    command_add_job,
    command_add_jobs,
    command_validate_jobs,
    command_generate,
    command_assemble_markdown,
    command_status,
)

_runtime.TOOL_GLOBALS = globals()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jewelry Codex CLI image-2 runner.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_active_task_arg(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--active-task-id", dest="active_task_id", default="", help="Guard reads and writes to the current task workspace.")

    validate_request = sub.add_parser(
        "validate-request",
        help="Pure read-only validation of request shape, references, provider route, and login readiness before task creation.",
    )
    validate_request.add_argument("--requested-count", type=int, required=True)
    validate_request.add_argument(
        "--output-shape",
        choices=["independent_images", "single_composed_grid"],
        default="independent_images",
        help="Use single_composed_grid only when the user explicitly requested one grid artifact.",
    )
    validate_request.add_argument("--output", action="append", required=True, help="Planned image output path; repeat once per independent design.")
    validate_request.add_argument("--reference", action="append", help="Existing reference image path; repeat for every required attachment.")
    validate_request.add_argument("--provider", default="codex-cli", help="Current requested provider; defaults to the project-local Codex image-2 route.")
    validate_request.add_argument(
        "--explicit-provider-request",
        action="store_true",
        help="Confirm that the current user explicitly requested the named external provider.",
    )
    validate_request.add_argument(
        "--provider-status",
        choices=["auto", "ready", "not-ready", "unauthorized", "login-required"],
        default="auto",
        help="Readiness supplied by the current external-provider owner; local Codex readiness is inspected read-only.",
    )
    validate_request.add_argument("--codex-home", default=os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"))
    validate_request.set_defaults(func=command_validate_request)

    init = sub.add_parser("init", help="Initialize a persisted jewelry image task media workspace.")
    add_active_task_arg(init)
    init.add_argument("--workspace", required=True)
    init.add_argument("--task-id", default="", help="Stable task id; defaults to the artifacts/runs workspace name.")
    init.add_argument("--title", default="Jewelry Image-2 Task")
    init.add_argument("--goal", default="")
    init.add_argument("--deliverables", default="")
    init.add_argument("--design-direction", default="")
    init.add_argument("--constraints", default="")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)

    add_job = sub.add_parser("add-job", help="Add or update one image generation job.")
    add_active_task_arg(add_job)
    add_job.add_argument("--workspace", required=True)
    add_job.add_argument("--job-id", required=True)
    add_job.add_argument("--title", default="")
    add_job.add_argument("--kind", default="jewelry-image")
    add_job.add_argument("--ratio", default="", help="Optional output aspect ratio. Ordinary jewelry design jobs default to 1:1 when omitted; preset/template jobs should pass their selected ratio.")
    prompt_group = add_job.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file")
    add_job.add_argument("--output", default="")
    add_job.add_argument("--reference", action="append")
    add_job.add_argument("--timeout", type=int, default=None, help="Optional per-job generation timeout in seconds; must be at least 60.")
    add_job.add_argument("--allow-duplicate-prompt", action="store_true", help="Allow an explicitly requested same-prompt variant and record the exception on the job.")
    add_job.set_defaults(func=command_add_job)

    add_jobs = sub.add_parser("add-jobs", help="Add jobs from a JSON list or {jobs: [...]} file.")
    add_active_task_arg(add_jobs)
    add_jobs.add_argument("--workspace", required=True)
    add_jobs.add_argument("--input", required=True)
    add_jobs.set_defaults(func=command_add_jobs)

    validate_jobs = sub.add_parser("validate-jobs", help="Run static job/prompt checks before image generation; faster replacement for ordinary batch dry-run.")
    add_active_task_arg(validate_jobs)
    validate_jobs.add_argument("--workspace", required=True)
    validate_jobs.add_argument("--job-id")
    validate_jobs.add_argument("--job-prefix", help="Select only jobs whose stable id begins with this prefix.")
    validate_jobs.add_argument("--job-manifest", help="Select the exact job ids listed in a workspace-local jobs JSON file.")
    validate_jobs.add_argument("--only", default="", help="Optional comma-separated status filter, for example pending,failed.")
    validate_jobs.add_argument("--requested-count", type=int, default=None)
    validate_jobs.set_defaults(func=command_validate_jobs)

    generate = sub.add_parser("generate", help="Generate pending jobs through codex exec.")
    add_active_task_arg(generate)
    generate.add_argument("--workspace", required=True)
    generate.add_argument("--job-id")
    generate.add_argument("--job-prefix", help="Generate only jobs whose stable id begins with this prefix.")
    generate.add_argument("--job-manifest", help="Generate the exact job ids listed in a workspace-local jobs JSON file.")
    generate.add_argument("--only", default="pending,failed,needs-regenerate")
    generate.add_argument("--codex-home", default=os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"))
    generate.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    generate.add_argument("--attempt-budget", type=int, default=DEFAULT_ATTEMPT_BUDGET, help="Total attempts per job including batch-end requeues; default 3.")
    generate.add_argument("--job-event-command", default="", help="Optional best-effort command receiving each job event as JSON on stdin; failures only emit warning evidence.")
    generate.add_argument("--retry-base", type=float, default=2.0, help="Base seconds for exponential retry backoff.")
    generate.add_argument("--retry-max", type=float, default=30.0, help="Maximum seconds for exponential retry backoff.")
    generate.add_argument("--parallel", type=int, default=8, help="Number of isolated Codex jobs to run concurrently.")
    generate.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    generate.add_argument("--circuit-breaker", type=int, default=3, help="Abort launching more jobs after the first N completions are uniform Codex transport failures.")
    generate.add_argument("--no-circuit-breaker", action="store_true", help="Disable batch transport failure circuit breaker for this generate invocation.")
    generate.add_argument("--allow-latest-recovery", dest="allow_latest_recovery", action="store_true", default=False, help="Opt in to newest generated_images recovery. Exact output-message recovery is used by default.")
    generate.add_argument("--no-latest-recovery", dest="allow_latest_recovery", action="store_false", help="Use exact output-message recovery only (default).")
    generate.set_defaults(early_stop=True)
    generate.add_argument("--no-early-stop", dest="early_stop", action="store_false", help="Do not terminate a running Codex worker after a stable worker generated image is recovered.")
    generate.add_argument("--monitor-interval", type=float, default=DEFAULT_MONITOR_INTERVAL, help="Seconds between current worker generated_images checks while a job is running.")
    generate.add_argument("--early-stop-grace", type=float, default=DEFAULT_EARLY_STOP_GRACE, help="Seconds a new worker image must remain unchanged before early recovery.")
    generate.add_argument("--dry-run", action="store_true")
    generate.set_defaults(func=command_generate)

    assemble = sub.add_parser("assemble-markdown", help="Assemble completed jobs into a Markdown report.")
    add_active_task_arg(assemble)
    assemble.add_argument("--workspace", required=True)
    assemble.add_argument("--title", default="")
    assemble.add_argument("--output", default=DEFAULT_REPORT)
    assemble.add_argument("--assets", default=DEFAULT_ASSETS)
    assemble.add_argument("--video-assets", default=DEFAULT_VIDEO_ASSETS)
    assemble.add_argument("--cover", default="", help="Optional local cover image path to place before references.")
    assemble.add_argument("--cover-title", default="封面设计")
    assemble.set_defaults(func=command_assemble_markdown)

    status = sub.add_parser("status", help="Print run status as JSON.")
    add_active_task_arg(status)
    status.add_argument("--workspace", required=True)
    status.set_defaults(func=command_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        phase = STEP_PHASE_BY_COMMAND.get(str(getattr(args, "command", "")))
        if phase:
            step_echo(f"image2.{phase}", "failed", f"{phase.title()} image-2 workflow", str(exc))
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
