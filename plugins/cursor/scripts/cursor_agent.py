#!/usr/bin/env python3
"""Safely invoke the Cursor agent CLI for delegated tasks and reviews."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_MODEL = "cursor-grok-4.5-high"


class CursorError(RuntimeError):
    pass


def run(command: list[str], *, cwd: Path, input_text: str | None = None, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def find_agent(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise CursorError("Cursor agent CLI is not installed; install it from https://cursor.com/cli")
    return executable


def read_prompt(path: str | None) -> str:
    if path:
        prompt_path = Path(path).expanduser().resolve()
        if not prompt_path.is_file():
            raise CursorError(f"prompt file not found: {prompt_path}")
        prompt = prompt_path.read_text(encoding="utf-8")
    else:
        prompt = sys.stdin.read()
    if not prompt.strip():
        raise CursorError("task prompt is empty")
    return prompt


def invoke_agent(
    executable: str,
    *,
    cwd: Path,
    prompt: str,
    model: str,
    read_only: bool,
    resume: bool,
    trust: bool,
    timeout: int,
) -> int:
    command = [executable, "-p", "--output-format", "json"]
    command.extend(["--mode", "plan"] if read_only else ["--force"])
    command.extend(["--model", model])
    if resume:
        command.append("--continue")
    if trust:
        command.append("--trust")
    if "\0" in prompt:
        raise CursorError("task prompt contains a NUL byte")
    try:
        # The current Cursor CLI accepts the prompt as a positional argument,
        # not on stdin. Passing an argv list directly avoids shell expansion.
        # For very large diffs, use an added temporary workspace to stay below
        # the operating system's argv-size limit.
        if len(prompt.encode("utf-8")) > 100_000:
            with tempfile.TemporaryDirectory(prefix="codex-cursor-prompt-") as temp_name:
                prompt_file = Path(temp_name) / "request.md"
                prompt_file.write_text(prompt, encoding="utf-8")
                result = run(
                    [
                        *command,
                        "--add-dir",
                        temp_name,
                        f"Read {prompt_file} as the complete review or task request and follow it.",
                    ],
                    cwd=cwd,
                    timeout=timeout,
                )
        else:
            result = run([*command, prompt], cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise CursorError(f"Cursor task timed out after {timeout} seconds")
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Cursor error"
        raise CursorError(detail)
    if not result.stdout.strip():
        raise CursorError("Cursor returned no output")
    try:
        event = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CursorError("Cursor returned invalid JSON output") from exc
    if not isinstance(event, dict) or event.get("is_error") is True:
        raise CursorError(str(event.get("result") if isinstance(event, dict) else event))
    response = event.get("result")
    if not isinstance(response, str) or not response.strip():
        raise CursorError("Cursor result contained no response text")
    sys.stdout.write(response)
    return 0


def git_output(root: Path, arguments: list[str]) -> str:
    result = run(["git", *arguments], cwd=root, timeout=60)
    if result.returncode != 0:
        raise CursorError(result.stderr.strip() or f"git {' '.join(arguments)} failed")
    return result.stdout


def git_root(path: Path) -> Path:
    output = git_output(path, ["rev-parse", "--show-toplevel"]).strip()
    if not output:
        raise CursorError("current directory is not inside a Git repository")
    return Path(output).resolve()


def build_review_prompt(root: Path, scope: str, base: str, adversarial: bool, focus: str) -> str:
    if scope == "working-tree":
        status = git_output(root, ["status", "--short", "--untracked-files=all"])
        staged = git_output(root, ["diff", "--cached"])
        unstaged = git_output(root, ["diff"])
        if not (status.strip() or staged.strip() or unstaged.strip()):
            raise CursorError("there are no working-tree changes to review")
        changes = (
            "--- changed files ---\n" + status +
            "\n--- staged diff ---\n" + staged +
            "\n--- unstaged diff ---\n" + unstaged
        )
        target = "the uncommitted working-tree changes"
    else:
        git_output(root, ["rev-parse", "--verify", base])
        names = git_output(root, ["diff", "--name-status", f"{base}...HEAD"])
        diff = git_output(root, ["diff", f"{base}...HEAD"])
        if not (names.strip() or diff.strip()):
            raise CursorError(f"there are no branch changes against {base}")
        changes = f"--- changed files (vs {base}) ---\n{names}\n--- diff (vs {base}) ---\n{diff}"
        target = f"the diff of HEAD against {base}"

    if adversarial:
        instructions = (
            "Challenge the approach itself, including its design choices, assumptions, tradeoffs, "
            "failure modes, scalability, concurrency, and maintainability. Propose a stronger "
            "alternative wherever the chosen approach is materially weak."
        )
    else:
        instructions = (
            "Report concrete correctness, security, edge-case, and likely-bug findings ordered by "
            "severity. Include exact file paths and line numbers where possible."
        )
    focus_line = f"\nFocus especially on: {focus}" if focus.strip() else ""
    return f"""Review {target} supplied below. This is review-only: do not edit files. You may read
other repository files for context. {instructions}{focus_line}
If there are no significant findings, say so and note residual risk briefly.

=== BEGIN CHANGES ===
{changes}
=== END CHANGES ===
"""


def command_setup(args: argparse.Namespace) -> int:
    executable = find_agent(args.agent_bin)
    for label, command in (
        ("About", [executable, "about"]),
        ("Status", [executable, "status"]),
        ("Models", [executable, "--list-models"]),
    ):
        result = run(command, cwd=Path.cwd(), timeout=60)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise CursorError(f"{label.lower()} check failed: {detail}")
        print(f"## {label}\n{result.stdout.rstrip()}\n")
    return 0


def command_task(args: argparse.Namespace) -> int:
    executable = find_agent(args.agent_bin)
    prompt = read_prompt(args.prompt_file)
    return invoke_agent(
        executable,
        cwd=Path(args.repo).expanduser().resolve(),
        prompt=prompt,
        model=args.model,
        read_only=args.read_only,
        resume=args.resume,
        trust=args.trust,
        timeout=args.timeout,
    )


def command_review(args: argparse.Namespace) -> int:
    executable = find_agent(args.agent_bin)
    root = git_root(Path(args.repo).expanduser().resolve())
    prompt = build_review_prompt(root, args.scope, args.base, args.adversarial, args.focus)
    return invoke_agent(
        executable,
        cwd=root,
        prompt=prompt,
        model=args.model,
        read_only=True,
        resume=False,
        trust=args.trust,
        timeout=args.timeout,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--agent-bin", default="agent")
    subparsers = root.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser("setup")
    setup.set_defaults(handler=command_setup)

    task = subparsers.add_parser("task")
    task.add_argument("--repo", default=".")
    task.add_argument("--prompt-file")
    task.add_argument("--model", default=DEFAULT_MODEL)
    task.add_argument("--read-only", action="store_true")
    task.add_argument("--resume", action="store_true")
    task.add_argument("--trust", action="store_true")
    task.add_argument("--timeout", type=int, default=600)
    task.set_defaults(handler=command_task)

    review = subparsers.add_parser("review")
    review.add_argument("--repo", default=".")
    review.add_argument("--model", default=DEFAULT_MODEL)
    review.add_argument("--scope", choices=("working-tree", "branch"), default="working-tree")
    review.add_argument("--base", default="main")
    review.add_argument("--adversarial", action="store_true")
    review.add_argument("--focus", default="")
    review.add_argument("--trust", action="store_true")
    review.add_argument("--timeout", type=int, default=600)
    review.set_defaults(handler=command_review)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except (CursorError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"cursor: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
