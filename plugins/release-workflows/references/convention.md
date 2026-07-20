# The release-workflows convention

This file is the contract that both `release-workflows:release` and
`release-workflows:setup` enforce. Everything else in this plugin —
templates, walkthroughs, error messages — refers back here.

A repo follows the convention when it has the four files below, the two
secrets, and a branch protection ruleset wired the way described. The
`setup` skill bootstraps these; the `release` skill assumes they're in
place.

## Required files

| Path | Owns |
|---|---|
| `scripts/release/update-version.sh` | Mechanical bump of every source-tree version manifest (and its lockfile, if any) |
| `scripts/release/` (the directory) | Also the conventional home for in-repo *templates* used by CI post-build jobs — e.g. a Homebrew formula template (`<name>.rb.tmpl`) consumed by `job-homebrew-tap.yml`. |
| `RELEASING.md` at repo root | Human + Codex readable policy doc — what's special about this repo, what's optional vs required |
| `.github/workflows/release.yml` | Tag-triggered build + publish + (where needed) bot-driven post-build asset updates |
| `.github/workflows/sanity-check-app.yml` | Manually-triggered verification that the release-bot App is wired into every repo this release touches (running repo + cross-repo push targets). Optional but recommended. |

## Required configuration

| Item | Where set |
|---|---|
| `RELEASE_BOT_CLIENT_ID` secret | Repo settings → Secrets and variables → Actions |
| `RELEASE_BOT_APP_KEY` secret | Same. Contents are the App's `.pem` private key |
| Branch protection ruleset on `main` | Repo settings → Rules → Rulesets |

The ruleset replaces classic branch protection. It requires `ci-success`
and lists two bypass actors: the release-bot App (so CI can push
post-build asset updates like signed appcasts), and the admin role (so
the maintainer's `$release-workflows:release` push lands without
waiting for ci-success on the new commits, which haven't been built yet
at the moment of push). Walkthrough: [`github-app.md`](github-app.md).

## What goes in `update-version.sh` and what doesn't

The dividing line is whether the new value of a file can be computed from
just the version string, or whether it depends on a built artifact.

**In the script** — anything from the version string alone:

- `Cargo.toml` workspace.version + `Cargo.lock` regeneration
- `pyproject.toml` `[project].version`
- `.claude-plugin/plugin.json` `version`
- `package.json` `version` + `package-lock.json` regeneration
- `build.gradle` / `build.gradle.kts` `version`
- A `VERSION` constant file embedded in source

**Not in the script — these belong in CI after the build**:

- Sparkle appcast `<sparkle:edSignature>` and `length="<bytes>"` (needs
  the signed DMG bytes)
