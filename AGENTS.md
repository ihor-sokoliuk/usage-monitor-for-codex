# Project Guidelines

Apply Python best practices and clean-code principles. Change only what the task requires. Prioritize readability and auditability: this monitor sits next to authenticated Codex tooling, so its provider boundary must be easy to verify.

## Platform and execution

- This is a Windows-only application. Windows APIs (`ctypes.windll`, `winreg`) may be used unconditionally; do not add `sys.platform` branches.
- Develop, test, and build with native Windows Python from an NTFS clone; do not depend on a fixed checkout path.
- At the start of local work, read `AGENTS.local.md` when it exists. It contains machine-specific workflow instructions and is intentionally ignored by Git; never copy its contents into tracked files, logs, fixtures, or responses intended for publication.
- Do not run Win32 tests or builds from WSL or a `\\wsl.localhost` UNC path. WSL-specific Codex CLI selection is a v1 non-goal.
- Activate `.\.venv\Scripts\Activate.ps1` before running Python commands.
- The internal package remains `usage_monitor_for_claude` deliberately for selective upstream UI mergeability.

## Popup window and DPI

- The popup uses pywebview with a WinForms host window and Edge WebView2.
- pywebview 6.x `resize()` and `move()` expect logical pixels; pywebview applies DPI scaling internally.
- `_tray_position()` receives physical pixel dimensions for Win32 calculations and returns logical coordinates for `move()`.
- `_tray_position()` uses `Shell_TrayWnd`, `MonitorFromWindow`, and `GetMonitorInfoW`, and detects a left taskbar with `work.left > mon.left`, not `> 0`.
- Never replace tray-anchored `resize()`/`move()` with direct `SetWindowPos`. The pinned-popup drag is the sole exception.
- Pinned drag deliberately uses raw `SetWindowPos` with physical cursor coordinates. `_end_drag` reasserts size through `resize()` after crossing a DPI boundary. Do not collapse this to `move()`.
- Hide the taskbar window with `WS_EX_TOOLWINDOW` and removal of `WS_EX_APPWINDOW`. Do not set WinForms `ShowInTaskbar = False`; it recreates the native handle and can crash WebView2 from background threads.

## Tray icon interaction

- pystray has no native double-click support. When `on_double_click_command` is configured, `_install_double_click_handler()` replaces the matching private `WM_NOTIFY` handler with `_on_tray_message`.
- With a double-click command, defer a single click by `GetDoubleClickTime()`, cancel it on the double-click, and swallow the trailing `WM_LBUTTONUP`. Guard all click state with `_click_lock`.
- Without a double-click command, do not install the handler; the immediate upstream single-click behavior must remain unchanged.
- Unhandled tray messages, including right-click menu behavior, must fall through to the saved pystray handler.

## Event commands

- Event commands are an explicit user-controlled execution surface; they are not part of the provider network boundary.
- Automatic events (`on_reset_command`, `on_threshold_command`, `on_startup_command`) run fire-and-forget with output discarded and must never display a failure dialog.
- User-driven actions (the test menu and `on_double_click_command`) use `capture_output=True`, print captured output, and show a dialog for nonzero exit.
- Captured commands wait on a daemon thread so tray, popup, and poll threads are never blocked.
- New event commands must be classified as automatic/background or user-driven and follow the corresponding failure behavior.

## Provider fields and formatting

- Never hardcode a closed list of quota field names in display, alert, reset, or event-variable logic.
- The adapter in `api.py` emits normalized top-level quota dictionaries with `utilization` and `resets_at` keys. Null windows are skipped; a missing reset is `''`.
- A non-empty keyed rate-limit map is used alone; otherwise the snapshot's primary/secondary windows are used. Never merge the sources.
- Field names derive from duration plus a sanitized limit ID when available. Missing-duration keyed windows use a limit slug; missing-duration snapshot windows use their slot fallback. Collision suffixes must prevent overwrites.
- A duration-less field is displayable but unparseable: it has utilization and reset text when present, but no time marker or dividers.
- Credits metadata is dropped. Dormant `extra_usage`, currency, legacy `rate_limited`, and paid-credit UI paths remain only for upstream mergeability and must not be advertised as active Codex v1 features.
- `parse_field_name()` accepts number words or digits and `minute`, `hour`, and `day`; sorting uses actual duration seconds with unparseable fields last.
- Locale files use generic templates such as `session_label`, `weekly_label`, and `notify_threshold_generic`; do not add a translation key per field.

