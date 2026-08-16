from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

from lib.run_path_guard import (
    active_task_id_from_args,
    assert_current_task_read_path,
    assert_current_task_write_path,
)


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MIN_REVIEW_IMAGE_BYTES = 100 * 1024
MIN_REVIEW_IMAGE_DIMENSION = 512
DEFAULT_RETRIES = 2
DEFAULT_ATTEMPT_BUDGET = 3
FAST_FAIL_NETWORK_SIGNALS = (
    "image generation failed due to a network error",
    "image generation failed: network error",
    "network error while generating image",
    "failed to fetch generated image",
)
DEFAULT_TIMEOUT = 600
DEFAULT_MONITOR_INTERVAL = 1.0
DEFAULT_EARLY_STOP_GRACE = 2.0
NON_RETRYABLE_FAILURE_CLASSES = {
    "codex_transport_dns_failure",
    "codex_transport_failure",
    "provider_auth_failed",
    "sandbox_path_failure",
}
BATCH_CIRCUIT_BREAKER_FAILURE_CLASSES = {
    "codex_transport_dns_failure",
    "codex_transport_failure",
    "provider_auth_failed",
}
PROVIDER_AUTH_FAILURE_PATTERN = re.compile(
    r"(?:\bhttp(?:/\d(?:\.\d)?)?\s*(?:status(?:\s+code)?\s*[:=]?\s*)?(?:401|403)\b|"
    r"\b(?:status|response|error)\s*(?:code)?\s*(?:[:=]\s*)?(?:401|403)\b|"
    r"\b(?:401|403)\s+(?:unauthori[sz]ed|forbidden)\b|"
    r"\b(?:authentication|authorization)\s+(?:failed|required|denied|rejected)\b|"
    r"\bnot\s+logged\s+in\b|"
    r"\binvalid\s+(?:api\s+key|access\s+token|credentials?)\b|"
    r"\b(?:access\s+)?token\s+(?:is\s+)?(?:expired|invalid|revoked)\b)",
    re.IGNORECASE,
)
DEFAULT_DESIGN_RATIO = "1:1"
DEFAULT_REPORT = "output/jewelry-image-report.md"
DEFAULT_ASSETS = "output/jewelry-image-assets.json"
DEFAULT_VIDEO_ASSETS = "output/jewelry-video-assets.json"
JOBS_LOCK = threading.Lock()
IMAGEGEN_FIRST_LINE = "$imagegen"
WORKER_CONTRACT_VERSION = "image2-direct-worker/v1"
EXECUTED_JOB_CONTRACT_FIELDS = ("executed_prompt_sha256", "worker_contract_version")
EXECUTED_RECORD_CONTRACT_FIELDS = (
    "executed_prompt",
    "executed_prompt_sha256",
    "executed_prompt_bytes",
    "worker_contract_version",
)
LOCAL_IMAGE2_ROUTE_VALUES = {
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
PROVIDER_ROUTE_FIELDS = [
    "provider",
    "requested_provider",
    "requestedProvider",
    "execution_provider",
    "executionProvider",
    "provider_route",
    "providerRoute",
    "plugin",
    "requested_plugin",
    "requestedPlugin",
    "execution_tool",
    "executionTool",
]


class ProviderRouteError(ValueError):
    """Raised when an external provider/plugin route is sent to the local image-2 runner."""


DIRECT_IMAGE_WORKER_GUARD = (
    "Direct image-generation worker mode: Use the built-in image generation tool now. "
    "Do not inspect repository files. Do not read skills or documentation. "
    "Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. "
    "Do not create extra task documents. Do not edit task progress. Do not assemble reports. "
    "Do not perform post-processing. Return only the generated image result."
)
DIRECT_IMAGE_WORKER_GUARD_PATTERNS = [
    ("direct_image_generation_mode", re.compile(r"\bdirect\s+image-generation\s+worker\s+mode\b|\bbuilt-in\s+image\s+generation\s+tool\b", re.IGNORECASE)),
    ("no_repository_inspection", re.compile(r"\bdo\s+not\s+inspect\s+repository\s+files\b", re.IGNORECASE)),
    ("no_skill_or_doc_reading", re.compile(r"\bdo\s+not\s+read\s+skills?\s+or\s+documentation\b", re.IGNORECASE)),
    ("no_shell_commands", re.compile(r"\bdo\s+not\s+run\s+shell\s+commands\b", re.IGNORECASE)),
    ("no_file_writes", re.compile(r"\bdo\s+not\s+(?:create,\s*edit,\s*move,\s*copy,\s*save,\s*or\s+write|write)\s+files?\b|\bdo\s+not\s+.*\bwrite\s+files?\b", re.IGNORECASE)),
    ("no_job_creation", re.compile(r"\bdo\s+not\s+create\s+jobs?\b", re.IGNORECASE)),
    ("no_task_document_update", re.compile(r"\bdo\s+not\s+(?:edit|update)\s+task\s+(?:documents?|progress)\b", re.IGNORECASE)),
    ("no_report_assembly", re.compile(r"\bdo\s+not\s+assemble\s+reports?\b", re.IGNORECASE)),
    ("no_post_processing", re.compile(r"\bdo\s+not\s+perform\s+post-processing\b|\bdo\s+not\s+post-process\b", re.IGNORECASE)),
    ("return_only_image", re.compile(r"\breturn\s+only\s+the\s+generated\s+image\b", re.IGNORECASE)),
]
IMAGEGEN_NEGATION_MARKERS = [
    "do not",
    "don't",
    "must not",
    "should not",
    "never",
    "no ",
    "without",
    "forbid",
    "forbidden",
    "禁止",
    "不要",
    "不得",
    "不能",
    "不允许",
]
DISALLOWED_IMAGEGEN_EXECUTION_PATTERNS = [
    ("shell_commands", re.compile(r"\b(run|execute|invoke)\s+(?:a\s+|the\s+)?(?:shell\s+)?commands?\b|\bshell\s*:\s*\S+", re.IGNORECASE)),
    ("write_files", re.compile(r"\b(write|create|save)\s+(?:local\s+)?files?\b", re.IGNORECASE)),
    ("create_jobs", re.compile(r"\b(create|add|register|queue)\s+jobs?\b|\badd-jobs?\b", re.IGNORECASE)),
    ("update_task_documents", re.compile(r"\b(update|write|edit)\s+task\s+(?:documents?|progress)\b", re.IGNORECASE)),
    ("assemble_reports", re.compile(r"\bassemble[- ]markdown\b|\bassemble\s+reports?\b", re.IGNORECASE)),
    ("post_processing", re.compile(r"\bpost-processing\b|\bpost processing\b|\bpostprocess\b", re.IGNORECASE)),
]
RECURSIVE_ORCHESTRATION_COMMAND = re.compile(
    r"(?:^|[\s\"'])(?:npm\s+run\s+jewelry:image2\s+--\s+add-jobs?\b|(?:python3?\s+)?\S*jewelry_image2_tool\.py\s+add-jobs?\b|"
    r"(?:spawn_agent|create_thread)\s*\()",
    re.IGNORECASE,
)
EXECUTION_LINE = re.compile(r"^\s*(?:exec(?:ute)?|command|cmd|shell)\s*:\s*(.+)$|^\s*\$\s+(.+)$", re.IGNORECASE)
EXECUTION_EVENT_KINDS = {"exec", "execute", "command", "command_execution", "shell", "tool_call"}
PRESET_RATIO_KIND_TOKENS = {
    "poster",
    "ecommerce",
    "grid",
    "nine-grid",
    "contact-sheet",
    "retouch",
    "redraw",
    "revision",
    "edit",
    "restore",
    "video",
}
STEP_PHASE_BY_COMMAND = {
    "validate-request": "prepare",
    "init": "prepare",
    "add-job": "prepare",
    "add-jobs": "prepare",
    "preflight": "prepare",
    "generate": "generate",
    "assemble-markdown": "assemble",
    "validate-jobs": "prepare",
}


def step_value(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    return text.replace("\\", "\\\\").replace('"', '\\"')


def step_echo(key: str, status: str, label: str, detail: str = "") -> None:
    print(
        f'[STEP] key={step_value(key)} status={status} '
        f'label="{step_value(label)}" detail="{step_value(detail)}"',
        file=sys.stderr,
        flush=True,
    )


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def duration_seconds(start: float, end: float | None = None) -> float:
    return round(max(0.0, (time.monotonic() if end is None else end) - start), 3)


def normalize_ratio_value(value: Any) -> str:
    text = re.sub(r"\s+", "", str(value or "").strip().lower().replace("：", ":"))
    if not text:
        return ""
    if text in {"square", "正方形", "方图", "正方图"}:
        return DEFAULT_DESIGN_RATIO
    match = re.fullmatch(r"(\d{1,2}):(\d{1,2})", text)
    if not match:
        return str(value or "").strip()
    return f"{int(match.group(1))}:{int(match.group(2))}"


def infer_ratio_from_prompt(prompt_text: str) -> str:
    normalized = str(prompt_text or "")
    if re.search(r"\b(square|1\s*[:：]\s*1)\b|正方形|方图|正方图", normalized, re.IGNORECASE):
        return DEFAULT_DESIGN_RATIO
    match = re.search(r"(?<!\d)(\d{1,2})\s*[:：]\s*(\d{1,2})(?!\d)", normalized)
    if match:
        return f"{int(match.group(1))}:{int(match.group(2))}"
    return ""


def kind_uses_default_design_ratio(kind: Any) -> bool:
    value = str(kind or "jewelry-image").strip().lower().replace("_", "-")
    if not value:
        return True
    return not any(token in value for token in PRESET_RATIO_KIND_TOKENS)


def resolve_job_ratio(payload: dict[str, Any], prompt_text: str) -> tuple[str, str]:
    explicit = normalize_ratio_value(payload.get("ratio"))
    if explicit:
        return explicit, "explicit"
    inferred = infer_ratio_from_prompt(prompt_text)
    if inferred:
        return inferred, "prompt"
    if kind_uses_default_design_ratio(payload.get("kind")):
        return DEFAULT_DESIGN_RATIO, "default_design"
    return "", "preset_or_unspecified"


def prompt_with_ratio_contract(prompt_text: str, ratio: str, ratio_source: str = "") -> str:
    text = str(prompt_text or "").rstrip()
    normalized_ratio = normalize_ratio_value(ratio)
    if not normalized_ratio:
        return text + "\n"
    if infer_ratio_from_prompt(text) == normalized_ratio:
        return text + "\n"
    source_note = "default jewelry design ratio" if ratio_source == "default_design" else "job ratio metadata"
    return f"{text}\n\nOutput aspect ratio: {normalized_ratio}. This is the {source_note}; keep it unless the user or selected preset explicitly specifies another ratio.\n"


def first_nonempty_line(text: str) -> str:
    for line in str(text or "").splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return ""


def validate_imagegen_prompt_contract(prompt_text: str, *, label: str) -> list[str]:
    issues: list[str] = []
    text = str(prompt_text or "")
    first_line = first_nonempty_line(text)
    present_guard_markers = [marker for marker, pattern in DIRECT_IMAGE_WORKER_GUARD_PATTERNS if pattern.search(text)]
    if not text.strip():
        issues.append(f"{label} must not be empty")
    elif IMAGEGEN_FIRST_LINE in text and first_line != IMAGEGEN_FIRST_LINE:
        issues.append(f"{label} must place {IMAGEGEN_FIRST_LINE} on the first non-empty line")
    if present_guard_markers and len(present_guard_markers) != len(DIRECT_IMAGE_WORKER_GUARD_PATTERNS):
        issues.append(f"{label} contains a partial direct-image worker guard")
    for line in text.splitlines():
        lower_line = line.lower()
        if not lower_line.strip():
            continue
        negated = any(marker in lower_line for marker in IMAGEGEN_NEGATION_MARKERS)
        for marker, pattern in DISALLOWED_IMAGEGEN_EXECUTION_PATTERNS:
            if pattern.search(line) and not negated:
                issues.append(f"{label} contains execution instruction instead of direct image generation: {marker}")
        if not negated and (EXECUTION_LINE.search(line) or RECURSIVE_ORCHESTRATION_COMMAND.search(line)):
            issues.append(f"{label} contains a positive shell or orchestration instruction")
    return issues


def ensure_imagegen_prompt_contract(prompt_text: str, *, label: str) -> None:
    issues = validate_imagegen_prompt_contract(prompt_text, label=label)
    if issues:
        raise ValueError("; ".join(issues))


def has_complete_legacy_worker_contract(prompt_text: str) -> bool:
    text = str(prompt_text or "")
    return (
        first_nonempty_line(text) == IMAGEGEN_FIRST_LINE
        and all(pattern.search(text) for _, pattern in DIRECT_IMAGE_WORKER_GUARD_PATTERNS)
    )


def build_executed_prompt(prompt_text: str, ratio: str, ratio_source: str = "") -> str:
    """Build the exact deterministic stdin sent to the direct image worker."""
    ensure_imagegen_prompt_contract(prompt_text, label="source prompt")
    if has_complete_legacy_worker_contract(prompt_text):
        enveloped = str(prompt_text or "")
    else:
        creative_body = str(prompt_text or "").strip()
        if first_nonempty_line(creative_body) == IMAGEGEN_FIRST_LINE:
            creative_body = creative_body.split(IMAGEGEN_FIRST_LINE, 1)[1].lstrip()
        enveloped = f"{IMAGEGEN_FIRST_LINE}\n{DIRECT_IMAGE_WORKER_GUARD}\n{creative_body}"
    return prompt_with_ratio_contract(enveloped, ratio, ratio_source)


def declares_executed_prompt_contract(payload: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return any(field in payload for field in fields)


def truthy_route_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text not in {"", "0", "false", "no", "none", "null"}


def normalize_route_value(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def image2_provider_route_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    declared: dict[str, str] = {}
    for field in PROVIDER_ROUTE_FIELDS:
        raw = payload.get(field)
        if raw is None:
            continue
        text = normalize_route_value(raw)
        if not text:
            continue
        declared[field] = text
        if text not in LOCAL_IMAGE2_ROUTE_VALUES:
            issues.append(f"provider_route_forbidden:{field}={raw}")
    if truthy_route_flag(payload.get("provider_exception") or payload.get("providerException")):
        requested = (
            declared.get("requested_provider")
            or declared.get("requestedProvider")
            or declared.get("provider")
            or declared.get("plugin")
            or declared.get("requested_plugin")
            or declared.get("requestedPlugin")
            or ""
        )
        if not requested or requested in LOCAL_IMAGE2_ROUTE_VALUES:
            issues.append("provider_route_forbidden:provider_exception_requires_external_provider_execution")
    return issues


def ensure_image2_provider_route_allowed(payload: dict[str, Any], *, label: str) -> None:
    issues = image2_provider_route_issues(payload)
    if issues:
        raise ProviderRouteError(
            f"{label} declares an explicit external provider/plugin route and cannot be run by the local image-2 runner: "
            + "; ".join(issues)
        )


def classify_codex_transport_failure(text: str) -> dict[str, str] | None:
    value = str(text or "").lower()
    has_codex_response_signal = bool(re.search(
        r"(backend-api/codex/responses|responses_websocket|codex_api::endpoint::responses|codex_core::responses_retry)",
        value,
    ))
    if not has_codex_response_signal:
        return None
    if re.search(r"(dns error|failed to lookup|could not resolve|nodename nor servname|temporary failure in name resolution|name or service not known)", value):
        return {
            "class": "codex_transport_dns_failure",
            "message": "Codex CLI could not reach the Codex responses transport because DNS or host resolution failed.",
        }
    if re.search(r"(stream disconnected|error sending request|failed to connect|connection reset|connection refused|transport channel closed|tls|proxy)", value):
        return {
            "class": "codex_transport_failure",
            "message": "Codex CLI transport failed before producing a recoverable image output.",
        }
    return None


def classify_provider_auth_failure(text: str) -> dict[str, str] | None:
    match = PROVIDER_AUTH_FAILURE_PATTERN.search(str(text or ""))
    if match is None:
        return None
    return {
        "class": "provider_auth_failed",
        "message": "The image provider rejected the current Codex authentication.",
        "signal": match.group(0),
    }


def classify_provider_network_failure(text: str) -> dict[str, str] | None:
    value = str(text or "").lower()
    signal = next((item for item in FAST_FAIL_NETWORK_SIGNALS if item in value), None)
    if signal is None:
        return None
    return {
        "class": "provider_network_error",
        "message": "The image provider request failed on its network transport before producing a usable image.",
        "signal": signal,
    }


def recursive_worker_output_flags(text: str) -> list[str]:
    """Detect actual orchestration execution, never prose or legitimate run paths.

    Worker stdout is not a trustworthy place to infer intent from words such as
    ``handoff``.  Only command-shaped execution evidence is actionable here.
    Paths below any current task are deliberately ignored at every depth.
    """
    for line in str(text or "").splitlines():
        command = ""
        match = EXECUTION_LINE.match(line)
        if match:
            command = str(match.group(1) or match.group(2) or "")
        else:
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                event = None
            if isinstance(event, dict) and str(event.get("event") or event.get("type") or "").lower() in EXECUTION_EVENT_KINDS:
                raw_command = event.get("command") or event.get("cmd") or event.get("input")
                if isinstance(raw_command, list):
                    command = " ".join(str(part) for part in raw_command)
                elif isinstance(raw_command, str):
                    command = raw_command
        if command and RECURSIVE_ORCHESTRATION_COMMAND.search(command):
            return ["orchestration_command_exec"]
    return []


def iso_to_timestamp(value: Any) -> float | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")






def safe_id(value: str, fallback: str = "job") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "")).strip("-._")
    return cleaned or fallback


def workspace_path(args: argparse.Namespace) -> Path:
    return Path(args.workspace).expanduser().resolve()


def guarded_workspace(args: argparse.Namespace, *, write: bool = True) -> Path:
    workspace = workspace_path(args)
    active_task_id = active_task_id_from_args(args)
    if active_task_id:
        guard = assert_current_task_write_path if write else assert_current_task_read_path
        guard(workspace, active_task_id, "image2 workspace")
    return workspace


def guard_write_path(path: Path, active_task_id: str, label: str) -> Path:
    if active_task_id:
        assert_current_task_write_path(path, active_task_id, label)
    return path


def guard_read_path(path: Path, active_task_id: str, label: str) -> Path:
    if active_task_id:
        assert_current_task_read_path(path, active_task_id, label)
    return path


def rel_to_workspace(workspace: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return str(path)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def image_header_metadata(path: Path) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "valid": False,
        "format": None,
        "width": None,
        "height": None,
    }
    try:
        data = path.read_bytes()
    except OSError as error:
        metadata["error"] = str(error)
        return metadata
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        metadata.update(
            {
                "valid": True,
                "format": "png",
                "width": int.from_bytes(data[16:20], "big"),
                "height": int.from_bytes(data[20:24], "big"),
            }
        )
        return metadata
    if data.startswith(b"\xff\xd8\xff"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            if index + 2 > len(data):
                break
            segment_length = int.from_bytes(data[index : index + 2], "big")
            if segment_length < 2:
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                if index + 7 <= len(data):
                    metadata.update(
                        {
                            "valid": True,
                            "format": "jpeg",
                            "height": int.from_bytes(data[index + 3 : index + 5], "big"),
                            "width": int.from_bytes(data[index + 5 : index + 7], "big"),
                        }
                    )
                return metadata
            index += segment_length
        metadata.update({"valid": True, "format": "jpeg"})
        return metadata
    if len(data) >= 16 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        metadata.update({"valid": True, "format": "webp"})
        chunk = data[12:16]
        if chunk == b"VP8X" and len(data) >= 30:
            metadata.update(
                {
                    "width": int.from_bytes(data[24:27], "little") + 1,
                    "height": int.from_bytes(data[27:30], "little") + 1,
                }
            )
        elif chunk == b"VP8 " and len(data) >= 30:
            metadata.update(
                {
                    "width": int.from_bytes(data[26:28], "little") & 0x3FFF,
                    "height": int.from_bytes(data[28:30], "little") & 0x3FFF,
                }
            )
        elif chunk == b"VP8L" and len(data) >= 25:
            b0, b1, b2, b3 = data[21], data[22], data[23], data[24]
            metadata.update(
                {
                    "width": 1 + (((b1 & 0x3F) << 8) | b0),
                    "height": 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6)),
                }
            )
        return metadata
    return metadata
