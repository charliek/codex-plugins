from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GLM = ROOT / "plugins/planning/scripts/review_with_glm.py"
CODERABBIT = ROOT / "plugins/planning/scripts/review_with_coderabbit.py"
CURSOR = ROOT / "plugins/cursor/scripts/cursor_agent.py"


def executable(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def run(command: list[str], *, cwd: Path, input_text: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def init_repo(path: Path) -> None:
    run(["git", "init", "-q"], cwd=path)
    run(["git", "config", "user.name", "Tests"], cwd=path)
    run(["git", "config", "user.email", "tests@example.com"], cwd=path)


class ExternalReviewTests(unittest.TestCase):
    def test_glm_forwards_plan_on_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            fake = executable(
                temp / "opencode",
                """#!/usr/bin/env python3
import json, sys
print(json.dumps({"argv": sys.argv[1:], "plan": sys.stdin.read()}))
""",
            )
            result = run(
                [sys.executable, str(GLM), "--opencode-bin", str(fake)],
                cwd=temp,
                input_text="# Plan\nDo the work safely.\n",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["plan"], "# Plan\nDo the work safely.\n")
            self.assertIn("zai-coding-plan/glm-5.2", payload["argv"])

    def test_coderabbit_reviews_only_synthetic_plan_diff(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            repo = temp / "source"
            repo.mkdir()
            init_repo(repo)
            (repo / "app.py").write_text("print('context')\n", encoding="utf-8")
            outside = temp / "outside-secret.txt"
            outside.write_text("do not copy\n", encoding="utf-8")
            (repo / "outside-link").symlink_to(outside)
            fake = executable(
                temp / "coderabbit",
                """#!/usr/bin/env python3
import json, pathlib, subprocess, sys
args = sys.argv[1:]
if args == ["--version"]:
    print("0.6.5")
elif args == ["auth", "status", "--agent"]:
    print(json.dumps({"type": "status", "authenticated": True}))
elif args[:2] == ["review", "--agent"]:
    status = subprocess.check_output(["git", "status", "--short"], text=True)
    plan = pathlib.Path(".codex-plan-review.md").read_text()
    rubric = pathlib.Path(args[args.index("-c") + 1]).read_text()
    if status.strip() != "A  .codex-plan-review.md":
        print(json.dumps({"type": "error", "message": "unexpected diff: " + status}))
        sys.exit(1)
    if pathlib.Path("outside-link").exists() or pathlib.Path("outside-link").is_symlink():
        print(json.dumps({"type": "error", "message": "external symlink copied"}))
        sys.exit(4)
    if "implementation plan" not in rubric.lower():
        sys.exit(2)
    print(json.dumps({"type": "status", "phase": "review"}))
    print(json.dumps({"type": "finding", "severity": "major", "message": plan.strip()}))
else:
    sys.exit(3)
""",
            )
            result = run(
                [
                    sys.executable,
                    str(CODERABBIT),
                    "--repo",
                    str(repo),
                    "--coderabbit-bin",
                    str(fake),
                    "--acknowledge-data-upload",
                ],
                cwd=repo,
                input_text="# Plan\nAdd a tested feature.\n",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            events = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(events[-1]["type"], "finding")
            self.assertIn("Add a tested feature", events[-1]["message"])
            self.assertEqual(
                run(["git", "status", "--short"], cwd=repo).stdout,
                "?? app.py\n?? outside-link\n",
            )

    def test_coderabbit_requires_upload_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            init_repo(temp)
            result = run([sys.executable, str(CODERABBIT)], cwd=temp, input_text="# Plan\n")
            self.assertEqual(result.returncode, 2)
            self.assertIn("acknowledge-data-upload", result.stderr)


class CursorHelperTests(unittest.TestCase):
    def fake_agent(self, directory: Path) -> Path:
        return executable(
            directory / "agent",
            """#!/usr/bin/env python3
import json, pathlib, sys
args = sys.argv[1:]
if args == ["about"]:
    print("Cursor CLI test")
elif args == ["status"]:
    print("Logged in")
elif args == ["--list-models"]:
    print("cursor-grok-4.5-high")
else:
    if "--add-dir" in args:
        directory = pathlib.Path(args[args.index("--add-dir") + 1])
        prompt = (directory / "request.md").read_text()
    else:
        prompt = args[-1]
    response = json.dumps({"argv": args, "prompt": prompt})
    print(json.dumps({"type": "result", "is_error": False, "result": response}))
""",
        )

    def test_cursor_task_passes_literal_prompt_on_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            fake = self.fake_agent(temp)
            prompt = "Fix `$(touch nope)` and preserve $HOME exactly.\n"
            result = run(
                [
                    sys.executable,
                    str(CURSOR),
                    "--agent-bin",
                    str(fake),
                    "task",
                    "--repo",
                    str(temp),
                ],
                cwd=temp,
                input_text=prompt,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["prompt"], prompt)
            self.assertIn("--force", payload["argv"])
            self.assertFalse((temp / "nope").exists())

    def test_cursor_large_prompt_uses_temporary_added_directory(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            fake = self.fake_agent(temp)
            prompt = "x" * 100_001
            result = run(
                [
                    sys.executable,
                    str(CURSOR),
                    "--agent-bin",
                    str(fake),
                    "task",
                    "--repo",
                    str(temp),
                    "--read-only",
                ],
                cwd=temp,
                input_text=prompt,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["prompt"], prompt)
            self.assertIn("--add-dir", payload["argv"])

    def test_cursor_review_is_read_only_and_contains_diff(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            init_repo(temp)
            fake = self.fake_agent(temp)
            source = temp / "app.py"
            source.write_text("value = 1\n", encoding="utf-8")
            run(["git", "add", "app.py"], cwd=temp)
            run(["git", "commit", "-q", "-m", "base"], cwd=temp)
            source.write_text("value = 2\n", encoding="utf-8")
            result = run(
                [
                    sys.executable,
                    str(CURSOR),
                    "--agent-bin",
                    str(fake),
                    "review",
                    "--repo",
                    str(temp),
                ],
                cwd=temp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["argv"][0:5], ["-p", "--output-format", "json", "--mode", "plan"])
            self.assertIn("-value = 1", payload["prompt"])
            self.assertIn("+value = 2", payload["prompt"])
            self.assertEqual(source.read_text(), "value = 2\n")

    def test_cursor_setup_reports_models(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            fake = self.fake_agent(temp)
            result = run(
                [sys.executable, str(CURSOR), "--agent-bin", str(fake), "setup"],
                cwd=temp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Cursor CLI test", result.stdout)
            self.assertIn("cursor-grok-4.5-high", result.stdout)


class RepositoryContractTests(unittest.TestCase):
    def test_marketplace_and_plugin_contract(self) -> None:
        marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        self.assertEqual(marketplace["name"], "codex-plugins")
        self.assertEqual([entry["name"] for entry in marketplace["plugins"]], ["planning", "cursor", "git-commands"])
        for entry in marketplace["plugins"]:
            manifest = json.loads((ROOT / entry["source"]["path"] / ".codex-plugin/plugin.json").read_text())
            self.assertEqual(manifest["name"], entry["name"])
            self.assertEqual(manifest["version"], "0.1.0")

    def test_ten_skills_have_matching_frontmatter(self) -> None:
        skills = sorted(ROOT.glob("plugins/*/skills/*/SKILL.md"))
        self.assertEqual(len(skills), 10)
        for skill in skills:
            text = skill.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), skill)
            name_line = next(line for line in text.splitlines() if line.startswith("name: "))
            self.assertEqual(name_line.removeprefix("name: "), skill.parent.name)

    def test_no_claude_command_artifacts(self) -> None:
        banned = ("$ARGUMENTS", "AskUserQuestion", "subagent_type:", ".claude-plugin")
        for path in ROOT.glob("plugins/*/skills/*/SKILL.md"):
            text = path.read_text(encoding="utf-8")
            for token in banned:
                self.assertNotIn(token, text, f"{token} in {path}")


if __name__ == "__main__":
    unittest.main()
