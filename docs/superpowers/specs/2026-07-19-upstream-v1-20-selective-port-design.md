# Upstream v1.20 Selective Port Design

## Goal

Adopt the provider-neutral reliability and UI fixes published in Usage Monitor
for Claude v1.20 without restoring Claude credentials, Anthropic networking,
Claude branding, WSL CLI selection, paid-credit behavior, or upstream release
workflow state.

## Source range

- Last reviewed upstream SHA: `f9224c2667ce7210464590d1e5e3f5d8637c8c69`
- Upstream v1.20.0 SHA: `e1606375bb3569e337aec6851c7868d9678f965b`
- Reviewed post-release SHA: `a3503e9a49c0028d8c5db6897dcd3964746bdd15`
- New commits through v1.20.0: 38
- New commits through reviewed upstream `main`: 39

The fork baseline is three commits after the upstream v1.19.0 tag and already
contains the upstream multi-account implementation and documentation.

## Import policy

All code is translated manually into the Codex fork. No upstream merge,
rebase, wholesale sync, or commit-producing cherry-pick is used. Runtime names,
settings, documentation, icons, provider code, updater behavior, and tests
remain Codex-specific.

The upstream MIT author attribution remains in `LICENSE`. `UPSTREAM_SYNC.md`
records one disposition for every reviewed SHA. User-facing imported fixes are
credited in the fork changelog without claiming original authorship.

## Imported behavior

### Test isolation

- `0d0a892`: real named kernel-object tests use a test-only suffix and prove
  that the live holder record is not modified.
- `42029a5`: tray-render tests pin default icon fields instead of inheriting a
  machine-local settings file.

### Single-instance safety

- `8ff9e47`: access-denied mutex creation is treated as an existing instance;
  other creation failures fail closed.
- `66461c5`: the holder PID is re-read after the confirmation dialog before
  termination, preventing PID-reuse termination.
- `958136f`: retain the fork's existing mutex-recreation proof and add only a
  dedicated localized replacement-failure message.

The three behaviors form one safety unit. Tests cover NULL handles, access
denied, unexpected errors, PID changes, replacement failure, and successful
replacement. Manual smoke covers elevated and unelevated instances.

### Popup and tray reliability

Port popup hook shutdown, exact-initial-height display, update-loop recovery,
geometry serialization, equal-count field-set rebuilding, and stable marker
positions. Port theme-watcher recovery, the 99 percent glyph clamp, overage
clamp behavior, DST-safe local-midnight dividers, and the missing
`BAR_DIVIDER` export.

Transient callback failures are logged through the fork's sanitized
application logging rather than silently discarded.

### Settings, localization, discovery, and diagnostics

Accept UTF-8 BOM settings, treat empty command strings as disabled, recognize
Chinese, Hindi, and Indonesian Windows locale names, skip unreadable Codex IDE
extension directories, preserve drive-root `--codex-home` values, redact the
home path case-insensitively at path boundaries, and tolerate Windows versions
without `SetProcessDpiAwarenessContext`.

### Polling and notifications

Keep popup-triggered fetches outside the pre-reset cooldown danger window,
recover from backward wall-clock jumps, lock and atomically swap deferred
notifications, flush them promptly when the user returns, and emit one reset
toast when several quotas reset together. Add a Codex-specific regression test
showing that a recovery retry returning 429 is classified as the final error
and arms the cache backoff.

## Covered without upstream code

- `0b976f4`: the cache's `None`-preserves profile contract retains the account
  baseline across a failed account read.
- `df86f18`: the adapter already normalizes known profiles; the popup's null
  guard is ported separately.
- `3823775`: display-field resolution already rejects non-dictionary icon
  entries; the tooltip guard is ported separately.
- `b2f5516`: the Codex adapter and cache already implement final retry error
  classification and backoff; only the composed regression test is added.

## Excluded or deferred

- `d4b67c3`: Claude credential-file access.
- `22bb349`: dormant paid-credit and currency behavior.
- `de3a73f`, `d363b81`: custom or WSL Claude CLI selection.
- `e160637`: upstream version and Claude branding release changes.
- `a3503e9`: upstream Claude maintainer commands.
- `a1b945c`: notification identity registration using a temporary one-file
  extraction path. It remains deferred until a stable multi-instance-safe icon
  path, ownership model, and cleanup behavior are designed.

## Verification

Before the test-isolation change, the production monitor must be stopped and
its absence verified before and after the baseline suite. After isolation
passes, the canonical monitor is relaunched and verified.

Every behavior follows a focused red-green test cycle, then the complete native
Windows `unittest` suite. Final verification includes a clean PyInstaller
build, frozen smoke, side-by-side Claude and Codex identity checks, privacy and
provider-boundary scans, and review of every changed file.
