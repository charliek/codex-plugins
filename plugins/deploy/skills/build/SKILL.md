---
name: build
description: Create a date-based release that updates the changelog, commits, tags, and pushes to trigger Docker image builds and site deployment. Use only when the user explicitly asks to deploy, create a deployment build, or cut a date-based deployment release.
---

# Create a deployment build

Create a new deployment release by generating a changelog entry, committing it, and pushing a date-based version tag.
This triggers the release workflow which builds and pushes Docker images.

**Execution discipline for release steps.** Release operations move
refs and create tags — don't chain them through `&&` with piped output
(e.g. `git commit -m ... | tail -3 && git tag ...`). Piping masks the
exit status of the left side, so a failed commit can still advance to
the tag step and produce a tag pointing at the wrong SHA. Run each
destructive step on its own, verify the expected state with the
post-step check listed below, then move on.

## Steps

1. **Check branch**: Ensure we're on the main branch
   - Run `git branch --show-current`
   - If not on main, stop and inform the user

2. **Check working tree**: Ensure there are no uncommitted changes
   - Run `git status --porcelain`
   - If there are changes, warn the user and ask how to proceed

3. **Verify CI status**: Check that CI has passed for the current commit
   - Run `gh run list --commit $(git rev-parse HEAD) --status completed --json conclusion,name`
   - All workflows should have conclusion "success"
   - If CI hasn't completed or failed, stop and inform the user

4. **Determine version tag**: Generate a date-based version
   - Format: `vYYYY.MM.DD` (e.g., `v2026.03.22`)
   - Check existing tags for today: `git tag -l "v$(date +%Y.%m.%d)*"`
   - If no tags exist for today, use `vYYYY.MM.DD`
   - If tags exist, find the highest suffix and increment: `v2026.03.22` → `v2026.03.22.2`, `v2026.03.22.2` → `v2026.03.22.3`, etc.
   - Show the proposed tag to the user for confirmation

5. **Generate changelog entry**: Summarize changes since last release
   - Find the previous release tag: `git describe --tags --abbrev=0 --match "v*" 2>/dev/null`
   - Get commits since that tag: `git log <previous-tag>..HEAD --oneline`
   - If no previous tag exists, get all commits: `git log --oneline`
   - Write a concise summary of the changes (group by type: features, fixes, updates)

6. **Update CHANGELOG.md**: Prepend the new entry
   - Read the current CHANGELOG.md (create if it doesn't exist)
   - Add a new section at the top (after the header) with the version and changes
   - Format:
     ```
     ## vYYYY.MM.DD

     - Change 1
     - Change 2
     ```

7. **Commit the changelog**: Create a release commit
   - Stage CHANGELOG.md: `git add CHANGELOG.md`
   - Commit with inline `-m` flags — do **not** use `git commit -F <file>`.
     A stale temp file left over from a previous session can silently
     produce a wrong commit message; inline avoids the whole class of
     bug:
     ```bash
     git commit -m "Release vYYYY.MM.DD" \
       -m "Co-Authored-By: Codex <noreply@openai.com>"
     ```
   - Run this as its own command. Don't chain it with `&&` through
     `| tail -N` — the pipe masks the commit's exit status.
   - **Verify the commit landed before tagging:**
     ```bash
     git log -1 --pretty=%s
     ```
     This must print `Release vYYYY.MM.DD`. If it doesn't, stop and
     reconcile (likely cause: nothing was staged, or a previous step
     failed silently). Don't tag the wrong commit.

8. **Create and push tag**: Trigger the release workflow
   - Create an **annotated** tag so `git push --follow-tags` actually
     pushes it (lightweight tags are skipped by `--follow-tags`):
     ```bash
     git tag -a vYYYY.MM.DD -m "vYYYY.MM.DD"
     ```
   - **Verify the tag points at the Release commit you just made:**
     ```bash
     [ "$(git rev-list -n1 vYYYY.MM.DD)" = "$(git rev-parse HEAD)" ] \
       && echo "tag SHA OK" || echo "tag does NOT point at HEAD — STOP"
     ```
     If the tag doesn't point at HEAD, fix locally before pushing.
   - Push commit and tag together:
     ```bash
     git push --follow-tags
     ```

9. **Confirm success**: Show the release URL
   - Get the repo URL: `gh repo view --json url --jq '.url'`
   - Display: `<repo-url>/releases/tag/vYYYY.MM.DD`
   - Inform user that the release workflow has been triggered
   - They can monitor it at the Actions tab

## Error Handling

- If CI hasn't passed, inform the user and suggest running `$deploy:build` again after CI completes
- If not on main branch, inform the user to switch branches
- If there are uncommitted changes, warn the user and ask how to proceed
- If push fails, provide troubleshooting steps

## Prerequisites

See `references/setup.md` for required GitHub Actions workflow configuration.
