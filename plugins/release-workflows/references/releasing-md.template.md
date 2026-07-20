# RELEASING.md template

This is the skeleton the setup skill fills in to produce a per-repo
`RELEASING.md` at the repo root. Placeholders are angle-bracketed and
get replaced with detected values during emission. Comments in `{:: …}`
form are guidance for Codex during emission, not text to keep in
the output.

```markdown
# Releasing <REPO_NAME>

The general release framework is `$release-workflows`; this
file documents what's specific to this repo.

## TL;DR

In Codex, invoke `$release-workflows:release v<NEXT_VERSION>`.

That's it. Everything else is automatic.

## What happens

1. **`release-workflows:release`** (Codex, local):
   - Verifies branch (`main`) + clean tree + `ci-success` green on HEAD
   - Asks/confirms version
   - Drafts CHANGELOG entry from `git log v<previous>..HEAD`, commits as
     `docs(changelog): vX.Y.Z entry`
   - Runs `scripts/release/update-version.sh X.Y.Z` → bumps <VERSION_MANIFESTS>
   - Commits as `chore(version): bump to X.Y.Z`
   - Tags `vX.Y.Z` (annotated) on the version commit
   - `git push --follow-tags`

2. **`release.yml`** (CI, on tag):
{:: list each pipeline phase the repo's workflow runs, with one bullet per job. Order: version-check, ci-gate, create-release, <build jobs>, <publish jobs>. ::}
   - version-check (tag matches `<MANIFEST_PATH>` version)
   - ci-gate (`ci-success` green on tagged commit)
   - create-release (extract CHANGELOG section → `gh release create`)
{:: insert repo-specific build + publish lines here ::}

## Version files this repo owns

`scripts/release/update-version.sh` bumps:
{:: list each manifest the script touches, with a one-line note on why it's the canonical version. ::}

NOT bumped:
{:: list any version-like files in the repo that are *not* release-managed (test harness pyproject.toml, embedded vendored manifests, etc.) with a one-liner explaining why. If there are none, omit this section. ::}

## Snapshot / dev versioning

Not used. Main between releases shows the last released version. If you
need a build-identity beyond "last released" (e.g. for a CLI's
`--version` diagnostics), derive it at build time from
`git describe --tags --dirty` rather than snapshotting the source tree.

{:: If this repo *does* implement snapshot or dev versioning, replace
this section with the policy: what gets bumped to what, in which step.
::}

## Secrets

| Secret | Purpose | Required? |
|---|---|---|
| `RELEASE_BOT_CLIENT_ID` | `<RELEASE_BOT_NAME>` GitHub App Client ID | required |
| `RELEASE_BOT_APP_KEY` | App private key (.pem) | required |
{:: list any pipeline-specific secrets: SPARKLE_ED_PRIVATE_KEY (Sparkle), APT_DISPATCH_TOKEN (apt-dispatch), HOMEBREW_TAP_TOKEN (homebrew), etc. with a note on optional vs required and what happens if unset. For Mac Developer ID signing + notarization, list the six (all gated together as CAN_NOTARIZE): MACOS_CERTIFICATE_P12_BASE64, MACOS_CERTIFICATE_PASSWORD, <APP>_DEVELOPER_ID_IDENTITY, APPLE_ID, APPLE_TEAM_ID, APPLE_APP_SPECIFIC_PASSWORD — any one missing → ad-hoc-signed DMG (Gatekeeper-bypass note); see references/mac-signing/. ::}

## Branch protection

`main` is protected by a ruleset with `required_status_checks=['ci-success']`
and two bypass actors:

- `<RELEASE_BOT_NAME>` (App ID `<APP_ID>`, type `Integration`) — lets
  the bot push post-build asset updates (signed appcasts, etc.)
- Admin role (id `5`, type `RepositoryRole`) — lets
  `$release-workflows:release` push the changelog + version commits + tag

Ruleset id: `<RULESET_ID>`. Inspect or edit at
`https://github.com/<OWNER>/<REPO>/rules`.

## When things break

