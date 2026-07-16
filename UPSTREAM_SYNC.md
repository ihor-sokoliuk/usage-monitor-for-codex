# Upstream Reconciliation Ledger

- Upstream: https://github.com/jens-duttke/usage-monitor-for-claude
- Previous complete review point: `a3503e9a49c0028d8c5db6897dcd3964746bdd15`
- Owner-authorized full-rebase target: `5cbccc5e6f20a03efbc6779cc3c6d8e621acdef2`
- Original Codex tip: `cbd5996`
- Fork product version remains `1.20.0`; no release is implied by this migration.

## Scope and policy

The owner authorized a complete isolated rebase including Linux on 2026-10-23. This supersedes the earlier selective-only and Windows-only migration policy. Preserve the complete upstream history and use its current platform/UI structure as the foundation. Adapt provider-specific behavior to fixed local Codex app-server stdio. Do not restore credential-store inspection, direct provider HTTP, unsupported billing/prepaid data, upstream application identity, or upstream publication targets.

The migration does not authorize remote publication, a shared-branch rewrite, a release, deployment, or replacement/restart of the running monitor. Preserve the primary checkout and its existing user changes. Future history operations require exact owner authorization.

## Reconciliation method

1. Pin both source heads and enumerate the entire commit range without a path filter.
2. Classify every commit, including docs, merges, releases and infrastructure. Review full patches where needed and reconcile every changed path against the complete upstream tree.
3. Preserve native Windows behavior and explicit Linux backends. Keep Codex quota/account/cache invariants, provider lifecycle, CLI discovery/update, sanitized logs and per-home identity.
4. Verify the rebased baseline independently before carrying any pending user change as an uncommitted overlay. Run full native Windows and applicable Linux suites; distinguish headless, virtual-X11/D-Bus and real-desktop checks.
5. Build and smoke-test Windows only with native Windows Python. Use synthetic isolated homes for identity checks, never live credential manipulation. Review final diffs and private-data scans before handoff.
6. Record exact verification separately. A disposition below records the design reconciliation; it is not by itself proof of successful runtime validation.

## Fork path map

| Upstream | Fork disposition |
|---|---|
| `claude_cli.py` and its tests | `codex_cli.py`, Codex discovery/version/update only |
| Direct provider HTTP in `api.py` | Codex normalization/classification plus local `app_server.py` transport |
| Credential/token refresh machinery | Removed; account state and bounded recovery come from app-server RPCs |
| `usage_monitor_for_claude.spec` and product icon | Codex spec, executable, and icon |
| `usage-monitor-for-claude` source launcher | `usage-monitor-for-codex`; internal module remains `usage_monitor_for_claude` |
| Platform identity, autostart, lock/mutex, notification logo | Distinct Codex names and per-home suffixes |
| Extra usage, currency and prepaid display | Dormant compatibility scaffolding only; no Codex data or active guide |
| Upstream WinGet publisher/watcher | Removed; no fork registration or credentials are assumed |
| Optional local signing | Retained, disabled without owner-supplied ignored signing configuration |
| Fork `codex-v*` release workflow | Retained; derives release notes from fork changelog and links to fork README |

## Complete upstream commit inventory

The 51 commits after the previous review point through the pin are all represented below. **Applied** preserves provider-neutral upstream behavior; **adapted** retains the change with Codex semantics; **dormant** retains only historical/inert scaffolding; **infrastructure-only** preserves history while reconciling fork tooling and publication policy.

