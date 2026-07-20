# codex-plugins

A public Codex plugin marketplace for reusable development workflows.

## Plugins

| Plugin | Skills | Purpose |
| --- | --- | --- |
| [planning](plugins/planning/) | `review-plan`, `ask-glm`, `ask-coderabbit`, `ask-panel` | Review implementation plans natively and with independent external reviewers. |
| [cursor](plugins/cursor/) | `rescue`, `review`, `adversarial-review`, `setup` | Delegate tasks and read-only reviews to the Cursor agent CLI. |
| [git-commands](plugins/git-commands/) | `watch-pr`, `merge-pr` | Monitor, repair, and safely merge GitHub pull requests. |
| [deploy](plugins/deploy/) | `build` | Create date-based releases that trigger Docker builds and deployments. |
| [release-workflows](plugins/release-workflows/) | `release`, `setup` | Bootstrap release infrastructure and cut convention-based semantic-version releases. |

Installed plugin skills are namespaced by their plugin, for example `$planning:ask-panel`, `$cursor:review`, `$deploy:build`, and `$release-workflows:release`.

## Install from GitHub

```bash
codex plugin marketplace add charliek/codex-plugins
codex plugin add planning@codex-plugins
codex plugin add cursor@codex-plugins
codex plugin add git-commands@codex-plugins
codex plugin add deploy@codex-plugins
codex plugin add release-workflows@codex-plugins
```

Start a new Codex thread after installation so the new skills are loaded.

## Local development

From the repository root:

```bash
codex plugin marketplace add .
codex plugin add planning@codex-plugins
codex plugin add cursor@codex-plugins
codex plugin add git-commands@codex-plugins
codex plugin add deploy@codex-plugins
codex plugin add release-workflows@codex-plugins
```

The marketplace manifest lives at [`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json). Plugin source directories remain under `plugins/`.

## Prerequisites

- Planning's GLM review requires [OpenCode](https://opencode.ai/) configured for `zai-coding-plan/glm-5.2`.
- Planning's CodeRabbit review requires the [CodeRabbit CLI](https://docs.coderabbit.ai/cli) and `coderabbit auth login --agent`.
- Cursor workflows require the [Cursor agent CLI](https://cursor.com/cli) and `agent login`.
- Git commands require authenticated `git` and [GitHub CLI](https://cli.github.com/) access.
- Deploy requires authenticated `git` and GitHub CLI access plus a target repository with a tag-triggered Docker release workflow.
- Release workflows require authenticated `git` and GitHub CLI access. Setup additionally guides GitHub App, secret, and ruleset configuration.

## Development validation

```bash
python3 -m unittest discover -s tests -v
PLUGIN_CREATOR_DIR="${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator"
python3 "$PLUGIN_CREATOR_DIR/scripts/validate_plugin.py" plugins/planning
python3 "$PLUGIN_CREATOR_DIR/scripts/validate_plugin.py" plugins/cursor
python3 "$PLUGIN_CREATOR_DIR/scripts/validate_plugin.py" plugins/git-commands
python3 "$PLUGIN_CREATOR_DIR/scripts/validate_plugin.py" plugins/deploy
python3 "$PLUGIN_CREATOR_DIR/scripts/validate_plugin.py" plugins/release-workflows
```

The validators are part of Codex's bundled creator skills; installed plugins do not depend on them.

## License

[MIT](LICENSE)
