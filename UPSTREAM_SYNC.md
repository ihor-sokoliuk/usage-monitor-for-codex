# Upstream Sync Ledger

- Upstream: https://github.com/jens-duttke/usage-monitor-for-claude
- Port baseline: `f9224c2667ce7210464590d1e5e3f5d8637c8c69`
- Last reviewed upstream SHA: `a3503e9a49c0028d8c5db6897dcd3964746bdd15`

This fork imports upstream UI/UX and provider-neutral fixes selectively. It never syncs the Claude provider implementation wholesale.

## One-time setup

Run these commands manually from the Windows clone:

```powershell
git remote add upstream https://github.com/jens-duttke/usage-monitor-for-claude.git
git remote set-url --push upstream https://example.invalid/disabled
git fetch upstream --tags
git config rerere.enabled true
```

If `upstream` already exists, verify `git remote -v` instead of adding it again. The disabled push URL is a safety guard; this fork never pushes to the upstream repository.

## Fork path map

| Upstream | Fork | Rule |
|---|---|---|
| `usage_monitor_for_claude/claude_cli.py` | `usage_monitor_for_claude/codex_cli.py` | Manually translate discovery/version changes |
| `tests/test_claude_cli.py` | `tests/test_codex_cli.py` | Keep tests aligned with the renamed module |
| `usage_monitor_for_claude.spec` | `usage_monitor_for_codex.spec` | Preserve Codex executable/icon identity |
| `usage_monitor_for_claude.ico` | `usage_monitor_for_codex.ico` | Never restore the Claude icon |
| Claude OAuth client in `api.py` | Codex adapter in `api.py` plus transport in `app_server.py` | Never cherry-pick provider code blindly |
| Claude token/credential refresh machinery | Deleted | Codex app-server owns authentication |
| `docs/automatic-update-check.md` | Deleted | Optional monitor release-check guide is outside v1 scope |

The Python package directory intentionally remains `usage_monitor_for_claude` so provider-neutral UI diffs stay reviewable.

## Prohibited sync operations

- Never use GitHub's one-click **Sync fork**.
- Never merge or rebase `upstream/main` wholesale into this fork.
- Never force-push, reset, or discard local work to match upstream.
- Never resolve a conflict by restoring Anthropic endpoints, credential-file access, token handling, `claude update`, Claude identity constants, branding, release links, or dependencies removed by the Codex port.
- Agents never run commit-producing cherry-picks. The user performs history operations after reviewing the proposed import.

## Review flow

1. Fetch without changing the worktree:

   ```powershell
   git fetch upstream --tags
   ```

2. Enumerate every commit in the full range. Do not add a path filter here; mixed UI commits can touch `app.py`, settings, tests, or docs:

   ```powershell
   git log --oneline --reverse <last-reviewed-sha>..upstream/main
   ```

3. Inspect each commit with `git show --stat <sha>` and then its full patch. Classify it as UI-only, mixed UI/provider, Claude backend, docs, or irrelevant.
4. Record skipped commits and the reason in **Review history**. Advance the last-reviewed SHA only after every commit through that SHA has been classified.
5. Create a temporary import branch. For a genuinely UI-only commit, the user may run `git cherry-pick -x <sha>`. Manually port only the provider-neutral portion of mixed commits.
6. Review every conflict against `AGENTS.md` and the revision-5 design. Preserve the Codex adapter, app-server lifecycle, no-credential boundary, Windows identities, and fork URLs.
7. After each imported change, run the full native-Windows unit suite, perform a clean build and frozen smoke, then run the official Claude EXE beside the Codex EXE and verify independent icons, mutexes, autostart entries, settings, restart, and quit behavior.
8. Add one **Imported changes** row per upstream commit incorporated and update the last-reviewed SHA.

Useful second-pass path view after the full commit enumeration:

```powershell
git log --oneline <last-reviewed-sha>..upstream/main -- usage_monitor_for_claude/app.py usage_monitor_for_claude/popup.py usage_monitor_for_claude/popup usage_monitor_for_claude/tray_icon.py usage_monitor_for_claude/formatting.py usage_monitor_for_claude/settings.py locale tests docs README.md CHANGELOG.md
```

## Review history

| Review date | Upstream range | Last reviewed SHA | Imported | Skipped / notes |
|---|---|---|---|---|
| 2026-07-15 | Port baseline | `f9224c2667ce7210464590d1e5e3f5d8637c8c69` | Baseline fork | Codex provider port begins from this upstream state |
| 2026-07-19 | `f9224c2..a3503e9` (upstream v1.20.0 plus one maintainer commit) | `a3503e9a49c0028d8c5db6897dcd3964746bdd15` | 32 provider-neutral commits were manually ported, adapted, or verified as already covered | `d4b67c3` reads Claude credentials; `a1b945c` notification-logo integration is deferred; `22bb349` changes dormant paid-credit currency UI; `de3a73f` and `d363b81` add WSL/custom Claude CLI behavior; `e160637` is the upstream release bump; `a3503e9` is upstream-only maintainer tooling |

