---
name: review
description: Run a read-only Cursor agent review of working-tree or branch changes. Use only when the user explicitly asks Cursor to review code, a diff, a branch, or local changes.
---

# Review changes with Cursor

1. Resolve the review scope:
   - Default to `working-tree` for staged, unstaged, and untracked changes.
   - Use `branch` when a base ref is supplied or branch comparison is requested; default the base to `main`.
2. Resolve the plugin root and run `scripts/cursor_agent.py review --scope <scope>`, adding `--base <ref>` and `--model <id>` when supplied.
3. The helper extracts and streams the diff safely and always invokes Cursor in plan/read-only mode. Do not bypass it with an inline shell pipeline.
4. Run in the foreground by default. Honor an explicit background request when the execution surface supports it.
5. Return Cursor's findings without rewriting their substance. Put severe findings first and preserve paths and line numbers.
6. If there are no changes, report that clearly. On CLI failure, report the error without substituting a manual review labeled as Cursor.
7. Stop after presenting findings. Ask which findings, if any, the user wants fixed before editing files.
