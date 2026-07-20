# Mac Developer ID signing + notarization

For a Mac app shipped as a DMG (usually alongside a Sparkle appcast), this
makes the download open with a normal double-click instead of being blocked
by Gatekeeper. Unlike the `job-*.yml` fragments, signing + notarization is
**woven into the existing mac build job as steps + job env**, not a standalone
job — the cert has to be in the keychain before the bundle is built, and the
DMG has to be notarized before it's uploaded/EdDSA-signed.

Everything here is **inert until all six secrets exist** (the `CAN_NOTARIZE`
gate). With any one missing, the bundle ships ad-hoc-signed and the build still
succeeds (Gatekeeper-bypass note in the DMG). Add all six and the next release
is signed + notarized with no code change.

**All-or-nothing — don't gate on the cert alone.** A signed-but-un-notarized DMG
is still Gatekeeper-blocked, so signing without notarizing has no value. Gating
on just `MACOS_CERTIFICATE_P12_BASE64` breaks under a partial secret rollout two
ways: cert set but notary creds missing → a Developer-ID-signed DMG ships
un-notarized *with the first-launch note dropped* (still blocked, no guidance);
notary creds set but cert missing → notarytool is asked to notarize an ad-hoc
DMG and the job fails. Require the whole set in one `CAN_NOTARIZE` expression,
hand the identity to the bundle/DMG steps only when it's true, and gate the
notarize step on it too; any gap falls back cleanly to ad-hoc.

## The pieces

1. **Job env** (on the mac build job) — a single all-or-nothing gate over the
   full secret set:
   ```yaml
   env:
     CAN_NOTARIZE: ${{ secrets.MACOS_CERTIFICATE_P12_BASE64 != '' && secrets.MACOS_CERTIFICATE_PASSWORD != '' && secrets.<APP>_DEVELOPER_ID_IDENTITY != '' && secrets.APPLE_ID != '' && secrets.APPLE_TEAM_ID != '' && secrets.APPLE_APP_SPECIFIC_PASSWORD != '' }}
   ```
   The identity is **not** set unconditionally at job level; it's handed to the
   bundle/DMG steps only when `CAN_NOTARIZE` (see step 3), so an empty value →
   the bundle script's ad-hoc (`-`) path.

2. **Import the cert** into a throwaway keychain (gated on `CAN_NOTARIZE`),
   before the bundle step. See `build-steps.yml`.

3. **The repo's bundle script signs with the identity.** This part is
   repo-owned (it knows the bundle layout). The identity is passed to the
   bundle + DMG steps as
   `${{ env.CAN_NOTARIZE == 'true' && secrets.<APP>_DEVELOPER_ID_IDENTITY || '' }}`.
   When set, the bundle script must: codesign every nested Mach-O
   (helpers, then frameworks `--deep` without the app's entitlements, then the
   outer `.app`) with `--options runtime` (hardened runtime — required for
   notarization) and `--timestamp`. See roost `mac/scripts/bundle.sh` and
   shed-desktop `scripts/bundle.sh` for the exact shape (including why Sparkle
   is signed `--deep` without entitlements).

4. **`notarize.sh`** after the DMG is built — `notarize.sh.template` here is the
   canonical copy. No-op (exit 0) without credentials, so it's safe to wire in
   before the secrets land.

5. **Detect notarization status** via `xcrun stapler validate` and gate the
   release-note / first-launch guidance on the *real* artifact state — a
   Developer-ID-signed but un-notarized DMG is still Gatekeeper-blocked, so
   "cert exists" is the wrong signal.

## Secrets (6)

| Secret | Purpose |
|---|---|
| `MACOS_CERTIFICATE_P12_BASE64` | Developer ID Application cert+key, base64 of the `.p12`. Part of the `CAN_NOTARIZE` gate. |
| `MACOS_CERTIFICATE_PASSWORD` | `.p12` export password |
| `<APP>_DEVELOPER_ID_IDENTITY` | codesign identity, e.g. `Developer ID Application: Name (TEAMID)` |
| `APPLE_ID` | Apple ID email for notarytool |
| `APPLE_TEAM_ID` | 10-char Apple team ID |
| `APPLE_APP_SPECIFIC_PASSWORD` | app-specific password from appleid.apple.com (NOT the Apple ID password) |

