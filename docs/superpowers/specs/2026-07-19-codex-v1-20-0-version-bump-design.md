# Codex v1.20.0 Version Bump Design

## Goal

Release the selectively ported upstream v1.20.0 work as Usage Monitor for
Codex v1.20.0, build the frozen Windows executable, install it as the
canonical local runtime, and restart the monitor.

## Version contract

- `usage_monitor_for_claude.__version__` is `1.20.0`.
- Windows `FileVersion` and `ProductVersion` are `1.20.0.0`.
- The imported `[Unreleased]` notes become the dated `1.20.0` changelog
  section.
- The fork keeps its `codex-vX.Y.Z` tag convention, but this task does not
  create a tag or GitHub release.

The exact upstream version is used because the user requested the same version
jump as upstream. The Codex-specific release notes remain authoritative for
the fork; Claude-only upstream features stay excluded.

## Verification

- Add a build-identity test that asserts Python and Windows version metadata
  remain synchronized.
- Run the full native Windows unit-test suite.
- Compile all Python modules.
- Run the repository privacy scan and staged-diff review.
- Perform a clean PyInstaller build and verify the executable reports
  `1.20.0.0`.

## Local installation and recovery

Before replacing the active monitor, verify the running processes belong to
the current interactive session and form the expected PyInstaller parent-child
pair. Preserve the known-good canonical executable as a temporary backup,
record the application log baseline, stop only those exact processes, and copy
the verified build into the canonical location.

After launch, verify the canonical hash equals the build hash, the process pair
runs from the canonical location in the interactive session, the app-server
child is present, and the new startup INFO entry appears. Allow up to 10 seconds
for startup, then require the process pair to remain healthy in 20 consecutive
one-second samples.

The log uses size-based rotation. Scan the active and rotated log files by
entry timestamp from the pre-stop baseline, rather than relying only on a byte
offset. If copy, launch, or verification fails, restore the backup and relaunch
the prior executable. If restoration fails, retain the verified backup, stop
further writes, and report its location for manual recovery. Retain the backup
after a successful deployment as a short-term rollback artifact.

## Publication

Commit the version bump and its documentation on a follow-up branch from the
merged selective-sync commit, push it to a new draft pull request, and verify
the remote branch points to the tested commit. Do not create a tag or release
without a separate request.
