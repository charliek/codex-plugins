---
name: rescue
description: Delegate a substantial coding, debugging, investigation, or follow-up task to the Cursor agent CLI and return its result. Use only when the user explicitly invokes Cursor or asks to hand work to the Cursor agent.
---

# Delegate a task to Cursor

1. Require a concrete task. Ask what Cursor should do when the request is empty.
2. Resolve the plugin root and use `scripts/cursor_agent.py task`. Provide the task on the helper's stdin; the helper passes it directly to Cursor as an argv value without invoking a shell.
3. Default to model `cursor-grok-4.5-high`. Honor an explicit model override.
4. Use write-capable mode for explicit implementation or fix requests. Add `--read-only` for diagnosis, research, planning, or review-only requests.
5. Add `--resume` when the user explicitly asks to resume or clearly continues prior Cursor work. Honor an explicit fresh request by omitting it.
6. Run in the foreground by default with a generous timeout. When the user requests background execution and the surface supports it, launch the script in a background execution session and report how to retrieve the result.
7. Return Cursor's stdout verbatim. Do not paraphrase it or silently complete the task yourself after a Cursor failure.
8. On failure, report the actionable stderr. Direct missing or unauthenticated installations to the sibling `setup` skill.

Cursor may modify the current repository in write-capable mode. Use it only when the user's explicit delegation authorizes those changes.