| Commit | Disposition | Reconciliation |
|---|---|---|
| `32444c8` | dormant | feat: support uncapped extra usage (popup display, tray indicator, spend-amount alerts) (#70) - Extra-usage UI retained as dormant scaffolding; Codex data cannot activate it. |
| `3ff45f9` | dormant | docs: credit @joeklittle and note extra-usage spend alerts in the feature list - Historical credit retained; no active Codex spending feature is advertised. |
| `aecd497` | adapted | docs: qualify the read-only claim in README and PRIVACY.md - Document local writes and external Codex, updater, webview and command boundaries. |
| `9f1b422` | applied | feat: add numbers icon style with two stacked percentages (#78) - Retain complete upstream behavior and relevant regression coverage. |
| `d5fc89d` | adapted | fix: refresh usage data immediately after an account switch - Preserve atomic Codex account/usage operations, auth revisions and bounded child refresh. |
| `1b10ab9` | infrastructure-only | ci: publish new releases to WinGet automatically - Upstream WinGet publisher removed; no fork package registration or token is assumed. |
| `64fdff8` | adapted | fix: decode Claude CLI output as UTF-8 regardless of the system code page - Decode Codex CLI diagnostics/version output as UTF-8 without logging raw output. |
| `87d89b2` | infrastructure-only | chore: release v1.21.0 - Retain historical upstream release notes; do not bump fork version. |
| `48b9de7` | infrastructure-only | docs: document the WinGet install path and monitor that channel - Retain historical upstream notes; remove active upstream WinGet installation claims. |
| `869f51c` | applied | fix: end the replaced instance with a success exit code - Retain complete upstream behavior and relevant regression coverage. |
| `3e2cfc3` | applied | docs: cut justification prose and duplication from the documentation - Retain complete upstream behavior and relevant regression coverage. |
| `501c3ea` | infrastructure-only | chore: point feature requests to Discussions from the issue chooser - Issue chooser targets the fork and its README antivirus section. |
| `eecd55c` | adapted | feat: add Linux support alongside Windows - Retain platform separation; add Codex Linux provider supervisor and identities. |
| `0ca00a6` | adapted | feat: start the Linux app from any directory with a launcher script - Rename source launcher to usage-monitor-for-codex; retain internal package name. |
| `8a8df15` | applied | fix: run on_reset_command when the reset quota has no active window - Retain complete upstream behavior and relevant regression coverage. |
| `b00aede` | adapted | fix: verify TLS certificates against the Windows certificate store - Direct provider HTTP/TLS client and truststore dependency removed; Codex owns networking. |
| `7030a81` | adapted | fix: restore the Windows test suite after the platform split - Platform tests use their native backend while retaining Codex regressions. |
| `b5fc52a` | infrastructure-only | chore: release v1.22.0 - Retain historical upstream release notes; do not bump fork version. |
| `d89df18` | infrastructure-only | chore: add preflight and build verification to the release command - Retain release preflight/verification guidance; fork owner publishes separately. |
| `4344671` | infrastructure-only | chore: add a temporary token diagnostic workflow - Temporary upstream diagnostic workflow remains historical only. |
| `3b4a001` | infrastructure-only | chore: trigger the token diagnostic on push - Temporary upstream diagnostic trigger remains historical only. |
| `2851b30` | infrastructure-only | chore: fix the diagnostic workflow syntax - Temporary upstream diagnostic fix remains historical only. |
| `c374112` | infrastructure-only | chore: remove the temporary token diagnostic workflow - Final upstream tree already removes the temporary diagnostic workflow. |
| `4f49926` | infrastructure-only | chore: note the winget-pkgs fork sync the submission depends on - Upstream package-fork synchronization does not apply to this fork. |
| `bcc7bde` | adapted | fix: keep polling on a reduced cadence while idle or locked - Keep reduced away polling, capped at 600 seconds for Codex TTL and auth freshness. |
| `7f15085` | adapted | fix: keep verbose output in the caller's stdout/stderr redirection - Retain caller redirection and Codex sanitized rotating logging. |
| `39bba11` | adapted | fix: name the CLI and the login command in the auth messages - All active authentication messages name Codex CLI and codex login. |
| `8d7899e` | dormant | feat: show the prepaid usage-credits balance in the popup (#82) - Prepaid fetch removed; credits dropped before popup serialization. |
| `9e6ab88` | adapted | docs: explain the antivirus false positive above the download link - Explain checksums and potential detections without asserting every warning is false. |
| `3c5308d` | adapted | docs: list the Codex and Copilot monitors as related projects - Preserve upstream attribution and use fork product/release links. |
| `fe1b3b8` | adapted | Merge branch 'main' of https://github.com/jens-duttke/usage-monitor-for-claude - Retain complete merged upstream ancestry; reconcile final tree to Codex. |
| `259393e` | adapted | docs: name the plans the monitor covers - Describe ChatGPT usage and explicit non-ChatGPT authentication states. |
| `61fc445` | adapted | fix: hide quota types the API announces but has not activated (#91) - Use normalized Codex quota dictionaries; retain valid duration-less windows. |
| `3bd6d62` | adapted | docs: state which quota types get a bar and event variables - Describe arbitrary normalized quota fields and dynamic event variables. |
| `063758d` | adapted | refactor: derive the config directory from instance_id everywhere (#96) - Use Codex-home derivation and per-home identities on both platforms. |
| `b4a258f` | adapted | docs: log the verbose redaction fix for a symlinked home directory - Retain sanitized path diagnostics without credential metadata. |
| `62242da` | infrastructure-only | feat: code sign the release EXE - Retain optional local signing and tests; no certificate/public signing claim is assumed. |
| `987fc00` | infrastructure-only | chore: release v1.23.0 - Retain historical upstream release notes; do not bump fork version. |
| `84270bb` | adapted | fix: show windows notifications under the app's own identity - Use distinct Codex notification identity and Codex notification logo. |
| `07d581d` | applied | feat: open the popup on a left-click on KDE Plasma (#102) - Retain complete upstream behavior and relevant regression coverage. |
| `4a2cd6e` | applied | fix: open the popup above a bottom panel on Linux (#103) - Retain complete upstream behavior and relevant regression coverage. |
| `6336b31` | applied | docs: log the bottom-panel popup fix on Linux - Retain complete upstream behavior and relevant regression coverage. |
| `fd40bec` | applied | fix: reuse the popup window on Linux instead of creating one per opening (#106) - Retain complete upstream behavior and relevant regression coverage. |
| `86e4723` | applied | fix: return a pointer-sized LRESULT from the popup's low-level hooks (#105) - Retain complete upstream behavior and relevant regression coverage. |
| `e1be0c6` | applied | Merged - thank you, @nerfarrow! This was an excellent contribution. The register-level reproduction in #104 made the root cause easy to verify, and the fix is minimal and well-tested. I could reproduce the mechanism on Python 3.12.10 here, and the new `TestHookSignatures` fail as soon as `_LRESULT` is narrowed back to `c_long`. - Retain complete upstream behavior and relevant regression coverage. |
| `39886b1` | adapted | docs: show the PowerShell variant for collecting the verbose log - Use Codex diagnostic names and document existing adjacent sanitized logs. |
| `5f27127` | applied | fix: size the popup to the scale WebKit renders at on X11 (#107) - Retain complete upstream behavior and relevant regression coverage. |
| `6c176f1` | dormant | perf: read the prepaid balance only while the popup is open - No Codex prepaid request exists; lazy upstream billing read is removed. |
| `31e2b32` | infrastructure-only | chore: release v1.24.0 - Retain historical upstream release notes; do not bump fork version. |
| `045079f` | applied | feat: support popup field exclusions (#113) - Retain complete upstream behavior and relevant regression coverage. |
| `5cbccc5` | applied | docs: credit the reporter and contributor of popup field exclusions - Retain complete upstream behavior and relevant regression coverage. |

## Earlier selective-port history

The following entries describe the historical migration before this full rebase. Their selective-policy wording is historical and does not override the scope above.

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
