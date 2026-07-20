---
name: ask-glm
description: Submit an implementation plan to GLM 5.2 through OpenCode, evaluate its feedback, and optionally incorporate useful changes. Use when the user explicitly asks for a GLM, Z.ai, OpenCode, or independent external plan review.
---

# Ask GLM to review a plan

1. Resolve the plan from an explicit file, pasted text, or the active plan. Stop and request it when none is available.
2. Read the plan and relevant repository files. Identify obvious missing context, acceptance criteria, or tests before submission and disclose any preflight refinements.
3. Check `opencode --version`. If unavailable, report that OpenCode is required and stop.
4. Resolve this skill's plugin root, then run `scripts/review_with_glm.py`:
   - Use `--plan <path>` for a file.
   - Otherwise provide the plan on the script's stdin. Never interpolate plan text into a shell command.
5. Treat a nonzero exit or empty output as a failed GLM review. Report the actionable error; do not produce substitute feedback labeled as GLM.
6. Evaluate every returned point against repository evidence. Accept correctness, completeness, interface, risk, and test improvements; reject unsupported or style-only suggestions.
7. Modify an explicit plan file only when requested. Otherwise summarize GLM's feedback and, when incorporation was requested, return the complete revised plan in the conversation.
