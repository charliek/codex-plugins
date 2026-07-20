---
name: setup
description: Bootstrap or migrate a repository onto the release-workflows convention, including its version bumper, release workflow, GitHub App, secrets, protection ruleset, release documentation, and artifact pipelines. Use only when the user explicitly asks to set up or migrate release-workflows, add a release artifact pipeline, or learn how to release a repository with this convention.
---

# Release-Workflows Setup

Bootstrap a repo onto the convention defined in
[`references/convention.md`](../../references/convention.md). Conversational:
survey what's there, ask what the repo needs, propose templates, write
files, gate on user review at every step.

The skill never auto-commits. Drafts files; the user reads, edits if
needed, and commits.

## How to drive this skill

The skill walks 8 phases. Each phase has a single question (or set of
questions) for the user, a concrete output, and a "DONE / PARTIAL /
NEEDS DOING" status used for idempotency. If the user re-runs the
skill on a partially-set-up repo, survey first, mark each phase, skip
DONE, offer to refresh PARTIAL.

**Operate in the user's current working directory.** Don't reach for
sibling repos unless the user explicitly says "use ../<name> as a
model". When they do, read that repo's files for reference only — don't
copy verbatim; the new repo always has its own shape.

**Show diffs before writing.** For every file the skill produces, show
the user the proposed content before writing. If the file already
exists, show a diff (`diff -u existing.txt proposed.txt`) and ask
before replacing.

## Phase 1 — Survey

Detect what's in the repo:

```bash
# Manifest files
ls Cargo.toml pyproject.toml package.json .claude-plugin/plugin.json \
   .codex-plugin/plugin.json \
   build.gradle build.gradle.kts go.mod 2>/dev/null

# Existing release infrastructure
ls .github/workflows/release.yml scripts/release/update-version.sh \
   RELEASING.md CHANGELOG.md 2>/dev/null

# Existing branch protection / ruleset state
gh api "/repos/$(gh repo view --json owner,name --jq '"\(.owner.login)/\(.name)"')/branches/main/protection" 2>&1 | head -3
gh api "/repos/$(gh repo view --json owner,name --jq '"\(.owner.login)/\(.name)"')/rulesets" --jq '[.[] | {id, name, enforcement}]'

# App installed?
gh secret list -R "$(gh repo view --json owner,name --jq '"\(.owner.login)/\(.name)"')" | grep RELEASE_BOT_ || echo "App secrets not set"
```

Report what you found in a compact table. Decide for each phase:

| Phase | Status | Why |
|---|---|---|
| 2 — pipelines chosen | NEEDS DOING / DONE / PARTIAL | (based on existing release.yml jobs) |
| 3 — App + secrets + protection | NEEDS DOING / DONE / PARTIAL | (secrets present + ruleset shape) |
| 4 — update-version.sh | NEEDS DOING / DONE | (file exists + executable) |
| 5 — release.yml | NEEDS DOING / PARTIAL / DONE | (file exists + has the expected job shape) |
| 6 — RELEASING.md | NEEDS DOING / DONE | (file exists) |
| 7 — sanity-check-app.yml | NEEDS DOING / DONE | (file exists) |

For DONE phases, ask: "Looks like X is already in place. Skip, or
should I refresh it against the latest template?" Skip by default.

## Phase 2 — Choose artifact pipelines

Ask the user which of these the repo ships:

- GitHub Release with binary assets (almost always yes)
- Sparkle appcast (Mac auto-update via EdDSA-signed feed)
- Mac Developer ID signing + notarization (Gatekeeper-clean DMG) — `references/mac-signing/` (woven into the mac build job, not a standalone job)
- Homebrew tap (formula update in another repo) — `references/workflows/job-homebrew-tap.yml` (requires `references/workflows/job-finalize-release.yml` between build and homebrew — see that file's header)
- apt repo (repository_dispatch to a receiver repo)
- Docker images (push to a registry) — `references/workflows/job-docker-push.yml` not yet shipped
- Claude Code plugin distribution
- PyPI / crates.io / npm publish

Each YES activates a sub-walkthrough in phases 4–5.

If the user is unsure, ask them to point at a similar repo or describe
how releases work today. Don't guess.

For pipelines whose templates don't yet ship in this plugin (Docker),
tell the user up-front: *"this template hasn't shipped yet — we can
either author it together as part of this setup (and contribute back to
the plugin), or leave a stub in `release.yml` for now and revisit."*

The Homebrew-tap and apt-dispatch templates use the release-bot App as a
cross-repo credential (no per-pipeline PAT): the running repo mints a token
scoped to the tap / receiver repo via `actions/create-github-app-token`. The App
must be installed on those repos too. See `references/github-app.md`, "Cross-repo
bot pushes". (The legacy `HOMEBREW_TAP_TOKEN` / `APT_DISPATCH_TOKEN` PATs are
documented inline in each template as the alternative.)

