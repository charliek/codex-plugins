---
name: release
description: Cut a semantic-version release with a changelog entry, a mechanical source-version bump, two commits, an annotated tag, and a push. Use only when the user explicitly asks to release, cut or ship a release, create a release tag, bump the release version, or prepare vX.Y.Z in a repository that follows the release-workflows convention.
---

# Release

Cut a semver release for a repo that follows the release-workflows
convention. Codex owns judgment (CHANGELOG content, version choice,
gates); the repo's `scripts/release/update-version.sh` owns mechanics
(bumping every source-tree manifest); CI owns publishing (build, sign,
push assets).

For the contract this skill assumes, read
[`references/convention.md`](../../references/convention.md). For the
two-commit + tag shape and the local/CI split, the same file.

Treat a version included in the user's request as optional input. If it is
present and valid, use it without prompting again.

## Execution discipline

Release operations move refs and create tags. Don't chain destructive
steps through `&&` and pipes — `git commit … | tail -3 && git tag …`
masks the exit status of the left side, so a failed commit can still
advance to a tag pointing at the wrong SHA. Run each destructive step
as its own command, verify the expected state with the post-step check
listed below, then move on.

If any check fails, stop. Don't paper over.

## Steps

### 1. Verify branch is `main`

```bash
git branch --show-current
```

Must print `main`. If not, stop and tell the user to switch.

### 2. Verify the working tree is clean

```bash
git status --porcelain
```

Must be empty. If there are uncommitted changes, ask the user how to
proceed — usually they want to commit (or stash) before releasing.

### 3. Verify ci-success is green on HEAD

Query for the `ci-success` check specifically (server-side `check_name`
filter, so it doesn't get lost in pagination on busy repos):

```bash
gh api "repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/commits/$(git rev-parse HEAD)/check-runs?check_name=ci-success" \
  --jq '.check_runs | sort_by(.started_at) | last | {status, conclusion}'
```

Expected: `{ "status": "completed", "conclusion": "success" }`.

If `status` is missing/empty, `ci-success` hasn't run on HEAD — wait
and retry, or push if you haven't yet. If `status` is `in_progress`,
wait until it completes. If `conclusion` is anything other than
`success`, stop and tell the user — releasing against red CI is wasted
CI time.

The release workflow itself will gate on this too; this check is just
a courtesy to avoid kicking off a release that's guaranteed to fail.

### 4. Resolve version

If the user's request includes a value matching
`v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?`, use it. Otherwise prompt:
*"What version should this release be? (e.g. v0.1.0,
v1.2.0-rc1, v2.0.0-alpha-1)"*. Validate the format. Hyphens inside the
pre-release identifier are legal per semver §9 — that's why the regex
allows `-` in the suffix character class.

Check the tag doesn't already exist:

```bash
git tag -l "vX.Y.Z"
```

Must be empty. If the tag exists, ask for a different version.

### 5. Confirm the repo has adopted the convention

```bash
test -x scripts/release/update-version.sh
```

If the file is missing or not executable, **stop**. The convention requires
this script. Tell the user:

> This repo hasn't adopted the release-workflows convention — `scripts/release/update-version.sh` is missing. Run `$release-workflows:setup` to bootstrap.

Don't try to bump manifests yourself. The reason the script exists is
that agent-driven bumps are unreliable for repos with lockfiles or
multiple manifests — the missing-lockfile bump is the bug we're avoiding.

### 6. Generate the CHANGELOG entry

Find the previous release tag:

```bash
git describe --tags --abbrev=0 --match "v*" 2>/dev/null
```

Collect commits since that tag:

```bash
git log <previous-tag>..HEAD --oneline
```

If no previous tag exists, use all commits.

Read the relevant commit subjects + PR descriptions (read PRs via
`gh pr view <num>` when a commit references one). Group by type:
features, fixes, docs, tests, release process. Match the style of the
repo's existing CHANGELOG.md if it has prior entries — preserve the
heading shape (`## vX.Y.Z` or `## vX.Y.Z — YYYY-MM-DD`), the section
ordering, the bullet style.

Add the new entry at the top, after the file header. Keep it tight: the
maintainer will read this when something breaks.

### 7. Commit the changelog

Stage and commit. Use inline `-m` flags — never `git commit -F <file>`
(a stale temp file from a previous session can silently produce the
wrong message; inline is unambiguous):

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): vX.Y.Z entry" \
           -m "Co-Authored-By: Codex <noreply@openai.com>"
```

Always use the Codex co-author trailer shown above so release commit
attribution is consistent.

Run that commit as its own command. Don't chain it through `| tail` and
`&&` — the pipe masks the commit's exit status.

Verify:

```bash
if [ "$(git log -1 --pretty=%s)" = "docs(changelog): vX.Y.Z entry" ]; then
  echo "OK"
else
  echo "STOP: last commit subject is not the changelog commit" >&2
  exit 1
