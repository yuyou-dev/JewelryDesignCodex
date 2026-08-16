from __future__ import annotations

import base64
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


TINY_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC"
)

SUPPORTED_REQUEST_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
LOCAL_REQUEST_PROVIDERS = {
    "",
    "$imagegen",
    "codex",
    "codex-cli",
    "codex exec",
    "codex-exec",
    "gpt-image-2",
    "image-2",
    "image2",
    "jewelry:image2",
    "npm run jewelry:image2",
    "project-local-image2",
    "scripts/jewelry_image2_tool.py",
}


def validate_request_readiness(
    *,
    requested_count: int,
    output_shape: str,
    outputs: list[str],
    references: list[str] | None = None,
    reference_base: Path | None = None,
    provider: str = "codex-cli",
    explicit_provider_request: bool = False,
    provider_status: str = "auto",
    codex_home: Path | None = None,
    check_provider: bool = True,
) -> dict[str, Any]:
    """Validate a not-yet-created design run without side effects."""

    issues: list[dict[str, str]] = []

    def add_issue(code: str, message: str, recovery: str) -> None:
        issues.append({"code": code, "message": message, "recovery": recovery})

    if isinstance(requested_count, bool) or not isinstance(requested_count, int) or requested_count < 1:
        add_issue(
            "requested_count_invalid",
            "requested_count must be a positive integer.",
            "Set --requested-count to the number of designs the user requested.",
        )

    normalized_shape = str(output_shape or "").strip().lower().replace("-", "_")
    if normalized_shape not in {"independent_images", "single_composed_grid"}:
        add_issue(
            "output_shape_invalid",
            "output_shape must be independent_images or single_composed_grid.",
            "Choose independent_images unless the user explicitly requested one composed grid.",
        )
    expected_outputs = requested_count if normalized_shape == "independent_images" else 1
    if isinstance(requested_count, int) and not isinstance(requested_count, bool) and requested_count > 0:
        if len(outputs) != expected_outputs:
            add_issue(
                "output_count_mismatch",
                f"{normalized_shape or 'requested output shape'} requires {expected_outputs} output path(s), received {len(outputs)}.",
                "Pass one unique --output per independent design, or exactly one for an explicitly requested grid.",
            )

    normalized_outputs: list[str] = []
    for raw in outputs:
        value = str(raw or "").strip()
        if not value:
            add_issue("output_path_missing", "An output path is empty.", "Provide a non-empty image output path.")
            continue
        if Path(value).suffix.lower() not in SUPPORTED_REQUEST_IMAGE_SUFFIXES:
            add_issue(
                "output_type_unsupported",
                f"Output is not a supported image path: {value}",
                "Use a .png, .jpg, .jpeg, or .webp output path.",
            )
        normalized_outputs.append(os.path.normcase(os.path.normpath(value)))
    if len(normalized_outputs) != len(set(normalized_outputs)):
        add_issue(
            "output_path_duplicate",
            "Each requested output must have a unique path.",
            "Assign one unique output path to every independent design.",
        )

    base = (reference_base or Path.cwd()).expanduser()
    reference_checks: list[dict[str, Any]] = []
    for raw in references or []:
        value = str(raw or "").strip()
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = base / path
        supported = path.suffix.lower() in SUPPORTED_REQUEST_IMAGE_SUFFIXES
        exists = path.is_file()
        reference_checks.append({"path": str(path), "exists": exists, "supported": supported})
        if not exists:
            add_issue(
                "reference_missing",
                f"Reference image does not exist: {value}",
                "Restore the attachment or pass the correct existing reference path, then retry validation.",
            )
        elif not supported:
            add_issue(
                "reference_type_unsupported",
                f"Reference is not a supported image: {value}",
                "Use a .png, .jpg, .jpeg, or .webp reference image.",
            )

    provider_name = str(provider or "codex-cli").strip()
    provider_key = provider_name.lower()
    local_provider = provider_key in LOCAL_REQUEST_PROVIDERS
    provider_check: dict[str, Any] = {
        "provider": provider_name or "codex-cli",
        "route": "local" if local_provider else "explicit_external",
        "status": provider_status,
        "provider_call": False,
    }
    if check_provider and local_provider and not issues:
        executable = shutil.which("codex")
        source_home = (codex_home or Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")).expanduser()
        login_ready = False
        if executable:
            login_env = os.environ.copy()
            login_env["CODEX_HOME"] = str(source_home)
            login_ready = subprocess.run(
                [executable, "login", "status"],
                env=login_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            ).returncode == 0
        provider_check.update({
            "status": "ready" if executable and login_ready else "blocked",
            "executable_found": bool(executable),
            "login_ready": login_ready,
        })
        if not executable:
            add_issue(
                "provider_not_ready",
                "Codex CLI executable is not available for the local image-2 route.",
                "Install or expose the existing Codex CLI on PATH, then retry validation.",
            )
        if executable and not login_ready:
            add_issue(
                "login_required",
                "Codex CLI reports that the local user is not logged in.",
                "Complete Codex login outside this validator, then rerun validate-request.",
            )
    elif check_provider and not local_provider:
        if not explicit_provider_request:
            add_issue(
                "provider_not_explicit",
                f"External provider {provider_name!r} was not explicitly requested for this request.",
                "Use the local route, or record the user's current explicit provider request.",
            )
        if provider_status == "auto":
            add_issue(
                "provider_readiness_unknown",
                f"External provider {provider_name!r} readiness was not supplied.",
                "Obtain read-only readiness from the current provider owner and pass its status; this validator will not probe it.",
            )
        elif provider_status != "ready":
            code = "login_required" if provider_status == "login-required" else "provider_not_ready"
            add_issue(
                code,
                f"External provider {provider_name!r} is {provider_status}.",
                "Complete provider authorization/readiness outside this validator, then rerun validate-request.",
            )

    return {
        "schema_version": 1,
        "kind": "jewelry_image_request_readiness",
        "status": "ready" if not issues else "blocked",
        "ok": not issues,
        "requested_count": requested_count,
        "output_shape": normalized_shape,
        "outputs": list(outputs),
        "references": reference_checks,
        "provider": provider_check,
        "issues": issues,
        "recovery_actions": [item["recovery"] for item in issues],
        "side_effects": {
            "writes": False,
            "copies": False,
            "login": False,
            "fallback": False,
            "provider_call": False,
        },
    }
