# Upstream v1.20 Selective Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Subagents are not used because the
> active repository instructions prohibit unrequested delegation.

**Goal:** Selectively port upstream v1.20 provider-neutral reliability fixes
while preserving the Codex provider and product boundaries.

**Architecture:** Translate upstream behavior into the existing Codex modules
and tests. Keep the adapter and app-server boundary unchanged, use focused
test-first cycles, and record every reviewed upstream SHA in the ledger.

**Tech Stack:** Windows Python, `unittest`, Win32 through `ctypes`, pywebview,
pystray, Pillow, JavaScript executed by the existing popup test harness, and
PyInstaller.

## Global Constraints

- Use native Windows Python from the activated `.venv`.
- Do not access Codex credential paths or stores.
- Do not restore Anthropic networking, token handling, Claude updater logic,
  Claude runtime branding, or WSL Codex CLI selection.
- Do not create commits, branches, pushes, tags, releases, merges, rebases, or
  cherry-picks.
- Preserve the existing untracked `.agents/` directory.
- Use tests before production changes and run the full suite after each task.
- Keep comments, docstrings, public APIs, and logging consistent with
  `AGENTS.md`.

---

### Task 1: Record baseline and isolate tests

**Files:**
- Modify: `tests/test_single_instance.py`
- Modify: `tests/test_app.py`

**Produces:** Kernel-object round-trip tests that cannot modify the production
holder record and tray tests independent of local settings.

- [ ] Stop only verified `UsageMonitorForCodex.exe` processes.
- [ ] Verify no matching production process remains.
- [ ] Activate `.venv` and run `python -m unittest discover -s tests`.
- [ ] Verify no matching production process appeared during the suite.
- [ ] Patch `config_dir_suffix` in real kernel-object tests to
  `'_test' + str(os.getpid())`.
- [ ] Add a test comparing the live holder record before and after the isolated
  `_store_holder_info()` call.
- [ ] Pin `usage_monitor_for_claude.app.ICON_FIELDS` to
  `['five_hour', 'seven_day']` in `_make_app`.
- [ ] Run the focused single-instance and app tests, then the full suite.
- [ ] Relaunch the canonical monitor and verify its process is running.

### Task 2: Port the single-instance safety unit

**Files:**
- Modify: `usage_monitor_for_claude/single_instance.py`
- Modify: `tests/test_single_instance.py`
- Modify: all `locale/*.json`

**Produces:** Fail-closed mutex creation and PID-safe replacement behavior.

- [ ] Add failing tests for access-denied NULL mutex creation, unexpected NULL
  creation errors, a changed post-dialog holder PID, and the localized
  replacement-failed dialog.
- [ ] Run the focused tests and confirm each fails for the missing behavior.
- [ ] Add `_ERROR_ACCESS_DENIED`, validate the initial mutex handle and last
  error, close only valid handles, and fail closed on unexpected creation
  errors.
- [ ] Re-read holder information after the confirmation dialog and terminate
  only when the PID still matches.
- [ ] Preserve the existing replacement mutex recreation proof.
- [ ] Add generic `replace_failed` locale text to all shipped locales.
- [ ] Run focused tests and the full suite.

### Task 3: Port popup lifecycle and concurrency fixes

**Files:**
- Modify: `usage_monitor_for_claude/popup.py`
- Modify: `tests/test_popup.py`

**Produces:** Deterministic popup shutdown, initial display, resizing, and
update recovery.

- [ ] Add failing tests for dismiss-pump shutdown on close, an initial 400-pixel
  height report, retry after a failed update push, and serialized height
  reports.
- [ ] Add `_WM_QUIT`, create the message queue before publishing `_pump_tid`,
  post quit on every close path, and clear the thread ID on exit.
- [ ] Initialize `_last_height` to zero.
- [ ] Serialize height check, resize, and first-show with `_geometry_lock`; use
  the same lock when reasserting drag size.
- [ ] Commit update deduplication markers only after successful JavaScript
  evaluation and log transient failures before retrying.
- [ ] Run focused tests and the full suite.

### Task 4: Port popup JavaScript fixes

**Files:**
- Modify: `usage_monitor_for_claude/popup/popup.js`
- Create: `tests/test_popup_js.py`

**Produces:** Correct bar identity and stable two-pixel marker positioning.

- [ ] Add the upstream provider-neutral JavaScript test harness with tests for
  equal-count field replacement and marker/divider stability.
- [ ] Run `python -m unittest tests.test_popup_js` and confirm failures.
- [ ] Store each bar's field in `dataset.key`.
- [ ] Rebuild when field keys differ even if the count is unchanged.
- [ ] Use `calc(<percent>% - 1px)` for updated markers and dividers.
- [ ] Run focused tests and the full suite.

### Task 5: Port tray and formatting fixes

**Files:**
- Modify: `usage_monitor_for_claude/tray_icon.py`
- Modify: `usage_monitor_for_claude/formatting.py`
- Modify: `usage_monitor_for_claude/settings.py`
- Modify: `tests/test_tray_icon.py`
- Modify: `tests/test_formatting.py`
- Modify: `tests/test_settings.py`

