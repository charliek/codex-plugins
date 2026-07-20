#!/usr/bin/env bash
# Bump the release version of a Rust workspace.
#
# Use this template for repos whose canonical version is
# `[workspace.package].version` in the root `Cargo.toml` (every workspace
# member inherits via `version.workspace = true`). The script bumps that
# field and regenerates `Cargo.lock` so the per-member entries match.
#
# ⚠ COLUMN-ALIGNMENT — IF YOUR CARGO.TOML USES THE COLUMN-ALIGNED STYLE,
# CHANGE THE REPLACEMENT BEFORE THE FIRST RELEASE.
#
# This template's sed pattern matches both vanilla cargo's single-space
# style (`version = "0.1.0"`) and hand-aligned column-style layouts
# (`version       = "0.1.0"`). But the REPLACEMENT writes a single space
# regardless. On a repo with column-aligned `[workspace.package]`,
# adopting the template as-is reflows the version line on first release,
# which makes the diff noisy and breaks the alignment with neighboring
# lines (edition, rust-version, license, …).
#
# If your repo is column-aligned (roost-style, e.g. 7 spaces before `=`),
# change the replacement to match — keep the same gap on both sides:
#
#     sed -i.bak -E 's/^version[[:space:]]*=[[:space:]]*"[^"]+"/version       = "'"$V"'"/' Cargo.toml
#                                                                       ^^^^^^^ match your alignment
#
# Also update the verification grep below to match the aligned form.
# (cargo itself doesn't care either way — this is a code-style question.)
#
# Also works for single-crate packages (no `[workspace.package]`, just
# `[package].version`) without changes — the pattern matches both.
#
# Not handled here:
#   - workspace member crates that override the inherited version
#     (rare; if you have one, list it explicitly with a second sed call)
#   - `Cargo.toml`s outside the workspace root (e.g. an `examples/`
#     directory with its own Cargo.toml — those are not release artifacts)
#
# Contract (see references/update-version/README.md):
#   - one arg: semver string, no `v` prefix
#   - idempotent
#   - no network (--offline)
#   - verifies its own work
#   - does not `git add` (the release skill stages + commits)

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <X.Y.Z>   e.g. $0 0.0.6" >&2
  exit 2
fi
V="$1"

if [[ ! "$V" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?$ ]]; then
  echo "error: '$V' is not semver (X.Y.Z or X.Y.Z-suffix)" >&2
  exit 2
fi

# 1. Bump [workspace.package].version. Variable whitespace around `=`
#    so both vanilla cargo (`version = "0.1.0"`) and column-aligned
#    layouts match.
sed -i.bak -E 's/^version[[:space:]]*=[[:space:]]*"[^"]+"/version = "'"$V"'"/' Cargo.toml
rm -f Cargo.toml.bak

# 2. Verify Cargo.toml saw the bump. A silent sed no-match — e.g. the
#    repo uses [package].version under a different section header, or
#    a layout the regex doesn't cover — is the most common failure
#    mode here. Catch it before blaming the lockfile.
if ! grep -q "^version = \"$V\"" Cargo.toml; then
  echo "error: Cargo.toml's [workspace.package].version did not update to $V." >&2
  echo "       The sed pattern matches \`version (whitespace) = (whitespace) \"<value>\"\` at column 0." >&2
  echo "       If your manifest has a different shape, adjust the sed pattern in this script." >&2
  exit 1
fi

# 3. Regenerate Cargo.lock so workspace member entries match.
#    --workspace is the surface that actually moves.
#    --offline is safe: we're only changing internal version strings,
#    not touching the dep tree, so the cache is sufficient.
#
#    Resolve cargo via `mise exec` when the repo pins its toolchain
#    there (.mise.toml is the source of truth), else fall back to
#    whatever cargo is on PATH (CI runners installing Rust via
#    actions-rs / actions/setup-rust don't need mise; same goes for
#    rustup users). Without this the script silently inherits the
#    caller's shell — non-interactive shells (`bash -c`, a release
#    skill subprocess, etc.) often don't have cargo on PATH even
#    when `mise install` already provisioned the pinned toolchain.
#    This was strix v0.0.2's failure mode before the fix: set -e
#    killed the run cleanly, but the symptom read as a lockfile bug
#    rather than a missing-cargo bug.
if command -v mise >/dev/null 2>&1 && [[ -f .mise.toml ]]; then
  cargo=(mise exec -- cargo)
elif command -v cargo >/dev/null 2>&1; then
  cargo=(cargo)
else
  echo "error: cargo not found and 'mise exec' unavailable." >&2
  echo "       Install Rust (via rustup) or run inside a shell where" >&2
  echo "       \`mise exec -- cargo --version\` or \`cargo --version\` works." >&2
  exit 1
fi
"${cargo[@]}" update --workspace --offline >/dev/null

# 4. Verify the lockfile saw the bump. If Cargo.toml updated but
#    Cargo.lock didn't, a member crate likely overrides version manually.
if ! grep -q "^version = \"$V\"" Cargo.lock; then
  echo "error: Cargo.lock did not update to $V — some member may override the version" >&2
  exit 1
fi

echo "Bumped Cargo.toml + Cargo.lock to $V"