Mac Developer ID signing + notarization is **not** a standalone job — it's a job
`env:` block plus three steps woven into the mac build job (cert import before
the bundle; notarize + staple after the DMG, before the upload/appcast-sign).
See `references/mac-signing/` (README + `notarize.sh.template` + `build-steps.yml`).
It's inert until all six Apple secrets land (gated together as `CAN_NOTARIZE`,
all-or-nothing — a signed-but-un-notarized DMG is still Gatekeeper-blocked), so
it's safe to add ahead of provisioning — the DMG ships ad-hoc-signed until then.
One Developer ID Application cert signs all of a team's apps, so the cert + Team
ID are shared across repos; only the per-app `<APP>_DEVELOPER_ID_IDENTITY` secret
name differs.

## Phase 3 — GitHub App + secrets + branch protection

Read [`references/github-app.md`](../../references/github-app.md). Walk
the user through each phase **out loud**, showing the exact commands
and confirming results.

| Step | What to do |
|---|---|
| 3.1 — App exists? | Ask: "Have you created a release-bot App on your GitHub account?" If no, walk through `github-app.md` Phase 1 with them. If yes, confirm the App name and ID. |
| 3.2 — App installed on this repo? | `gh api /installation/repositories` from a token that owns the App, or `gh secret list -R <repo> \| grep RELEASE_BOT_` for indirect signal. If not installed, walk through Phase 2 of `github-app.md`. |
| 3.3 — Secrets set? | `gh secret list -R <repo>` must show `RELEASE_BOT_CLIENT_ID` and `RELEASE_BOT_APP_KEY`. If not, walk through Phase 3 of `github-app.md` together — the user runs the commands; don't run `gh secret set` for them without explicit confirmation. |
| 3.4 — Branch protection migrated to a ruleset? | Inspect `gh api /repos/<r>/branches/main/protection` (classic) and `gh api /repos/<r>/rulesets`. If still on classic, walk through Phase 4 of `github-app.md`. Show the JSON before posting. **The maintainer runs the `gh api` calls themselves**, not the skill. |

When you're done, drop in
[`references/workflows/sanity-check-app.yml.template`](../../references/workflows/sanity-check-app.yml.template)
to `.github/workflows/sanity-check-app.yml` and tell the user how to
run it from the Actions UI. The output should print the repo name, an
installation count of at least 1, and a token identity ending in
`[bot]`.

## Phase 4 — Draft scripts/release/update-version.sh

Picker:

```
Cargo.toml present (and is a workspace)?  → references/update-version/cargo-workspace.sh
.claude-plugin/plugin.json present?       → references/update-version/plugin-json.sh (not yet shipped — author one)
.codex-plugin/plugin.json present?        → deferred; identify the repo's release unit before authoring a bumper
pyproject.toml as canonical version?      → references/update-version/pyproject.sh (not yet shipped — author one)
build.gradle present?                     → references/update-version/gradle.sh (not yet shipped — author one)
Multiple of the above?                    → compose by concatenating the relevant sections
```

Codex plugin manifest bumping is intentionally deferred in this version of
the plugin. A repository may release one plugin, independently version several
plugins, or share one version across a marketplace. If a
`.codex-plugin/plugin.json` is present, report it during the survey but do not
guess which manifests move together or write a generic bumper. Ask the user to
define that repository's release unit and leave the phase PARTIAL until a
future template supports the chosen policy.

For shipped templates, read the relevant file from
`references/update-version/`. Substitute any paths the template comments
out as repo-specific. Show the proposed script to the user. Write to
`scripts/release/update-version.sh`. Mark executable. Don't commit.

