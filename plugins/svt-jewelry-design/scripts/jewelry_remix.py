#!/usr/bin/env python3
"""Compile a structured jewelry remix brief into Image-2 runner jobs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
import uuid


SCHEMA_VERSION = 2
JDC_IMAGE2_COMMAND = f"node {json.dumps(str(Path(__file__).resolve().with_name('jdc.mjs')))} image2"
VALID_COUNTS = {4, 8}
VALID_FIDELITY = {"high", "medium", "low"}
VALID_INTENSITY = {"subtle", "balanced", "bold"}
VALID_FUSION = {"shape_grafting", "pattern_translation", "structural_rebuild"}
ROLE_NAMES = {
    "A": "保守商业化",
    "B": "主题强化",
    "C": "工艺材质化",
    "D": "大胆概念化",
    "E": "高级珠宝化",
    "F": "日常轻量化",
    "G": "文化符号化",
    "H": "系列延展化",
}
FIDELITY_TEXT = {
    "high": "高：保持原款轮廓、比例、主石位置和佩戴结构，只调整局部语言",
    "medium": "中：保留家族轮廓和主结构，允许局部体量、边缘与支撑变化",
    "low": "低：保留原款识别基因，允许大胆重组，但仍须真实可佩戴",
}
INTENSITY_TEXT = {
    "subtle": "微调：集中改善比例、边缘、镶嵌和材质细节",
    "balanced": "平衡：变化清晰，同时保持原款识别度",
    "bold": "重塑：允许轮廓和局部结构重组，不得成为不可佩戴装置",
}
FUSION_TEXT = {
    "shape_grafting": "保形嫁接：保留原结构，将元素植入局部结构、宝石排列和边缘",
    "pattern_translation": "纹样转译：将元素转化为镂空、浮雕、肌理、爪镶节奏或宝石排列",
    "structural_rebuild": "结构重组：把元素转化为新的局部轮廓、连接方式与视觉重心",
}


def load_taxonomy() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    candidates = [
        root / ".agents" / "skills" / "jewelry-remix" / "references" / "remix-taxonomy.v2.json",
        root / "skills" / "jewelry-remix" / "references" / "remix-taxonomy.v2.json",
    ]
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise ValueError("remix taxonomy v2 is missing")
    taxonomy = require_object(json.loads(path.read_text(encoding="utf-8")), "remix taxonomy")
    if taxonomy.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("remix taxonomy schema_version must be 2")
    require_object(taxonomy.get("design_systems"), "remix taxonomy.design_systems")
    return taxonomy


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def require_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def text_list(value: Any, label: str, *, required: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    items = [require_text(item, label) for item in value]
    if required and not items:
        raise ValueError(f"{label} must not be empty")
    return items


def normalize_taxonomy_selection(
    preferences: dict[str, Any],
    system: dict[str, Any],
    field: str,
) -> tuple[list[str], list[str], str]:
    selected = text_list(preferences.get(field), f"preferences.{field}")
    custom_field = f"custom_{field}"
    custom = str(preferences.get(custom_field) or "").strip()
    options = system.get(field)
    if not isinstance(options, list):
        raise ValueError(f"taxonomy.{field} must be a list")
    labels = {}
    for item in options:
        option = require_object(item, f"taxonomy.{field}")
        labels[require_text(option.get("id"), f"taxonomy.{field}.id")] = require_text(
            option.get("label"), f"taxonomy.{field}.label"
        )
    allowed = {*labels, "other"}
    invalid = [item for item in selected if item not in allowed]
    if invalid:
        raise ValueError(f"preferences.{field} contains values outside the selected design system: {invalid}")
    if "other" in selected and not custom:
        raise ValueError(f"preferences.{custom_field} is required when preferences.{field} contains other")
    resolved = [labels[item] for item in selected if item != "other"]
    if "other" in selected:
        resolved.append(custom)
    return selected, resolved, custom


def workspace_file(workspace: Path, value: Any, label: str, *, must_exist: bool = True) -> tuple[Path, str]:
    raw = require_text(value, label)
    candidate = Path(raw).expanduser()
    resolved = (candidate if candidate.is_absolute() else workspace / candidate).resolve()
    if not resolved.is_relative_to(workspace):
        raise ValueError(f"{label} must stay inside the workspace")
    if must_exist and not resolved.is_file():
        raise ValueError(f"{label} does not exist: {raw}")
    return resolved, resolved.relative_to(workspace).as_posix()


def read_brief(workspace: Path, brief_path: str) -> dict[str, Any]:
    candidate = Path(require_text(brief_path, "brief")).expanduser()
    if candidate.is_absolute():
        path = candidate.resolve()
    else:
        from_cwd = candidate.resolve()
        path = from_cwd if from_cwd.is_file() else (workspace / candidate).resolve()
    if not path.is_relative_to(workspace):
        raise ValueError("brief must stay inside the workspace")
    if not path.is_file():
        raise ValueError(f"brief does not exist: {brief_path}")
    try:
        return require_object(json.loads(path.read_text(encoding="utf-8")), "brief")
    except json.JSONDecodeError as error:
        raise ValueError(f"brief is not valid JSON: {error.msg}") from error


def normalize_brief(workspace: Path, brief: dict[str, Any]) -> dict[str, Any]:
    if brief.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version must be 2")
    count = brief.get("count")
    if count not in VALID_COUNTS:
        raise ValueError("count must be 4 or 8")

    _, source = workspace_file(workspace, brief.get("source"), "source")
    identity = require_object(brief.get("identity"), "identity")
    normalized_identity = {
        "type": require_text(identity.get("type"), "identity.type"),
        "silhouette": require_text(identity.get("silhouette"), "identity.silhouette"),
        "proportions": require_text(identity.get("proportions"), "identity.proportions"),
        "focal_materials": require_text(identity.get("focal_materials"), "identity.focal_materials"),
        "construction": require_text(identity.get("construction"), "identity.construction"),
        "locked_parts": text_list(identity.get("locked_parts"), "identity.locked_parts"),
        "editable_parts": text_list(identity.get("editable_parts"), "identity.editable_parts"),
    }

    taxonomy = load_taxonomy()
    preferences = require_object(brief.get("preferences"), "preferences")
    design_system = require_text(preferences.get("design_system"), "preferences.design_system")
    systems = taxonomy["design_systems"]
    if design_system not in systems:
        raise ValueError(f"design_system must be one of {sorted(systems)}")
    system = require_object(systems[design_system], f"taxonomy.design_systems.{design_system}")
    fidelity = require_text(preferences.get("structure_fidelity"), "preferences.structure_fidelity")
    intensity = require_text(preferences.get("intensity"), "preferences.intensity")
    fusion = require_text(preferences.get("fusion_strategy"), "preferences.fusion_strategy")
    if fidelity not in VALID_FIDELITY:
        raise ValueError(f"structure_fidelity must be one of {sorted(VALID_FIDELITY)}")
    if intensity not in VALID_INTENSITY:
        raise ValueError(f"intensity must be one of {sorted(VALID_INTENSITY)}")
    if fusion not in VALID_FUSION:
        raise ValueError(f"fusion_strategy must be one of {sorted(VALID_FUSION)}")
    normalized_preferences: dict[str, Any] = {
        "design_system": design_system,
        "design_system_label": require_text(system.get("label"), f"taxonomy.design_systems.{design_system}.label"),
        "structure_fidelity": fidelity,
        "intensity": intensity,
        "fusion_strategy": fusion,
        "direction": str(preferences.get("direction") or "").strip(),
    }
    for field, label_field in (
        ("themes", "theme_labels"),
        ("morphologies", "morphology_labels"),
        ("styles", "style_labels"),
        ("materials", "material_labels"),
    ):
        selected, resolved, custom = normalize_taxonomy_selection(preferences, system, field)
        normalized_preferences[field] = selected
        normalized_preferences[label_field] = resolved
        normalized_preferences[f"custom_{field}"] = custom

    references: list[dict[str, str]] = []
    raw_references = brief.get("references", [])
    if not isinstance(raw_references, list):
        raise ValueError("references must be a list")
    for index, item in enumerate(raw_references):
        reference = require_object(item, f"references[{index}]")
        _, relative = workspace_file(workspace, reference.get("path"), f"references[{index}].path")
        references.append({"path": relative, "role": require_text(reference.get("role"), f"references[{index}].role")})

    candidates = brief.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != count:
        raise ValueError(f"candidates must contain exactly {count} items")
    expected_ids = [f"REMIX-{letter}" for letter in "ABCDEFGH"[:count]]
    normalized_candidates = []
    differences: set[str] = set()
    for index, item in enumerate(candidates):
        candidate = require_object(item, f"candidates[{index}]")
        candidate_id = require_text(candidate.get("id"), f"candidates[{index}].id")
        if candidate_id != expected_ids[index]:
            raise ValueError(f"candidate {index + 1} id must be {expected_ids[index]}")
        difference = require_text(candidate.get("difference"), f"candidates[{index}].difference")
        if difference in differences:
            raise ValueError("candidate differences must be unique")
        differences.add(difference)
        normalized_candidates.append({
            "id": candidate_id,
            "title": require_text(candidate.get("title"), f"candidates[{index}].title"),
            "positioning": require_text(candidate.get("positioning"), f"candidates[{index}].positioning"),
            "default_role": ROLE_NAMES[candidate_id[-1]],
            "difference": difference,
            "theme": require_text(candidate.get("theme"), f"candidates[{index}].theme"),
            "morphology": require_text(candidate.get("morphology"), f"candidates[{index}].morphology"),
            "style": require_text(candidate.get("style"), f"candidates[{index}].style"),
            "material_craft": require_text(candidate.get("material_craft"), f"candidates[{index}].material_craft"),
            "change_scope": require_text(candidate.get("change_scope"), f"candidates[{index}].change_scope"),
            "use_case": require_text(candidate.get("use_case"), f"candidates[{index}].use_case"),
        })

    return {
        "count": count,
        "source": source,
        "identity": normalized_identity,
        "preferences": normalized_preferences,
        "references": references,
        "candidates": normalized_candidates,
    }


def joined(items: list[str]) -> str:
    return "、".join(items)


def compile_prompt(brief: dict[str, Any], candidate: dict[str, str]) -> str:
    identity = brief["identity"]
    preferences = brief["preferences"]
    reference_rules = ["原款图是第一张参考，负责轮廓、比例、主石和佩戴逻辑。"]
    for index, item in enumerate(brief["references"], start=2):
        reference_rules.append(f"参考图 {index} 只用于{item['role']}，不得取代原款轮廓。")
    direction = preferences["direction"] or "无额外方向，依据上述约束完成"
    return f"""$imagegen
