# deploy

Date-based deployment releases for Codex.

## Skills

- `$deploy:build` verifies the repository is ready, proposes a `vYYYY.MM.DD[.N]` tag, updates `CHANGELOG.md`, commits, creates an annotated tag, and pushes it to trigger the repository's release workflow.

The skill requires authenticated `git` and GitHub CLI access. The target repository must have a tag-triggered GitHub Actions workflow that builds and publishes its Docker image; the bundled setup reference contains a starting example.

Release actions are explicit-only and stop on a non-`main` branch, working-tree changes, unsuccessful CI, failed commits, or tag verification errors.
