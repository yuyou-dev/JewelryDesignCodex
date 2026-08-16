from __future__ import annotations

import io
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "scripts" / "jewelry_image2_tool.py"
spec = importlib.util.spec_from_file_location("jewelry_image2_tool", TOOL_PATH)
TOOL = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(TOOL)


class JewelryImage2ToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "run"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_tool(self, *args: str) -> int:
        return TOOL.main(list(args))

    def write_reference(self, name: str = "ref.png") -> Path:
        path = self.workspace / "references" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png-reference")
        return path

    def valid_review_png(self, label: str = "image") -> bytes:
        header = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR"
            b"\x00\x00\x02\x00"
            b"\x00\x00\x02\x00"
            b"\x08\x02\x00\x00\x00"
        )
        return header + label.encode("utf-8") + (b"\0" * (TOOL.MIN_REVIEW_IMAGE_BYTES + 64))

    def valid_imagegen_prompt(self, text: str = "Create one jewelry image with gpt-image-2.") -> str:
        return f"$imagegen\n{text}"

    def test_prompt_contract_validation_does_not_depend_on_job_local_names(self) -> None:
        issues = TOOL.validate_imagegen_prompt_contract(
            self.valid_imagegen_prompt("Create a jade and lapis necklace."),
            label="historical prompt outside generation-job scope",
        )

        self.assertEqual(issues, [])



    def test_recursive_detection_ignores_instructional_command_mentions(self) -> None:
        text = "Do not execute npm run harness:init under any circumstances."
        self.assertEqual(TOOL.recursive_worker_output_flags(text), [])

    def test_recursive_detection_blocks_npm_wrapped_add_job_execution(self) -> None:
        text = "command: npm run jewelry:image2 -- add-job --workspace nested --job-id child"
        self.assertEqual(TOOL.recursive_worker_output_flags(text), ["orchestration_command_exec"])


    def test_registration_rejects_duplicate_prompt_and_allows_explicit_variant(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.add_basic_job("first")
        duplicate_prompt = self.valid_imagegen_prompt("Create the registered design for first.")
        self.assertEqual(self.run_tool(
            "add-job", "--workspace", str(self.workspace), "--job-id", "second",
            "--prompt", duplicate_prompt, "--output", "outputs/second.png",
        ), 1)
        self.assertEqual(self.run_tool(
            "add-job", "--workspace", str(self.workspace), "--job-id", "variant",
            "--prompt", duplicate_prompt, "--output", "outputs/variant.png", "--allow-duplicate-prompt",
        ), 0)
        variant = next(job for job in TOOL.load_jobs(self.workspace.resolve())["jobs"] if job["id"] == "variant")
        self.assertTrue(variant["allow_duplicate_prompt"])
        self.assertRegex(variant["prompt_sha256"], r"^[0-9a-f]{64}$")

    def test_recovery_with_multiple_new_worker_images_is_ambiguous(self) -> None:
        worker = self.workspace / ".codex-home" / "job-workers" / "ambiguous"
        generated = worker / "generated_images" / "session"
        generated.mkdir(parents=True)
        for name in ["one.png", "two.png"]:
            (generated / name).write_bytes(TOOL.TINY_PNG_BYTES + name.encode())
        result = subprocess.CompletedProcess(["fake"], 0, "", "")
        with self.assertRaisesRegex(RuntimeError, "ambiguous_recovery"):
            TOOL.recover_generated_image(
                self.workspace, self.workspace / "outputs" / "ambiguous.png", result,
                self.workspace / "missing-message", worker, 0, True, set(),
            )


    def test_preview_gallery_only_lists_existing_workspace_images(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.add_basic_job("gallery")
        self.mark_job_done("gallery")

        preview = TOOL.write_preview_html(self.workspace.resolve())
        content = preview.read_text(encoding="utf-8")

        self.assertIn('content="5"', content)
        self.assertIn('src="outputs/gallery.png"', content)
        self.assertNotIn("<script", content.lower())

    def test_runner_snapshot_warns_and_records_hash_change(self) -> None:
        self.workspace.mkdir(parents=True)
        with mock.patch.object(TOOL, "runner_hashes", side_effect=[{"runner.py": "one"}, {"runner.py": "two"}]):
            self.assertEqual(TOOL.check_runner_snapshot(self.workspace), [])
            warnings = TOOL.check_runner_snapshot(self.workspace)

        self.assertEqual(warnings, ["runner files changed after this design run started"])
        self.assertTrue((self.workspace / "logs" / "runner-change-warnings.jsonl").is_file())

    def test_job_event_command_receives_json_and_failure_is_best_effort(self) -> None:
        self.workspace.mkdir(parents=True)
        sink = Path(self.tmp.name) / "event-sink.py"
        received = Path(self.tmp.name) / "received.json"
        sink.write_text(
            "import pathlib,sys\npathlib.Path(sys.argv[1]).write_text(sys.stdin.read(), encoding='utf-8')\n",
            encoding="utf-8",
        )
        result = {"id": "hook-job", "status": "done", "output": "outputs/hook-job.png"}

        TOOL.progress_line(
            self.workspace, result, 1, 1,
            event_command=f"{sys.executable} {sink} {received}",
        )
        payload = json.loads(received.read_text(encoding="utf-8"))
        self.assertEqual(payload["job_id"], "hook-job")
        self.assertEqual(payload["status"], "done")
        self.assertEqual(payload["output"], "outputs/hook-job.png")

        TOOL.progress_line(
            self.workspace, {"id": "failed-hook", "status": "failed", "failure_class": "provider_no_output"}, 1, 1,
            event_command=f"{sys.executable} -c 'import sys; sys.exit(7)'",
        )
        warnings = self.workspace / "logs" / "image-job-event-hook-warnings.jsonl"
        self.assertTrue(warnings.is_file())
        self.assertEqual(json.loads(warnings.read_text(encoding="utf-8").splitlines()[0])["returncode"], 7)




    def test_job_event_command_missing_executable_is_best_effort(self) -> None:
        self.workspace.mkdir(parents=True)

        TOOL.progress_line(
            self.workspace, {"id": "missing-hook", "status": "done"}, 1, 1,
            event_command="/definitely/missing/svt-job-event-hook",
        )

        warning = json.loads((self.workspace / "logs" / "image-job-event-hook-warnings.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(warning["failure_class"], "launch_or_subprocess_error")
        self.assertIsNone(warning["returncode"])

    def test_job_event_command_timeout_is_best_effort(self) -> None:
        self.workspace.mkdir(parents=True)
        timeout = subprocess.TimeoutExpired(["slow-hook"], 30)

        with mock.patch.object(TOOL.subprocess, "run", side_effect=timeout) as run:
            TOOL.progress_line(
                self.workspace, {"id": "timeout-hook", "status": "failed"}, 1, 1,
                event_command="slow-hook",
            )

        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        warning = json.loads((self.workspace / "logs" / "image-job-event-hook-warnings.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(warning["failure_class"], "timeout")
        self.assertIsNone(warning["returncode"])

    def test_monitored_attempt_fast_fails_whitelisted_network_signal(self) -> None:
        self.workspace.mkdir(parents=True)
        stdout_log = self.workspace / "logs" / "stdout.txt"
        stderr_log = self.workspace / "logs" / "stderr.txt"
        started = time.monotonic()

        result, details = TOOL.run_monitored_generation_attempt(
            command=[sys.executable, "-c", "import time; print('Image generation failed due to a network error', flush=True); time.sleep(5)"],
            prompt_text="prompt", workspace=self.workspace, env=os.environ.copy(),
            worker_home=self.workspace / "worker", output_path=self.workspace / "outputs" / "x.png",
            stdout_log=stdout_log, stderr_log=stderr_log, start_time=time.time(), timeout=10,
            allow_latest_recovery=False, early_stop=False, monitor_interval=0.05,
            early_stop_grace=0, existing_hashes=set(),
        )

        self.assertTrue(details["fast_failed"])
        self.assertLess(time.monotonic() - started, 2)
        self.assertNotEqual(result.returncode, 0)

    def test_auth_classifier_ignores_creative_forbidden_label_but_keeps_real_http_rejections(self) -> None:
        prompt = "Forbidden elements: no duplicate ring, fake logo, watermark, or random words."

        self.assertIsNone(TOOL.classify_provider_auth_failure(prompt))
        self.assertIsNone(TOOL.classify_provider_auth_failure(
            prompt + "\nimage generation failed: network error: error sending request for url "
            "(https://chatgpt.com/backend-api/codex/images/edits)"
        ))
        for message in (
            "HTTP 401 Unauthorized",
            "HTTP 403 Forbidden",
            "status code: 403",
            "Request failed with status code 401",
            "Request failed with status code 403",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    TOOL.classify_provider_auth_failure(message)["class"],
                    "provider_auth_failed",
                )

    def test_monitored_attempt_classifies_prompt_forbidden_plus_image_endpoint_error_as_network(self) -> None:
        self.workspace.mkdir(parents=True)
        stdout_log = self.workspace / "logs" / "stdout.txt"
        stderr_log = self.workspace / "logs" / "stderr.txt"
        started = time.monotonic()
        network_line = (
            "image generation failed: network error: error sending request for url "
            "(https://chatgpt.com/backend-api/codex/images/edits)"
        )

        result, details = TOOL.run_monitored_generation_attempt(
            command=[
                sys.executable,
                "-c",
                (
                    "import sys,time; "
                    "print(sys.stdin.read(), file=sys.stderr, flush=True); "
                    f"print({network_line!r}, file=sys.stderr, flush=True); "
                    "time.sleep(5)"
                ),
            ],
            prompt_text="Forbidden elements: no duplicate ring or fake logo.",
            workspace=self.workspace,
            env=os.environ.copy(),
            worker_home=self.workspace / "worker",
            output_path=self.workspace / "outputs" / "poster.png",
            stdout_log=stdout_log,
            stderr_log=stderr_log,
            start_time=time.time(),
            timeout=10,
            allow_latest_recovery=False,
            early_stop=False,
            monitor_interval=0.05,
            early_stop_grace=0,
            existing_hashes=set(),
        )

        self.assertTrue(details["fast_failed"])
        self.assertEqual(details["fast_fail_class"], "provider_network_error")
        self.assertEqual(details["fast_fail_signal"], "image generation failed: network error")
        self.assertLess(time.monotonic() - started, 2)
        classified = TOOL.classify_generation_failure(
            result,
            self.workspace / "worker",
            time.time(),
            self.workspace / "outputs" / "poster.png",
            "\n".join([result.stdout or "", result.stderr or ""]),
        )
        self.assertEqual(classified["class"], "provider_network_error")

    def add_basic_job(self, job_id: str, *, timeout: int | None = None) -> None:
        args = [
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            job_id,
            "--prompt",
            self.valid_imagegen_prompt(f"Create the registered design for {job_id}."),
            "--output",
            f"outputs/{job_id}.png",
        ]
        if timeout is not None:
            args.extend(["--timeout", str(timeout)])
        self.assertEqual(self.run_tool(*args), 0)

    def mark_job_done(self, job_id: str, *, image_bytes: bytes | None = None) -> None:
        output = self.workspace / "outputs" / f"{job_id}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(image_bytes if image_bytes is not None else self.valid_review_png(job_id))
        data = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))
        prompt_sha256 = None
        registered_job = None
        for job in data["jobs"]:
            if job["id"] == job_id:
                job["status"] = "done"
                prompt_sha256 = job.get("prompt_sha256")
                registered_job = job
        if prompt_sha256 is None:
            prompt_path = self.workspace / "prompts" / f"{TOOL.safe_id(job_id)}.prompt.txt"
            prompt_sha256 = TOOL.text_sha256(prompt_path.read_text(encoding="utf-8")) if prompt_path.is_file() else None
        (self.workspace / "jobs.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        prompt_path = self.workspace / "prompts" / f"{TOOL.safe_id(job_id)}.prompt.txt"
        executed_prompt = TOOL.build_executed_prompt(
            prompt_path.read_text(encoding="utf-8"),
            str((registered_job or {}).get("ratio") or ""),
            str((registered_job or {}).get("ratio_source") or ""),
        )
        executed_path = self.workspace / "logs" / "executed-prompts" / f"{TOOL.safe_id(job_id)}.prompt.txt"
        executed_path.parent.mkdir(parents=True, exist_ok=True)
        executed_path.write_text(executed_prompt, encoding="utf-8")
        executed_sha256 = TOOL.file_hash(executed_path)
        worker_version = str((registered_job or {}).get("worker_contract_version") or TOOL.WORKER_CONTRACT_VERSION)
        TOOL.write_json(
            self.workspace / "jobs" / f"{TOOL.safe_id(job_id)}.json",
            {
                "schema_version": 1,
                "id": job_id,
                "status": "done",
                "prompt": f"prompts/{TOOL.safe_id(job_id)}.prompt.txt",
                "output": f"outputs/{TOOL.safe_id(job_id)}.png",
                "prompt_sha256": prompt_sha256,
                "executed_prompt": f"evidence/executed-prompts/{TOOL.safe_id(job_id)}.prompt.txt",
                "executed_prompt_sha256": executed_sha256,
                "executed_prompt_bytes": executed_path.stat().st_size,
                "worker_contract_version": worker_version,
                "output_sha256": TOOL.file_hash(output),
                "attempts": [{
                    "attempt": 1,
                    "prompt_sha256": prompt_sha256,
                    "executed_prompt_sha256": executed_sha256,
                    "worker_contract_version": worker_version,
                    "binding": {
                        "job_id": job_id,
                        "prompt_sha256": prompt_sha256,
                        "executed_prompt_sha256": executed_sha256,
                        "worker_contract_version": worker_version,
                        "output_sha256": TOOL.file_hash(output),
                    },
                }],
            },
        )

    def local_generator_command(self, code: str) -> list[str]:
        return [sys.executable, "-c", code]

    @contextmanager
    def guarded_workspace(self):
        root = REPO_ROOT / "artifacts" / "runs"
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root, prefix="2026-05-24-image2-guard-") as workspace:
            task_documents = REPO_ROOT / "artifacts" / "design-tasks" / Path(workspace).name
            try:
                yield workspace
            finally:
                shutil.rmtree(task_documents, ignore_errors=True)

    def test_init_creates_persisted_workspace(self) -> None:
        result = self.run_tool("init", "--workspace", str(self.workspace), "--title", "Toucan Run")

        self.assertEqual(result, 0)
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["provider"], "codex-cli")
        self.assertEqual(state["image_model"], "gpt-image-2")
        self.assertFalse((self.workspace / ".codex-home").exists())
        self.assertEqual(json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"], [])

    def test_add_job_missing_reference_blocks_before_workspace_or_copy_side_effects(self) -> None:
        missing = Path(self.tmp.name) / "incoming" / "missing-reference.png"
        with mock.patch.object(TOOL.subprocess, "run") as run, mock.patch.object(
            TOOL.shutil, "copy"
        ) as copy, mock.patch.object(TOOL.shutil, "copy2") as copy2:
            result = self.run_tool(
                "add-job",
                "--workspace",
                str(self.workspace),
                "--job-id",
                "missing-ref",
                "--prompt",
                self.valid_imagegen_prompt(),
                "--output",
                "outputs/missing-ref.png",
                "--reference",
                str(missing),
            )

        self.assertEqual(result, 1)
        self.assertFalse(self.workspace.exists())
        for relative in ["prompts", "jobs", "evidence", "output/local-delivery-manifest.json", ".codex-home/job-workers"]:
            self.assertFalse((self.workspace / relative).exists())
        run.assert_not_called()
        copy.assert_not_called()
        copy2.assert_not_called()


    def test_validate_request_accepts_current_explicit_ready_provider_and_enforces_output_shape(self) -> None:
        ready = TOOL.validate_request_readiness(
            requested_count=3,
            output_shape="single_composed_grid",
            outputs=["outputs/explicit-grid.png"],
            provider="current-external-provider",
            explicit_provider_request=True,
            provider_status="ready",
        )
        mismatch = TOOL.validate_request_readiness(
            requested_count=3,
            output_shape="independent_images",
            outputs=["outputs/only-one.png"],
            provider="current-external-provider",
            explicit_provider_request=True,
            provider_status="ready",
        )

        self.assertTrue(ready["ok"])
        self.assertEqual(ready["provider"]["route"], "explicit_external")
        self.assertFalse(ready["provider"]["provider_call"])
        self.assertIn("output_count_mismatch", {item["code"] for item in mismatch["issues"]})

    def test_validate_request_login_required_does_not_start_login_or_worker_home(self) -> None:
        source_home = Path(self.tmp.name) / "source-codex"
        source_home.mkdir()
        prospective = Path(self.tmp.name) / "login-required-run"
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch.object(
            TOOL.shutil, "which", return_value="/usr/local/bin/codex"
        ), mock.patch.object(TOOL.subprocess, "run") as run, mock.patch.object(
            TOOL.shutil, "copy"
        ) as copy, mock.patch.object(TOOL.shutil, "copy2") as copy2:
            result = self.run_tool(
                "validate-request",
                "--requested-count",
                "1",
                "--output",
                str(prospective / "outputs" / "one.png"),
                "--codex-home",
                str(source_home),
            )
        run.return_value.returncode = 1

        self.assertEqual(result, 1)
        payload = json.loads(stdout.getvalue())
        self.assertIn("login_required", {item["code"] for item in payload["issues"]})
        self.assertFalse(prospective.exists())
        self.assertFalse((source_home / "job-workers").exists())
        self.assertFalse((prospective / "output" / "local-delivery-manifest.json").exists())
        run.assert_called_once()
        copy.assert_not_called()
        copy2.assert_not_called()

    def test_validate_request_complete_inputs_pass_without_creating_run(self) -> None:
        source_home = Path(self.tmp.name) / "ready-codex"
        source_home.mkdir()
        (source_home / "auth.json").write_text("ready", encoding="utf-8")
        reference = Path(self.tmp.name) / "reference.webp"
        reference.write_bytes(b"webp-reference")
        prospective = Path(self.tmp.name) / "ready-run"
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch.object(
            TOOL.shutil, "which", return_value="/usr/local/bin/codex"
        ), mock.patch.object(TOOL.subprocess, "run") as run, mock.patch.object(
            TOOL.shutil, "copy"
        ) as copy, mock.patch.object(TOOL.shutil, "copy2") as copy2:
            run.return_value.returncode = 0
            result = self.run_tool(
                "validate-request",
                "--requested-count",
                "2",
                "--output",
                str(prospective / "outputs" / "one.png"),
                "--output",
                str(prospective / "outputs" / "two.png"),
                "--reference",
                str(reference),
                "--codex-home",
                str(source_home),
            )

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "ready")
        self.assertFalse(prospective.exists())
        run.assert_called_once()
        copy.assert_not_called()
        copy2.assert_not_called()

    def test_generate_missing_registered_reference_blocks_before_preview_or_state_write(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.add_basic_job("legacy-ref")
        jobs_path = self.workspace / "jobs.json"
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
        jobs["jobs"][0]["references"] = ["references/missing.png"]
        jobs_path.write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        state_before = (self.workspace / "state.json").read_bytes()
        source_home = Path(self.tmp.name) / "generation-codex"
        source_home.mkdir()
        (source_home / "auth.json").write_text("ready", encoding="utf-8")

        with mock.patch.object(TOOL.shutil, "which", return_value="/usr/local/bin/codex"), mock.patch.object(
            TOOL, "write_preview_html"
        ) as preview, mock.patch.object(TOOL, "prepare_codex_home") as prepare, mock.patch.object(
            TOOL.subprocess, "run"
        ) as run, mock.patch.object(TOOL.shutil, "copy2") as copy2:
            result = self.run_tool(
                "generate",
                "--workspace",
                str(self.workspace),
                "--job-id",
                "legacy-ref",
                "--codex-home",
                str(source_home),
            )

        self.assertEqual(result, 1)
        self.assertEqual((self.workspace / "state.json").read_bytes(), state_before)
        self.assertFalse((self.workspace / "preview.html").exists())
        self.assertFalse((self.workspace / "evidence").exists())
        self.assertFalse((self.workspace / ".codex-home" / "job-workers").exists())
        preview.assert_not_called()
        prepare.assert_not_called()
        run.assert_not_called()
        copy2.assert_not_called()

    def test_add_job_defaults_ordinary_design_ratio_to_square(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))

        result = self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "square-default",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
        )

        self.assertEqual(result, 0)
        job = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"][0]
        self.assertEqual(job["ratio"], "1:1")
        self.assertEqual(job["ratio_source"], "default_design")
        prompt = (self.workspace / job["prompt"]).read_text(encoding="utf-8")
        self.assertNotIn("Output aspect ratio: 1:1", prompt)
        self.assertNotEqual(job["prompt_sha256"], job["executed_prompt_sha256"])

    def test_add_job_accepts_creative_only_prompt_without_transport_contract(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))

        result = self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "old-style",
            "--prompt",
            "Create one jewelry image.",
        )

        self.assertEqual(result, 0)
        job = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"][0]
        self.assertEqual((self.workspace / job["prompt"]).read_text(encoding="utf-8"), "Create one jewelry image.")
        self.assertEqual(job["prompt_sha256"], TOOL.text_sha256("Create one jewelry image."))
        executed = TOOL.build_executed_prompt("Create one jewelry image.", "1:1", "default_design")
        self.assertEqual(job["executed_prompt_sha256"], TOOL.text_sha256(executed))


    def test_add_job_preserves_explicit_ratio(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))

        result = self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "portrait-explicit",
            "--ratio",
            "3:4",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
        )

        self.assertEqual(result, 0)
        job = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"][0]
        self.assertEqual(job["ratio"], "3:4")
        self.assertEqual(job["ratio_source"], "explicit")
        prompt = (self.workspace / job["prompt"]).read_text(encoding="utf-8")
        self.assertNotIn("Output aspect ratio: 3:4", prompt)
        self.assertEqual(job["executed_prompt_sha256"], TOOL.text_sha256(TOOL.build_executed_prompt(prompt, "3:4", "explicit")))

    def test_add_jobs_keeps_preset_kind_from_forced_square_default(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        input_path = self.workspace / "jobs-input.json"
        input_path.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "id": "ordinary-design",
                            "prompt": "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nCreate one product jewelry design.",
                        },
                        {
                            "id": "poster-prompt-ratio",
                            "kind": "jewelry-poster",
                            "prompt": "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nCreate one campaign poster. Aspect ratio 3:4.",
                        },
                        {
                            "id": "poster-preset",
                            "kind": "jewelry-poster",
                            "prompt": "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nCreate one poster using the selected poster preset. Aspect ratio 3:4.",
                        },
                        {
                            "id": "source-retouch",
                            "kind": "jewelry-retouch",
                            "prompt": "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nClean up the supplied source product photo without changing its crop.",
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = self.run_tool("add-jobs", "--workspace", str(self.workspace), "--input", str(input_path))

        self.assertEqual(result, 0)
        jobs = {job["id"]: job for job in json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]}
        self.assertEqual(jobs["ordinary-design"]["ratio"], "1:1")
        self.assertEqual(jobs["ordinary-design"]["ratio_source"], "default_design")
        self.assertEqual(jobs["poster-prompt-ratio"]["ratio"], "3:4")
        self.assertEqual(jobs["poster-prompt-ratio"]["ratio_source"], "prompt")
        self.assertEqual(jobs["poster-preset"]["ratio"], "3:4")
        self.assertEqual(jobs["poster-preset"]["ratio_source"], "prompt")
        self.assertEqual(jobs["source-retouch"]["ratio"], "")
        self.assertEqual(jobs["source-retouch"]["ratio_source"], "preset_or_unspecified")

    def test_catalog_and_reference_sheet_default_square_unless_slot_ratio_declared(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        input_path = self.workspace / "jobs-input.json"
        input_path.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "id": "catalog-main",
                            "kind": "jewelry-catalog",
                            "prompt": "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nCreate one SKU main white-background product image.",
                        },
                        {
                            "id": "reference-sheet",
                            "kind": "jewelry-reference-sheet",
                            "prompt": "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nCreate one 2x2 white-background product reference sheet.",
                        },
                        {
                            "id": "pdp-hero",
                            "kind": "jewelry-catalog",
                            "prompt": "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nCreate one PDP hero image. Aspect ratio 16:9.",
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = self.run_tool("add-jobs", "--workspace", str(self.workspace), "--input", str(input_path))

        self.assertEqual(result, 0)
        jobs = {job["id"]: job for job in json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]}
        self.assertEqual(jobs["catalog-main"]["ratio"], "1:1")
        self.assertEqual(jobs["catalog-main"]["ratio_source"], "default_design")
        self.assertEqual(jobs["reference-sheet"]["ratio"], "1:1")
        self.assertEqual(jobs["reference-sheet"]["ratio_source"], "default_design")
        self.assertEqual(jobs["pdp-hero"]["ratio"], "16:9")
        self.assertEqual(jobs["pdp-hero"]["ratio_source"], "prompt")

    def test_generation_job_wraps_creative_prompt_file_once_and_binds_both_hashes(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        prompt_path = self.workspace / "prompts" / "from-file.prompt.txt"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        source_prompt = "Create one platinum ring with a bezel-set sapphire."
        prompt_path.write_text(source_prompt, encoding="utf-8")
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "from-file",
            "--prompt-file",
            "prompts/from-file.prompt.txt",
            "--output",
            "outputs/from-file.png",
        )
        jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        captured: dict[str, str] = {}

        def fake_attempt(**kwargs):
            captured["prompt_text"] = kwargs["prompt_text"]
            output_path = kwargs["output_path"]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(TOOL.TINY_PNG_BYTES)
            return subprocess.CompletedProcess(kwargs["command"], 0, "", ""), {
                "early_stopped": False,
                "early_stop_reason": None,
                "recovered_from": None,
                "termination": None,
                "timed_out": False,
            }

        with mock.patch.object(TOOL, "run_monitored_generation_attempt", side_effect=fake_attempt):
            record = TOOL.run_generation_job(
                self.workspace.resolve(),
                jobs[0],
                self.workspace / ".codex-home",
                retries=0,
                timeout=60,
                retry_base=0,
                retry_max=0,
                allow_latest_recovery=False,
                dry_run=False,
            )

        self.assertEqual(record["status"], "done")
        self.assertIn("Output aspect ratio: 1:1", captured["prompt_text"])
        self.assertEqual(captured["prompt_text"].count("$imagegen"), 1)
        self.assertEqual(captured["prompt_text"].count(TOOL.DIRECT_IMAGE_WORKER_GUARD), 1)
        self.assertEqual(captured["prompt_text"].count("Output aspect ratio:"), 1)
        self.assertEqual(record["prompt_sha256"], TOOL.text_sha256(source_prompt))
        self.assertNotEqual(record["prompt_sha256"], record["executed_prompt_sha256"])
        executed_path = self.workspace / record["executed_prompt"]
        self.assertEqual(executed_path.read_text(encoding="utf-8"), captured["prompt_text"])
        self.assertEqual(TOOL.file_hash(executed_path), record["executed_prompt_sha256"])
        self.assertEqual(record["attempts"][0]["executed_prompt_sha256"], record["executed_prompt_sha256"])
        self.assertEqual(record["attempts"][0]["binding"]["prompt_sha256"], record["prompt_sha256"])
        self.assertEqual(record["attempts"][0]["binding"]["executed_prompt_sha256"], record["executed_prompt_sha256"])
        self.assertEqual(record["ratio"], "1:1")
        self.assertEqual(record["ratio_source"], "default_design")


    def test_noncanonical_prompt_file_cannot_overwrite_conflicting_job_prompt(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        prompts = self.workspace / "prompts"
        prompts.mkdir(parents=True, exist_ok=True)
        canonical = prompts / "bead-01.prompt.txt"
        frozen = self.valid_imagegen_prompt("Frozen design A.")
        canonical.write_text(frozen, encoding="utf-8")
        source = prompts / "blind-test-name.txt"
        source.write_text(self.valid_imagegen_prompt("Different design B."), encoding="utf-8")

        result = self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "bead-01",
            "--prompt-file",
            "prompts/blind-test-name.txt",
            "--output",
            "outputs/bead-01.png",
        )

        self.assertEqual(result, 1)
        self.assertEqual(canonical.read_text(encoding="utf-8"), frozen)
        self.assertEqual(TOOL.load_jobs(self.workspace.resolve())["jobs"], [])


    def test_creative_visual_negative_is_allowed_but_positive_execution_is_rejected(self) -> None:
        allowed = "A clean white-background ring photograph. Negative: no post-processing artifacts or fake text."
        rejected = "Create a ring, then run shell command: npm run jewelry:image2."

        self.assertEqual(TOOL.validate_imagegen_prompt_contract(allowed, label="creative"), [])
        self.assertTrue(TOOL.validate_imagegen_prompt_contract(rejected, label="disguised prompt"))

    def test_add_job_and_dry_run_codex_command_with_reference(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        ref = self.write_reference()
        result = self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "cell-01",
            "--title",
            "Cell 01",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
            "--output",
            "outputs/cell-01.png",
            "--reference",
            str(ref),
        )
        self.assertEqual(result, 0)

        dry = TOOL.run_generation_job(
            self.workspace.resolve(),
            json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"][0],
            self.workspace / ".codex-home",
            retries=0,
            timeout=60,
            retry_base=0,
            retry_max=0,
            allow_latest_recovery=False,
            dry_run=True,
        )

        command = dry["command"]
        self.assertEqual(command[:4], ["codex", "-a", "never", "exec"])
        self.assertIn("-C", command)
        self.assertIn("--skip-git-repo-check", command)
        self.assertIn("-o", command)
        self.assertIn("-i", command)
        self.assertEqual(command[-1], "-")
        self.assertEqual(dry["output"], "outputs/cell-01.png")
        executed_path = self.workspace / dry["executed_prompt"]
        self.assertTrue(executed_path.is_file())
        self.assertEqual(TOOL.file_hash(executed_path), dry["executed_prompt_sha256"])
        self.assertEqual(dry["executed_prompt_sha256"], json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"][0]["executed_prompt_sha256"])

    def test_validate_jobs_passes_static_contract_without_dry_run(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        result = self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "static-ok",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
            "--output",
            "outputs/static-ok.png",
        )
        self.assertEqual(result, 0)

        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            validate = self.run_tool("validate-jobs", "--workspace", str(self.workspace), "--requested-count", "1")

        self.assertEqual(validate, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["selected_count"], 1)

    def test_validate_jobs_rejects_tampered_executed_prompt_hash(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.add_basic_job("static-executed-tamper")
        jobs_path = self.workspace / "jobs.json"
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
        jobs["jobs"][0]["executed_prompt_sha256"] = "f" * 64
        jobs_path.write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            result = self.run_tool("validate-jobs", "--workspace", str(self.workspace), "--requested-count", "1")

        self.assertEqual(result, 1)
        payload = json.loads(stdout.getvalue())
        self.assertIn("static-executed-tamper:executed_prompt_hash_mismatch", payload["issues"])

    def test_job_prefix_isolates_current_workflow_in_reused_workspace(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        for job_id in ["REMIX-A", "REMIX-B", "SKETCH-A", "SKETCH-B", "SKETCH-C", "SKETCH-D"]:
            self.assertEqual(
                self.run_tool(
                    "add-job", "--workspace", str(self.workspace), "--job-id", job_id,
                    "--prompt", self.valid_imagegen_prompt(f"Distinct {job_id} design."),
                    "--output", f"outputs/{job_id}.png",
                ),
                0,
            )
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            result = self.run_tool(
                "validate-jobs", "--workspace", str(self.workspace),
                "--job-prefix", "SKETCH-", "--requested-count", "4",
            )
        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["selected_count"], 4)
        self.assertEqual([item["job_id"] for item in payload["items"]], ["SKETCH-A", "SKETCH-B", "SKETCH-C", "SKETCH-D"])
        self.assertEqual(
            [job["id"] for job in TOOL.selected_jobs(self.workspace.resolve(), None, "pending", "REMIX-")],
            ["REMIX-A", "REMIX-B"],
        )

    def test_job_manifest_selects_exact_current_round_with_same_workflow_history(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        new_ids = [f"REMIX-{letter}-NEW" for letter in "ABCDEFGH"]
        job_ids = ["REMIX-A-OLD", "REMIX-B-OLD", *new_ids]
        for job_id in job_ids:
            self.assertEqual(self.run_tool(
                "add-job", "--workspace", str(self.workspace), "--job-id", job_id,
                "--prompt", self.valid_imagegen_prompt(f"Distinct {job_id} design."),
                "--output", f"outputs/{job_id}.png",
            ), 0)
        manifest = self.workspace / "remix" / "jobs.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"jobs": [{"id": job_id} for job_id in new_ids]}) + "\n", encoding="utf-8")
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            result = self.run_tool(
                "validate-jobs", "--workspace", str(self.workspace),
                "--job-manifest", "remix/jobs.json", "--requested-count", "8",
            )
        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual([item["job_id"] for item in payload["items"]], new_ids)
        self.assertIn("--job-manifest remix/jobs.json", payload["recommended_next_command"])
        self.assertIn("--parallel 4", payload["recommended_next_command"])

        manifest.write_text(json.dumps({"jobs": [{"id": "REMIX-A-NEW"}, {"id": "REMIX-C-MISSING"}]}) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unregistered ids: REMIX-C-MISSING"):
            TOOL.selected_jobs(self.workspace.resolve(), None, "pending", None, "remix/jobs.json")



    def test_registration_blocks_duplicate_outputs_before_validation(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.assertEqual(self.run_tool(
                    "add-job",
                    "--workspace",
                    str(self.workspace),
                    "--job-id",
                    "dup-a",
                    "--prompt",
                    "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
                    "--output",
                    "outputs/shared.png",
                ), 0)
        self.assertEqual(self.run_tool(
                    "add-job", "--workspace", str(self.workspace), "--job-id", "dup-b",
                    "--prompt", self.valid_imagegen_prompt("A distinct second design."),
                    "--output", "outputs/shared.png",
                ), 1)
        self.assertEqual(len(TOOL.load_jobs(self.workspace.resolve())["jobs"]), 1)

    def test_add_jobs_rejects_explicit_external_provider_route_without_partial_write(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        input_path = self.workspace / "jobs-input.json"
        input_path.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "id": "local-ok",
                            "prompt": self.valid_imagegen_prompt(),
                            "output": "outputs/local-ok.png",
                        },
                        {
                            "id": "gemini-track",
                            "prompt": self.valid_imagegen_prompt(),
                            "output": "outputs/gemini-track.png",
                            "requested_provider": "svt-jewelry-design-gemini",
                            "provider_exception": True,
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = self.run_tool("add-jobs", "--workspace", str(self.workspace), "--input", str(input_path))

        self.assertEqual(result, 1)
        self.assertEqual(json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"], [])

    def test_validate_jobs_blocks_legacy_external_provider_route(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.assertEqual(
            self.run_tool(
                "add-job",
                "--workspace",
                str(self.workspace),
                "--job-id",
                "legacy-provider",
                "--prompt",
                self.valid_imagegen_prompt(),
                "--output",
                "outputs/legacy-provider.png",
            ),
            0,
        )
        data = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))
        data["jobs"][0]["requested_provider"] = "svt-jewelry-design"
        data["jobs"][0]["provider_exception"] = True
        (self.workspace / "jobs.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            result = self.run_tool("validate-jobs", "--workspace", str(self.workspace), "--requested-count", "1")

        self.assertEqual(result, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "failed")
        self.assertTrue(any("provider_route_forbidden" in issue for issue in payload["issues"]))

    def test_generate_blocks_external_provider_route_before_codex_execution(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.assertEqual(
            self.run_tool(
                "add-job",
                "--workspace",
                str(self.workspace),
                "--job-id",
                "external-route",
                "--prompt",
                self.valid_imagegen_prompt(),
                "--output",
                "outputs/external-route.png",
            ),
            0,
        )
        data = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))
        data["jobs"][0]["plugin"] = "svt-jewelry-design-gemini"
        (self.workspace / "jobs.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        with mock.patch.object(TOOL, "codex_generate_command", side_effect=AssertionError("codex should not start")):
            result = self.run_tool("generate", "--workspace", str(self.workspace), "--job-id", "external-route")

        self.assertEqual(result, 1)
        jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        self.assertEqual(jobs[0]["status"], "blocked")
        self.assertEqual(jobs[0]["failure_class"], "provider_route_forbidden")
        record = json.loads((self.workspace / "jobs" / "external-route.json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "blocked")
        self.assertEqual(record["failure_class"], "provider_route_forbidden")

    def test_generate_recovers_direct_imagegen_result_from_worker_codex_home(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        ref = self.write_reference()
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "cell-02",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
            "--output",
            "outputs/cell-02.png",
            "--reference",
            str(ref),
        )
        jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]

        command = self.local_generator_command(
            """
import os
from pathlib import Path
generated = Path(os.environ["CODEX_HOME"]) / "generated_images" / "session-1" / "ig_good.png"
generated.parent.mkdir(parents=True, exist_ok=True)
generated.write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63f8ffff3f0005fe02fe0def46b80000000049454e44ae426082"))
print(f"selected {generated}")
"""
        )
        with mock.patch.object(TOOL, "codex_generate_command", return_value=command):
            record = TOOL.run_generation_job(
                self.workspace.resolve(),
                jobs[0],
                self.workspace / ".codex-home",
                retries=0,
                timeout=60,
                retry_base=0,
                retry_max=0,
                allow_latest_recovery=False,
                dry_run=False,
            )

        self.assertEqual(record["status"], "done")
        self.assertEqual((self.workspace / "outputs" / "cell-02.png").read_bytes(), TOOL.TINY_PNG_BYTES)
        job_record = json.loads((self.workspace / "jobs" / "cell-02.json").read_text(encoding="utf-8"))
        self.assertIn("recovered_from", job_record["attempts"][0])

    def test_generation_blocks_recursive_worker_output_without_retry(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "recursive",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
            "--output",
            "outputs/recursive.png",
        )
        command = self.local_generator_command(
            "print('exec: python3 scripts/jewelry_image2_tool.py add-job --workspace nested --job-id child')"
        )
        with mock.patch.object(TOOL, "codex_generate_command", return_value=command):
            result = self.run_tool(
                "generate",
                "--workspace",
                str(self.workspace),
                "--job-id",
                "recursive",
                "--retries",
                "2",
                "--retry-base",
                "0",
                "--retry-max",
                "0",
                "--allow-latest-recovery",
            )

        self.assertEqual(result, 1)
        jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        self.assertEqual(jobs[0]["status"], "blocked_non_retryable")
        record = json.loads((self.workspace / "jobs" / "recursive.json").read_text(encoding="utf-8"))
        self.assertEqual(record["failure_class"], "recursive_worker_output")
        self.assertEqual(len(record["attempts"]), 1)

    def test_cli_generate_defaults_to_latest_worker_recovery(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "latest-default",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
            "--output",
            "outputs/latest-default.png",
        )

        command = self.local_generator_command(
            """
import os
from pathlib import Path
generated = Path(os.environ["CODEX_HOME"]) / "generated_images" / "session-latest" / "ig_latest.png"
generated.parent.mkdir(parents=True, exist_ok=True)
generated.write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63f8ffff3f0005fe02fe0def46b80000000049454e44ae426082"))
print("image generated")
"""
        )
        with mock.patch.object(TOOL, "codex_generate_command", return_value=command):
            result = self.run_tool(
                "generate",
                "--workspace",
                str(self.workspace),
                "--job-id",
                "latest-default",
                "--retries",
                "0",
                "--retry-base",
                "0",
                "--retry-max",
                "0",
                "--allow-latest-recovery",
            )

        self.assertEqual(result, 0)
        self.assertEqual((self.workspace / "outputs" / "latest-default.png").read_bytes(), TOOL.TINY_PNG_BYTES)
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(state["last_generation"]["latest_recovery"])

    def test_generate_writes_timing_summary_to_stdout_and_state(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        for job_id in ["timing-a", "timing-b"]:
            self.run_tool(
                "add-job",
                "--workspace",
                str(self.workspace),
                "--job-id",
                job_id,
                "--prompt",
                "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
                "--allow-duplicate-prompt",
                "--output",
                f"outputs/{job_id}.png",
            )

        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            result = self.run_tool(
                "generate",
                "--workspace",
                str(self.workspace),
                "--only",
                "pending",
                "--parallel",
                "3",
                "--dry-run",
            )

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        summary = payload["timing_summary"]
        self.assertIn("started_at", summary["batch"])
        self.assertIn("finished_at", summary["batch"])
        self.assertGreaterEqual(summary["batch"]["duration_seconds"], 0)
        self.assertEqual(summary["parallel"], {"requested": 3, "effective": 2})
        self.assertEqual(summary["failure_classes"], {})
        self.assertEqual(summary["recovered_jobs"], 0)
        self.assertEqual(summary["early_stopped_jobs"], 0)
        self.assertEqual(len(summary["jobs"]), 2)
        self.assertTrue(all(job["status"] == "dry_run" for job in summary["jobs"]))
        self.assertIn("status=done", stderr.getvalue())
        self.assertIn("dry_run provider_not_executed", stderr.getvalue())
        self.assertNotIn("provider_failure", stderr.getvalue())
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_generation"]["timing_summary"], summary)

    def fake_batch_result(self, job: dict, *, status: str = "failed", failure_class: str = "codex_transport_failure") -> dict:
        job_id = str(job.get("id") or "")
        if status == "done":
            output = self.workspace / "outputs" / f"{job_id}.png"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(TOOL.TINY_PNG_BYTES)
            record = {
                "id": job_id,
                "status": "done",
                "finished_at": TOOL.now_iso(),
                "duration_seconds": 0.01,
                "attempts": [{"attempt": 1, "returncode": 0, "recovered_from": str(output)}],
                "early_stopped": False,
                "early_stop_reason": None,
            }
            TOOL.set_job_status(self.workspace, job_id, {"status": "done", "output": f"outputs/{job_id}.png"})
        else:
            record = {
                "id": job_id,
                "status": "failed",
                "failure_class": failure_class,
                "error": failure_class,
                "finished_at": TOOL.now_iso(),
                "duration_seconds": 0.01,
                "attempts": [{"attempt": 1, "returncode": 1, "failure_class": failure_class}],
                "early_stopped": False,
                "early_stop_reason": None,
            }
            TOOL.set_job_status(self.workspace, job_id, {"status": "failed", "failure_class": failure_class, "error": failure_class})
        TOOL.write_job_record(self.workspace, job_id, record)
        return record

    def test_generate_circuit_breaker_blocks_not_started_transport_batch(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        for index in range(6):
            self.add_basic_job(f"breaker-{index}")
        executed: list[str] = []

        def fake_run(*, job, **kwargs):
            executed.append(str(job["id"]))
            return self.fake_batch_result(job, failure_class="codex_transport_failure")

        with mock.patch.object(TOOL, "run_generation_job", side_effect=fake_run):
            result = self.run_tool(
                "generate",
                "--workspace",
                str(self.workspace),
                "--only",
                "pending",
                "--parallel",
                "2",
                "--circuit-breaker",
                "3",
            )

        self.assertEqual(result, 1)
        self.assertLessEqual(len(executed), 4)
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        breaker = state["last_generation"]["circuit_breaker"]
        self.assertTrue(breaker["tripped"])
        self.assertEqual(breaker["trigger_class"], "codex_transport_failure")
        self.assertEqual(breaker["completed_failures"], 3)
        self.assertTrue(breaker["blocked_jobs"])
        jobs = {job["id"]: job for job in json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]}
        for job_id in breaker["blocked_jobs"]:
            self.assertEqual(jobs[job_id]["status"], "blocked")
            self.assertEqual(jobs[job_id]["failure_class"], "batch_circuit_breaker")

    def test_generate_circuit_breaker_does_not_trip_after_success(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        for index in range(5):
            self.add_basic_job(f"mixed-{index}")

        def fake_run(*, job, **kwargs):
            if str(job["id"]) == "mixed-1":
                return self.fake_batch_result(job, status="done")
            return self.fake_batch_result(job, failure_class="codex_transport_failure")

        with mock.patch.object(TOOL, "run_generation_job", side_effect=fake_run):
            result = self.run_tool(
                "generate",
                "--workspace",
                str(self.workspace),
                "--only",
                "pending",
                "--parallel",
                "1",
                "--circuit-breaker",
                "3",
            )

        self.assertEqual(result, 1)
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(state["last_generation"]["circuit_breaker"]["tripped"])
        jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        self.assertFalse(any(job.get("failure_class") == "batch_circuit_breaker" for job in jobs))

    def test_generate_no_circuit_breaker_runs_everything(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        for index in range(6):
            self.add_basic_job(f"no-breaker-{index}")
        executed: list[str] = []

        def fake_run(*, job, **kwargs):
            executed.append(str(job["id"]))
            return self.fake_batch_result(job, failure_class="codex_transport_failure")

        with mock.patch.object(TOOL, "run_generation_job", side_effect=fake_run):
            result = self.run_tool(
                "generate",
                "--workspace",
                str(self.workspace),
                "--only",
                "pending",
                "--parallel",
                "2",
                "--no-circuit-breaker",
            )

        self.assertEqual(result, 1)
        self.assertEqual(len(executed), 6)
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(state["last_generation"]["circuit_breaker"]["tripped"])

    def test_generate_requeues_only_failed_job_at_batch_end_with_fresh_routes_and_budget(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        for job_id in ["batch-a", "batch-b", "batch-c"]:
            self.add_basic_job(job_id)
        calls: list[tuple[str, str]] = []

        def fake_run(*, job, base_codex_home, **kwargs):
            job_id = str(job["id"])
            calls.append((job_id, str(base_codex_home)))
            call_count = sum(1 for called_id, _ in calls if called_id == job_id)
            if job_id != "batch-b" or call_count == 3:
                record = self.fake_batch_result(job, status="done")
            else:
                record = self.fake_batch_result(job, failure_class="provider_no_output")
            record["attempts"][0]["route"] = str(base_codex_home)
            record["attempts"][0]["trigger"] = "initial"
            record["prompt_sha256"] = job["prompt_sha256"]
            record["executed_prompt_sha256"] = job["executed_prompt_sha256"]
            record["worker_contract_version"] = job["worker_contract_version"]
            record["attempts"][0]["prompt_sha256"] = job["prompt_sha256"]
            record["attempts"][0]["executed_prompt_sha256"] = job["executed_prompt_sha256"]
            TOOL.write_job_record(self.workspace, job_id, record)
            return record

        with mock.patch.object(TOOL, "run_generation_job", side_effect=fake_run):
            result = self.run_tool(
                "generate", "--workspace", str(self.workspace), "--only", "pending",
                "--parallel", "1", "--attempt-budget", "3", "--no-circuit-breaker",
            )

        self.assertEqual(result, 0)
        self.assertEqual([job_id for job_id, _ in calls[:3]], ["batch-a", "batch-b", "batch-c"])
        self.assertEqual([job_id for job_id, _ in calls[3:]], ["batch-b", "batch-b"])
        routes = [route for job_id, route in calls if job_id == "batch-b"]
        self.assertEqual(len(set(routes)), 3)
        record = json.loads((self.workspace / "jobs" / "batch-b.json").read_text(encoding="utf-8"))
        self.assertEqual(len(record["attempts"]), 3)
        self.assertEqual(record["attempts"][0].get("trigger"), "initial")
        self.assertEqual([attempt["trigger"] for attempt in record["attempts"][1:]], ["batch_requeue", "batch_requeue"])
        self.assertTrue(all(attempt["requeued"] for attempt in record["attempts"][1:]))
        self.assertEqual({attempt["executed_prompt_sha256"] for attempt in record["attempts"]}, {record["executed_prompt_sha256"]})
        events = [json.loads(line) for line in (self.workspace / "logs" / "image-job-events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual({event["job_id"] for event in events}, {"batch-a", "batch-b", "batch-c"})
        self.assertTrue(all({"job_id", "status", "output", "requeue"} <= set(event) for event in events))
        self.assertEqual(sum(1 for event in events if event["job_id"] == "batch-b" and event["requeue"]), 2)

    def test_generate_success_batch_does_not_requeue(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        for job_id in ["success-a", "success-b"]:
            self.add_basic_job(job_id)
        calls: list[str] = []

        def fake_run(*, job, **kwargs):
            calls.append(str(job["id"]))
            return self.fake_batch_result(job, status="done")

        with mock.patch.object(TOOL, "run_generation_job", side_effect=fake_run):
            result = self.run_tool("generate", "--workspace", str(self.workspace), "--only", "pending", "--parallel", "1")

        self.assertEqual(result, 0)
        self.assertEqual(calls, ["success-a", "success-b"])


















    def test_local_sleeping_subprocess_early_recovers_and_terminates(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "sleeping-early",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
            "--output",
            "outputs/sleeping-early.png",
        )
        jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        command = self.local_generator_command(
            """
import os
import time
from pathlib import Path
generated = Path(os.environ["CODEX_HOME"]) / "generated_images" / "session-sleep" / "ig_sleep.png"
generated.parent.mkdir(parents=True, exist_ok=True)
generated.write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63f8ffff3f0005fe02fe0def46b80000000049454e44ae426082"))
print("generated worker image", flush=True)
time.sleep(10)
"""
        )

        started = time.monotonic()
        with mock.patch.object(TOOL, "codex_generate_command", return_value=command):
            record = TOOL.run_generation_job(
                self.workspace.resolve(),
                jobs[0],
                self.workspace / ".codex-home",
                retries=0,
                timeout=5,
                retry_base=0,
                retry_max=0,
                allow_latest_recovery=True,
                dry_run=False,
                monitor_interval=0.05,
                early_stop_grace=0.05,
            )
        elapsed = time.monotonic() - started

        self.assertEqual(record["status"], "done")
        self.assertLess(elapsed, 2)
        self.assertEqual((self.workspace / "outputs" / "sleeping-early.png").read_bytes(), TOOL.TINY_PNG_BYTES)
        self.assertTrue(record["early_stopped"])
        self.assertEqual(record["early_stop_reason"], "stable_worker_generated_image")
        self.assertTrue(record["attempts"][0]["early_stopped"])
        self.assertEqual(record["attempts"][0]["early_stop_reason"], "stable_worker_generated_image")
        self.assertIsNotNone(record["attempts"][0]["duration_seconds"])

    def test_generation_retry_preserves_attempt_durations_and_logs(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "retry-success",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
            "--output",
            "outputs/retry-success.png",
        )
        jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        command = self.local_generator_command(
            """
import os
import sys
from pathlib import Path
marker = Path.cwd() / "logs" / "retry-attempt.txt"
try:
    attempt = int(marker.read_text(encoding="utf-8")) + 1
except FileNotFoundError:
    attempt = 1
marker.write_text(str(attempt), encoding="utf-8")
print(f"attempt {attempt} stdout")
print(f"attempt {attempt} stderr", file=sys.stderr)
if attempt == 1:
    raise SystemExit(7)
generated = Path(os.environ["CODEX_HOME"]) / "generated_images" / "session-retry" / "ig_retry.png"
generated.parent.mkdir(parents=True, exist_ok=True)
generated.write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63f8ffff3f0005fe02fe0def46b80000000049454e44ae426082"))
print(f"selected {generated}")
"""
        )

        with mock.patch.object(TOOL, "codex_generate_command", return_value=command):
            record = TOOL.run_generation_job(
                self.workspace.resolve(),
                jobs[0],
                self.workspace / ".codex-home",
                retries=1,
                timeout=5,
                retry_base=0,
                retry_max=0,
                allow_latest_recovery=False,
                dry_run=False,
            )

        self.assertEqual(record["status"], "done")
        self.assertEqual((self.workspace / "outputs" / "retry-success.png").read_bytes(), TOOL.TINY_PNG_BYTES)
        self.assertEqual(len(record["attempts"]), 2)
        self.assertEqual(record["attempts"][0]["returncode"], 7)
        self.assertEqual(record["attempts"][1]["returncode"], 0)
        self.assertIsNotNone(record["attempts"][0]["duration_seconds"])
        self.assertIsNotNone(record["attempts"][1]["duration_seconds"])
        self.assertIsNone(record["attempts"][0]["recovered_from"])
        self.assertIn("session-retry", record["attempts"][1]["recovered_from"])
        stdout_log = (self.workspace / record["stdout_log"]).read_text(encoding="utf-8")
        stderr_log = (self.workspace / record["stderr_log"]).read_text(encoding="utf-8")
        self.assertIn("attempt 1 stdout", stdout_log)
        self.assertIn("attempt 2 stdout", stdout_log)
        self.assertIn("attempt 1 stderr", stderr_log)
        self.assertIn("attempt 2 stderr", stderr_log)
        self.assertEqual(
            {attempt["executed_prompt_sha256"] for attempt in record["attempts"]},
            {record["executed_prompt_sha256"]},
        )
        self.assertTrue(all(attempt["prompt_sha256"] == record["prompt_sha256"] for attempt in record["attempts"]))

    def test_bundled_imagegen_skill_markers_do_not_block_worker_recovery(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "bundled-skill-markers",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
            "--output",
            "outputs/bundled-skill-markers.png",
        )

        command = self.local_generator_command(
            """
import os
from pathlib import Path
codex_home = Path(os.environ["CODEX_HOME"])
skill_root = codex_home / "skills" / ".system" / "imagegen"
(skill_root / "docs").mkdir(parents=True, exist_ok=True)
(skill_root / "scripts").mkdir(parents=True, exist_ok=True)
(skill_root / "docs" / "image-api.md").write_text("Example docs mention OPENAI_API_KEY and SDK routes.\\n", encoding="utf-8")
(skill_root / "scripts" / "image_gen.py").write_text("print('SDK helper example only')\\n", encoding="utf-8")
generated = codex_home / "generated_images" / "session-markers" / "ig_marker_safe.png"
generated.parent.mkdir(parents=True, exist_ok=True)
generated.write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63f8ffff3f0005fe02fe0def46b80000000049454e44ae426082"))
print("image generated")
"""
        )
        with mock.patch.object(TOOL, "codex_generate_command", return_value=command):
            result = self.run_tool(
                "generate",
                "--workspace",
                str(self.workspace),
                "--job-id",
                "bundled-skill-markers",
                "--retries",
                "0",
                "--retry-base",
                "0",
                "--retry-max",
                "0",
                "--allow-latest-recovery",
            )

        self.assertEqual(result, 0)
        self.assertEqual((self.workspace / "outputs" / "bundled-skill-markers.png").read_bytes(), TOOL.TINY_PNG_BYTES)
        record = json.loads((self.workspace / "jobs" / "bundled-skill-markers.json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "done")
        self.assertNotEqual(record.get("failure_class"), "provider_route_forbidden")
        self.assertIn("recovered_from", record["attempts"][0])

    def test_no_latest_recovery_opt_out_fails_when_only_worker_latest_exists(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "no-latest",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
            "--output",
            "outputs/no-latest.png",
        )

        command = self.local_generator_command(
            """
import os
import time
from pathlib import Path
generated = Path(os.environ["CODEX_HOME"]) / "generated_images" / "session-no-latest" / "ig_no_latest.png"
generated.parent.mkdir(parents=True, exist_ok=True)
generated.write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63f8ffff3f0005fe02fe0def46b80000000049454e44ae426082"))
print("image generated")
time.sleep(0.4)
"""
        )
        started = time.monotonic()
        with mock.patch.object(TOOL, "codex_generate_command", return_value=command):
            result = self.run_tool(
                "generate",
                "--workspace",
                str(self.workspace),
                "--job-id",
                "no-latest",
                "--no-latest-recovery",
                "--monitor-interval",
                "0.05",
                "--early-stop-grace",
                "0.05",
                "--retries",
                "0",
                "--retry-base",
                "0",
                "--retry-max",
                "0",
            )
        elapsed = time.monotonic() - started

        self.assertEqual(result, 1)
        self.assertGreaterEqual(elapsed, 0.3)
        self.assertFalse((self.workspace / "outputs" / "no-latest.png").exists())
        record = json.loads((self.workspace / "jobs" / "no-latest.json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["failure_class"], "recovery_failed")
        self.assertEqual(record["attempts"][0]["recovered_from"], None)
        self.assertFalse(record["attempts"][0]["early_stopped"])
        self.assertFalse(record["early_stopped"])
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(state["last_generation"]["latest_recovery"])

    def test_sandbox_header_alone_does_not_classify_as_sandbox_path_failure(self) -> None:
        result = subprocess.CompletedProcess(["codex"], 0, "", "")
        failure = TOOL.classify_generation_failure(
            result,
            self.workspace / ".codex-home" / "job-workers" / "header-only",
            0,
            self.workspace / "outputs" / "missing.png",
            "sandbox: workspace-write [workdir, /tmp, $TMPDIR]\nGenerated image inline.",
        )

        self.assertEqual(failure["class"], "provider_no_output")

    def test_codex_response_dns_failure_gets_specific_class(self) -> None:
        result = subprocess.CompletedProcess(["codex"], 1, "", "")
        failure = TOOL.classify_generation_failure(
            result,
            self.workspace / ".codex-home" / "job-workers" / "dns-fail",
            time.time(),
            self.workspace / "outputs" / "missing.png",
            "ERROR codex_api::endpoint::responses_websocket: failed to connect to websocket: "
            "IO error: failed to lookup address information: nodename nor servname provided, or not known, "
            "url: wss://chatgpt.com/backend-api/codex/responses",
        )

        self.assertEqual(failure["class"], "codex_transport_dns_failure")

    def test_codex_response_transport_failure_gets_specific_class(self) -> None:
        result = subprocess.CompletedProcess(["codex"], 1, "", "")
        failure = TOOL.classify_generation_failure(
            result,
            self.workspace / ".codex-home" / "job-workers" / "transport-fail",
            time.time(),
            self.workspace / "outputs" / "missing.png",
            "ERROR: stream disconnected before completion: error sending request for url "
            "(https://chatgpt.com/backend-api/codex/responses)",
        )

        self.assertEqual(failure["class"], "codex_transport_failure")

    def test_non_retryable_dns_failure_skips_remaining_attempts(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.add_basic_job("dns-non-retry")
        jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]

        def fake_attempt(**kwargs):
            return subprocess.CompletedProcess(
                kwargs["command"],
                1,
                "",
                "ERROR backend-api/codex/responses dns error: failed to lookup chatgpt.com",
            ), {
                "early_stopped": False,
                "early_stop_reason": None,
                "recovered_from": None,
                "termination": None,
                "timed_out": False,
            }

        with mock.patch.object(TOOL, "run_monitored_generation_attempt", side_effect=fake_attempt):
            record = TOOL.run_generation_job(
                self.workspace.resolve(),
                jobs[0],
                self.workspace / ".codex-home",
                retries=2,
                timeout=60,
                retry_base=0,
                retry_max=0,
                allow_latest_recovery=False,
                dry_run=False,
            )

        self.assertEqual(record["failure_class"], "codex_transport_dns_failure")
        self.assertEqual(record["retry_skipped_reason"], "codex_transport_dns_failure is non-retryable")
        self.assertEqual(len(record["attempts"]), 1)
        self.assertEqual(record["attempts"][0]["failure_class"], "codex_transport_dns_failure")

    def test_provider_no_output_still_uses_all_retry_attempts(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.add_basic_job("no-output-retries")
        jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]

        def fake_attempt(**kwargs):
            return subprocess.CompletedProcess(kwargs["command"], 0, "no image emitted", ""), {
                "early_stopped": False,
                "early_stop_reason": None,
                "recovered_from": None,
                "termination": None,
                "timed_out": False,
            }

        with mock.patch.object(TOOL, "run_monitored_generation_attempt", side_effect=fake_attempt):
            record = TOOL.run_generation_job(
                self.workspace.resolve(),
                jobs[0],
                self.workspace / ".codex-home",
                retries=2,
                timeout=60,
                retry_base=0,
                retry_max=0,
                allow_latest_recovery=False,
                dry_run=False,
            )

        self.assertEqual(record["failure_class"], "provider_no_output")
        self.assertNotIn("retry_skipped_reason", record)
        self.assertEqual(len(record["attempts"]), 3)
        self.assertTrue(all(attempt["failure_class"] == "provider_no_output" for attempt in record["attempts"]))
        self.assertEqual({attempt["executed_prompt_sha256"] for attempt in record["attempts"]}, {record["executed_prompt_sha256"]})

    def test_job_timeout_resolution_order(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.add_basic_job("job-timeout", timeout=321)
        jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        captured: list[int] = []

        def fake_attempt(**kwargs):
            captured.append(kwargs["timeout"])
            kwargs["output_path"].parent.mkdir(parents=True, exist_ok=True)
            kwargs["output_path"].write_bytes(TOOL.TINY_PNG_BYTES)
            return subprocess.CompletedProcess(kwargs["command"], 0, "", ""), {
                "early_stopped": False,
                "early_stop_reason": None,
                "recovered_from": None,
                "termination": None,
                "timed_out": False,
            }

        with mock.patch.object(TOOL, "run_monitored_generation_attempt", side_effect=fake_attempt):
            TOOL.run_generation_job(
                self.workspace.resolve(),
                jobs[0],
                self.workspace / ".codex-home",
                retries=0,
                timeout=123,
                retry_base=0,
                retry_max=0,
                allow_latest_recovery=False,
                dry_run=False,
            )
        self.assertEqual(captured[-1], 321)

        jobs[0].pop("timeout", None)
        with mock.patch.object(TOOL, "run_monitored_generation_attempt", side_effect=fake_attempt):
            TOOL.run_generation_job(
                self.workspace.resolve(),
                jobs[0],
                self.workspace / ".codex-home",
                retries=0,
                timeout=234,
                retry_base=0,
                retry_max=0,
                allow_latest_recovery=False,
                dry_run=False,
            )
        self.assertEqual(captured[-1], 234)
        self.assertEqual(TOOL.DEFAULT_TIMEOUT, 600)

    def test_validate_jobs_rejects_timeout_below_minimum(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.add_basic_job("short-timeout", timeout=30)

        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            result = self.run_tool("validate-jobs", "--workspace", str(self.workspace), "--requested-count", "1")

        self.assertEqual(result, 1)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(any("timeout_too_small" in issue for issue in payload["issues"]))

    def test_plugin_sync_timeout_warning_does_not_classify_as_provider_timeout(self) -> None:
        result = subprocess.CompletedProcess(["codex"], 0, "", "")
        failure = TOOL.classify_generation_failure(
            result,
            self.workspace / ".codex-home" / "job-workers" / "plugin-warning",
            0,
            self.workspace / "outputs" / "missing.png",
            "git fetch curated plugins repo timed out after 30s\nGenerated image inline.",
        )

        self.assertEqual(failure["class"], "provider_no_output")

    def test_generate_rejects_recovery_from_sibling_or_base_codex_home(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "cell-stale",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2 to create one jewelry image.",
            "--output",
            "outputs/cell-stale.png",
        )
        jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]

        command = self.local_generator_command(
            f"""
from pathlib import Path
base_stale = Path({str((self.workspace / ".codex-home" / "generated_images" / "old-session" / "stale.png"))!r})
sibling_stale = Path({str((self.workspace / ".codex-home" / "job-workers" / "other-job" / "generated_images" / "session" / "stale.png"))!r})
base_stale.parent.mkdir(parents=True, exist_ok=True)
sibling_stale.parent.mkdir(parents=True, exist_ok=True)
base_stale.write_bytes(b"base stale image")
sibling_stale.write_bytes(b"sibling stale image")
print(f"created {{base_stale}}")
print(f"created {{sibling_stale}}")
"""
        )
        with mock.patch.object(TOOL, "codex_generate_command", return_value=command):
            record = TOOL.run_generation_job(
                self.workspace.resolve(),
                jobs[0],
                self.workspace / ".codex-home",
                retries=0,
                timeout=60,
                retry_base=0,
                retry_max=0,
                allow_latest_recovery=True,
                dry_run=False,
            )

        self.assertEqual(record["status"], "failed")
        self.assertFalse((self.workspace / "outputs" / "cell-stale.png").exists())
        self.assertIsNone(record["attempts"][0]["recovered_from"])
        self.assertIn(record["failure_class"], {"provider_failure", "provider_no_output", "recovery_failed"})

    def test_prompt_constraints_do_not_trigger_post_processing_rejection(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        ref = self.write_reference()
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "cell-03",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2. Do not post-process with PIL, ImageMagick, ffmpeg, sips, or overlays.",
            "--output",
            "outputs/cell-03.png",
            "--reference",
            str(ref),
        )
        jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]

        command = self.local_generator_command(
            """
import os
import sys
from pathlib import Path
prompt = sys.stdin.read()
generated = Path(os.environ["CODEX_HOME"]) / "generated_images" / "session-1" / "ig_constraint_safe.png"
generated.parent.mkdir(parents=True, exist_ok=True)
generated.write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63f8ffff3f0005fe02fe0def46b80000000049454e44ae426082"))
print(prompt)
print(f"selected {generated}")
"""
        )
        with mock.patch.object(TOOL, "codex_generate_command", return_value=command):
            record = TOOL.run_generation_job(
                self.workspace.resolve(),
                jobs[0],
                self.workspace / ".codex-home",
                retries=0,
                timeout=60,
                retry_base=0,
                retry_max=0,
                allow_latest_recovery=False,
                dry_run=False,
            )

        self.assertEqual(record["status"], "done")
        self.assertNotIn("processing_rejection", record["attempts"][0])

    def test_actual_processing_marker_still_triggers_rejection(self) -> None:
        rejection = TOOL.detect_disallowed_processing("ran ffmpeg -i tmp.png outputs/final.png")

        self.assertEqual(rejection, "post-generation processing marker detected: ffmpeg")

    def test_plain_convert_word_does_not_trigger_processing_rejection(self) -> None:
        rejection = TOOL.detect_disallowed_processing("I will convert the brief into a complete image prompt.")

        self.assertIsNone(rejection)

    def test_codex_home_is_reused_without_copying_identity_or_config(self) -> None:
        source_home = Path(self.tmp.name) / "source-codex"
        source_home.mkdir()
        (source_home / "auth.json").write_text("secret", encoding="utf-8")
        (source_home / "config.toml").write_text("config", encoding="utf-8")

        with mock.patch.dict(os.environ, {"CODEX_HOME": str(source_home)}):
            codex_home = TOOL.prepare_codex_home(self.workspace)
            worker_home = TOOL.prepare_worker_codex_home(codex_home, "cell-01")

        self.assertEqual(codex_home, source_home.resolve())
        self.assertEqual(worker_home, source_home.resolve())
        self.assertFalse((self.workspace / ".codex-home").exists())
        self.assertTrue((codex_home / "auth.json").exists())
        self.assertTrue((codex_home / "config.toml").exists())

    def test_codex_home_preparation_never_mutates_user_files(self) -> None:
        source_home = Path(self.tmp.name) / "source-codex"
        source_home.mkdir()
        (source_home / "auth.json").write_text("fresh-auth-v1", encoding="utf-8")
        (source_home / "config.toml").write_text("source-config-v1", encoding="utf-8")

        with mock.patch.dict(os.environ, {"CODEX_HOME": str(source_home)}):
            codex_home = TOOL.prepare_codex_home(self.workspace)

        (source_home / "auth.json").write_text("fresh-auth-v2", encoding="utf-8")
        (source_home / "config.toml").write_text("source-config-v2", encoding="utf-8")

        with mock.patch.dict(os.environ, {"CODEX_HOME": str(source_home)}):
            codex_home = TOOL.prepare_codex_home(self.workspace)
            worker_home = TOOL.prepare_worker_codex_home(codex_home, "cell-01")

        self.assertEqual((codex_home / "auth.json").read_text(encoding="utf-8"), "fresh-auth-v2")
        self.assertEqual((codex_home / "config.toml").read_text(encoding="utf-8"), "source-config-v2")
        self.assertEqual((worker_home / "auth.json").read_text(encoding="utf-8"), "fresh-auth-v2")
        self.assertFalse((self.workspace / ".codex-home").exists())









    def test_assemble_markdown_creates_assets_with_stable_anchors(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace), "--title", "Jewelry Board")
        output = self.workspace / "outputs" / "hero.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"png")
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "hero",
            "--title",
            "Hero",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.",
            "--output",
            "outputs/hero.png",
        )
        self.run_tool("assemble-markdown", "--workspace", str(self.workspace))

        markdown = (self.workspace / "output" / "jewelry-image-report.md").read_text(encoding="utf-8")
        assets = json.loads((self.workspace / "output" / "jewelry-image-assets.json").read_text(encoding="utf-8"))
        self.assertIn("SVT_JEWELRY_IMAGE_HERO", markdown)
        self.assertEqual(assets["assets"][0]["anchor"], "SVT_JEWELRY_IMAGE_HERO")
        self.assertTrue(assets["assets"][0]["exists"])

    def test_assemble_markdown_can_include_reference_and_cover_assets(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace), "--title", "Jewelry Board")
        cover = self.workspace / "outputs" / "cover.png"
        cover.parent.mkdir(parents=True, exist_ok=True)
        cover.write_bytes(b"cover")
        ref = self.write_reference("source.jpg")
        output = self.workspace / "outputs" / "hero.png"
        output.write_bytes(b"png")
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "hero",
            "--title",
            "Hero",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.",
            "--output",
            "outputs/hero.png",
            "--reference",
            str(ref),
        )
        self.run_tool("assemble-markdown", "--workspace", str(self.workspace), "--cover", "outputs/cover.png")

        markdown = (self.workspace / "output" / "jewelry-image-report.md").read_text(encoding="utf-8")
        assets = json.loads((self.workspace / "output" / "jewelry-image-assets.json").read_text(encoding="utf-8"))["assets"]
        self.assertIn("## 封面设计", markdown)
        self.assertIn("## 参考图", markdown)
        self.assertEqual([asset["role"] for asset in assets], ["cover", "reference", "generated"])

    def test_guarded_mode_allows_current_run_workspace(self) -> None:
        with self.guarded_workspace() as workspace_raw:
            workspace = Path(workspace_raw)
            active_run_id = workspace.name
            with mock.patch.dict(os.environ, {"SVT_ACTIVE_TASK_ID": active_run_id}):
                self.assertEqual(self.run_tool("init", "--workspace", str(workspace)), 0)
                result = self.run_tool(
                    "add-job",
                    "--workspace",
                    str(workspace),
                    "--job-id",
                    "guarded",
                    "--prompt",
                    "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.",
                    "--output",
                    "outputs/guarded.png",
                )

            self.assertEqual(result, 0)
            self.assertTrue((workspace / "state.json").exists())
            self.assertTrue((workspace / "jobs.json").exists())
            self.assertTrue((workspace / "prompts" / "guarded.prompt.txt").exists())

    def test_guarded_mode_rejects_other_run_workspace_and_output_traversal(self) -> None:
        with self.guarded_workspace() as workspace_raw:
            workspace = Path(workspace_raw)
            active_run_id = workspace.name
            other = workspace.parent / f"{active_run_id}-other"
            with mock.patch.dict(os.environ, {"SVT_ACTIVE_TASK_ID": active_run_id}):
                other_result = self.run_tool("init", "--workspace", str(other))
                self.assertNotEqual(other_result, 0)
                self.assertFalse(other.exists())

                self.assertEqual(self.run_tool("init", "--workspace", str(workspace)), 0)
                traversal = self.run_tool(
                    "add-job",
                    "--workspace",
                    str(workspace),
                    "--job-id",
                    "traversal",
                    "--prompt",
                    "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.",
                    "--output",
                    "../../docs/leak.png",
                )

            self.assertNotEqual(traversal, 0)
            self.assertFalse((REPO_ROOT / "artifacts" / "docs" / "leak.png").exists())

    def test_guarded_mode_rejects_outside_prompt_reference_and_symlink_output(self) -> None:
        with self.guarded_workspace() as workspace_raw:
            workspace = Path(workspace_raw)
            active_run_id = workspace.name
            outside = Path(self.tmp.name) / "outside"
            outside.mkdir(parents=True)
            prompt = outside / "prompt.txt"
            prompt.write_text("$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.\n", encoding="utf-8")
            reference = outside / "ref.png"
            reference.write_bytes(b"png")
            symlink_target = outside / "escaped-outputs"
            symlink_target.mkdir()

            with mock.patch.dict(os.environ, {"SVT_ACTIVE_TASK_ID": active_run_id}):
                self.assertEqual(self.run_tool("init", "--workspace", str(workspace)), 0)
                prompt_result = self.run_tool(
                    "add-job",
                    "--workspace",
                    str(workspace),
                    "--job-id",
                    "outside-prompt",
                    "--prompt-file",
                    str(prompt),
                )
                reference_result = self.run_tool(
                    "add-job",
                    "--workspace",
                    str(workspace),
                    "--job-id",
                    "outside-reference",
                    "--prompt",
                    "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.",
                    "--reference",
                    str(reference),
                    "--output",
                    "safe-output.png",
                )
                (workspace / "outputs").rmdir()
                outputs_link = workspace / "outputs"
                outputs_link.symlink_to(symlink_target, target_is_directory=True)
                symlink_result = self.run_tool(
                    "add-job",
                    "--workspace",
                    str(workspace),
                    "--job-id",
                    "symlink-output",
                    "--prompt",
                    "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.",
                    "--output",
                    "outputs/leak.png",
                )

            self.assertNotEqual(prompt_result, 0)
            self.assertNotEqual(reference_result, 0)
            self.assertNotEqual(symlink_result, 0)


    def test_assemble_markdown_includes_completed_video_assets(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace), "--title", "Video Board")
        output = self.workspace / "outputs" / "hero.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"png")
        video = self.workspace / "video" / "downloads" / "video-01.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"mp4")
        result_path = self.workspace / "video" / "results" / "video-01.query-result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps({
            "job_id": "video-01",
            "title": "Video 01",
            "submit_id": "submit-01",
            "gen_status": "success",
            "video": {
                "local_path": "video/downloads/video-01.mp4",
                "width": 720,
                "height": 1280,
                "fps": 60,
                "duration": 12.0,
                "format": "mp4",
            },
        }), encoding="utf-8")
        self.run_tool(
            "add-job",
            "--workspace",
            str(self.workspace),
            "--job-id",
            "hero",
            "--title",
            "Hero",
            "--prompt",
            "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.",
            "--output",
            "outputs/hero.png",
        )
        self.run_tool("assemble-markdown", "--workspace", str(self.workspace))

        video_asset = json.loads((self.workspace / "output" / "jewelry-video-assets.json").read_text(encoding="utf-8"))["assets"][0]
        self.assertEqual(video_asset["title"], "Video 01")
        self.assertEqual(video_asset["path"], "video/downloads/video-01.mp4")
        self.assertTrue(video_asset["exists"])

    def test_generate_dry_run_records_parallel_settings(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        for job_id in ["cell-a", "cell-b"]:
            self.run_tool(
                "add-job",
                "--workspace",
                str(self.workspace),
                "--job-id",
                job_id,
                "--prompt",
                "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.",
                "--allow-duplicate-prompt",
                "--output",
                f"outputs/{job_id}.png",
            )

        result = self.run_tool(
            "generate",
            "--workspace",
            str(self.workspace),
            "--dry-run",
            "--parallel",
            "2",
            "--retry-base",
            "0",
            "--retry-max",
            "0",
        )

        self.assertEqual(result, 0)
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_generation"]["parallel"], 2)

    def test_generate_dry_run_defaults_to_parallel_eight(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        for job_id in ["cell-a", "cell-b"]:
            self.run_tool(
                "add-job",
                "--workspace",
                str(self.workspace),
                "--job-id",
                job_id,
                "--prompt",
                "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.",
                "--allow-duplicate-prompt",
                "--output",
                f"outputs/{job_id}.png",
            )

        result = self.run_tool(
            "generate",
            "--workspace",
            str(self.workspace),
            "--dry-run",
            "--retry-base",
            "0",
            "--retry-max",
            "0",
        )

        self.assertEqual(result, 0)
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_generation"]["parallel"], 8)

    def test_generate_dry_run_records_launch_evidence_for_multiple_jobs(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        ref = self.write_reference()
        for job_id in ["cell-a", "cell-b", "cell-c"]:
            self.run_tool(
                "add-job",
                "--workspace",
                str(self.workspace),
                "--job-id",
                job_id,
                "--prompt",
                "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.",
                "--allow-duplicate-prompt",
                "--output",
                f"outputs/{job_id}.png",
                "--reference",
                str(ref),
            )

        result = self.run_tool(
            "generate",
            "--workspace",
            str(self.workspace),
            "--dry-run",
            "--retry-base",
            "0",
            "--retry-max",
            "0",
        )

        self.assertEqual(result, 0)
        worker_homes = set()
        for job_id in ["cell-a", "cell-b", "cell-c"]:
            record = json.loads((self.workspace / "jobs" / f"{job_id}.json").read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "dry_run")
            self.assertTrue(record["dry_run"])
            self.assertEqual(record["launch_evidence"]["kind"], "dry_run")
            self.assertIn("queued_at", record)
            self.assertIn("worker_prepared_at", record)
            self.assertIn("launch_started_at", record)
            self.assertEqual(record["attempts"], [])
            self.assertEqual(record["prompt"], f"prompts/{job_id}.prompt.txt")
            self.assertEqual(record["output"], f"outputs/{job_id}.png")
            self.assertEqual(record["references"], [str(ref)])
            self.assertTrue((self.workspace / record["cmd_log"]).exists())
            self.assertTrue((self.workspace / record["stdout_log"]).exists())
            self.assertTrue((self.workspace / record["stderr_log"]).exists())
            worker_homes.add(record["worker_codex_home"])
        self.assertEqual(worker_homes, {"user-codex-home"})

    def test_generate_real_run_fans_out_before_first_completion(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        for job_id in ["cell-a", "cell-b", "cell-c"]:
            self.run_tool(
                "add-job",
                "--workspace",
                str(self.workspace),
                "--job-id",
                job_id,
                "--prompt",
                "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.",
                "--allow-duplicate-prompt",
                "--output",
                f"outputs/{job_id}.png",
            )

        command = self.local_generator_command(
            """
import os
import time
from pathlib import Path
workspace = Path.cwd()
codex_home = Path(os.environ["CODEX_HOME"])
job_id = os.environ["JDC_IMAGE2_JOB_ID"]
markers = workspace / "logs" / "fanout-markers"
markers.mkdir(parents=True, exist_ok=True)
(markers / f"{job_id}.entered").write_text(str(codex_home), encoding="utf-8")
deadline = time.time() + 5
while len(list(markers.glob("*.entered"))) < 3:
    if time.time() > deadline:
        raise SystemExit("fanout barrier was not reached")
    time.sleep(0.02)
if not list(markers.glob("*.done")):
    (markers / f"{job_id}.first-count").write_text(str(len(list(markers.glob("*.entered")))), encoding="utf-8")
generated = codex_home / "generated_images" / "session-1" / f"{job_id}.png"
generated.parent.mkdir(parents=True, exist_ok=True)
generated.write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63f8ffff3f0005fe02fe0def46b80000000049454e44ae426082") + job_id.encode("utf-8"))
print(f"selected {generated}")
(markers / f"{job_id}.done").write_text("done", encoding="utf-8")
"""
        )
        with mock.patch.object(TOOL, "codex_generate_command", return_value=command):
            result = self.run_tool(
                "generate",
                "--workspace",
                str(self.workspace),
                "--parallel",
                "3",
                "--retries",
                "0",
                "--retry-base",
                "0",
                "--retry-max",
                "0",
            )

        self.assertEqual(result, 0)
        markers = self.workspace / "logs" / "fanout-markers"
        entered = sorted(markers.glob("*.entered"))
        first_counts = [path.read_text(encoding="utf-8") for path in markers.glob("*.first-count")]
        codex_homes = {path.read_text(encoding="utf-8") for path in entered}
        self.assertEqual(len(entered), 3)
        self.assertTrue(first_counts)
        self.assertTrue(all(count == "3" for count in first_counts))
        self.assertEqual(len(codex_homes), 1)
        for job_id in ["cell-a", "cell-b", "cell-c"]:
            record = json.loads((self.workspace / "jobs" / f"{job_id}.json").read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "done")
            self.assertFalse(record["dry_run"])
            self.assertEqual(record["launch_evidence"]["kind"], "subprocess_popen_monitor")
            self.assertEqual(record["worker_codex_home"], "user-codex-home")
            attempt = record["attempts"][0]
            self.assertIsNotNone(attempt["started_at"])
            self.assertIsNotNone(attempt["finished_at"])
            self.assertIsNotNone(attempt["duration_seconds"])
            self.assertEqual(attempt["returncode"], 0)
            self.assertIn("recovered_from", attempt)
            jobs = json.loads((self.workspace / "jobs.json").read_text(encoding="utf-8"))["jobs"]
            job_status = next(job for job in jobs if job["id"] == job_id)
            self.assertEqual(job_status["status"], "done")

    def test_generate_dry_run_fanout_parent_exits_after_all_jobs_finish(self) -> None:
        self.run_tool("init", "--workspace", str(self.workspace))
        for job_id in ["cell-a", "cell-b", "cell-c", "cell-d"]:
            self.run_tool(
                "add-job",
                "--workspace",
                str(self.workspace),
                "--job-id",
                job_id,
                "--prompt",
                "$imagegen\nDirect image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not create extra task documents. Do not edit task progress. Do not assemble reports. Do not perform post-processing. Return only the generated image result.\nUse gpt-image-2.",
                "--allow-duplicate-prompt",
                "--output",
                f"outputs/{job_id}.png",
            )

        started = time.monotonic()
        proc = subprocess.Popen(
            [
                sys.executable,
                str(TOOL_PATH),
                "generate",
                "--workspace",
                str(self.workspace),
                "--dry-run",
                "--parallel",
                "4",
                "--retry-base",
                "0",
                "--retry-max",
                "0",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate(timeout=5)

        self.assertEqual(proc.returncode, 0, stderr)
        self.assertLess(time.monotonic() - started, 5)
        self.assertIsNotNone(proc.poll())
        payload = json.loads(stdout)
        self.assertEqual(payload["failures"], 0)
        self.assertEqual(len(payload["results"]), 4)
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_generation"]["parallel"], 4)
        for job_id in ["cell-a", "cell-b", "cell-c", "cell-d"]:
            record = json.loads((self.workspace / "jobs" / f"{job_id}.json").read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "dry_run")

if __name__ == "__main__":
    unittest.main()
