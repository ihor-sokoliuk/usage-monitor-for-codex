# Upstream Sync Ledger

- Upstream: https://github.com/jens-duttke/usage-monitor-for-claude
- Port baseline: `f9224c2667ce7210464590d1e5e3f5d8637c8c69`
- Last reviewed upstream SHA: `f9224c2667ce7210464590d1e5e3f5d8637c8c69`

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

## Port verification history

| Date | Codex CLI | Result | Notes |
|---|---|---|---|
| 2026-07-16 | 0.140.0 | Live wire probe passed | Verified `initialize`/`initialized`, `account/read`, `account/rateLimits/read`, keyed-bucket preference, nested credits metadata, and unrelated-notification tolerance. No exact authentication-error code was observed, so the production auth-code set remains empty. |
| 2026-07-16 | 0.140.0 | Native Windows build and process smoke passed | `UsageMonitorForCodex.exe` 1.0.0 ran beside the official `UsageMonitorForClaude.exe` 1.19.0 with independent process identities and autostart values. Hard-terminating the Codex application child reaped its app-server Job child without disturbing Claude; terminating Claude did not disturb Codex. |

The optional external-login reload experiment was not performed: verification did not automate logout, credential-store changes, or login. The ten-minute healthy-child TTL and every-tenth-error-cadence recycle therefore remain required safety bounds until a future manual, opt-in experiment records otherwise.

## Imported changes

| Date | Upstream SHA | Method | Notes |
|---|---|---|---|
