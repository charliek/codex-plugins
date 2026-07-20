# update-version templates

This directory holds drop-in templates for `scripts/release/update-version.sh`,
keyed by the manifest the repo uses to track its release version.

The setup skill picks the right template (or composes a few when a repo has
multiple manifests — e.g. a Cargo workspace that also ships a plugin.json)
and emits a single script per repo.

## Picker

| Repo shape | Template | Bumps |
|---|---|---|
| Rust workspace (single canonical version in `[workspace.package].version`) | [`cargo-workspace.sh`](cargo-workspace.sh) | `Cargo.toml` + `Cargo.lock` |
| Claude Code plugin (canonical version in `.claude-plugin/plugin.json`) | `plugin-json.sh` *(deferred until first consumer)* | `.claude-plugin/plugin.json` |
| Codex plugin (`.codex-plugin/plugin.json`) | deferred until a real target establishes its release unit | Not yet supported by this port |
| Python project (canonical version in `pyproject.toml [project].version`) | `pyproject.sh` *(deferred)* | `pyproject.toml` |
| Java / Gradle (canonical version in `build.gradle` or `build.gradle.kts`) | `gradle.sh` *(deferred)* | the Gradle build file |
| Go module without an in-source version | not needed | Go derives version from the tag; no source-tree bump |

The "deferred" entries are tiny (10–30 lines each) and ship when the first
repo of that shape adopts the convention.

Codex plugin repositories need one extra policy decision before a template can
ship: a repository may contain one plugin, several independently versioned
plugins, or a repository-wide version spanning multiple plugin manifests. Do
not infer that policy or bump every `.codex-plugin/plugin.json`; defer support
until a target repository defines the release unit explicitly.

## Composition

When a repo has multiple version sources (rare but real — a Cargo
workspace that *also* ships a Claude plugin from a sub-directory), the
setup skill emits a script that bumps both in sequence:

```bash
# scripts/release/update-version.sh
set -euo pipefail
V="${1:?usage: $0 <X.Y.Z>}"

# Cargo workspace (flexible whitespace — matches vanilla + aligned layouts)
sed -i.bak -E 's/^version[[:space:]]*=[[:space:]]*"[^"]+"/version = "'"$V"'"/' Cargo.toml
rm -f Cargo.toml.bak
cargo update --workspace --offline >/dev/null

# Embedded Claude plugin
jq --arg v "$V" '.version = $v' .claude-plugin/plugin.json > .claude-plugin/plugin.json.tmp
mv .claude-plugin/plugin.json.tmp .claude-plugin/plugin.json

echo "Bumped Cargo.toml + Cargo.lock + plugin.json to $V"
```

That composition is something the setup skill produces with the user's
input ("you have both X and Y; should both move together?"), not a
prebuilt template.

## Contract for any update-version.sh

Whatever the template, every `update-version.sh` shares this contract:

1. **One argument**: the semver string with no `v` prefix (e.g. `0.0.6`,
   `1.2.3-beta1`, `2.0.0-alpha-1`). Validate it matches
   `^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?$` (hyphens in the
   pre-release identifier are legal per semver §9).
2. **Idempotent**: re-running with the same version is a no-op (or
   replaces the existing value with the same value — diffs to nothing).
3. **No network**: nothing here should hit the registry/PyPI/etc.
   Lockfile regeneration must use `--offline` or equivalent.
4. **Verifies its own work**: after bumping, read the result back and
   confirm the new version made it into the file. Fail loud if not.
   This is non-negotiable — sed/jq/regex-based bumpers silently no-op
   when the manifest's shape doesn't match the pattern (missing field,
   different key style, reformatted). Reproduced in prox v0.1.2:
   removing the `"version"` field from `plugin.json` made the underlying
   `scripts/set-version.sh` exit 0 with the file unchanged; the wrapper
   relayed the success, and only an explicit read-back at the wrapper
   level caught the silent failure. Every template must close this gap.
   If you delegate to an existing in-repo bumper that doesn't verify,
   **the wrapper does the verification**.

   **For JSON manifests** (plugin.json, package.json, etc.), use `jq`,
   not grep+sed:

   ```bash
   [ "$(jq -r '.version' "${PLUGIN_JSON}")" = "${V}" ] || \
     { echo "error: plugin.json .version did not bump to ${V}" >&2; exit 1; }
   ```

   Why: grep+sed against `"version"[^"]*"[^"]+"` matches ANY occurrence
   of `"version"` in the file. If the JSON ever gains a nested
   `"version"` field (a `dependencies` block, a tool config that uses
   the same key, etc.), the verify accepts a wrong value and the
   delegated sed silently clobbers all of them. jq anchors to the
   top-level `.version` unambiguously and fails loudly on malformed
   JSON. jq is preinstalled on ubuntu-latest runners and ships with
   Homebrew + apt out of the box. Hardened in codelens v0.0.5 and prox
   #23 after the codelens PR review caught this class of risk.
5. **Quiet on success**: print one line per file mutated, nothing else.
   `set -euo pipefail` so silent failures don't reach the release skill.
6. **Doesn't `git add`**: leaves the working tree dirty. The release
   skill stages and commits.

If a future template diverges from this contract, document the reason
in the script's header so the next reader understands why.
