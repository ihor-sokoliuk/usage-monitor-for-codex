# Full Upstream Codex Rebase Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. The owner authorized collaboration with Claude for this migration.

**Goal:** Rebase the full Codex fork onto pinned upstream while retaining Codex-only monitoring and adding upstream Linux support.

**Architecture:** Keep the complete upstream platform/UI structure and reconcile the Codex provider boundary into it. Resolve history in an isolated branch, then preserve the owner's existing local shutdown changes as an uncommitted overlay. Use sanitized Claude review advice and independent evidence, not reviewer agreement, for acceptance.

**Tech Stack:** Python, unittest, Pillow, pystray, pywebview, Windows Job objects, Linux process lifecycle, PyInstaller, Docker for Linux validation.

**Spec:** `docs/superpowers/specs/2026-10-23-full-upstream-codex-rebase-design.md`

## Global Constraints

- Upstream pin: `5cbccc5e6f20a03efbc6779cc3c6d8e621acdef2`; original Codex tip: `cbd5996`.
- No monitor credential-store access or direct provider network access; fixed app-server RPCs only.
- Preserve original checkout and existing local changes; no remote publication or live runtime replacement.
- Retain the internal package name; all active user-facing identity and commands use Codex.
- Windows builds/tests use the activated native Windows venv on NTFS; Linux checks use Linux Python.

## Review Focus

- Parent death and blocked descendants must not leak Linux app-server children or weaken Windows Job cleanup.
- The reduced idle cadence must not bypass Codex auth-revision observation, reset alignment, or quota-fetch cooldown.
- Platform extraction must not restore credential checks, Anthropic endpoint calls, raw payload logging, or a Claude subprocess.
- New display filters must keep valid duration-less Codex quotas visible and preserve dynamic keyed buckets.
- Source, frozen Windows and Linux launcher identities/configuration/logging must remain isolated across homes and from the Claude monitor.

### Task 1: Inventory and preserve the starting state

**Files:** `UPSTREAM_SYNC.md`, private Git-directory migration snapshot, the design and this plan.

- [x] Pin both heads; inventory all upstream commits and changed paths without a path filter.
- [x] Snapshot the primary checkout's tracked patch and named untracked shutdown test outside publishable files.
- [x] Verify the isolated branch baseline using the activated Windows venv.
- [x] Obtain Claude's bounded review of the migration design; reconcile findings against owner requirements.

### Task 2: Rebase and reconcile the complete tree

**Files:** All paths conflicted by replaying the fork onto upstream; platform package, launcher, assets, workflows, docs and locale files.

- [x] Rebase only the isolated local branch onto the pinned upstream, retaining the original fork tip as a recovery reference.
- [x] Resolve UI/platform conflicts from current upstream behavior; preserve Codex provider modules and tests. Keep all upstream history, including changes whose Claude-specific implementation must be adapted or made dormant.
- [x] Preserve distinct Codex identity, CLI discovery/update, normalized fields, profile/cache policy and logging; remove active upstream credential and HTTP paths.
- [x] Carry the pre-existing local changes into the rebased workspace as an uncommitted overlay, adapting paths without discarding them.
- [x] Verify upstream ancestry and a complete path-by-path Codex-vs-upstream reconciliation inventory.

### Task 3: Make Codex lifecycle cross-platform

**Files:** `usage_monitor_for_claude/app_server.py`, new provider lifecycle backend module(s), `codex_cli.py`, `instance_id.py`, `logging_setup.py`, `tests/test_app_server*.py`, Linux lifecycle/discovery tests.

- [x] Add regressions for importing the provider on Linux, real fake-child JSONL, shutdown, restart, spawn failure, descendants and monitor-parent exit. Demonstrate failures before the implementation changes that address them.
- [x] Isolate Windows Job APIs from portable transport; implement Linux child containment/reaping and discovery without a credential path.
- [x] Retain fixed method literals, whole-operation retry, lock ordering, bounded redacted diagnostics and the existing graceful-shutdown protections.
- [x] Verify lifecycle regressions and the provider/cache test suites on both platforms.

### Task 4: Integrate upstream behavior with Codex data

**Files:** `app.py`, `cache.py`, `popup.py`, `formatting.py`, `settings.py`, `tray_icon.py`, `platforms/*`, locale files and their tests.

- [x] Add/run adapted upstream regressions for numbers icons, exclusions, idle/visible-popup cadence, hook signatures, UTF-8/redirection and notification fallback.
- [x] Reconcile arbitrary quota durations, model labels, dynamic tray fallback, account revisions, recovery, safe poll scheduling and deferred notifications with the upstream implementation.
- [x] Preserve legacy quick-action settings and document any intentional event-name compatibility behavior.
- [x] Run complete Windows and Linux suites; never remove a valid regression merely to make the migration pass.

### Task 5: Document and verify the complete application

**Files:** `AGENTS.md`, `UPSTREAM_SYNC.md`, README/privacy/configuration/event/API docs, changelog, spec/build/workflows and relevant privacy/identity tests.

- [x] Update rules and documentation for the owner-authorized full rebase and Linux support; record every upstream commit's disposition.
- [x] Run the full Windows suite, boundary/privacy scans, Linux suite and available virtual-display Linux smoke.
- [x] Perform a clean Windows build and an isolated frozen smoke without live authentication, updater, runtime replacement, or unrelated processes.
- [x] Review the final upstream delta and original-fork delta, reconcile material findings, and rerun the affected verification.
- [x] Confirm primary-checkout preservation and report exact pass counts, remaining desktop limitations and the isolated branch/artifact paths.

