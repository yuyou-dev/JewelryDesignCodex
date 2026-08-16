#!/usr/bin/env python3
"""Compile visual-workbench drafts into project-local Image-2 jobs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


JOB_ID = re.compile(r"^(LOCAL-EDIT|TRYON)-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
ANNOTATION_ID = re.compile(r"^(ANCHOR|REGION)-[0-9]{2}$")
LOCAL_MODES = {"local_edit", "put_here", "sketch_design"}
LOCAL_CATEGORIES = {"ring", "necklace", "earrings", "bracelet", "pendant", "brooch", "other"}
TRYON_CATEGORIES = {"ring", "bracelet", "necklace", "pendant", "earrings", "brooch"}
REFERENCE_ROLES = {"material", "craft", "style", "structure", "mood"}

CATEGORY_NAMES = {
    "ring": "戒指",
    "bracelet": "手链/手镯",
    "necklace": "项链",
    "pendant": "吊坠",
    "earrings": "耳饰",
    "brooch": "胸针",
}

CATEGORY_RULES = {
    "ring": "保持单一戒指品类：戒臂连续闭合，镶口、戒肩与受力支撑真实，不得改成吊坠、胸针或两用结构。",
    "bracelet": "保持单一手链或手镯品类：链节、铰接或刚性腕围逻辑连续，扣件可制造且可佩戴。",
    "necklace": "保持单一项链品类：链条、连接环与后扣完整，主体遵循颈部悬挂和重力逻辑。",
    "pendant": "保持单一吊坠品类：吊环、金属支撑与悬挂重心真实，不得增加胸针背针或两用结构。",
    "earrings": "保持单一耳饰品类：耳针、耳钩或耳夹连接明确，重心、平衡与佩戴方向合理。",
    "brooch": "保持单一胸针品类：背部针梁、针扣与主体支撑可制造，不得改成吊坠或两用结构。",
}

SKETCH_BRANCHES = (
    ("SKETCH-A", "忠实可制造转译", "最忠实保留草图的轮廓、连接和主石关系，优先解决镶嵌、支撑与佩戴可制造性。"),
    ("SKETCH-B", "比例与结构精修", "保持草图身份，优化主次比例、对称或动势、金属厚度、连接节点与佩戴舒适度。"),
    ("SKETCH-C", "工艺与材质强化", "保持草图几何意图，重点强化贵金属表面、宝石镶嵌、边缘收口与细节工艺层次。"),
    ("SKETCH-D", "主题与形态强化", "保持草图核心轮廓和品类，强化主题辨识度、形态节奏和系列化设计语言，但不得改成其他首饰品类。"),
)

TRYON_RULES = {
    "ring": "让戒指环绕所选手指，匹配指节透视与近远端遮挡，戒臂必须在手指背后自然消失。",
    "bracelet": "让手链或手镯环绕手腕椭圆，匹配腕部透视、重力与皮肤接触，不得漂浮。",
    "necklace": "让项链沿颈部和锁骨弧线自然下垂，链条受重力并与皮肤或衣物产生真实遮挡。",
    "pendant": "让吊坠悬挂在真实链条最低点，保持正面朝向并形成合理重力、接触与投影。",
    "earrings": "让耳饰连接耳垂或耳廓的真实穿戴点，成对时保持同款但遵循两侧透视和头发遮挡。",
    "brooch": "让胸针固定在衣物平面上，匹配布料透视、褶皱与接触阴影，不改变服装结构。",
}

MODE_TEXT = {
    "local_edit": "局部修改",
    "put_here": "Put it here 定点放置",
    "sketch_design": "草图转珠宝",
}


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or isinstance(value, list):
        raise ValueError(f"{label} must be an object")
    return value


def clean_text(value: Any, fallback: str = "") -> str:
    return str(value or "").strip() or fallback


def workspace_file(workspace: Path, value: Any, label: str, *, required: bool = True) -> str | None:
    raw = clean_text(value)
    if not raw:
        if required:
            raise ValueError(f"{label} is required")
        return None
    candidate = Path(raw).expanduser()
    resolved = (candidate if candidate.is_absolute() or candidate.exists() else workspace / candidate).resolve()
    if not resolved.is_relative_to(workspace):
        raise ValueError(f"{label} must stay inside the workspace")
    if not resolved.is_file():
        raise ValueError(f"{label} does not exist: {raw}")
    return resolved.relative_to(workspace).as_posix()


def load_draft(workspace: Path, draft_arg: str) -> tuple[dict[str, Any], Path]:
    candidate = Path(clean_text(draft_arg)).expanduser()
    resolved = (candidate if candidate.is_absolute() or candidate.exists() else workspace / candidate).resolve()
    if not resolved.is_relative_to(workspace):
        raise ValueError("draft must stay inside the workspace")
    if not resolved.is_file():
        raise ValueError("draft does not exist")
    try:
        payload = require_object(json.loads(resolved.read_text(encoding="utf-8")), "draft")
    except json.JSONDecodeError as error:
        raise ValueError(f"draft is not valid JSON: {error.msg}") from error
    return payload, resolved


def normalize_job_id(value: str, prefix: str) -> str:
    job_id = clean_text(value)
    if len(job_id) > 64 or not JOB_ID.fullmatch(job_id) or not job_id.startswith(f"{prefix}-"):
        raise ValueError(f"job-id must use the stable {prefix}-A format")
    return job_id


def scoped_job_id(stable_id: str, draft_id: str) -> str:
    token = re.sub(r"[^A-Z0-9]+", "", draft_id.upper())[-16:] or "DRAFT"
    return f"{stable_id}-{token}"


def write_jobs(workspace: Path, draft_path: Path, draft_id: str, jobs_and_prompts: list[tuple[dict[str, Any], str]]) -> dict[str, Any]:
    prompt_paths: list[str] = []
    jobs: list[dict[str, Any]] = []
    for job, prompt in jobs_and_prompts:
        prompt_relative = f"prompts/{job['id']}.prompt.txt"
        prompt_path = workspace / prompt_relative
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt, encoding="utf-8")
        job["prompt_file"] = prompt_relative
        job["allow_duplicate_prompt"] = True
        prompt_paths.append(prompt_relative)
        jobs.append(job)
    jobs_path = draft_path.parent / "jobs.json"
    jobs_path.write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result: dict[str, Any] = {
        "draft_id": draft_id,
        "job_ids": [job["id"] for job in jobs],
        "stable_job_ids": [job.get("stable_id", job["id"]) for job in jobs],
        "prompt": prompt_paths[0],
        "prompts": prompt_paths,
        "jobs": jobs_path.relative_to(workspace).as_posix(),
    }
    return result


def draft_schema_version(draft: dict[str, Any]) -> int:
    raw = draft.get("schema_version", draft.get("schemaVersion", 1))
    if isinstance(raw, bool):
        raise ValueError("draft schema version must be 1 or 2")
    try:
        version = int(raw)
    except (TypeError, ValueError) as error:
        raise ValueError("draft schema version must be 1 or 2") from error
    if version not in {1, 2}:
        raise ValueError("draft schema version must be 1 or 2")
    return version


def normalized_coordinate(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a number between 0 and 1") from error
    if not 0 <= number <= 1:
        raise ValueError(f"{label} must be between 0 and 1")
    return number


def normalize_annotations(state: dict[str, Any], mode: str, schema_version: int) -> list[dict[str, Any]]:
    raw = state.get("annotations", [])
    if raw is None and schema_version == 1:
        raw = []
    if not isinstance(raw, list):
        raise ValueError("state.annotations must be a list")
    if len(raw) > 8:
        raise ValueError("state.annotations supports at most 8 items")
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw):
        annotation = require_object(item, f"state.annotations[{index}]")
        annotation_id = clean_text(annotation.get("id"))
        kind = clean_text(annotation.get("kind"))
        match = ANNOTATION_ID.fullmatch(annotation_id)
        if not match or annotation_id in seen_ids:
            raise ValueError(f"state.annotations[{index}].id must be a unique ANCHOR-01 or REGION-01 id")
        if kind not in {"anchor", "region"} or match.group(1).lower() != kind:
            raise ValueError(f"state.annotations[{index}].kind must match its id")
        instruction = clean_text(annotation.get("instruction"))
        if not instruction:
            raise ValueError(f"state.annotations[{index}].instruction is required")
        result: dict[str, Any] = {"id": annotation_id, "kind": kind, "instruction": instruction}
        if kind == "anchor":
            position = require_object(annotation.get("position"), f"state.annotations[{index}].position")
            result["position"] = {
                "x": normalized_coordinate(position.get("x"), f"state.annotations[{index}].position.x"),
                "y": normalized_coordinate(position.get("y"), f"state.annotations[{index}].position.y"),
            }
        else:
            bounds = require_object(annotation.get("bounds"), f"state.annotations[{index}].bounds")
            x = normalized_coordinate(bounds.get("x"), f"state.annotations[{index}].bounds.x")
            y = normalized_coordinate(bounds.get("y"), f"state.annotations[{index}].bounds.y")
            width = normalized_coordinate(bounds.get("width"), f"state.annotations[{index}].bounds.width")
            height = normalized_coordinate(bounds.get("height"), f"state.annotations[{index}].bounds.height")
            if width == 0 or height == 0 or x + width > 1 or y + height > 1:
                raise ValueError(f"state.annotations[{index}].bounds must be a positive rectangle inside the canvas")
            result["bounds"] = {"x": x, "y": y, "width": width, "height": height}
        seen_ids.add(annotation_id)
        normalized.append(result)
    if schema_version == 2 and mode in {"local_edit", "put_here"} and not normalized:
        raise ValueError("draft schema v2 local_edit and put_here require at least one annotation")
    return normalized


def category_details(state: dict[str, Any]) -> tuple[str, str, str]:
    category = clean_text(state.get("category"))
    if category not in LOCAL_CATEGORIES:
        raise ValueError("state.category is unsupported")
    if category == "other":
        custom = clean_text(state.get("customCategory"))
        if not custom:
            raise ValueError("state.customCategory is required when state.category is other")
        if len(custom) > 40:
            raise ValueError("state.customCategory must be 40 characters or fewer")
        return category, custom, f"保持单一「{custom}」品类；必须建立真实可制造的佩戴、悬挂或连接结构，不得改成其他首饰品类或两用款。"
    return category, CATEGORY_NAMES[category], CATEGORY_RULES[category]


def reference_items(workspace: Path, state: dict[str, Any]) -> list[tuple[str, str]]:
    raw = state.get("referenceImages", [])
    if not isinstance(raw, list):
        raise ValueError("state.referenceImages must be a list")
    normalized: list[tuple[str, str]] = []
    for index, item in enumerate(raw):
        reference = require_object(item, f"state.referenceImages[{index}]")
        role = clean_text(reference.get("role"))
        if role not in REFERENCE_ROLES:
            raise ValueError(f"state.referenceImages[{index}].role is unsupported")
        path = workspace_file(workspace, reference.get("path"), f"state.referenceImages[{index}].path")
        assert path is not None
        normalized.append((path, role))
    return normalized


def annotation_lines(annotations: list[dict[str, Any]]) -> str:
    if not annotations:
        return "-无结构化标注；仅使用画布和设计指令。"
    lines: list[str] = []
    for annotation in annotations:
        if annotation["kind"] == "anchor":
            position = annotation["position"]
            location = f"锚点 x={position['x']:.3f}, y={position['y']:.3f}"
        else:
            bounds = annotation["bounds"]
            location = (
                f"区域 x={bounds['x']:.3f}, y={bounds['y']:.3f}, "
                f"width={bounds['width']:.3f}, height={bounds['height']:.3f}"
            )
        lines.append(f"- {annotation['id']} ({location})：{annotation['instruction']}")
    return "\n".join(lines)


def local_prompt(
    state: dict[str, Any],
    mode: str,
    category_name: str,
    category_rule: str,
    references: list[tuple[str, str]],
    has_source: bool,
    has_stone: bool,
    has_cutout: bool,
    annotations: list[dict[str, Any]],
    branch: tuple[str, str, str] | None = None,
) -> str:
    instruction = clean_text(state.get("instruction"), "依据画布标注完成设计意图")
    preserve = clean_text(state.get("preserve"), "保留未标注区域与原有产品身份" if has_source else "保留画布中的轮廓、连接、比例和视觉节奏")
    change = clean_text(state.get("change"), "只改变画布明确标注的区域或结构" if has_source else "将画布线条转译为完整可制造的珠宝结构")
    material = clean_text(state.get("material"), "沿用原图可见贵金属与宝石材质" if has_source else "使用符合设计意图的真实贵金属、宝石与镶嵌工艺")
    style = clean_text(state.get("style"), "高级珠宝产品设计")
    priority: list[str] = []
    if has_source:
        priority.append("原始图负责现有产品事实，或在纯草图场景中负责几何意图。")
        priority.append("画布合成图只负责空间标记、局部范围、放置、比例、朝向与草图意图；忽略界面、控制点、辅助色、画笔锯齿和粗糙抠图边缘。")
    else:
        priority.append("没有上传源图；画布合成图负责全部几何意图，包括轮廓、连接、比例、朝向和手绘节奏；忽略界面、控制点、辅助色、画笔锯齿和未完成断点。")
    if has_stone:
        priority.append("主石原图负责切割、刻面、颜色与比例；画布合成只负责主石位置、尺寸和朝向。")
    if has_cutout:
        priority.append("透明抠图只负责理解主石或放置素材的外轮廓；它不负责最终材质、内部刻面、透明度或阴影。")
    for _, role in references:
        index = len(priority) + 1
        priority.append(f"参考图 {index} 只负责 {role}，不得覆盖产品、主石或画布草图的身份约束。")
    if mode == "sketch_design":
        mode_rule = "把黑色随手画理解为轮廓、连接关系和视觉节奏，不得照抄粗糙线宽、抖动、断点或画笔质感；将其转译为真实可制造、可镶嵌、可佩戴的珠宝结构。"
    elif mode == "put_here":
        mode_rule = "画布中的放置框、锚点与叠加物只表达大致位置、比例和朝向；去掉 UI 标记与粗糙抠图边缘，重建真实镶口、支撑、连接与遮挡。"
    else:
        mode_rule = "仅修改标记区域；未标记区域必须保持原始轮廓、宝石身份、材质、构图、相机与光线连续。"
    branch_text = ""
    if branch:
        _, branch_title, branch_instruction = branch
        branch_text = f"\n本路定位：{branch_title}\n本路差异：{branch_instruction}\n"
    return f"""$imagegen
