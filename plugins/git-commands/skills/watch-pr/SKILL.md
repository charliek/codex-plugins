---
name: watch-pr
description: Monitor a GitHub pull request's CI checks and bot reviews, diagnose failures, verify and push fixes, and stop when the PR is ready or needs user guidance. Use only when the user explicitly asks to watch, babysit, repair, or follow a PR through CI.
---

# Watch a pull request

1. Load applicable repository instructions and confirm `git` and `gh` access.
2. Resolve the PR from an explicit number or the current branch with `gh pr view`. Stop for a missing, closed, or merged PR.
3. Inspect required checks with `gh pr checks <number>`. Treat bot-review checks such as CodeRabbit as informational unless branch protection marks them required.
4. Monitor incomplete checks with the available recurring wait mechanism or bounded polling. Do not block silently for more than 60 seconds; provide concise status updates during long waits.
5. When a required check fails:
   - Resolve its run ID and read failed logs with `gh run view <id> --log-failed`.
   - Inspect the corresponding CI configuration and repository commands.
   - Determine the smallest justified fix without hardcoding a language or job name.
   - Apply the fix, run equivalent local validation, commit, and push when the user's watch request authorizes repair.
   - Re-enter monitoring after the push.
   - Stop and request guidance if the same check fails again after one fix attempt.
6. Detect bot-review results from checks, reviews, comments, and review threads. Wait up to roughly ten minutes when a detected review is still pending.
7. Validate each review comment against the code. Fix material correctness, security, and maintainability issues; skip unsupported or style-only feedback. Revalidate, commit, push, and re-monitor after changes.
8. Finish with check status, fixes made, feedback addressed or skipped, remaining risk, and a suggestion to use `$git-commands:merge-pr` when everything is ready.

Never expose authentication data from logs. Do not force-push, bypass required checks, or retry the same failed repair indefinitely.