**Cargo-specific check**: if `Cargo.toml` uses the column-aligned style
(`version       = "X.Y.Z"` with extra spaces before `=`, common in
hand-formatted workspace manifests), the cargo-workspace template needs
a one-line edit to preserve that style. Before showing the script, peek
at `Cargo.toml`:

```bash
grep -E '^version' Cargo.toml | head -1
```

If the line has extra spaces between `version` and `=`, edit the sed
replacement and the verification grep to match. See
[`references/update-version/cargo-workspace.sh`](../../references/update-version/cargo-workspace.sh)
header's "COLUMN-ALIGNMENT" warning for the exact change. If you ship
the template as-is on a column-aligned repo, the first release's diff
will reflow the version line (functional but noisy).

**Special case — Go modules**: Go binaries typically derive their
version from a build-time ldflag (`-X .../version.Version={{.Version}}`
in GoReleaser, or hand-rolled equivalent), NOT from a source-tree
manifest. For Go repos with no in-source version constant,
`update-version.sh` can be a near-no-op: simply
`echo "Go module: version comes from the tag at build time; nothing to bump."`
and exit 0. The convention still calls for the file to exist — but it
just acknowledges that fact. Add a documenting header explaining the
choice.

For templates not yet shipped, write one following the contract in
[`references/update-version/README.md`](../../references/update-version/README.md):

- one arg, the semver string with no `v` prefix
- idempotent (re-running with the same version is a no-op)
- no network (lockfile regeneration uses `--offline` / equivalent)
- verifies its own work
- quiet on success
- doesn't `git add` (release skill does)

Show the user what you wrote. After confirming it works locally
(`./scripts/release/update-version.sh 0.0.0-test` followed by
`git diff` and `git checkout -- .`), suggest contributing the template
back to the plugin in a follow-up PR. Don't do that contribution as
part of this setup walkthrough — keep the scope tight.

## Phase 5 — Draft .github/workflows/release.yml