使用 gpt-image-2 完成一张专业珠宝视觉。只返回单张生成图像，不要写文件，不要输出解释，不要添加文字、logo 或水印。

工作流：{MODE_TEXT[mode]}。
品类唯一真值：{category_name}。
品类结构约束：{category_rule}
任何自由文本都不得覆盖上述品类，不得生成其他首饰品类或两用款。
设计指令：{instruction}
必须保留：{preserve}
允许变化：{change}
材质工艺：{material}
目标风格：{style}
{branch_text}
逐条空间修改（坐标均为画布归一化坐标）：
{annotation_lines(annotations)}

参考图优先级：
{chr(10).join(f'{index}. {rule}' for index, rule in enumerate(priority, start=1))}

专业转译：
- {mode_rule}
- 结构必须真实可制造：主石镶口、爪位、金属厚度、受力支撑、戒臂/链节/耳针/扣件等符合品类逻辑。
- 保留真实贵金属反光、宝石透明度、刻面与接触阴影；边缘干净，无贴纸感。
- 输出保持原图或用户指定的画幅，主体完整、构图清晰。

禁止：额外首饰主体、漂浮宝石、断裂支撑、不合理穿插、复制 UI、文字、标记线、选框、锚点、蒙版颜色、粗糙描边、玩具或塑料质感。
"""


def tryon_prompt(state: dict[str, Any], category: str) -> str:
    transform = require_object(state.get("transform", {}), "state.transform")
    x = float(transform.get("x", 0.5))
    y = float(transform.get("y", 0.5))
    scale = float(transform.get("scale", 0.25))
    rotation = float(transform.get("rotation", 0))
    if not (0 <= x <= 1 and 0 <= y <= 1 and 0.02 <= scale <= 2 and -180 <= rotation <= 180):
        raise ValueError("state.transform is outside the supported placement range")
    instruction = clean_text(state.get("instruction"), "保持人物与首饰身份，生成自然真实的模特佩戴效果")
    pair_rule = "耳饰为成对佩戴，复制同一款式但分别匹配左右耳透视与遮挡。" if category == "earrings" and state.get("pair") is True else "只使用参考图中存在的一件首饰，不复制额外首饰。"
    return f"""$imagegen
