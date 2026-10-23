---
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
description: Prepare a fork release for owner review without publishing
---

Prepare only the explicitly requested release version. Read `AGENTS.md`, `README.md` release checklist, and `.github/workflows/release.yml` first. Never create a commit, tag, push, release, deployment, or runtime replacement without exact owner authorization.

1. Inspect the current source, branch and worktree without changing history. Preserve user edits. Confirm the requested version; never invent a release bump.
2. Update `__version__` in `usage_monitor_for_claude/__init__.py` and all four fields in `version_info.py`.
3. Roll the fork `[Unreleased]` entries into a dated version section; leave historical upstream release sections accurate. Use fork compare URLs and the `codex-vX.Y.Z` namespace.
4. Run the full native Windows suite in the activated venv, applicable Linux checks, source smoke, a clean Windows build, and an isolated frozen smoke. Never replace a running monitor or touch live credentials. Report desktop limitations explicitly.
5. Read the version from `dist/UsageMonitorForCodex.exe` and compute its SHA-256. Signing is optional and uses only an owner's configured certificate. A build without `signing.env` stays unsigned; never claim a signature or prompt for a token that is not configured.
6. Scan publishable tracked and untracked files for private paths, emails, credentials, settings, logs, probe output, and build artifacts. Confirm `AGENTS.local.md` is ignored and excluded. Remind the owner that Git author metadata is public and suggest a GitHub `noreply` email when privacy is desired.
7. Report the concrete reviewed files and validation. The owner manages release preparation history and the matching `codex-vX.Y.Z` tag; the existing workflow builds, checks versions, writes a checksum, and derives notes from that fork changelog section with the fork README link.

No WinGet registration, publication token, or signing credentials are configured by this workflow. Do not reuse upstream publication infrastructure or URLs. Release notes must reproduce the version's changelog section; use a notes file rather than inline shell text if a later explicit publication request needs manual commands.
