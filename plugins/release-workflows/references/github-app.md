# Release-bot App, secrets, and branch protection ruleset

This file explains how to wire the GitHub App that performs CI-driven
bot pushes (signed appcasts, etc.) and the branch protection ruleset
that lets it through without weakening protection for everyone else.

The setup skill walks the user through this once per repo. The release
skill links here when a push is rejected by branch protection — that
usually means a bypass actor is missing.

## Why an App at all

CI steps that update files in `main` after a build (a signed Sparkle
appcast, a bumped formula reference, etc.) can't use the default
`GITHUB_TOKEN` because that token is rejected by branch protection's
required-status-check rule — the new commit hasn't been built yet, so
no `ci-success` exists on it at push time.

Two viable workarounds for branch-protected bot pushes:

1. **A GitHub App with bypass.** The App's installation token is
   listed in the branch ruleset's bypass actors. The App pushes
   directly; ci-success runs after, but the push isn't gated on it.
2. **A PAT belonging to an admin.** Admins bypass protection
   regardless. PATs work but expire and live tied to a personal
   identity.

This plugin uses (1) — a single App, installed on every repo that opts
in, listed in each repo's ruleset bypass. One private key to rotate, one
audit trail, scoped permissions per installation, doesn't tie to anyone's
personal account.

The App name is up to you — the plugin doesn't hard-code it. Throughout
this doc, the App is referred to as "the release-bot App"; substitute
your own name where it appears.

## Phase 1 — Create the App (once per account)

If you already have a release-bot App for your account, skip to Phase 2.

`Settings → Developer settings → GitHub Apps → New GitHub App`:

| Field | Value |
|---|---|
| GitHub App name | Anything unique on GitHub. `<account>-release-bot` is a common shape. |
| Description | A one-liner. "Pushes release-derived artifacts on tag." |
| Homepage URL | Any HTTPS URL. Required by the form; otherwise unused. Your account page works. |
| **Webhook → Active** | **UNCHECK.** The App is invoked from CI workflows, not from webhook events. Leaving this on forces a public HTTPS receiver to exist; you'll be debugging an unrelated rabbit hole. |
| Webhook URL / Secret | Blank (greyed out once Active is off) |
| Callback URL | Blank. There is no OAuth user flow. |
| Setup URL | Blank. |
| Repository permissions → Contents | **Read and write** |
| Repository permissions → Metadata | Read-only (GitHub auto-selects this; leave it) |
| All other permissions | No access |
| Subscribe to events | None |
| Where can this GitHub App be installed? | Only on this account |

Click Create.

On the next page, note **two** identifiers — they're different fields
and you'll need both:

1. **Client ID** (top, under "About"). Alphanumeric, looks like
   `Iv23ctXXXXXX` or `lv1.XXXXXXXX`. This is the *workflow auth* input
   for `actions/create-github-app-token@v3` (the `client-id:` field
   superseded `app-id:` in v3.1.0; `app-id` still works but is
   deprecated with a warning).
2. **App ID** (also under "About"). A 6–7 digit integer (e.g.
   `3902108`). Used for ruleset `bypass_actors` entries as the
   `actor_id` of the App (Integration type). Phase 4 below uses it.
3. **Generate a private key** (bottom of the page, "Private keys" →
   "Generate a private key"). Downloads a `.pem` file. GitHub never
   shows it again — copy it into a password manager. The local copy is
   needed once per repo for the secret upload below; delete after.

## Phase 2 — Install the App on each repo

Left sidebar of the App settings → "Install App" → click "Install" next
to your account.

| Field | Choice |
|---|---|
| Only select repositories | Pick this repo |
| All repositories | Don't — defeats the per-repo audit |

Click Install. Repeat for each repo that opts into this plugin's
convention.

## Phase 3 — Set the secrets on each repo

```bash
CLIENT_ID=<your-client-id>                 # the alphanumeric ID from Phase 1
PEM=~/Downloads/<your-key>.private-key.pem
REPO=<owner>/<repo>

gh secret set RELEASE_BOT_CLIENT_ID -R "$REPO" -b "$CLIENT_ID"
gh secret set RELEASE_BOT_APP_KEY   -R "$REPO" < "$PEM"

# Verify
gh secret list -R "$REPO" | grep RELEASE_BOT_
```

Both secret names are the convention; the workflow templates expect
exactly these. The integer App ID stays on the App settings page — the
workflows don't need it as a secret (only ruleset bypass entries
reference it, and you paste it into the JSON template in Phase 4).
Once the secrets are set on every repo, move the `.pem` into your
password manager and delete it from `~/Downloads/`.

## Phase 4 — Migrate `main` to a ruleset

Classic branch protection has no per-actor bypass for required status
checks. Even with `enforce_admins=false`, only admin *users* bypass —
Apps don't. The fix is to migrate `main` to a ruleset, which has a
per-actor bypass list.

The ruleset keeps `ci-success` required for the general case and lists
two bypass actors:

- **The release-bot App** — so the bot's post-build push (signed
  appcast, etc.) lands without waiting on its own ci-success.
- **The admin role** — so `$release-workflows:release`'s push of the
  two release commits lands; those commits don't have ci-success yet
  either at the moment of push.