## Polling, account changes, and recovery

- `cache.update()` enforces the `POLL_FAST` successful-fetch floor. Reset alignment must never schedule inside the last `POLL_FAST - RESET_BUFFER` seconds before a reset.
- A poll reads account and rate limits as one generation-atomic provider operation. Usage and profile are stored atomically under the cache state lock.
- Profile semantics are three-valued: a profile dict replaces cached profile, `{}` is authoritative signed-out state, and `None` preserves the previous profile.
- Account identity comes from the per-poll account response. Fingerprints use auth type plus normalized email; plan is excluded. A missing email yields no comparable fingerprint.
- `account/updated` increments a monotonic auth revision. A revision change may trigger an account-only confirmation that bypasses the usage cooldown; it is a hint, not the usage source of truth.
- The app-server child is restarted only at logical operation boundaries. Its ten-minute TTL bounds healthy account-switch staleness; TTL expiry never interrupts an operation in progress.
- While scheduled polls remain signed out or in a classified authentication-error state, recycle the child every tenth error-cadence poll. Other states rely on the operation-boundary TTL. Popup/manual `update()` calls must not advance this counter.
- The cache owns the continuous failing-rate-limits episode guard. The adapter remains stateless and performs at most one refresh-enabled account read when called with recovery allowed. Reset the guard on success or stored-fingerprint change.
- Unknown error codes default to transient. Authentication classification must use exact codes/data established in `tests/fixtures/codex/WIRE_NOTES.md`, never substring guessing. Method-not-found on required account methods means the Codex CLI is too old.

## App-server transport

- Provider RPC method names and known handshake/notification names must be fixed auditable constants or literals; never construct method names dynamically.
- Wire framing is JSONL with JSON-RPC 2.0 semantics and no `jsonrpc` member.
- The logical provider operation holds the operation lock across all RPCs, pins one child generation, and retries the whole operation at most once after child death. Never return mixed-generation partials.
- The reader may answer an unexpected server request while a client request is outstanding; it must hold only the stdin-write lock for that reply.
- Startup and Job-object failures must kill, wait for, and close the local child resources. Shutdown must not join the reader while holding a lock the reader needs.
- Configure WinAPI `argtypes`/`restype` explicitly for 64-bit handles. Keep the child in a kill-on-close Job object.
- Never log payloads, tokens, email addresses, or raw stderr. The stderr diagnostic ring is bounded and redacts the real home path and token-shaped strings.

## Codex CLI updates and application logging

- Automatic updates invoke only the fixed official `codex update` command. Never scrape release pages or construct download URLs.
- Stop the app-server and serialize the updater against logical provider operations before invoking the updater. Never replace a CLI while a provider operation is active.
- Notify only when the installed CLI version actually changes. Update failures are logged without raw subprocess output and retry only after the configured interval.
- Write the default instance's `usage-monitor-for-codex.log` beside the frozen executable, or in the project root in source mode. Custom Codex homes add `config_dir_suffix()` so concurrent instances never share a rotating file. Use size-based rotation with user-configurable size and retained backup count.
- Startup must fail visibly if the adjacent log cannot be opened. Do not silently fall back to a different directory.
- Logs may contain sanitized system/runtime diagnostics, fixed provider method names, timings, utilization summaries, classifications, update versions, and tracebacks. Never log raw provider payloads, tokens, credentials or credential metadata, emails, raw Codex stdout/stderr, or event-command output.

## Security and transparency

- The built-in monitor makes no outbound provider/API request. Provider account/usage data flows only through the local app-server child over stdio; the Codex child owns its own authentication and network behavior. The separately invoked official `codex update` command may use the network and replace Codex installation files.
- pywebview/WebView2 may use local loopback/runtime caches. User-configured event commands may access the network or filesystem. Keep these caveats in README and privacy claims.
- Monitor code must not access a Codex credential store in any way: no contents, path construction, existence check, timestamp, watcher, or metadata. Auth state comes only from the app-server account read.
- The provider security boundary is isolated in `api.py` (adapter/classification) and `app_server.py` (transport/lifecycle). Other subprocess surfaces such as event commands remain isolated in their dedicated modules.
- Keep provider method names fixed and auditable. Do not dynamically construct endpoints or methods.
- No `eval()`, `exec()`, `compile()`, dynamic imports, obfuscation, encoded endpoints, or hidden/minified logic.
- Pure data files remain separate from logic.
- Runtime dependencies remain minimal and well-known: Pillow, pystray, and pywebview.

