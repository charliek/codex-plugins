---
name: merge-pr
description: Verify and merge a GitHub pull request, choose an appropriate merge strategy, delete the remote branch, and synchronize local branches. Use only when the user explicitly asks to merge or land a PR.
---

# Merge a pull request

1. Load applicable repository instructions and resolve the PR from an explicit number or the current branch using `gh pr view` with number, state, draft status, refs, commits, title, and URL.
2. Stop when the PR is missing, draft, closed, already merged, or conflicted.
3. Run `gh pr checks <number>` and require every required check to pass. Ignore purely informational bot-review checks. If checks are pending or failed, stop and recommend `$git-commands:watch-pr`.
4. Choose the merge strategy:
   - For one commit, default to a merge commit.
   - For multiple commits, show their messages and recommend squash when they are primarily fixups, debug iterations, review nits, or generic work-in-progress commits.
   - Recommend a merge commit when commits are meaningful, atomic changes with distinct purposes.
   - Ask the user to confirm squash versus merge commit, putting the recommendation first.
5. Run `gh pr merge <number> --squash --delete-branch` or `--merge --delete-branch` according to the confirmed choice.
6. After GitHub confirms the merge, switch to the base branch, pull it with a fast-forward-safe operation, and delete the local head branch when it still exists and is fully merged.
7. Report the PR title, URL, strategy, resulting base branch, and cleanup status.

Do not bypass checks, use an unrequested rebase merge, force-delete an unmerged local branch, or claim success until GitHub reports the PR merged.