使用 gpt-image-2 生成一张完成度高的珠宝爆款二创产品图。只返回生成图像，不要写文件、不要生成合集、不要在画面中添加文字。

任务：基于原款图生成独立候选 {candidate['id']} / {candidate['title']}。
候选定位：{candidate['positioning']}（默认分支：{candidate['default_role']}）。
与其他候选的核心差异：{candidate['difference']}。
适用方向：{candidate['use_case']}。

底座身份锁：
- 珠宝类型：{identity['type']}
- 原始轮廓：{identity['silhouette']}
- 比例与视觉中心：{identity['proportions']}
- 主石与主材质：{identity['focal_materials']}
- 真实可佩戴结构：{identity['construction']}
- 必须保留：{joined(identity['locked_parts'])}
- 可改动：{joined(identity['editable_parts'])}

全局二创变量：
- 产品体系：{preferences['design_system_label']}（{preferences['design_system']}）
- 结构保留度：{FIDELITY_TEXT[preferences['structure_fidelity']]}
- 创改强度：{INTENSITY_TEXT[preferences['intensity']]}
- 融合策略：{FUSION_TEXT[preferences['fusion_strategy']]}
- 主题池：{joined(preferences['theme_labels'])}
- 形态语言池：{joined(preferences['morphology_labels'])}
- 风格池：{joined(preferences['style_labels'])}
- 材质工艺池：{joined(preferences['material_labels'])}
- 用户补充：{direction}