Compose from `references/workflows/`. Start with
[`release.yml.example`](../../references/workflows/release.yml.example) as
the skeleton. For each Phase 2 YES, paste the corresponding job's full
body inline (not `uses:` — the templates aren't reusable workflows).
Replace every angle-bracket placeholder in the pasted blocks with the
repo's concrete values from Phase 1's detection (manifest path,
extraction regex, DMG pattern, etc.).

Show the assembled `release.yml` to the user. If they already have a
`release.yml` (Phase 1 said PARTIAL), produce a diff and walk through
each hunk — explain what's being added, what's being removed (if the
old shape conflicts), what stays the same.

Write to `.github/workflows/release.yml`. Don't commit.

YAML syntax validation is intentionally left to CI: a local check that
catches outright syntax errors but not the actual class of bugs (job
indentation mistakes, missing required fields, invalid action refs) is
worse than no check, because it gives false confidence. CI will run on
the next push and flag any real issue. If you want a stronger
gate-before-commit, point the user at `actionlint` (which understands
the GitHub Actions schema, not just YAML); they can install it
separately.

## Phase 6 — Draft RELEASING.md

Read [`references/releasing-md.template.md`](../../references/releasing-md.template.md).
Fill in:

- `<REPO_NAME>` — from `gh repo view`
- `<NEXT_VERSION>` — current manifest version + 1 patch (a starter
  example; the user can change it)
- `<VERSION_MANIFESTS>` — what `scripts/release/update-version.sh`
  bumps (from Phase 4)
- The "What happens" CI step list — generated from the jobs in the
  release.yml from Phase 5
- The Secrets table — `RELEASE_BOT_APP_*` plus pipeline-specific
  secrets activated in Phase 2 (Sparkle → `SPARKLE_ED_PRIVATE_KEY`,
  apt → `APT_DISPATCH_TOKEN`, etc.)
- The branch protection block — `<RELEASE_BOT_NAME>` from Phase 3,
  ruleset ID from `gh api /repos/<r>/rulesets`
- The breakage table — include only rows relevant to this repo's
  pipelines

Show to the user. Write to `RELEASING.md` at the repo root. Don't commit.

## Phase 7 — sanity-check-app.yml

Drop in
[`references/workflows/sanity-check-app.yml.template`](../../references/workflows/sanity-check-app.yml.template)
to `.github/workflows/sanity-check-app.yml`.

**Default to multi-target when there are cross-repo pipelines.** For
every cross-repo target chosen in Phase 2 (a Homebrew tap, an apt
receiver, a Docker registry repo), uncomment and duplicate the
template's commented-out "── 2. <CROSS_REPO_TARGET_NAME>" block. Emit
one block per target. This is the single most valuable App-install
verification — a missing install on the target repo causes the real
release to fail mid-flight, and the sanity-check catches it with one
manual `workflow_dispatch` click.

A repo whose release.yml touches only its own `main` (Sparkle appcast
push but no cross-repo dispatch) ships just the self block; that's fine.

Substitute per-target placeholders at emit time:

- `<TARGET_TOKEN_ID>` — a unique step id (e.g. `tap-token`, `apt-token`)
- `<TARGET_OWNER>` — usually `${{ github.repository_owner }}` literal or the explicit owner
- `<TARGET_REPO_NAME>` — repo name only, e.g. `homebrew-tap`, `apt-charliek`

A failed reach check at sanity-check time means the App isn't installed on
that target repo — fix that BEFORE the first real release runs, because the
release will fail mid-flight if a target isn't reachable.

Tell the user: *"To verify the App wiring, go to Actions → run
`sanity-check-app` from the Actions UI. The output should print the
repo's name, an installation count of at least 1, a token identity
ending in `[bot]`, and (for each cross-repo target) the target repo's
full name."*

## Phase 8 — First release dry-run

Suggest the user run `$release-workflows:release v<NEXT_VERSION>` to
cut the first release using the new flow. Walk through what to expect:

1. Two commits land on main: `docs(changelog): vX.Y.Z entry` and
   `chore(version): bump to X.Y.Z`.
2. Tag pushed; `release.yml` triggers.
3. `version-check` and `ci-gate` pass.
4. Build jobs (mac/linux/docker/etc.) produce artifacts and upload to
   the GitHub Release.
5. Post-build jobs (sparkle-appcast, apt-dispatch, etc.) update
   external state — the bot pushes signed appcast updates, receivers
   get dispatched.

Tell the user what to watch for failure modes (the breakage table in
the RELEASING.md you just drafted) and what to do if something
specific fails.

## Optional: "Use a sibling repo as a model"

If the user says *"use `<path>` as a model"* during any phase (most
useful for Phase 4 and Phase 5), read that repo's relevant files and
adapt — don't blindly copy. Call out specifically where the new repo
diverges. Example: *"The model repo uses Sparkle; your repo uses
Homebrew. Here's how the appcast job translates to a homebrew job."*

If the user doesn't volunteer a sibling repo, don't ask for one — the
walkthrough works without it. Sibling references are an accelerator,
not a requirement.

## Idempotency

When the user re-runs `$release-workflows:setup` on a partially set-up
repo:

1. Phase 1's survey computes a status per phase.
2. Skip DONE phases by default; show what's there and ask if they want a refresh.
3. For PARTIAL phases, show what's missing or out of date, and offer to fix
   each part individually.
4. NEEDS DOING phases run the full walkthrough.

Never silently overwrite a file. Always diff and ask. Hand-edits the
user added to existing files (extra steps in `release.yml`, custom prose
in `RELEASING.md`) should be preserved; the skill suggests *additions*
or *replacements* for specific blocks, not whole-file rewrites.

## What this skill never does

- Auto-commit. Every file write is followed by *"review and commit when
  ready."*
- Run `gh secret set` without showing the user the secret value first
  (or, for `RELEASE_BOT_APP_KEY` which is multi-line and binary-ish,
  showing the command they'll run with the path to the `.pem`).
- Mutate branch protection without an explicit "yes, proceed".
- Assume the App name, App ID, ruleset ID, secret value, or apt
  receiver. Always ask, then confirm before writing them into files.
- Overwrite a file without showing a diff first.
- Cut a release on the user's behalf. That's `$release-workflows:release`.

## Outputs checklist

By the end of a clean run on a fresh repo, the user has these files
ready to review and commit:

- `scripts/release/update-version.sh` (executable)
- `.github/workflows/release.yml`
- `.github/workflows/sanity-check-app.yml`
- `RELEASING.md`

And these one-time configurations done on GitHub:

- `RELEASE_BOT_CLIENT_ID` + `RELEASE_BOT_APP_KEY` secrets
- App installed on the repo
- `main` ruleset with App + admin in `bypass_actors`
- Classic protection deleted (replaced by the ruleset)

Nothing else.