Provisioning (one-time, shared across all of a team's apps — one cert signs
them all): create a **Developer ID Application** certificate (Xcode → Settings
→ Accounts → Manage Certificates → +, or the Developer portal with a CSR),
then read the identity string + Team ID straight off it with
`security find-identity -v -p codesigning | grep "Developer ID Application"`
(the quoted CN is the identity; the parenthesized 10 chars are the Team ID).
Export the cert+key as a `.p12` from Keychain Access and `base64 -i cert.p12`.

## Ordering trap (with Sparkle)

`xcrun stapler staple` **rewrites the DMG bytes**, so any later step that hashes
or EdDSA-signs the DMG must run *after* notarization:

- If the Sparkle appcast steps are **inline** in the mac job (roost,
  shed-desktop): place the notarize + staple step after "make DMG" and before
  the "upload DMG to Release" and `sign_update` steps.
- If `job-sparkle-appcast.yml` is a **separate** job that re-downloads the DMG
  from the Release: notarize + staple must finish before the build job's
  "upload DMG to Release" step, so the uploaded artifact is the stapled one.

## CI gotcha: `hdiutil create` "Resource busy"

Packaging the DMG with `hdiutil create` on a macOS runner intermittently fails
with `hdiutil: create failed - Resource busy` — transient device/Spotlight
contention, often right after codesign touches the bundle, **not** a real error
and unrelated to signing (the same command runs ad-hoc too). It surfaced on
shed-desktop's *first* notarized release. Make the repo's make-dmg script
resilient: wrap `hdiutil create` in a short retry loop (e.g. 5× with a few
seconds' backoff, `rm -f` the partial DMG between attempts) so a one-off flake
doesn't fail an otherwise-good release. See `mac/scripts/make-dmg.sh` in roost or
`scripts/make-dmg.sh` in shed-desktop.

## Verifying a notarized DMG

`stapler validate <dmg>` is the authoritative check (and what `notarize.sh`
runs). To see the real Gatekeeper verdict, mount the DMG and assess the app
inside:

```bash
hdiutil attach Foo.dmg -nobrowse -mountpoint /tmp/m -quiet
spctl -a -t exec -vv /tmp/m/Foo.app    # → accepted, source=Notarized Developer ID
hdiutil detach /tmp/m -quiet
```

Gotcha: `spctl -a -t open --context context:primary-signature <dmg>` reports
`no usable signature` on a correctly notarized DMG — that lens expects a
*codesigned* DMG, but the standard flow notarizes an un-codesigned DMG and
relies on the stapled ticket. Don't use it as the pass/fail check.

## Optional offline robustness: staple the .app too

The flow above notarizes + staples the **DMG**; the app inside is notarized
(its cdhash was in the submission) but carries no stapled ticket of its own, so
an *offline* first launch after copying to /Applications would need an online
notarization check. To be fully offline-robust, staple the `.app` before
building the DMG: submit the `.app` (zipped) to notarytool, `xcrun stapler
staple Foo.app`, then build the DMG from the stapled app (and still
notarize+staple the DMG so it mounts clean). Most apps ship the DMG-only flow;
add app-stapling only if offline first-launch matters.

## Reference implementations

- **roost** (`charliek/roost`) — `mac/scripts/notarize.sh`, the "Import
  Developer ID certificate" + "Notarize + staple" + "Detect DMG notarization
  status" steps in `.github/workflows/release.yml`'s `mac:` job, and the
  signing half of `mac/scripts/bundle.sh`.
- **shed-desktop** (`charliek/shed-desktop`) — same shape in a pure-Swift
  package: `scripts/notarize.sh` + the woven steps in
  `.github/workflows/release.yml`'s single `build` job.

Both were proven end-to-end (cert imports, hardened-runtime sign, notarytool
submit + staple, app assesses as Notarized Developer ID) before first release.