**Produces:** Resilient theme updates, correct glyphs and overage bars,
DST-safe dividers, and a complete settings API.

- [ ] Add failing tests for theme callback recovery, 99.5-to-99.999 glyph
  display, overage at a 100 percent time clamp, DST midpoint dividers, and
  `BAR_DIVIDER` export.
- [ ] Catch and sanitize-log theme callback failures without ending the watcher.
- [ ] Clamp the percentage glyph to 99 below actual exhaustion.
- [ ] Preserve overage semantics when elapsed time is clamped to 100.
- [ ] Generate each local midnight from its calendar date so timezone offsets
  are recalculated across DST.
- [ ] Export `BAR_DIVIDER`.
- [ ] Run focused tests and the full suite.

### Task 6: Port settings, locale, discovery, and diagnostic fixes

**Files:**
- Modify: `usage_monitor_for_claude/settings.py`
- Modify: `usage_monitor_for_claude/i18n.py`
- Modify: `usage_monitor_for_claude/codex_cli.py`
- Modify: `usage_monitor_for_claude/instance_id.py`
- Modify: `usage_monitor_for_claude/verbose.py`
- Modify: `usage_monitor_for_claude/__main__.py`
- Modify: corresponding `tests/test_*.py`

**Produces:** Robust Windows configuration, locale detection, CLI discovery,
path handling, redaction, and old-Windows startup.

- [ ] Add failing tests for UTF-8 BOM settings, empty command strings and list
  entries, Windows Chinese/Hindi/Indonesian locale names, unreadable extension
  directories, drive-root `--codex-home`, case-insensitive boundary-aware home
  redaction, and missing DPI API.
- [ ] Read settings with `utf-8-sig`; normalize empty string commands to `[]`
  and reject empty command-array entries.
- [ ] Add the Windows locale-name mappings.
- [ ] Wrap each extension-directory enumeration in `try/except OSError`.
- [ ] Restore the root separator for bare drive letters after trimming.
- [ ] Redact only exact home paths or descendants using case-insensitive
  Windows comparison.
- [ ] Fall back when `SetProcessDpiAwarenessContext` is unavailable.
- [ ] Run focused tests and the full suite.

### Task 7: Port polling and notification fixes

**Files:**
- Modify: `usage_monitor_for_claude/app.py`
- Modify: `usage_monitor_for_claude/cache.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_cache.py`
- Modify: `tests/test_api.py`

**Produces:** Reset-safe scheduling, clock-jump recovery, thread-safe deferred
notifications, deduplicated reset toasts, and composed recovery-429 coverage.

- [ ] Add failing tests for popup fetches landing in the pre-reset danger
  window, backward clock jumps in app and cache, a deferral arriving during a
  flush, prompt flush after return, several simultaneous resets, and a recovery
  retry whose final response is rate-limited.
- [ ] Keep pushed-forward targets out of the last
  `POLL_FAST - RESET_BUFFER` seconds before reset.
- [ ] Re-anchor the app wait target after backward wall-clock jumps and clamp
  stale cache cooldown/backoff timestamps.
- [ ] Guard deferred notification state with `_notify_lock`, atomically swap the
  pending dictionary during flush, and flush whenever the user is present.
- [ ] Aggregate reset detection before sending the generic reset toast.
- [ ] Verify the existing adapter final-error result arms cache backoff without
  importing Claude recovery code.
- [ ] Run focused tests and the full suite.

### Task 8: Documentation and upstream ledger

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `UPSTREAM_SYNC.md`

**Produces:** Accurate user-facing release notes and one disposition per
reviewed upstream SHA.

- [ ] Add concise `[Unreleased]` entries for imported user-visible fixes.
- [ ] Add one imported or skipped row for every SHA from `f9224c2..a3503e9`.
- [ ] Mark `958136f` as a partial manual port and `b2f5516` as covered plus a
  Codex regression test.
- [ ] Advance the last-reviewed SHA only after all 39 rows are present.
- [ ] Verify the documented count and SHA range mechanically.

### Task 9: Final verification and review

**Files:**
- Review all changed tracked files.

**Produces:** A tested, buildable, privacy-safe handoff with no repository
history changes.

- [ ] Run `python -m unittest discover -s tests`.
- [ ] Run `git diff --check`.
- [ ] Scan added lines for credential paths, Anthropic endpoints, token
  handlers, `claude update`, Claude runtime identities, and machine paths,
  allowing only the intentional internal package name and sync documentation.
- [ ] Run the clean native Windows PyInstaller build.
- [ ] Replace and relaunch the canonical runtime only after a successful build.
- [ ] Smoke the frozen Codex monitor and verify the Claude monitor remains
  independent.
- [ ] Review every changed file, test, changelog entry, and ledger row.
- [ ] Report exact verification commands and outcomes without committing.
