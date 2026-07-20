---
name: review-plan
description: Review an implementation plan for completeness, feasibility, repository alignment, interfaces, risks, acceptance criteria, and tests. Use when the user asks Codex to critique, validate, or strengthen a plan without delegating to an external reviewer.
---

# Review an implementation plan

1. Resolve the plan from an explicit file, pasted text, or the active plan in the conversation. Ask for the plan only when none is available.
2. Read applicable repository instructions and inspect the files, configuration, and conventions the plan depends on. Do not judge the plan from prose alone.
3. Check that the plan is standalone and decision-complete:
   - Explain the goal and intended outcome.
   - Name material interfaces, data flow, compatibility constraints, and failure behavior.
   - Cover relevant edge cases, migrations, and operational risks.
   - Give test scenarios and objective acceptance criteria.
   - Match the repository's actual structure and patterns.
4. Report concrete findings ordered by severity. Tie each finding to the plan section and repository evidence that supports it.
5. Distinguish correctness gaps from optional refinements and style preferences.
6. Do not edit a plan file unless the user asked for incorporation. When incorporation is requested, apply worthwhile findings and return a complete revised plan that requires no conversation context.