## Review-driven checks

- Task 2 must pass the committed rebased baseline before applying the owner's pending shutdown overlay; Task 5 verifies the overlay separately.
- Task 3 adds a Linux supervisor/control-pipe/subreaper/pidfd lifecycle and tests all exits plus an unrelated sentinel, Linux updater serialization, and Linux identity/config/log/launcher isolation.
- Task 4 adds credits-to-popup inertness coverage, unknown Linux lock-state privacy coverage, and the 600-second Codex idle-cadence cap.
- Task 5 attempts real virtual-display GTK/WebKit/tray startup and labels unsupported/unverified desktop paths accurately.

## Verification record

The complete inventory covers 51 unique upstream commits and 87 changed upstream paths. The pin is an ancestor of isolated branch `agent/codex-upstream-rebase` at `ca80f5e`; pending shutdown adaptations and final review corrections remain uncommitted. The primary checkout remains at its original tip with its tracked patch and named untracked shutdown test matching the private pre-migration snapshots.

| Check | Result |
|---|---|
| Native Windows baseline before pending overlay | 1,314 tests, 23 skipped, success |
| Linux integration baseline before pending overlay | 1,351 tests, 13 skipped, success |
| Final native Windows suite, independently run by the reviewer | 1,344 tests, 26 skipped, success |
| Final Linux suite, network-disabled Ubuntu 24.04 container | 1,381 tests, 30 skipped, success |
| Clean native Windows build | Python 3.14.6 / PyInstaller 6.21.0; unsigned 15.4 MB executable |
| Final executable SHA-256 | `85f76687676e67ebbc070cb5225143a56859a956e8cfe3e7da3b856eebf4fc11` |
| Final frozen Windows smoke | Synthetic local CLI; startup/profile/three quotas, WebView2 popup at 150% DPI, tray double-click quick action, and Job cleanup after hard monitor termination passed |
| Provider/privacy and publishable-source scans | No active upstream provider calls, credential paths, private home/checkout paths or token material; local instructions and generated evidence remain ignored |
| Fresh-context source review | No outstanding Critical or Important findings after the reset-command compatibility correction; idle-glyph documentation corrected |

Claude's initial migration-design review and one re-review supplied advisory lifecycle, privacy, compatibility and validation requirements. Those requirements were reconciled into implementation and tests. The independent final source reviewer separately examined the actual pending overlay against upstream and the original fork.

Linux smoke used immutable baseline and pending-overlay snapshots, the real module entrypoint, GTK/WebKit, AppIndicator, Xvfb/Openbox and D-Bus with networking disabled. A synthetic local Codex CLI and notification service verified three quota fields, profile display, settled popup rendering, pinning, startup and quick actions, actual restart and quit, no overlapping provider generations, cleanup of owned descendants, and survival of an unrelated sentinel. The final reset-hook correction was additionally covered by the final Linux suite.

The frozen Windows smoke ran the unchanged final artifact beside the existing Codex and Claude monitors with an isolated home, fake native CLI and automatic updates disabled. It verified real popup rendering, events, and termination of the live provider plus a long-running descendant when the exact test monitor was killed. Automated menu selection did not verify frozen Quit or Restart. Injecting pystray's stop message bypassed the application's quit callback and was not a valid quit test; no product hang is inferred from that attempt. Shared notification identity was restored to its captured state, all exact test processes/runtime/logs/settings/cache were removed, the test autostart entry was absent, and existing monitor processes survived unchanged.

Live Codex authentication, real account switching, and actual GNOME/KDE/Wayland desktop integration were not exercised. Linux remains experimental; external SIGKILL/OOM death of its supervisor is a documented containment limitation. No remote push, release, live runtime replacement, or restart of the existing monitors was performed. Fork version `1.20.0` is retained until a separately authorized release. Before publication, review Git author name/email metadata; a GitHub noreply email is appropriate when privacy is desired.

## Follow-up verification and publication scope

The owner subsequently requested completion of frozen Windows Quit/Restart verification, version alignment, source commits and a push to the fork, and updating the locally running application. Upstream was fetched again and remained at the pinned commit with version `1.24.0`. Runtime, PE metadata, development preview and dated fork changelog now agree on that version.

Fresh native Windows verification passed 1,344 tests with 26 skips; the Linux container passed 1,381 tests with 30 skips. The clean native Windows build has FileVersion and ProductVersion `1.24.0.0`; SHA-256 is `d6c576d1d7e6e9e8c7c826ba452e0ef50954505ee75d47b85a9b5797453b78da`.

The unchanged versioned executable passed actual native tray-menu Restart and Quit callbacks, invoked through the observed MSAA menu children for the exact isolated test-process image. Restart created a fresh monitor generation after the prior provider and descendant exited. Quit closed the second monitor, provider and descendant without forced cleanup. An unrelated sentinel survived, the updater was not invoked, test state and notification identity were restored, and the existing monitors remained unchanged. This supersedes the frozen-menu verification limitation in the initial-phase record above.

Publication preserves the already-published fork ancestry alongside the rebased upstream ancestry, retaining the verified source tree and avoiding a force-push. Source publication uses a branch and pull request. GitHub release/tag creation and pull-request merge are outside this follow-up request. Local executable replacement is authorized separately from publication and uses a rollback copy plus post-start application-log verification; private machine paths and runtime evidence remain outside tracked files.