Without the admin entry, even an admin's release push is rejected.
This is the gotcha that bit roost on v0.0.5 — classic protection's
`enforce_admins=false` does **not** translate to rulesets.

### Step 4.1 — Create the ruleset

```bash
REPO=<owner>/<repo>
APP_ID=<your-app-id>

cat > /tmp/main-ruleset.json <<JSON
{
  "name": "main-protection",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "required_status_checks",
      "parameters": {
        "required_status_checks": [ { "context": "ci-success" } ],
        "strict_required_status_checks_policy": false
      }
    }
  ],
  "bypass_actors": [
    { "actor_id": ${APP_ID}, "actor_type": "Integration", "bypass_mode": "always" },
    { "actor_id": 5,         "actor_type": "RepositoryRole", "bypass_mode": "always" }
  ]
}
JSON

gh api -X POST "/repos/${REPO}/rulesets" --input /tmp/main-ruleset.json \
  | jq '{id, name, enforcement, bypass_actors}'
```

`actor_type: "Integration"` with `actor_id: <your App ID>` is the App.
`actor_type: "RepositoryRole"` with `actor_id: 5` is the admin role
(the role ID is the same across all repos; it's not configurable).

### Step 4.2 — Delete the classic protection

```bash
gh api -X DELETE "/repos/${REPO}/branches/main/protection"
```

### Step 4.3 — Verify

```bash
echo "Classic protection (should be 404):"
gh api "/repos/${REPO}/branches/main/protection" 2>&1 | head -3

echo "Ruleset (should list main-protection with both bypass actors):"
gh api "/repos/${REPO}/rulesets" --jq '.[] | {id, name, enforcement, bypass_actors}'
```

A direct push by an admin should now print
`remote: Bypassed rule violations for refs/heads/main` and succeed even
when the new commit has no ci-success yet. A bot push from CI using
the App's token should print the same and succeed.

### Step 4.4 — Edit an existing ruleset (instead of recreating it)

If the ruleset already exists and you only need to add or change a
bypass actor, **update** it in place — don't re-run the POST from
Step 4.1, which would either fail with "ruleset name already exists"
or create a duplicate.

```bash
REPO=<owner>/<repo>
APP_ID=<your-app-id>

# Find the ruleset's id
RULESET_ID="$(gh api "/repos/${REPO}/rulesets" \
  --jq '.[] | select(.name=="main-protection") | .id')"
echo "ruleset id: ${RULESET_ID}"

# Fetch its current body
gh api "/repos/${REPO}/rulesets/${RULESET_ID}" > /tmp/ruleset.json

# Edit /tmp/ruleset.json by hand (or with jq) to add the missing actor
# under .bypass_actors. Then PUT it back:
gh api -X PUT "/repos/${REPO}/rulesets/${RULESET_ID}" --input /tmp/ruleset.json \
  | jq '{id, name, bypass_actors}'
```

GitHub's Rules UI (Repo Settings → Rules → Rulesets → main-protection →
Bypass list) is just as good for this kind of one-off edit.

## Phase 5 — Sanity-check the wiring

Use the bundled
[`sanity-check-app.yml`](workflows/sanity-check-app.yml.template)
workflow — `workflow_dispatch`-only, mints a release-bot token in CI
and prints which repo the token can see plus the bot's identity. Run
it from the Actions UI on the branch where you've set the secrets and
confirm:

- The repo it sees matches the repo it's running in
- The installation repository count is at least 1
- The token's identity ends with `[bot]`

If any of those don't match, fix the App install or secrets before
proceeding to the first real release.

## Per-repo selective installs vs single-installation

How you install the App per repo affects what `gh api /installation/repositories`
returns inside a workflow — and it's a non-obvious gotcha that traps anyone
trying to write a "verify the App can reach N target repos" assertion in
sanity-check.

There are two install patterns:

| Pattern | What `/installation/repositories` returns from each repo |
|---|---|
| **Per-repo selective** (typical for personal accounts) — install the App separately on each repo, picking "Only select repositories" each time, choosing one repo per install | Each repo's installation sees **only itself** (count = 1). Cross-repo minting via `owner` + `repositories` reaches OTHER installations through the App's private key, NOT via this installation's repo list. |
| **Single installation, all selected repos** — install the App once with "Only select repositories" + a multi-select including all target repos | All repos in that installation see the same count (count = N for the multi-selected list). |

Charlie's setup uses **per-repo selective** — installing on prox, strix, roost,
homebrew-tap, apt-charliek, etc. as separate App installations, each scoped to
one repo.

**Do not write count-based assertions in `sanity-check-app.yml`** like
"assert `total_count >= 3`". On the per-repo selective pattern, count is always
1 from any single repo's perspective, regardless of how many target repos the
App can reach via cross-repo minting. The per-target reach checks (mint a
scoped token + `gh api /repos/<target>` GET) are the correct verification.

This bit prox during initial sanity-check: a "≥3 expected" assertion fired
because prox's installation legitimately has count=1, then the per-target
reach checks didn't even get to run. Removed in prox `4910290` and in the
template's count comment here.

