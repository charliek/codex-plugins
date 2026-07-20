# release-workflows

Convention-based release workflows for Codex.

## Skills

- `$release-workflows:release vX.Y.Z` verifies `main`, a clean working tree, and `ci-success`; writes and commits a changelog entry; runs the repository's mechanical version bumper; creates a second version commit and annotated tag; and pushes them together.
- `$release-workflows:setup` interactively bootstraps or refreshes the convention without auto-committing. It covers version bumping, release workflows, a release-bot GitHub App, rulesets, release documentation, and optional artifact pipelines.

The setup skill preserves support for repositories that distribute Claude Code plugins through `.claude-plugin/plugin.json`. Generic release bumping for `.codex-plugin/plugin.json` is intentionally deferred until a target repository defines whether one plugin, several independently versioned plugins, or a repository-wide version is the release unit.

## Included references

The plugin ships the convention contract, GitHub App and branch-protection walkthrough, `RELEASING.md` template, Cargo workspace version bumper, composable GitHub Actions job templates, Sparkle appcast guidance, apt and Homebrew publishing jobs, release finalization, and macOS signing/notarization templates.

Both skills require authenticated `git` and GitHub CLI access. Release is explicit-only; setup shows proposed file content or diffs and asks before sensitive GitHub changes.