- Homebrew formula `sha256` (needs the released tarball's hash)
- Docker image digest references (need the pushed manifest's sha256)

The test: *can I produce the new value of this file knowing only
`X.Y.Z`?* If yes, it's `update-version.sh`'s job. If no, it's a CI job
that runs after the build.

This split exists because forcing every release to compute build-output
hashes locally would require running the full build chain on the
maintainer's laptop. By doing those updates in CI as a follow-on
bot-driven step, the local release stays portable.

## Two-commit shape per release

Every release produces exactly two commits and one annotated tag:

```
<previous main HEAD>
│
├── docs(changelog): vX.Y.Z entry        ← CHANGELOG.md only
│
└── chore(version): bump to X.Y.Z        ← whatever update-version.sh
    ↑                                       modified (Cargo.toml, lockfile, …)
    tag vX.Y.Z (annotated) points here
```

Why two commits not one:
- Each commit has a single concern, so `git log --oneline` reads cleanly
  and `git blame` resolves to the right intent
- A reverter (rare but real) can roll back only one piece if needed
- The tag points at the version commit, which means CI's "tag matches
  manifest" assertion compares against the right tree

If a future repo needs the combined-commit shape, override in that repo's
`RELEASING.md`. The skill respects it.

## Snapshot / dev-version bumping

Not handled by this plugin. Most ecosystems Charlie's repos live in
(Rust, Python, Claude Code plugins) don't have a snapshot convention —
main between releases shows the last released version.

If a specific repo wants Maven-style `X.Y.(Z+1)-SNAPSHOT` bumping after
release, add it to that repo's `update-version.sh` as a post-bump
sub-step, and document the choice in `RELEASING.md`. The release skill
won't get in the way; the repo owns the policy.

If a build identity beyond "last released" is needed (e.g., a CLI's
`--version` should show whether the build is past the latest tag),
derive it at build time from `git describe --tags --dirty` rather than
snapshotting the source tree.

## Why the workflow has a `finalize-release` job

`gh release create <tag> …` is supposed to create a non-draft release tagged at
`<tag>` — and usually does. Occasionally, when the just-pushed tag isn't yet
visible to the Release API at the moment the `create-release` job runs, gh
stores the release as a tag-less draft instead, with a `releases/tag/untagged-<hash>`
URL slug. Asset uploads in that state attach to the draft, and the public
`releases/download/<tag>/<asset>` URL serves 404 — even though
`gh release view <tag>` shows the assets present. Any post-build job that curls
the public asset URLs (homebrew tap, etc.) then fails.

The `finalize-release` job in `references/workflows/job-finalize-release.yml`
runs after every build/upload job and explicitly flips the release out of
draft (`gh release edit <tag> --draft=false --latest`). Subsequent publish
jobs (homebrew, sparkle, apt-dispatch) should `needs: finalize-release`
rather than `needs: build`. The flip is idempotent — no harm if the release
was already published.

Even with `finalize-release` in place, the public download URL has a short
CDN propagation delay (typically 5-20s) after a release is first published.
`job-homebrew-tap.yml` retries with backoff to cover that window; other
post-publish jobs that download assets from the public URL should do the same.

## The release flow end to end

1. **Codex (`$release-workflows:release vX.Y.Z`)** — local:
   - Verify branch + clean tree + ci-success green on HEAD
   - Draft a CHANGELOG entry from `git log <prev-tag>..HEAD`
   - Commit as `docs(changelog): vX.Y.Z entry`
   - Run `scripts/release/update-version.sh X.Y.Z`
   - Commit what it modified as `chore(version): bump to X.Y.Z`
   - Tag `vX.Y.Z` annotated on the version commit
   - `git push --follow-tags` (admin bypasses ruleset's `ci-success` rule)

2. **CI (`release.yml`)** — tag-triggered:
   - `version-check` asserts the tag matches the manifest's version
   - `ci-gate` polls `ci-success` on the tagged commit (the CI for the
     just-pushed commit runs in parallel; release.yml waits for it)
   - `create-release` extracts this version's CHANGELOG section and
     creates the GitHub Release
   - Repo-specific build jobs produce artifacts and upload them to the
     Release
   - `finalize-release` flips the release out of draft (if any) and marks
     it as `latest`, so the public asset URLs are reachable
   - Post-build jobs publish derived assets (sign Sparkle appcast and
     bot-push; dispatch apt receivers; etc.) — these `needs: finalize-release`

The maintainer runs step 1; everything else is automated.

## Secret naming — generic, not account-specific

All secrets this plugin references are named generically so the
templates work for anyone, not just one account. `RELEASE_BOT_CLIENT_ID`
and `RELEASE_BOT_APP_KEY` refer to *your* release-bot App, whichever
one you set up. The App itself isn't part of this plugin; you create it
once per account and install it on each repo that opts in (see
[`github-app.md`](github-app.md)).

## When a repo has not yet adopted the convention

`release-workflows:release` refuses to run on repos that haven't
adopted. It checks for `scripts/release/update-version.sh` and stops
with an error pointing at `release-workflows:setup` if the script is
missing. This is intentional: making the skill try to guess what to
bump leads to the kind of incomplete bump that happened in roost's
v0.0.5 (the lockfile wasn't bumped because the agent didn't know to). The
script is the only path; if it's absent, fix that first.

The legacy `release` plugin that once served as the migration fallback
has been retired; `release-workflows` is now the only supported path.