## Cross-repo bot pushes

The App isn't limited to the repo whose workflow is running. One App, installed
on several repos, is the single credential for a release's *cross-repo* side
effects — e.g. strix's `release.yml` pushes a formula to `homebrew-tap` and fires
a dispatch at `apt-charliek`, both from the App, with no PATs.

In CI, mint a token scoped to the *target* repo (not the running repo):

```yaml
- uses: actions/create-github-app-token@v3
  id: tap
  with:
    client-id: ${{ secrets.RELEASE_BOT_CLIENT_ID }}
    private-key: ${{ secrets.RELEASE_BOT_APP_KEY }}
    owner: ${{ github.repository_owner }}
    repositories: homebrew-tap        # repo name only, under the same owner
# … then use ${{ steps.tap.outputs.token }} as GH_TOKEN / in the clone URL
```

Notes:

- The App must be **installed on the target repo** (Phase 2). The
  `RELEASE_BOT_CLIENT_ID`/`_KEY` secrets live only on the *running* repo; the target
  repos need no secrets.
- The minted token is scoped to just that repo and expires in ~1h — a smaller
  blast radius than a broad PAT.
- A target repo needs a **ruleset bypass only if its default branch is protected**
  with required checks. An unprotected `main` (typical for a tap or apt-index
  repo) needs nothing beyond the install.
- **Bot git identity** for commits: installation tokens can't call `gh api /user`
  (403). Use the action's `app-slug` output plus the public `/users` endpoint:
  ```bash
  bot_id="$(gh api "/users/${SLUG}[bot]" --jq .id)"
  git config user.name  "${SLUG}[bot]"
  git config user.email "${bot_id}+${SLUG}[bot]@users.noreply.github.com"
  ```
  where `SLUG` is `${{ steps.<id>.outputs.app-slug }}`.
- **`git push` authentication: URL-embedded token, NOT
  `git -c http.extraheader=…`.** This is a non-obvious gotcha. Setting
  `http.https://github.com/.extraheader=AUTHORIZATION: bearer <token>` via
  `git -c` is accepted by `git config` (you can verify with
  `git config --get …`), but the HTTP layer ignores it on the outgoing
  request and git still prompts:
  ```
  fatal: could not read Username for 'https://github.com'
  ```
  `actions/checkout` makes this pattern work by setting it via persistent
  `git config` then unsetting; the ephemeral `-c` form does not. The proven
  pattern for cross-repo (or same-repo bot) pushes is the token embedded in
  the URL:
  ```bash
  TOKEN_URL="https://x-access-token:${GH_TOKEN}@github.com/${REPO_FULL}.git"
  git push "${TOKEN_URL}" HEAD:main
  git fetch "${TOKEN_URL}" main   # for retry loops; rebase against FETCH_HEAD
  ```
  The token stays in argv (not on-disk config). Reproduced in roost v0.0.6
  and fixed in the original release-workflows history and roost `f101aad` — every
  template ships this shape now.

## Rollback

If migrating the ruleset goes wrong:

```bash
# Restore classic protection.
# Note: `-F` (capital) sends the value as a JSON literal — required for
# booleans and arrays. `-f` (lowercase) only sends strings; use it for
# string values like the status-check contexts.
gh api -X PUT "/repos/${REPO}/branches/main/protection" \
  -F required_status_checks[strict]=false \
  -f required_status_checks[contexts][]=ci-success \
  -F enforce_admins=false \
  -F required_pull_request_reviews= \
  -F restrictions=

# Find and delete the ruleset
gh api "/repos/${REPO}/rulesets" --jq '.[] | select(.name=="main-protection") | .id'
gh api -X DELETE "/repos/${REPO}/rulesets/<id-from-previous-line>"
```

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `git push origin main` → `Required status check "ci-success" is expected` | Admin role missing from ruleset bypass | Update the ruleset's `bypass_actors` (see Step 4.4 below) to include `{ actor_id: 5, actor_type: "RepositoryRole", bypass_mode: "always" }` |
| `git push origin main` from CI bot → same error | App missing from ruleset bypass | Update the ruleset's `bypass_actors` (see Step 4.4 below) to include `{ actor_id: <APP_ID>, actor_type: "Integration", bypass_mode: "always" }` |
| `actions/create-github-app-token@v3` → `Bad credentials` | `RELEASE_BOT_CLIENT_ID` or `RELEASE_BOT_APP_KEY` not set, or `.pem` corrupted | Re-upload the `.pem` from the password manager |
| Bot push succeeds but workflow says "Resource not accessible by integration" | App is installed but doesn't have the right permission for the API call being made | Edit the App's permissions, then re-accept the installation |
| CI says `App is installed but token has no access to <repo>` | App install missed this repo | Re-run Phase 2 and add the repo |

## What the plugin doesn't ship

- The App itself. Create it once per account; the plugin is repo-agnostic.
- A management script for rotating the App's private key. If you rotate,
  re-run Phase 3 on every repo with the new `.pem` and re-run the
  sanity-check workflow to confirm.
- An automated migration for repos that already use classic protection.
  Run Step 4.1, then Step 4.2, then test.