## Type hints and documentation

- A module docstring is the first element in every Python file, followed by `from __future__ import annotations`.
- Use signature type hints and numpydoc docstrings for public functions/classes and nontrivial methods. Skip redundant docstrings for self-explanatory one-to-three-line methods.
- Never describe changes or improvements in comments/docstrings; document current behavior.
- A `# type: ignore` requires a specific error code and a short reason.

## Formatting and structure

- Use PEP 8 with a flexible 140-160 character line length where readability benefits.
- Prefer single quotes; use double quotes when the string contains a single quote and triple double quotes for docstrings.
- Use hyphens for prose dashes, never typographic em/en dashes.
- Use two blank lines between top-level definitions and one between methods. Separate logical blocks with blank lines.
- Import groups are standard library, third party, then local; sort `import` before `from` within each group.
- Use relative imports inside `usage_monitor_for_claude`, except `__main__.py` where absolute imports support PyInstaller.
- Export library APIs through `__all__`; prefix private helpers with `_`.
- Prefer pure functions and focused modules. Use descriptive names and comments only for non-obvious behavior.
- Avoid complex comprehensions with multiple conditions or repeated calls; use explicit loops and guard clauses.
- Validate inputs at function entry and favor early returns.

## PyInstaller and build

- All build configuration lives in `usage_monitor_for_codex.spec`; output is `dist\UsageMonitorForCodex.exe`.
- Add new data assets to `datas`; add hidden imports only when PyInstaller cannot detect them.
- Do not exclude standard-library modules needed transitively. After dependency changes, perform a clean build and frozen smoke rather than guessing.
- Build with native Windows Python only.

## README and changelog

- Keep README claims synchronized with user-visible behavior and `PRIVACY.md`.
- Preserve feature order: getting started, daily visible value, proactive protection, visual quality, reliability, then reach/preferences.
- Use "Codex versions" and "Automatic session recovery" language. Never restore Claude token-refresh or Anthropic endpoint claims.
- Document multi-account only with the per-home `cli_auth_credentials_store = "file"` prerequisite and keyring-isolation warning.
- Update `[Unreleased]` for every user-visible feature, fix, or behavior change. Do not add changelog entries for internal refactors or rule-file-only changes.
- Release notes are derived from the version's changelog section and link to the fork, not upstream release URLs.

## Testing

- After every task, run `python -m unittest discover -s tests` in the activated native Windows venv and require success.
- Add or update `unittest` coverage for behavior changes, including concurrency, boundary, empty, and malformed cases.
- Never weaken or remove tests to make a change pass. Tests for genuinely deleted provider code may be deleted only with that code.
- Mock time through the module under test. Notification test helpers default to a present, unlocked user; override those inputs for idle/lock behavior.
- Live app-server probing is manual and opt-in. Never automate logout, login, credential configuration, or credential-store inspection.

## Selective upstream sync

- Follow `UPSTREAM_SYNC.md`; enumerate and classify every upstream commit in the review range before importing anything.
- Never use GitHub's one-click Sync fork, merge or rebase `upstream/main` wholesale, or resolve a conflict by reintroducing Anthropic endpoints, credential handling, Claude identity, or `claude update` behavior.
- Only the user performs commit-producing cherry-picks. After every imported UI change, run the full Windows suite, rebuild, and smoke-test Claude and Codex monitors side by side.

## Git

- Agents never create commits, push, tag, publish releases, or perform destructive Git operations. The user manages repository history.
- Preserve unrelated worktree changes. Prefer noninteractive, non-destructive Git commands.
- Before a public handoff, scan tracked and untracked publishable files for user-home paths, fixed checkout paths, real emails, tokens, credentials, raw probe output, settings files, logs, and build artifacts. Confirm `AGENTS.local.md` is ignored and absent from the proposed commit.
- Live probe output must be sanitized before display and must never be committed verbatim. Public fixtures and wire notes use deterministic synthetic account details, utilization, reset times, balances, and identifiers.
- Keep machine-specific paths and deployment instructions only in ignored `AGENTS.local.md`. Public documentation and tests use relative paths, portable placeholders, or clearly synthetic identities.
- Remind the user that Git commit author name/email are public metadata and recommend a GitHub `noreply` email when privacy is desired.

## Memory and persistence

- Never write to the Claude auto-memory system under `~/.claude/projects/.../memory/`. Persistent repository guidance belongs in this file.
