import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REMIX = ROOT / "scripts" / "jewelry_remix.py"
IMAGE2 = ROOT / "scripts" / "jewelry_image2_tool.py"


class JewelryRemixCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name) / "artifacts" / "runs" / "remix-test"
        (self.workspace / "references").mkdir(parents=True)
        self.source = self.workspace / "references" / "source.png"
        self.source.write_bytes(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
                "0000000d49444154789c6360f8cfc000000401010018dd8db10000000049454e44ae426082"
            )
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def brief(self, count: int = 4) -> dict:
        roles = [
            ("A", "商业化", "收紧轮廓与小钻节奏", "日常主款"),
            ("B", "主题强化", "将藤蔓转译为戒肩结构", "系列主款"),
            ("C", "工艺材质", "强化镜空与微镶层次", "展示工艺"),
            ("D", "大胆概念", "重组局部体量与视觉重心", "形象款"),
            ("E", "高级珠宝", "增加收藏级宝石层次", "高级系列"),
            ("F", "日常轻量", "减少金属体量并优化佩戴", "日常线"),
            ("G", "文化符号", "将东方云纹转译为边缘秩序", "文化限定"),
            ("H", "系列延展", "建立可迁移至耳饰的模块", "套系延展"),
        ]
        return {
            "schema_version": 2,
            "count": count,
            "source": "references/source.png",
            "identity": {
                "type": "戒指",
                "silhouette": "中心镶嵌、左右对称戒肩",
                "proportions": "主石占视觉中心约二分之一",
                "focal_materials": "黄宝石主石、白色贵金属、配钻",
                "construction": "四爪主镶、对称戒肩、闭合戒臂",
                "locked_parts": ["主石颜色与切割", "戒指佩戴逻辑"],
                "editable_parts": ["戒肩", "副石排列", "金属边缘"],
            },
            "preferences": {
                "design_system": "gem_set",
                "structure_fidelity": "medium",
                "intensity": "balanced",
                "fusion_strategy": "pattern_translation",
                "themes": ["nature-universe", "gemstone-narrative"],
                "morphologies": ["organic-natural", "central-symmetry"],
                "styles": ["modern-minimal", "artistic-avant-garde"],
                "materials": ["preserve-source-material", "diamond-accent"],
                "direction": "白底棚拍，保持真实可佩戴",
            },
            "references": [],
            "candidates": [
                {
                    "id": f"REMIX-{letter}",
                    "title": title,
                    "positioning": title,
                    "difference": difference,
                    "theme": "藤蔓花叶" if letter < "G" else "东方云纹",
                    "morphology": "流线曲面" if letter in "ABEF" else "镂空花丝",
                    "style": "当代极简" if letter in "AF" else "高级珠宝",
                    "material_craft": "铂金、钻石、精密爪镶",
                    "change_scope": difference,
                    "use_case": use_case,
                }
                for letter, title, difference, use_case in roles[:count]
            ],
        }

    def run_prepare(self, brief: dict) -> subprocess.CompletedProcess[str]:
        brief_path = self.workspace / "remix-brief.json"
        brief_path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(REMIX),
                "prepare",
                "--workspace",
                str(self.workspace),
                "--brief",
                str(brief_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def test_prepare_four_compiles_runner_jobs_and_matrix(self) -> None:
        result = self.run_prepare(self.brief(4))
        self.assertEqual(result.returncode, 0, result.stderr)

        matrix = json.loads((self.workspace / "remix" / "matrix.json").read_text(encoding="utf-8"))
        jobs = json.loads((self.workspace / "remix" / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        self.assertEqual(matrix["requested_count"], 4)
        self.assertEqual(matrix["schema_version"], 2)
        self.assertEqual(matrix["preferences"]["design_system"], "gem_set")
        self.assertEqual(matrix["preferences"]["theme_labels"], ["自然万象", "宝石叙事"])
        self.assertEqual([item["id"] for item in matrix["candidates"]], ["REMIX-A", "REMIX-B", "REMIX-C", "REMIX-D"])
        self.assertEqual(len(jobs), 4)
        self.assertEqual(len({job["output"] for job in jobs}), 4)
        self.assertTrue(all(job["references"][0] == "references/source.png" for job in jobs))

        prompts = [(self.workspace / job["prompt_file"]).read_text(encoding="utf-8") for job in jobs]
        self.assertEqual(len(set(prompts)), 4)
        for prompt in prompts:
            self.assertIn("$imagegen", prompt)
            self.assertIn("底座身份锁", prompt)
            self.assertIn("产品体系：镶嵌（gem_set）", prompt)
            self.assertIn("主题池：自然万象、宝石叙事", prompt)
            self.assertIn("真实可佩戴结构", prompt)
            self.assertIn("禁止", prompt)

        add = subprocess.run(
            [sys.executable, str(IMAGE2), "add-jobs", "--workspace", str(self.workspace), "--input", str(self.workspace / "remix" / "jobs.json")],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(add.returncode, 0, add.stderr)
        validate = subprocess.run(
            [sys.executable, str(IMAGE2), "validate-jobs", "--workspace", str(self.workspace), "--job-manifest", "remix/jobs.json", "--requested-count", "4"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_prepare_accepts_repo_relative_brief_path_used_by_skill(self) -> None:
        brief_path = self.workspace / "remix-brief.json"
        brief_path.write_text(json.dumps(self.brief(4), ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(REMIX),
                "prepare",
                "--workspace",
                str(self.workspace),
                "--brief",
                os.path.relpath(brief_path, ROOT),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_prepare_eight_keeps_stable_ids(self) -> None:
        result = self.run_prepare(self.brief(8))
        self.assertEqual(result.returncode, 0, result.stderr)
        jobs = json.loads((self.workspace / "remix" / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        self.assertEqual([job["stable_id"] for job in jobs], [f"REMIX-{letter}" for letter in "ABCDEFGH"])
        self.assertEqual(len({job["batch_id"] for job in jobs}), 1)
        add = subprocess.run(
            [sys.executable, str(IMAGE2), "add-jobs", "--workspace", str(self.workspace), "--input", str(self.workspace / "remix" / "jobs.json")],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(add.returncode, 0, add.stderr)
        validate = subprocess.run(
            [sys.executable, str(IMAGE2), "validate-jobs", "--workspace", str(self.workspace), "--job-manifest", "remix/jobs.json", "--requested-count", "8"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_repeated_remix_rounds_use_distinct_runner_ids_and_exact_manifest(self) -> None:
        first = self.run_prepare(self.brief(4))
        self.assertEqual(first.returncode, 0, first.stderr)
        first_jobs = json.loads((self.workspace / "remix" / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        add_first = subprocess.run(
            [sys.executable, str(IMAGE2), "add-jobs", "--workspace", str(self.workspace), "--input", str(self.workspace / "remix" / "jobs.json")],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(add_first.returncode, 0, add_first.stderr)

        second = self.run_prepare(self.brief(4))
        self.assertEqual(second.returncode, 0, second.stderr)
        second_jobs = json.loads((self.workspace / "remix" / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        self.assertTrue({job["id"] for job in first_jobs}.isdisjoint(job["id"] for job in second_jobs))
        self.assertEqual([job["stable_id"] for job in second_jobs], ["REMIX-A", "REMIX-B", "REMIX-C", "REMIX-D"])
        add_second = subprocess.run(
            [sys.executable, str(IMAGE2), "add-jobs", "--workspace", str(self.workspace), "--input", str(self.workspace / "remix" / "jobs.json")],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(add_second.returncode, 0, add_second.stderr)
        validate = subprocess.run(
            [sys.executable, str(IMAGE2), "validate-jobs", "--workspace", str(self.workspace), "--job-manifest", "remix/jobs.json", "--requested-count", "4"],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_rejects_invalid_count_duplicate_ids_and_missing_source(self) -> None:
        invalid_count = self.brief(4)
        invalid_count["count"] = 5
        self.assertNotEqual(self.run_prepare(invalid_count).returncode, 0)

        duplicate = self.brief(4)
        duplicate["candidates"][1]["id"] = "REMIX-A"
        self.assertNotEqual(self.run_prepare(duplicate).returncode, 0)

        missing = self.brief(4)
        missing["source"] = "references/missing.png"
        self.assertNotEqual(self.run_prepare(missing).returncode, 0)

    def test_rejects_reference_outside_workspace(self) -> None:
        brief = self.brief(4)
        brief["references"] = [{"path": "../../outside.png", "role": "style"}]
        result = self.run_prepare(brief)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workspace", result.stderr.lower())

    def test_gold_system_resolves_stable_ids_and_custom_other(self) -> None:
        brief = self.brief(4)
        preferences = brief["preferences"]
        preferences.update({
            "design_system": "gold",
            "themes": ["auspicious-meaning", "other"],
            "custom_themes": "家族家徽",
            "morphologies": ["openwork-filigree"],
            "styles": ["song-dynasty-elegance"],
            "materials": ["enamel-accent"],
        })
        result = self.run_prepare(brief)
        self.assertEqual(result.returncode, 0, result.stderr)
        matrix = json.loads((self.workspace / "remix" / "matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix["preferences"]["theme_labels"], ["吉祥寓意", "家族家徽"])
        job = json.loads((self.workspace / "remix" / "jobs.json").read_text(encoding="utf-8"))["jobs"][0]
        prompt = (self.workspace / job["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn("产品体系：黄金（gold）", prompt)
        self.assertIn("主题池：吉祥寓意、家族家徽", prompt)

    def test_rejects_missing_schema_unknown_system_cross_system_id_and_empty_other(self) -> None:
        missing_schema = self.brief(4)
        missing_schema.pop("schema_version")
        self.assertIn("schema_version", self.run_prepare(missing_schema).stderr)

        unknown_system = self.brief(4)
        unknown_system["preferences"]["design_system"] = "platinum"
        self.assertIn("design_system", self.run_prepare(unknown_system).stderr)

        cross_system = self.brief(4)
        cross_system["preferences"]["themes"] = ["auspicious-meaning"]
        self.assertIn("outside the selected design system", self.run_prepare(cross_system).stderr)

        empty_other = self.brief(4)
        empty_other["preferences"]["themes"] = ["other"]
        self.assertIn("custom_themes", self.run_prepare(empty_other).stderr)


if __name__ == "__main__":
    unittest.main()