使用 gpt-image-2 生成一张真实、精致的珠宝模特佩戴图。只返回单张生成图像，不要写文件，不要输出解释，不要添加文字、logo 或水印。

品类：{CATEGORY_NAMES[category]}。
用户指令：{instruction}

参考图优先级：
1. 珠宝原图负责首饰的准确款式、轮廓、宝石切割与颜色、金属结构、镶嵌与比例，不得擅自改款。
2. 人物原图负责身份、姿态、肤色、服装与背景，不得改变脸、手、身体结构或服装款式。
3. 画布合成图只负责近似佩戴位置、尺寸、旋转和成对关系；忽略画布 UI、控制柄、平面抠图边缘和不真实光线。
4. 抠图预览只用于理解珠宝边界，不是最终材质或最终阴影。

放置约束：画布归一化位置 x={x:.3f}, y={y:.3f}，相对尺度={scale:.3f}，旋转={rotation:.1f}°。这些是近似构图约束，不得凌驾于人体结构与真实佩戴逻辑。
品类物理规则：{TRYON_RULES[category]}
成对规则：{pair_rule}

融合要求：重建与人物场景一致的透视、光向、色温、宝石折射、金属反射、接触阴影与必要遮挡；避免贴纸感、漂浮感、硬抠图边、重复首饰和尺寸失真。保持自然皮肤纹理与人体解剖。

