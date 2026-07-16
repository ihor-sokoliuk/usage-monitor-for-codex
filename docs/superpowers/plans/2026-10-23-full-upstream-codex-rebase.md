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

- [ ] Pin both heads; inventory all upstream commits and changed paths without a path filter.
- [ ] Snapshot the primary checkout's tracked patch and named untracked shutdown test outside publishable files.
- [ ] Verify the isolated branch baseline using the activated Windows venv.
- [ ] Obtain Claude's bounded review of the migration design; reconcile findings against owner requirements.

### Task 2: Rebase and reconcile the complete tree

**Files:** All paths conflicted by replaying the fork onto upstream; platform package, launcher, assets, workflows, docs and locale files.

- [ ] Rebase only the isolated local branch onto the pinned upstream, retaining the original fork tip as a recovery reference.
- [ ] Resolve UI/platform conflicts from current upstream behavior; preserve Codex provider modules and tests. Keep all upstream history, including changes whose Claude-specific implementation must be adapted or made dormant.
- [ ] Preserve distinct Codex identity, CLI discovery/update, normalized fields, profile/cache policy and logging; remove active upstream credential and HTTP paths.
- [ ] Carry the pre-existing local changes into the rebased workspace as an uncommitted overlay, adapting paths without discarding them.
- [ ] Verify upstream ancestry and a complete path-by-path Codex-vs-upstream reconciliation inventory.

### Task 3: Make Codex lifecycle cross-platform

**Files:** `usage_monitor_for_claude/app_server.py`, new provider lifecycle backend module(s), `codex_cli.py`, `instance_id.py`, `logging_setup.py`, `tests/test_app_server*.py`, Linux lifecycle/discovery tests.

- [ ] Add regressions for importing the provider on Linux, real fake-child JSONL, shutdown, restart, spawn failure, descendants and monitor-parent exit. Demonstrate failures before the implementation changes that address them.
- [ ] Isolate Windows Job APIs from portable transport; implement Linux child containment/reaping and discovery without a credential path.
- [ ] Retain fixed method literals, whole-operation retry, lock ordering, bounded redacted diagnostics and the existing graceful-shutdown protections.
- [ ] Verify lifecycle regressions and the provider/cache test suites on both platforms.

### Task 4: Integrate upstream behavior with Codex data

**Files:** `app.py`, `cache.py`, `popup.py`, `formatting.py`, `settings.py`, `tray_icon.py`, `platforms/*`, locale files and their tests.

- [ ] Add/run adapted upstream regressions for numbers icons, exclusions, idle/visible-popup cadence, hook signatures, UTF-8/redirection and notification fallback.
- [ ] Reconcile arbitrary quota durations, model labels, dynamic tray fallback, account revisions, recovery, safe poll scheduling and deferred notifications with the upstream implementation.
- [ ] Preserve legacy quick-action settings and document any intentional event-name compatibility behavior.
- [ ] Run complete Windows and Linux suites; never remove a valid regression merely to make the migration pass.

### Task 5: Document and verify the complete application

**Files:** `AGENTS.md`, `UPSTREAM_SYNC.md`, README/privacy/configuration/event/API docs, changelog, spec/build/workflows and relevant privacy/identity tests.

- [ ] Update rules and documentation for the owner-authorized full rebase and Linux support; record every upstream commit's disposition.
- [ ] Run the full Windows suite, boundary/privacy scans, Linux suite and available virtual-display Linux smoke.
- [ ] Perform a clean Windows build and an isolated frozen smoke without live authentication, updater, runtime replacement, or unrelated processes.
- [ ] Review the final upstream delta and original-fork delta, reconcile material findings, and rerun the affected verification.
- [ ] Confirm primary-checkout preservation and report exact pass counts, remaining desktop limitations and the isolated branch/artifact paths.

## Review-driven checks

- Task 2 must pass the committed rebased baseline before applying the owner's pending shutdown overlay; Task 5 verifies the overlay separately.
- Task 3 adds a Linux supervisor/control-pipe/subreaper/pidfd lifecycle and tests all exits plus an unrelated sentinel, Linux updater serialization, and Linux identity/config/log/launcher isolation.
- Task 4 adds credits-to-popup inertness coverage, unknown Linux lock-state privacy coverage, and the 600-second Codex idle-cadence cap.
- Task 5 attempts real virtual-display GTK/WebKit/tray startup and labels unsupported/unverified desktop paths accurately.