## Port verification history

| Date | Codex CLI | Result | Notes |
|---|---|---|---|
| 2026-07-16 | 0.140.0 | Live wire probe passed | Verified `initialize`/`initialized`, `account/read`, `account/rateLimits/read`, keyed-bucket preference, nested credits metadata, and unrelated-notification tolerance. No exact authentication-error code was observed, so the production auth-code set remains empty. |
| 2026-07-16 | 0.140.0 | Native Windows build and process smoke passed | `UsageMonitorForCodex.exe` 1.0.0 ran beside the official `UsageMonitorForClaude.exe` 1.19.0 with independent process identities and autostart values. Hard-terminating the Codex application child reaped its app-server Job child without disturbing Claude; terminating Claude did not disturb Codex. |

The optional external-login reload experiment was not performed: verification did not automate logout, credential-store changes, or login. The ten-minute healthy-child TTL and every-tenth-error-cadence recycle therefore remain required safety bounds until a future manual, opt-in experiment records otherwise.

## Imported changes

| Date | Upstream SHA | Method | Notes |
|---|---|---|---|
| 2026-07-19 | `2bb37e5` | Manual Codex port | Wake the popup dismiss pump during close so hooks are released while pinned |
| 2026-07-19 | `5646050` | Manual Codex port | Treat the first height report as a change even at the initial window height |
| 2026-07-19 | `8ff9e47` | Manual Codex port | Fail closed when a differently privileged instance owns the mutex |
| 2026-07-19 | `958136f` | Manual Codex port | Prove the old instance is gone before accepting a recreated mutex |
| 2026-07-19 | `0b976f4` | Existing Codex behavior verified | Generation-atomic provider results already preserve profile state on a failed profile read |
| 2026-07-19 | `18404a3` | Manual Codex port | Keep popup-triggered poll push-forwards out of the pre-reset danger window |
| 2026-07-19 | `978c4af` | Manual Codex port | Recognize Chinese, Hindi, and Indonesian Windows locale names |
| 2026-07-19 | `df86f18` | Manual Codex port | Tolerate null account and organization sections in popup profile data |
| 2026-07-19 | `3823775` | Adapted Codex port | Skip non-dict tooltip fields; dynamic icon-field resolution already filters them |
| 2026-07-19 | `566bc9a` | Manual Codex port | Skip IDE extension directories that cannot be enumerated |
| 2026-07-19 | `66461c5` | Manual Codex port | Re-read and match the holder PID after the replacement dialog |
| 2026-07-19 | `67b0273` | Manual Codex port | Read settings as UTF-8 with optional BOM |
| 2026-07-19 | `7049fbb` | Manual Codex port | Lock and swap deferred notifications, then flush promptly on return |
| 2026-07-19 | `d5f8f3b` | Manual Codex port | Treat blank event commands as disabled and reject blank list entries |
| 2026-07-19 | `d8e7b45` | Manual Codex port | Deduplicate simultaneous quota-reset notifications |
| 2026-07-19 | `b2f5516` | Existing Codex behavior verified | Stateless adapter already returns the recovery retry result; added composed 429/backoff coverage |
| 2026-07-19 | `c6656ec` | Manual Codex port | Re-anchor cooldown, backoff, and poll targets after backward clock jumps |
| 2026-07-19 | `f8cbdbf` | Manual Codex port | Retry transient popup update failures without advancing dedup markers |
| 2026-07-19 | `125158a` | Manual Codex port | Keep the theme watcher alive after a callback failure |
| 2026-07-19 | `404be58` | Manual Codex port | Serialize resize, show, and cross-DPI correction paths |
| 2026-07-19 | `11c6782` | Manual Codex port | Rebuild popup bars when quota keys change without a count change |
| 2026-07-19 | `8eda635` | Manual Codex port | Clamp pre-exhaustion tray glyphs to 99 |
| 2026-07-19 | `c1213d3` | Manual Codex port | Preserve overage-bar meaning when elapsed time reaches 100 percent |
| 2026-07-19 | `d707104` | Manual Codex port | Recompute each weekly divider from its local calendar date across DST |
| 2026-07-19 | `d2785fe` | Adapted Codex port | Preserve drive-root `--codex-home` values |
| 2026-07-19 | `d6dd959` | Adapted Codex port | Redact Codex home paths case-insensitively and on path boundaries |
| 2026-07-19 | `964f51b` | Manual Codex port | Fall back when `SetProcessDpiAwarenessContext` is unavailable |
| 2026-07-19 | `8210b85` | Manual Codex port | Correct reset-alignment documentation to match the danger-window invariant |
| 2026-07-19 | `0df5b16` | Manual Codex port | Use identical centering expressions for created and updated popup markers |
| 2026-07-19 | `af1c4c5` | Manual Codex port | Export `BAR_DIVIDER` from the settings module |
| 2026-07-19 | `0d0a892` | Adapted Codex port | Isolate single-instance tests from the live default instance |
| 2026-07-19 | `42029a5` | Adapted Codex port | Isolate tray rendering tests from machine-local icon settings |
