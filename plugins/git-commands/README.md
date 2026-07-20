# Git Commands

GitHub pull-request workflows for Codex.

## Skills

- `$git-commands:watch-pr` monitors required checks and bot reviews, diagnoses failures, verifies repairs locally, and pushes fixes with a repeated-failure circuit breaker.
- `$git-commands:merge-pr` verifies readiness, recommends squash or merge-commit history, merges, deletes the remote branch, and synchronizes the local base branch.

Both skills require authenticated `gh` and `git` access. They are explicit-only because they can change local branches and remote pull requests.