fi
```

If verification fails (likely cause: nothing was staged, or a previous
step failed silently), stop and reconcile. Don't proceed to the bump.

### 8. Run update-version.sh

```bash
./scripts/release/update-version.sh X.Y.Z
```

Note: the script takes the version *without* the `v` prefix.

The script prints one line per file it modified. It does not `git add` —
that's the next step.

If the script fails, stop. Common causes: the script's semver validation
rejected the version; the lockfile re-resolve hit a problem
(`cargo update` couldn't reach offline cache); a sed pattern didn't
match (someone reformatted the manifest in a way the script didn't
expect). Each of these wants a real fix, not a workaround.

### 9. Commit the version bump

Stage what the script modified — every modified path, no `-A` (so
incidental working-tree dirt doesn't get swept in):

```bash
git add -u
```

`git add -u` updates the index to match the working tree for
already-tracked files. Since `update-version.sh` only mutates tracked
manifests (the convention), this captures exactly what changed.

Then commit (same `Co-Authored-By` guidance as step 7):

```bash
git commit -m "chore(version): bump to X.Y.Z" \
           -m "Co-Authored-By: Codex <noreply@openai.com>"
```

Verify with proper exit status — the check must `exit 1` on mismatch
so a downstream `set -e` shell catches it, not just print:

```bash
if [ "$(git log -1 --pretty=%s)" = "chore(version): bump to X.Y.Z" ]; then
  echo "OK"
else
  echo "STOP: last commit subject is not the version-bump commit" >&2
  exit 1
fi
```

### 10. Tag (annotated) on the version commit

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
```

Verify the tag points at the version commit (which is HEAD) — proper
exit status, not just an echo:

```bash
if [ "$(git rev-list -n1 vX.Y.Z)" = "$(git rev-parse HEAD)" ]; then
  echo "tag SHA OK"
else
  echo "tag does NOT point at HEAD — STOP" >&2
  exit 1
fi
```

If verification fails, delete the tag (`git tag -d vX.Y.Z`) and figure
out what happened locally before pushing.

### 11. Push commit and tag together

```bash
git push --follow-tags
```

On a repo whose `main` ruleset has both the admin role and the
release-bot App in `bypass_actors` (see
[`references/github-app.md`](../../references/github-app.md)), this push
should print:

```
remote: Bypassed rule violations for refs/heads/main:
remote:   - Required status check "ci-success" is expected.
```

…and succeed. If it's rejected with `protected branch hook declined`,
the admin role isn't in the ruleset's bypass list. Fix the bypass and
retry (the local commits + tag are already in place).

### 12. Confirm

Get the repo URL:

```bash
gh repo view --json url --jq '.url'
```

Print:

```
Release tag: <repo-url>/releases/tag/vX.Y.Z
Watch:       <repo-url>/actions
```

Tell the user the release workflow has been triggered and where to watch.

## Snapshot / dev versioning

Not handled by this skill. If a repo wants post-release snapshot bumping
(Maven-style `X.Y.(Z+1)-SNAPSHOT`), it adds the logic to its own
`update-version.sh` as a post-bump sub-step. The skill respects whatever
the script does and commits the result; it doesn't introduce a third
commit for snapshot bumping.

If you want build-time version identity beyond "last released" (so a
CLI's `--version` shows commits past the latest tag), derive it from
`git describe --tags --dirty` at build time. That's not a release-time
concern.

## Error handling reference

| Symptom | Likely cause | Fix |
|---|---|---|
| CI hasn't completed on HEAD | Recent push, CI still running | Wait, re-check |
| Latest CI on HEAD is `failure` | Something is broken | Fix it, push, re-check |
| Not on `main` | Working on a feature branch | Switch branches; or maybe you meant to merge a PR first |
| Uncommitted changes | Work in progress | Commit or stash; tell the user before either |
| Tag already exists | Released before; or aborted release that pushed the tag but not main | Pick a fresh patch tag (don't force-update an existing one). If you must rewrite a just-pushed tag — e.g. CI revealed a packaging bug and no artifact has shipped externally — cancel any in-flight workflow runs first, delete the tag with `git push origin :refs/tags/vX.Y.Z`, reset main, redo the commits and tag, and push with `git push --force-with-lease` (not `--force`) so the rewrite refuses if anyone else pushed in the meantime. |
| `update-version.sh` missing | Convention not adopted | `$release-workflows:setup` |
| `update-version.sh` failed | See its stderr | Most are real bugs (lockfile out of sync, manifest reformatted) |
| Push rejected: "Required status check ci-success is expected" | Pusher not in ruleset bypass | See [`references/github-app.md`](../../references/github-app.md) Phase 4 |
| Push rejected: "non-fast-forward" | Local main behind origin | `git pull --rebase`, redo the commits + tag (or push the tag separately after pulling) |

## What this skill does NOT do

- Bump version files itself. That's `update-version.sh`'s job.
- Push the tag separately from the commit. `--follow-tags` is the
  single-shot. Pushing the tag alone strands main behind a tag, which
  triggers CI to release a SHA that isn't on main — a confusing state.
- Update post-build assets (signed appcasts, Homebrew SHA256s, etc.).
  Those happen in CI after the build, owned by `release.yml`.
- Auto-merge anything. Releases are produced from the current state of
  main; if a PR isn't merged yet, the release won't include it.
