# Cursor

Delegate substantial tasks and code reviews to the Cursor agent CLI.

## Skills

- `$cursor:rescue` delegates an implementation, investigation, or follow-up task.
- `$cursor:review` reviews working-tree or branch changes in read-only mode.
- `$cursor:adversarial-review` challenges design choices, assumptions, and failure modes.
- `$cursor:setup` reports installation, authentication, version, and model readiness.

The default model is `cursor-grok-4.5-high`. Override it explicitly in the request when another installed model is preferred.

## Setup

Install the CLI from <https://cursor.com/cli>, then authenticate:

```bash
agent login
agent status
agent --list-models
```

Rescue runs are write-capable only after explicit invocation. Both review skills always use Cursor's plan/read-only mode and stop before applying fixes.
