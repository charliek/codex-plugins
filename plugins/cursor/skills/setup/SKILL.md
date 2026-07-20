---
name: setup
description: Check whether the Cursor agent CLI is installed, authenticated, and ready, including version, account, and available models. Use when the user asks to install, configure, diagnose, or verify Cursor CLI access.
---

# Check Cursor CLI readiness

1. Resolve the plugin root and run `scripts/cursor_agent.py setup`.
2. Report the executable path, CLI version, authenticated account, and whether `cursor-grok-4.5-high` is available.
3. If the executable is missing, point to the official installation instructions at <https://cursor.com/cli>. Do not run an installer automatically.
4. If authentication is missing, instruct the user to run `agent login` and then repeat this check.
5. Mention `agent --list-models` for model discovery and report any failed readiness check precisely.
