# Planning

Review implementation plans with native Codex reasoning and independent external reviewers.

## Skills

- `$planning:review-plan` performs an in-thread Codex review without recursively launching `codex exec`.
- `$planning:ask-glm` sends the plan to GLM 5.2 through OpenCode.
- `$planning:ask-coderabbit` makes the plan the sole diff in a temporary repository so CodeRabbit's actual engine reviews it.
- `$planning:ask-panel` runs native Codex, GLM, and CodeRabbit passes and synthesizes their feedback.

## External reviewers

GLM requires `opencode`. CodeRabbit requires an authenticated `coderabbit` CLI:

```bash
opencode --version
coderabbit --version
coderabbit auth status --agent
```

CodeRabbit's CLI accepts Git diffs rather than arbitrary plan text. The bundled adapter snapshots the current non-ignored repository state as a temporary baseline, adds the plan as the only change, runs the review, and removes the snapshot. It never stages or commits the plan in the source repository. The plan and repository context may be sent to CodeRabbit.
