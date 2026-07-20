# Codex v1.20.0 Version Bump Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Version, build, install, restart, and publish the selectively synced
Codex monitor as v1.20.0.

**Architecture:** Keep the Python package version, Windows version resource,
changelog release section, and build-identity test synchronized. Build once,
verify the artifact, install it through the canonical runtime path with a
rollback copy, and publish the exact tested source commit to the existing pull
request workflow.

**Tech Stack:** Python 3, unittest, PyInstaller, PowerShell, native Windows
process and file APIs, Git, GitHub CLI.

## Global Constraints

- The application version is `1.20.0`; Windows file/product versions are
  `1.20.0.0`.
- Use native Windows Python from the activated `.venv`.
- Never run the packaged monitor from `dist`.
- Stop only the verified canonical-path process pair in the current interactive
  session.
- Restore the prior executable if installation or relaunch verification fails.
- Do not create a tag or GitHub release.
- Leave unrelated `.agents/` content untouched and unpublished.

---

### Task 1: Synchronize version metadata and release notes

**Files:**
- Modify: `usage_monitor_for_claude/__init__.py`
- Modify: `version_info.py`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_identity.py`

**Interfaces:**
- Produces: `usage_monitor_for_claude.__version__ == '1.20.0'`
- Produces: Windows version resource values `1.20.0.0`

- [ ] **Step 1: Add a failing version-consistency test**

  Assert the package version is `1.20.0` and the version resource contains
  `(1, 20, 0, 0)`, `FileVersion 1.20.0.0`, and
  `ProductVersion 1.20.0.0`.

- [ ] **Step 2: Run the focused test and confirm it fails**

  Run `python -m unittest tests.test_identity.TestBuildIdentity` from the
  activated native Windows virtual environment. Expect a version mismatch.

- [ ] **Step 3: Update the package and Windows metadata**

  Change the package version to `1.20.0` and all four Windows version resource
  values to `1.20.0.0`.

- [ ] **Step 4: Publish the changelog section**

  Keep an empty `[Unreleased]` heading and move the imported fixes under
  `## [1.20.0] - 2026-07-19`.

- [ ] **Step 5: Run the focused test and confirm it passes**

  Re-run `python -m unittest tests.test_identity.TestBuildIdentity`.

### Task 2: Review and verify the source

**Files:**
- Review: every staged file

**Interfaces:**
- Consumes: synchronized v1.20.0 metadata from Task 1
- Produces: reviewed, tested source ready for a clean build

- [ ] **Step 1: Run the independent re-review**

  Submit the revised, sanitized versioned-deployment plan and reconcile every
  finding before runtime mutation.

- [ ] **Step 2: Run static and whitespace checks**

  Run `python -m compileall -q usage_monitor_for_claude tests` and
  `git diff --check`.

- [ ] **Step 3: Run the full test suite**

  Run `python -m unittest discover -s tests` and require at least 1,035 tests,
  zero failures, zero errors, and no unexplained skips.

- [ ] **Step 4: Run the privacy and provider-boundary scan**

  Check tracked and publishable untracked files for personal paths, credentials,
  tokens, raw probes, logs, settings, executables, and build artifacts.

- [ ] **Step 5: Review the complete staged diff**

  Confirm every change belongs to the v1.20.0 release and no unrelated
  `.agents/` content is staged.

### Task 3: Build and install the frozen application

**Files:**
- Build output: `dist/UsageMonitorForCodex.exe`
- Runtime: canonical executable defined by ignored local machine instructions

**Interfaces:**
- Consumes: tested v1.20.0 source
- Produces: verified v1.20.0 canonical runtime

- [ ] **Step 1: Run a clean PyInstaller build**

  Run `python build.py` in the activated native Windows virtual environment and
  require a successful build.

- [ ] **Step 2: Verify the build artifact**

  Confirm file/product version `1.20.0.0`, record size and SHA-256, and confirm
  the artifact is not tracked.

- [ ] **Step 3: Validate the active process topology**

  Verify exactly one canonical PyInstaller parent-child pair owned by the
  current user in the current interactive session. Confirm the Run-key
  autostart is login-only and that no service or scheduled-task supervisor can
  respawn the process during replacement.

- [ ] **Step 4: Preserve rollback state and stop the monitor**

  Record a timestamp baseline for the active and rotated logs, copy the
  canonical executable to a temporary backup, stop only the verified process
  IDs, confirm both exit, and observe three seconds without a respawn.

- [ ] **Step 5: Install and launch the build**

  Copy the build to the canonical path, verify its hash, and launch it from the
  canonical working directory.

- [ ] **Step 6: Smoke-test or roll back**

  Allow up to 10 seconds for both the canonical v1.20.0 process pair and its
  app-server child to reach startup readiness. Then verify both continuously in
  20 one-second samples, require the startup INFO entry, and scan the active and
  rotated logs for timestamped ERROR or CRITICAL entries after the baseline.
  Restore and relaunch the backup if any acceptance criterion fails. If
  restoration fails, retain the backup, stop further writes, and report its
  location. Retain the verified backup after success as a short-term rollback
  artifact.

### Task 4: Publish the tested version update

**Files:**
- Commit: only the v1.20.0 source, test, changelog, design, and plan files

**Interfaces:**
- Consumes: exact source used for the verified build
- Produces: follow-up draft pull request from the merged selective-sync main

- [ ] **Step 1: Stage and review the intended files**

  Explicitly stage only the version-update files and verify `.agents/` remains
  unstaged.

- [ ] **Step 2: Commit the version update**

  Commit with the configured GitHub noreply identity.

- [ ] **Step 3: Push and verify**

  Push the follow-up branch without force, verify the remote SHA equals local
  `HEAD`, and confirm the new draft pull request contains the commit.