| Symptom | Cause | Fix |
|---|---|---|
| `git push` rejected: "Required status check ci-success" | Pusher not in ruleset bypass | Confirm both the App and the admin role are in `bypass_actors` (see github-app.md) |
| `update-version.sh` not found | Convention not adopted | Run `$release-workflows:setup` |
| Tag pushed, `version-check` fails on tag | Tagged a commit that didn't run `update-version.sh` | Re-bump locally + cut a fresh patch tag (don't force-update an existing tag) |
{:: append pipeline-specific rows: appcast not on Pages → docs.yml didn't redeploy; apt-dispatch warned → APT_DISPATCH_TOKEN missing; etc. ::}

## Break-glass recovery

If a post-build job fails after the artifacts have already uploaded
(common pattern: DMG/tarball is on the Release, but the appcast/formula
push fails), you don't need to re-cut the release. Recover the missing
step locally:

{:: For each post-build step the repo runs, document the manual recovery.
The most common is the Sparkle appcast — runbook below. Drop the section
if the repo has no post-build push that could fail like this. ::}

### Sparkle appcast — manual sign + publish

If `mac` job's appcast step fails (the DMG IS on the Release):

```bash
# From a Mac with the EdDSA key in keychain (account: roost-release)
W=$(mktemp -d); chmod 700 "$W"
SIGN_UPDATE=<repo-local sign_update path, e.g. mac/.build/artifacts/sparkle/Sparkle/bin/sign_update>
GENERATE_KEYS=<sibling path to generate_keys>

# 1. Download the DMG that was uploaded by the build step
gh release download v<X.Y.Z> --pattern "<DMG_PATTERN>" --dir "$W"

# 2. Export the EdDSA key prompt-free (generate_keys is the creating
#    tool, so it has ACL access; sign_update would prompt)
"$GENERATE_KEYS" --account roost-release -x "$W/key" >/dev/null

# 3. Sign
"$SIGN_UPDATE" --ed-key-file "$W/key" "$W/<DMG_NAME>" > "$W/sign.txt"
rm -f "$W/key"

# 4. Append entry to docs/appcast.xml
ROOST_VERSION=<X.Y.Z> ROOST_TAG=v<X.Y.Z> ROOST_SIGN_FILE="$W/sign.txt" \
  python3 mac/scripts/update-appcast.py

# 5. Commit + push (admin bypasses the ruleset's ci-success rule)
git add docs/appcast.xml
git commit -m "chore(appcast): publish v<X.Y.Z>"
git push origin main

# 6. docs.yml redeploys Pages with the new entry
rm -rf "$W"
```

### Homebrew formula push

{:: For repos that ship via Homebrew tap. Pattern: download tarballs
from Release, hash, render formula template, clone tap + commit + push
locally with the maintainer's own credentials. Document the path to the
in-repo .rb.tmpl and the four (or whatever) per-arch SHA placeholders. ::}

### apt-receiver re-dispatch

{:: For repos that dispatch to an apt receiver. The receiver should
self-heal on its next scheduled re-scan; if you need to force it, use
`gh api repos/<receiver>/dispatches --method POST -f event_type=publish
-F client_payload[package]=<pkg> -F client_payload[tag]=v<X.Y.Z>` with
a personal token that has Contents:write on the receiver. ::}

## Adopting the convention (for new contributors)

If you're new to this repo and need to understand the release pipeline,
read the [`release-workflows` convention](https://github.com/charliek/codex-plugins/blob/main/plugins/release-workflows/references/convention.md)
in the framework repo. It defines the contract every file in this
repo's `scripts/release/` and `.github/workflows/release.yml` is
written against.
```

## Emission guidance

When the setup skill writes a RELEASING.md into a repo, it should:

1. Replace every `<PLACEHOLDER>` with a concrete value detected in
   phase 1 of setup or asked of the user.
2. Resolve every `{:: comment ::}` by either inserting the
   corresponding content or omitting the section entirely if the
   comment says "if there are none, omit".
3. Keep the prose tight — RELEASING.md is meant to be read at a glance
   when something breaks. If a section turns out to be 0–1 lines of
   useful content, fold it into another section or drop it.
4. Add a "## Notes for this repo" section at the end if there's
   anything unusual Codex caught that doesn't fit the template (e.g.
   "tag pushes used to require manual apt-charliek re-trigger; now
   automated").

Never auto-commit. The user reviews + commits the file themselves.
