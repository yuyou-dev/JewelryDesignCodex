import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "scripts" / "jewelry_visual_workbench.py"
IMAGE2 = ROOT / "scripts" / "jewelry_image2_tool.py"


PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cfc000000401010018dd8db10000000049454e44ae426082"
)


class JewelryVisualWorkbenchCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name) / "artifacts" / "runs" / "visual-test"
        (self.workspace / "references").mkdir(parents=True)
        for name in ["source.png", "stone.png", "jewelry.png", "model.png", "style.png"]:
            (self.workspace / "references" / name).write_bytes(PIXEL)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_draft(self, draft_id: str, payload: dict) -> Path:
        directory = self.workspace / "visual-workbench" / draft_id
        directory.mkdir(parents=True)
        (directory / "composite.jpg").write_bytes(PIXEL)
        (directory / "cutout.png").write_bytes(PIXEL)
        path = directory / "draft.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def run_prepare(self, command: str, draft: Path, job_id: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(WORKBENCH),
                command,
                "--workspace",
                str(self.workspace),
                "--draft",
                str(draft),
                "--job-id",
                job_id,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def test_prepare_sketch_compiles_four_distinct_runner_jobs_and_reference_priority(self) -> None:
        draft = self.write_draft("LOCAL-1234ABCD", {
            "id": "LOCAL-1234ABCD",
            "workflow": "local_edit",
            "state": {
                "mode": "sketch_design",
                "category": "ring",
                "sourcePath": "references/source.png",
                "stonePath": "references/stone.png",
                "referenceImages": [{"path": "references/style.png", "role": "style"}],
                "instruction": "围绕椭圆蓝宝石形成流线戒肩",
                "preserve": "主石切割、颜色与正面比例",
                "change": "把粗线转译为可制造戒臂",
                "material": "18K 白金、钻石",
                "style": "当代高级珠宝",
                "ratio": "1:1",
            },
            "assets": {
                "composite": "visual-workbench/LOCAL-1234ABCD/composite.jpg",
                "cutout": "visual-workbench/LOCAL-1234ABCD/cutout.png",
            },
        })
        result = self.run_prepare("prepare-local-edit", draft, "LOCAL-EDIT-A")
        self.assertEqual(result.returncode, 0, result.stderr)

        jobs_path = self.workspace / "visual-workbench" / "LOCAL-1234ABCD" / "jobs.json"
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))["jobs"]
        self.assertEqual([job["stable_id"] for job in jobs], ["SKETCH-A", "SKETCH-B", "SKETCH-C", "SKETCH-D"])
        self.assertTrue(all(job["batch_id"] == "LOCAL-1234ABCD" for job in jobs))
        self.assertEqual(len({job["output"] for job in jobs}), 4)
        self.assertEqual(len({job["prompt_file"] for job in jobs}), 4)
        self.assertEqual(jobs[0]["references"], [
            "references/source.png",
            "visual-workbench/LOCAL-1234ABCD/composite.jpg",
            "references/stone.png",
            "visual-workbench/LOCAL-1234ABCD/cutout.png",
            "references/style.png",
        ])
        prompt = (self.workspace / jobs[0]["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn("草图转珠宝", prompt)
        self.assertIn("不得照抄粗糙线宽", prompt)
        self.assertIn("主石原图负责切割、刻面、颜色与比例", prompt)
        self.assertIn("透明抠图只负责理解主石或放置素材的外轮廓", prompt)
        self.assertIn("参考图 5 只负责 style", prompt)
        self.assertIn("本路定位：忠实可制造转译", prompt)
        self.assertIn("真实可制造", prompt)
        prompts = [(self.workspace / job["prompt_file"]).read_text(encoding="utf-8") for job in jobs]
        self.assertEqual(len(set(prompts)), 4)

        add = subprocess.run(
            [sys.executable, str(IMAGE2), "add-jobs", "--workspace", str(self.workspace), "--input", str(jobs_path)],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(add.returncode, 0, add.stderr)
        validate = subprocess.run(
            [sys.executable, str(IMAGE2), "validate-jobs", "--workspace", str(self.workspace), "--job-manifest", str(draft.parent / "jobs.json"), "--requested-count", "4"],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(validate.returncode, 0, validate.stderr)

        second = self.write_draft("LOCAL-BLANK-SECOND", {
            "id": "LOCAL-BLANK-SECOND",
            "workflow": "local_edit",
            "state": {"mode": "sketch_design", "category": "bracelet", "instruction": "第二轮空白手链草图"},
            "assets": {"composite": "visual-workbench/LOCAL-BLANK-SECOND/composite.jpg"},
        })
        second_result = self.run_prepare("prepare-local-edit", second, "LOCAL-EDIT-A")
        self.assertEqual(second_result.returncode, 0, second_result.stderr)
        second_jobs = json.loads((second.parent / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        self.assertTrue({job["id"] for job in jobs}.isdisjoint(job["id"] for job in second_jobs))
        add_second = subprocess.run(
            [sys.executable, str(IMAGE2), "add-jobs", "--workspace", str(self.workspace), "--input", str(second.parent / "jobs.json")],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(add_second.returncode, 0, add_second.stderr)
        validate_second = subprocess.run(
            [sys.executable, str(IMAGE2), "validate-jobs", "--workspace", str(self.workspace), "--job-manifest", str(second.parent / "jobs.json"), "--requested-count", "4"],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(validate_second.returncode, 0, validate_second.stderr)

    def test_prepare_tryon_covers_ring_and_bracelet_physical_rules(self) -> None:
        for category, phrase in [("ring", "环绕所选手指"), ("bracelet", "环绕手腕椭圆")]:
            draft_id = f"TRYON-{category.upper()}"
            draft = self.write_draft(draft_id, {
                "id": draft_id,
                "workflow": "tryon",
                "state": {
                    "category": category,
                    "jewelryPath": "references/jewelry.png",
                    "modelPath": "references/model.png",
                    "instruction": "保持人物与首饰身份，生成自然佩戴效果",
                    "transform": {"x": 0.52, "y": 0.64, "scale": 0.22, "rotation": -8},
                    "pair": False,
                    "ratio": "3:4",
                },
                "assets": {
                    "composite": f"visual-workbench/{draft_id}/composite.jpg",
                    "cutout": f"visual-workbench/{draft_id}/cutout.png",
                },
            })
            result = self.run_prepare("prepare-tryon", draft, f"TRYON-{category.upper()}-A")
            self.assertEqual(result.returncode, 0, result.stderr)
            jobs = json.loads((self.workspace / "visual-workbench" / draft_id / "jobs.json").read_text(encoding="utf-8"))["jobs"]
            prompt = (self.workspace / jobs[0]["prompt_file"]).read_text(encoding="utf-8")
            self.assertEqual(jobs[0]["references"], [
                "references/jewelry.png",
                "references/model.png",
                f"visual-workbench/{draft_id}/composite.jpg",
                f"visual-workbench/{draft_id}/cutout.png",
            ])
            self.assertIn(phrase, prompt)
            self.assertIn("避免贴纸感", prompt)
            self.assertIn("人物原图负责身份、姿态、肤色、服装与背景", prompt)

    def test_schema_v2_local_edit_compiles_each_annotation_and_stays_single_output(self) -> None:
        draft = self.write_draft("LOCAL-V2", {
            "schema_version": 2,
            "id": "LOCAL-V2",
            "workflow": "local_edit",
            "state": {
                "mode": "local_edit",
                "category": "ring",
                "sourcePath": "references/source.png",
                "instruction": "按标注分别调整",
                "annotations": [
                    {
                        "id": "ANCHOR-01",
                        "kind": "anchor",
                        "position": {"x": 0.25, "y": 0.4},
                        "instruction": "此处改为18K黄金包边",
                    },
                    {
                        "id": "REGION-01",
                        "kind": "region",
                        "bounds": {"x": 0.55, "y": 0.2, "width": 0.25, "height": 0.3},
                        "instruction": "该区域增加密钉钻石",
                    },
                ],
            },
            "assets": {
                "composite": "visual-workbench/LOCAL-V2/composite.jpg",
                "cutout": "visual-workbench/LOCAL-V2/cutout.png",
                "cutoutPreview": "visual-workbench/LOCAL-V2/cutout-preview.jpg",
            },
        })
        (draft.parent / "cutout-preview.jpg").write_bytes(PIXEL)
        result = self.run_prepare("prepare-local-edit", draft, "LOCAL-EDIT-A")
        self.assertEqual(result.returncode, 0, result.stderr)
        jobs = json.loads((draft.parent / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["stable_id"], "LOCAL-EDIT-A")
        self.assertEqual(jobs[0]["references"], [
            "references/source.png",
            "visual-workbench/LOCAL-V2/composite.jpg",
            "visual-workbench/LOCAL-V2/cutout.png",
        ])
        prompt = (self.workspace / jobs[0]["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn("ANCHOR-01 (锚点 x=0.250, y=0.400)：此处改为18K黄金包边", prompt)
        self.assertIn("REGION-01 (区域 x=0.550, y=0.200, width=0.250, height=0.300)：该区域增加密钉钻石", prompt)
        self.assertIn("品类唯一真值：戒指", prompt)
        self.assertIn("不得改成吊坠、胸针或两用结构", prompt)
        self.assertNotIn("cutout-preview.jpg", jobs[0]["references"])

    def test_other_category_requires_custom_name_and_becomes_the_only_product_truth(self) -> None:
        draft = self.write_draft("LOCAL-OTHER", {
            "schemaVersion": 2,
            "id": "LOCAL-OTHER",
            "workflow": "local_edit",
            "state": {
                "mode": "put_here",
                "category": "other",
                "customCategory": "领带夹",
                "sourcePath": "references/source.png",
                "instruction": "把宝石放在中央，不要做成吊坠",
                "annotations": [{
                    "id": "ANCHOR-01",
                    "kind": "anchor",
                    "position": {"x": 0.5, "y": 0.5},
                    "instruction": "宝石中心对齐这个位置",
                }],
            },
            "assets": {"composite": "visual-workbench/LOCAL-OTHER/composite.jpg"},
        })
        result = self.run_prepare("prepare-local-edit", draft, "LOCAL-EDIT-CUSTOM")
        self.assertEqual(result.returncode, 0, result.stderr)
        jobs = json.loads((draft.parent / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        prompt = (self.workspace / jobs[0]["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn("品类唯一真值：领带夹", prompt)
        self.assertIn("真实可制造的佩戴、悬挂或连接结构", prompt)

        payload = json.loads(draft.read_text(encoding="utf-8"))
        del payload["state"]["customCategory"]
        draft.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        missing = self.run_prepare("prepare-local-edit", draft, "LOCAL-EDIT-CUSTOM")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("state.customCategory is required", missing.stderr)

    def test_schema_v2_rejects_missing_or_invalid_annotations(self) -> None:
        draft = self.write_draft("LOCAL-ANNOTATIONS", {
            "schema_version": 2,
            "id": "LOCAL-ANNOTATIONS",
            "workflow": "local_edit",
            "state": {
                "mode": "local_edit",
                "category": "ring",
                "sourcePath": "references/source.png",
                "annotations": [],
            },
            "assets": {"composite": "visual-workbench/LOCAL-ANNOTATIONS/composite.jpg"},
        })
        missing = self.run_prepare("prepare-local-edit", draft, "LOCAL-EDIT-A")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("require at least one annotation", missing.stderr)

        payload = json.loads(draft.read_text(encoding="utf-8"))
        payload["state"]["annotations"] = [{
            "id": "REGION-01",
            "kind": "region",
            "bounds": {"x": 0.9, "y": 0.9, "width": 0.2, "height": 0.2},
            "instruction": "改这里",
        }]
        draft.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        invalid = self.run_prepare("prepare-local-edit", draft, "LOCAL-EDIT-A")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("positive rectangle inside the canvas", invalid.stderr)

    def test_uploaded_pure_sketch_keeps_each_supported_category_across_all_four_outputs(self) -> None:
        category_phrases = {
            "ring": ("戒指", "戒臂连续闭合"),
            "bracelet": ("手链/手镯", "腕围逻辑连续"),
            "necklace": ("项链", "链条、连接环与后扣完整"),
            "pendant": ("吊坠", "吊环、金属支撑与悬挂重心真实"),
            "earrings": ("耳饰", "耳针、耳钩或耳夹连接明确"),
            "brooch": ("胸针", "背部针梁、针扣与主体支撑可制造"),
        }
        for category, (name, rule) in category_phrases.items():
            draft_id = f"LOCAL-SKETCH-{category.upper()}"
            draft = self.write_draft(draft_id, {
                "schema_version": 2,
                "id": draft_id,
                "workflow": "local_edit",
                "state": {
                    "mode": "sketch_design",
                    "category": category,
                    "sourcePath": "references/source.png",
                    "instruction": "将上传线稿转成一组可制造珠宝",
                    "annotations": [],
                },
                "assets": {"composite": f"visual-workbench/{draft_id}/composite.jpg"},
            })
            result = self.run_prepare("prepare-local-edit", draft, "LOCAL-EDIT-A")
            self.assertEqual(result.returncode, 0, result.stderr)
            jobs = json.loads((draft.parent / "jobs.json").read_text(encoding="utf-8"))["jobs"]
            self.assertEqual([job["stable_id"] for job in jobs], ["SKETCH-A", "SKETCH-B", "SKETCH-C", "SKETCH-D"])
            for job in jobs:
                prompt = (self.workspace / job["prompt_file"]).read_text(encoding="utf-8")
                self.assertIn(f"品类唯一真值：{name}", prompt)
                self.assertIn(rule, prompt)
                self.assertIn("不得生成其他首饰品类或两用款", prompt)

    def test_rejects_wrong_workflow_paths_and_unstable_job_ids(self) -> None:
        outside = Path(self.temp.name) / "outside.png"
        outside.write_bytes(PIXEL)
        draft = self.write_draft("LOCAL-BAD", {
            "id": "LOCAL-BAD",
            "workflow": "local_edit",
            "state": {
                "mode": "local_edit",
                "category": "ring",
                "sourcePath": str(outside),
                "instruction": "改动局部",
            },
            "assets": {"composite": "visual-workbench/LOCAL-BAD/composite.jpg"},
        })
        escaped = self.run_prepare("prepare-local-edit", draft, "LOCAL-EDIT-A")
        self.assertNotEqual(escaped.returncode, 0)
        self.assertIn("workspace", escaped.stderr)

        payload = json.loads(draft.read_text(encoding="utf-8"))
        payload["state"]["sourcePath"] = "references/source.png"
        draft.write_text(json.dumps(payload), encoding="utf-8")
        unstable = self.run_prepare("prepare-local-edit", draft, "../escape")
        self.assertNotEqual(unstable.returncode, 0)
        self.assertIn("job-id", unstable.stderr)

    def test_accepts_the_documented_project_relative_draft_path(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as local_temp:
            workspace = Path(local_temp) / "artifacts" / "runs" / "docs-path"
            references = workspace / "references"
            draft_dir = workspace / "visual-workbench" / "LOCAL-DOCS"
            references.mkdir(parents=True)
            draft_dir.mkdir(parents=True)
            (references / "source.png").write_bytes(PIXEL)
            (draft_dir / "composite.jpg").write_bytes(PIXEL)
            draft = draft_dir / "draft.json"
            draft.write_text(json.dumps({
                "id": "LOCAL-DOCS",
                "workflow": "local_edit",
                "state": {
                    "mode": "sketch_design",
                    "category": "pendant",
                    "sourcePath": "references/source.png",
                    "instruction": "把线稿转成吊坠",
                },
                "assets": {"composite": "visual-workbench/LOCAL-DOCS/composite.jpg"},
            }, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([
                sys.executable,
                str(WORKBENCH),
                "prepare-local-edit",
                "--workspace",
                str(workspace.relative_to(ROOT)),
                "--draft",
                str(draft.relative_to(ROOT)),
                "--job-id",
                "LOCAL-EDIT-A",
            ], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_prepare_blank_canvas_sketch_without_source_image(self) -> None:
        draft = self.write_draft("LOCAL-BLANK", {
            "id": "LOCAL-BLANK",
            "workflow": "local_edit",
            "state": {
                "mode": "sketch_design",
                "category": "ring",
                "instruction": "从空白画板上的线条设计一枚戒指",
                "material": "18K 黄金",
                "ratio": "1:1",
            },
            "assets": {"composite": "visual-workbench/LOCAL-BLANK/composite.jpg"},
        })
        result = self.run_prepare("prepare-local-edit", draft, "LOCAL-EDIT-A")
        self.assertEqual(result.returncode, 0, result.stderr)
        jobs = json.loads((draft.parent / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        self.assertEqual(len(jobs), 4)
        self.assertEqual([job["stable_id"] for job in jobs], ["SKETCH-A", "SKETCH-B", "SKETCH-C", "SKETCH-D"])
        self.assertTrue(all(job["references"] == ["visual-workbench/LOCAL-BLANK/composite.jpg"] for job in jobs))
        prompt = (self.workspace / jobs[0]["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn("没有上传源图", prompt)
        self.assertIn("画布合成图负责全部几何意图", prompt)
        add = subprocess.run(
            [sys.executable, str(IMAGE2), "add-jobs", "--workspace", str(self.workspace), "--input", str(draft.parent / "jobs.json")],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(add.returncode, 0, add.stderr)
        validate = subprocess.run(
            [sys.executable, str(IMAGE2), "validate-jobs", "--workspace", str(self.workspace), "--requested-count", "4"],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_non_sketch_modes_still_require_source_image(self) -> None:
        for mode in ["local_edit", "put_here"]:
            draft = self.write_draft(f"LOCAL-{mode.upper()}", {
                "id": f"LOCAL-{mode.upper()}",
                "workflow": "local_edit",
                "state": {"mode": mode, "category": "ring", "instruction": "修改局部"},
                "assets": {"composite": f"visual-workbench/LOCAL-{mode.upper()}/composite.jpg"},
            })
            result = self.run_prepare("prepare-local-edit", draft, "LOCAL-EDIT-A")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("state.sourcePath is required", result.stderr)


if __name__ == "__main__":
    unittest.main()
