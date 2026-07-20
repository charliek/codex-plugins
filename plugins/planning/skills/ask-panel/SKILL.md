---
name: ask-panel
description: Review an implementation plan with native Codex reasoning, GLM 5.2, and the CodeRabbit engine, then synthesize and optionally incorporate their feedback. Use when the user explicitly asks for a panel, multi-model, or independent multi-reviewer plan review.
---

# Run the plan review panel

1. Resolve the plan from an explicit file, pasted text, or the active conversation plan. Request it and stop if unavailable.
2. Read relevant repository instructions and implementation files. Check that the plan is review-ready and disclose any preflight refinements.
3. Start the GLM and CodeRabbit workflows from the sibling `ask-glm` and `ask-coderabbit` skills concurrently when the execution surface supports independent background work. Otherwise run them sequentially. Do not spawn a nested `codex exec` process.
4. While external reviews run, perform the native review defined by the sibling `review-plan` skill.
5. Continue with successful reviewers when one external tool is missing or fails, but name every skipped or failed reviewer.
6. Normalize all feedback into concrete findings:
   - Prioritize findings supported by multiple reviewers.
   - Evaluate unique findings on their own evidence.
   - Give native Codex findings no automatic preference over sound external evidence.
   - Surface direct contradictions for user judgment instead of silently choosing.
   - Exclude style-only changes and unsupported speculation.
7. Report reviewer-by-reviewer results, consensus findings, accepted unique findings, rejected suggestions, contradictions, and tool failures.
8. When incorporation is requested, update the explicit plan file or return a complete revised plan in the conversation. Preserve a standalone goal, implementation details, interfaces, tests, acceptance criteria, and explicit assumptions.