禁止：改变人物身份、手指数量或肢体结构，替换服装，改变首饰设计，悬浮首饰，穿模，不合理复制，文字，logo，水印，控制点或选框。
"""


def prepare(workspace_arg: str, draft_arg: str, job_id_arg: str, workflow: str) -> dict[str, Any]:
    workspace = Path(workspace_arg).expanduser().resolve()
    if not workspace.is_dir():
        raise ValueError("workspace must exist")
    draft, draft_path = load_draft(workspace, draft_arg)
    if clean_text(draft.get("workflow")) != workflow:
        raise ValueError(f"draft workflow must be {workflow}")
    draft_id = clean_text(draft.get("id"))
    if not draft_id or draft_path.parent.name != draft_id:
        raise ValueError("draft id must match its visual-workbench directory")
    schema_version = draft_schema_version(draft)
    state = require_object(draft.get("state"), "draft.state")
    assets = require_object(draft.get("assets"), "draft.assets")
    composite = workspace_file(workspace, assets.get("composite"), "draft.assets.composite")
    assert composite is not None

    if workflow == "local_edit":
        requested_job_id = normalize_job_id(job_id_arg, "LOCAL-EDIT")
        mode = clean_text(state.get("mode"))
        if mode not in LOCAL_MODES:
            raise ValueError("state.mode must be local_edit, put_here, or sketch_design")
        _, category_name, category_rule = category_details(state)
        annotations = normalize_annotations(state, mode, schema_version)
        source = workspace_file(workspace, state.get("sourcePath"), "state.sourcePath", required=mode != "sketch_design")
        stone = workspace_file(workspace, state.get("stonePath"), "state.stonePath", required=False)
        cutout = workspace_file(workspace, assets.get("cutout"), "draft.assets.cutout", required=False)
        workspace_file(workspace, assets.get("cutoutPreview"), "draft.assets.cutoutPreview", required=False)
        references = reference_items(workspace, state)
        reference_paths = [source, composite] if source else [composite]
        if stone:
            reference_paths.append(stone)
        if cutout:
            reference_paths.append(cutout)
        reference_paths.extend(path for path, _ in references)
        ratio = clean_text(state.get("ratio"), "1:1")
        kind = "jewelry-local-edit"
        if mode == "sketch_design":
            jobs_and_prompts = []
            for branch in SKETCH_BRANCHES:
                stable_id, branch_title, _ = branch
                job_id = scoped_job_id(stable_id, draft_id)
                job = {
                    "id": job_id,
                    "stable_id": stable_id,
                    "batch_id": draft_id,
                    "title": f"{MODE_TEXT[mode]} · {category_name} · {branch_title}",
                    "kind": kind,
                    "ratio": ratio,
                    "output": f"outputs/{job_id}.png",
                    "references": reference_paths,
                }
                prompt = local_prompt(
                    state,
                    mode,
                    category_name,
                    category_rule,
                    references,
                    source is not None,
                    stone is not None,
                    cutout is not None,
                    annotations,
                    branch,
                )
                jobs_and_prompts.append((job, prompt))
            return write_jobs(workspace, draft_path, draft_id, jobs_and_prompts)
        stable_id = requested_job_id
        job_id = scoped_job_id(stable_id, draft_id)
        prompt = local_prompt(
            state,
            mode,
            category_name,
            category_rule,
            references,
            source is not None,
            stone is not None,
            cutout is not None,
            annotations,
        )
        title = f"{MODE_TEXT[mode]} · {category_name}"
    else:
        stable_id = normalize_job_id(job_id_arg, "TRYON")
        job_id = scoped_job_id(stable_id, draft_id)
        category = clean_text(state.get("category"))
        if category not in TRYON_CATEGORIES:
            raise ValueError("state.category is unsupported")
        jewelry = workspace_file(workspace, state.get("jewelryPath"), "state.jewelryPath")
        model = workspace_file(workspace, state.get("modelPath"), "state.modelPath")
        cutout = workspace_file(workspace, assets.get("cutout"), "draft.assets.cutout", required=False)
        reference_paths = [jewelry, model, composite]
        if cutout:
            reference_paths.append(cutout)
        prompt = tryon_prompt(state, category)
        ratio = clean_text(state.get("ratio"), "3:4")
        title = f"模特佩戴 · {CATEGORY_NAMES[category]}"
        kind = "jewelry-model-tryon"

    job = {
        "id": job_id,
        "stable_id": stable_id,
        "batch_id": draft_id,
        "title": title,
        "kind": kind,
        "ratio": ratio,
        "output": f"outputs/{job_id}.png",
        "references": reference_paths,
    }
    return write_jobs(workspace, draft_path, draft_id, [(job, prompt)])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ["prepare-local-edit", "prepare-tryon"]:
        sub = subparsers.add_parser(command)
        sub.add_argument("--workspace", required=True)
        sub.add_argument("--draft", required=True)
        sub.add_argument("--job-id", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workflow = "local_edit" if args.command == "prepare-local-edit" else "tryon"
    try:
        result = prepare(args.workspace, args.draft, args.job_id, workflow)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
