---
name: adversarial-review
description: Run a read-only Cursor challenge review that questions an implementation's design, assumptions, tradeoffs, and failure modes. Use only when the user explicitly requests an adversarial or design-focused Cursor review.
---

# Run an adversarial Cursor review

1. Resolve scope exactly as in the sibling `review` skill: working tree by default, or branch diff against an explicit/default `main` base.
2. Preserve any user-provided focus text as review guidance, not shell syntax.
3. Resolve the plugin root and run `scripts/cursor_agent.py review --adversarial`, adding `--scope`, `--base`, `--focus`, and `--model` as needed.
4. Keep the run read-only. Challenge whether the chosen approach is correct, what assumptions it depends on, and how it behaves under real failure, scale, concurrency, and maintenance pressure.
5. Honor foreground/background preferences when supported and report tool failures without inventing Cursor feedback.
6. Present findings ordered by severity with concrete alternatives where the approach is weak.
7. Stop before fixes and ask which findings the user wants addressed.