本候选 prompt_spec：
- preserve：{joined(identity['locked_parts'])}；保持原款的珠宝类型、家族识别度与佩戴逻辑。
- change_scope：{candidate['change_scope']}。
- design_translation：以{candidate['theme']}为主题，使用{candidate['morphology']}形态语言，按“{FUSION_TEXT[preferences['fusion_strategy']]}”转译成珠宝结构，不是平面贴图。
- construction：保证主石镶口、支撑、连接、扣件或戒臂等真实可佩戴结构合理。
- material_craft：{candidate['material_craft']}；整体风格为{candidate['style']}。
- rendering：1:1 单件居中白底或极浅灰白底高级珠宝棚拍，清晰轮廓，真实金属反光、宝石透明度与轻微接触阴影。

参考图角色：
{chr(10).join(f'- {rule}' for rule in reference_rules)}

禁止：文字、logo、水印、证书、价格、复杂道具、额外珠宝主体、漂浮宝石、断裂支撑、不可佩戴装置、玩具或塑料质感、直接复制品牌款、把多个方案放进同一画面。
"""


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare(workspace_arg: str, brief_arg: str) -> dict[str, Any]:
    workspace = Path(workspace_arg).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    brief = normalize_brief(workspace, read_brief(workspace, brief_arg))
    prompt_dir = workspace / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    reference_paths = [brief["source"], *[item["path"] for item in brief["references"]]]

    batch_id = f"REMIX-{uuid.uuid4().hex[:10].upper()}"
    jobs = []
    for candidate in brief["candidates"]:
        stable_id = candidate["id"]
        job_id = f"{stable_id}-{batch_id.removeprefix('REMIX-')}"
        prompt_relative = f"prompts/{job_id}.prompt.txt"
        (workspace / prompt_relative).write_text(compile_prompt(brief, candidate), encoding="utf-8")
        jobs.append({
            "id": job_id,
            "stable_id": stable_id,
            "batch_id": batch_id,
            "title": candidate["title"],
            "kind": "jewelry-remix",
            "ratio": "1:1",
            "prompt_file": prompt_relative,
            "output": f"outputs/{job_id}.png",
            "references": reference_paths,
            "allow_duplicate_prompt": True,
        })

    matrix = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "requested_count": brief["count"],
        "job_ids": [job["id"] for job in jobs],
        "stable_job_ids": [job["stable_id"] for job in jobs],
        "source": brief["source"],
        "identity": brief["identity"],
        "preferences": brief["preferences"],
        "references": brief["references"],
        "candidates": brief["candidates"],
    }
    matrix_path = workspace / "remix" / "matrix.json"
    jobs_path = workspace / "remix" / "jobs.json"
    write_json(matrix_path, matrix)
    write_json(jobs_path, {"jobs": jobs})
    return {
        "requested_count": brief["count"],
        "batch_id": batch_id,
        "job_ids": [job["id"] for job in jobs],
        "stable_job_ids": [job["stable_id"] for job in jobs],
        "matrix": matrix_path.relative_to(workspace).as_posix(),
        "jobs": jobs_path.relative_to(workspace).as_posix(),
        "prompt_count": len(jobs),
        "next": (
            f"{JDC_IMAGE2_COMMAND} add-jobs, then use the same bundled command for "
            "validate-jobs and generate --parallel 4"
        ),
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Compile a 4/8-way jewelry remix brief for the project Image-2 runner.")
    commands = root.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="Validate a remix brief and compile matrix, prompts, and runner jobs.")
    prepare_parser.add_argument("--workspace", required=True)
    prepare_parser.add_argument("--brief", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "prepare":
            print(json.dumps(prepare(args.workspace, args.brief), ensure_ascii=False))
        return 0
    except (OSError, ValueError) as error:
        print(f"jewelry-remix: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
