#!/usr/bin/env python3
"""Review a plan as the sole diff in an isolated repository using CodeRabbit."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath


PLAN_NAME = ".codex-plan-review.md"
RUBRIC = """Review the Markdown implementation plan in this diff as a plan, not as
product documentation. Check that it is standalone, implementable, consistent
with repository patterns, explicit about public interfaces and failure modes,
and supported by adequate acceptance criteria and tests. Identify concrete
gaps, contradictions, unsafe assumptions, and missing edge cases. Do not ask
for implementation changes unrelated to the proposed work. Return actionable
findings ordered by severity."""


class ReviewError(RuntimeError):
    pass


def run(command: list[str], *, cwd: Path, input_text: str | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def read_plan(path: str | None) -> str:
    if path:
        plan_path = Path(path).expanduser().resolve()
        if not plan_path.is_file():
            raise ReviewError(f"plan file not found: {plan_path}")
        plan = plan_path.read_text(encoding="utf-8")
    else:
        plan = sys.stdin.read()
    if not plan.strip():
        raise ReviewError("plan content is empty")
    return plan


def repository_root(path: Path) -> Path:
    result = run(["git", "rev-parse", "--show-toplevel"], cwd=path)
    if result.returncode != 0:
        raise ReviewError("current directory is not inside a Git repository")
    return Path(result.stdout.strip()).resolve()


def repository_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReviewError(result.stderr.decode(errors="replace").strip() or "git ls-files failed")
    files: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
        pure = PurePosixPath(relative.as_posix())
        if pure.is_absolute() or ".." in pure.parts or pure.as_posix() == PLAN_NAME:
            continue
        files.append(relative)
    return files


def copy_repository_snapshot(source: Path, destination: Path) -> None:
    for relative in repository_files(source):
        origin = source / relative
        target = destination / relative
        if origin.is_symlink():
            try:
                resolved = origin.resolve(strict=True)
                resolved.relative_to(source)
            except (OSError, ValueError):
                # Do not let a tracked symlink expose data outside the repository
                # to the temporary review context.
                continue
            if resolved.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(resolved, target)
        elif origin.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, target)


def git(command: list[str], cwd: Path) -> None:
    result = run(["git", *command], cwd=cwd)
    if result.returncode != 0:
        raise ReviewError(result.stderr.strip() or f"git {' '.join(command)} failed")


def validate_agent_output(output: str) -> None:
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "error":
            message = event.get("message") or event.get("error") or line
            raise ReviewError(f"CodeRabbit reported an error: {message}")


def check_coderabbit(executable: str, cwd: Path) -> None:
    version = run([executable, "--version"], cwd=cwd)
    if version.returncode != 0:
        raise ReviewError(version.stderr.strip() or "CodeRabbit CLI is not usable")
    auth = run([executable, "auth", "status", "--agent"], cwd=cwd)
    authenticated = auth.returncode == 0
    for line in auth.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("authenticated") is False:
            authenticated = False
    if not authenticated:
        raise ReviewError("CodeRabbit is not authenticated; run `coderabbit auth login --agent`")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", help="Plan file; omit to read the plan from stdin")
    parser.add_argument("--repo", default=".", help="Repository used for review context")
    parser.add_argument("--coderabbit-bin", default="coderabbit")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument(
        "--acknowledge-data-upload",
        action="store_true",
        help="Confirm that plan and repository context may be sent to CodeRabbit",
    )
    args = parser.parse_args()

    if not args.acknowledge_data_upload:
        print(
            "ask-coderabbit: pass --acknowledge-data-upload after informing the user that "
            "plan and repository context may leave the machine",
            file=sys.stderr,
        )
        return 2

    try:
        plan = read_plan(args.plan)
        root = repository_root(Path(args.repo).expanduser().resolve())
        executable = shutil.which(args.coderabbit_bin)
        if not executable:
            raise ReviewError("coderabbit is not installed or not on PATH")
        check_coderabbit(executable, root)

        with tempfile.TemporaryDirectory(prefix="codex-plan-coderabbit-") as temp_name:
            temp = Path(temp_name)
            snapshot = temp / "repository"
            snapshot.mkdir()
            copy_repository_snapshot(root, snapshot)
            git(["init", "-q", "-b", "main"], snapshot)
            git(["config", "user.name", "Codex Plan Review"], snapshot)
            git(["config", "user.email", "codex-plan-review@localhost"], snapshot)
            git(["add", "-A"], snapshot)
            git(["commit", "-q", "--allow-empty", "-m", "review baseline"], snapshot)

            (snapshot / PLAN_NAME).write_text(plan, encoding="utf-8")
            git(["add", "-f", PLAN_NAME], snapshot)
            rubric = temp / "plan-review-rubric.md"
            rubric.write_text(RUBRIC, encoding="utf-8")

            try:
                result = run(
                    [
                        executable,
                        "review",
                        "--agent",
                        "-t",
                        "uncommitted",
                        "--base",
                        "main",
                        "-c",
                        str(rubric),
                    ],
                    cwd=snapshot,
                    timeout=args.timeout,
                )
            except subprocess.TimeoutExpired as exc:
                raise ReviewError(f"review timed out after {args.timeout} seconds") from exc

            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip() or "unknown CodeRabbit error"
                raise ReviewError(detail)
            if not result.stdout.strip():
                raise ReviewError("CodeRabbit returned no review output")
            validate_agent_output(result.stdout)
            sys.stdout.write(result.stdout)
            return 0
    except (OSError, ReviewError, subprocess.TimeoutExpired) as exc:
        print(f"ask-coderabbit: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
