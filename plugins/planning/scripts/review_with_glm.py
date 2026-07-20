#!/usr/bin/env python3
"""Send an implementation plan to GLM through OpenCode without a shell."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_MODEL = "zai-coding-plan/glm-5.2"
REVIEW_PROMPT = """Review the implementation plan supplied on stdin.
Evaluate whether it is standalone, implementation-complete, aligned with the
repository, explicit about interfaces and edge cases, and backed by sufficient
acceptance criteria and tests. Return specific, actionable feedback organized
by severity. Do not edit files."""


def read_plan(path: str | None) -> str:
    if path:
        plan_path = Path(path).expanduser().resolve()
        if not plan_path.is_file():
            raise ValueError(f"plan file not found: {plan_path}")
        plan = plan_path.read_text(encoding="utf-8")
    else:
        plan = sys.stdin.read()
    if not plan.strip():
        raise ValueError("plan content is empty")
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", help="Plan file; omit to read the plan from stdin")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--opencode-bin", default="opencode")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    try:
        plan = read_plan(args.plan)
    except (OSError, ValueError) as exc:
        print(f"ask-glm: {exc}", file=sys.stderr)
        return 2

    executable = shutil.which(args.opencode_bin)
    if not executable:
        print("ask-glm: opencode is not installed or not on PATH", file=sys.stderr)
        return 127

    command = [executable, "run", "-m", args.model, "--", REVIEW_PROMPT]
    try:
        result = subprocess.run(
            command,
            input=plan,
            text=True,
            capture_output=True,
            timeout=args.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"ask-glm: review timed out after {args.timeout} seconds", file=sys.stderr)
        return 124

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown OpenCode error"
        print(f"ask-glm: {detail}", file=sys.stderr)
        return result.returncode
    if not result.stdout.strip():
        print("ask-glm: OpenCode returned no review text", file=sys.stderr)
        return 1

    sys.stdout.write(result.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
