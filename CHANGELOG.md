# Changelog

All notable changes to Usage Monitor for Codex are documented here.

This project is a fork of Jens Duttke's [Usage Monitor for Claude](https://github.com/jens-duttke/usage-monitor-for-claude). Its pre-fork release history remains in the upstream repository.

## [Unreleased]

## [1.20.0] - 2026-07-19

### Fixed

- Popup windows now show reliably at their initial height, release their Win32 hooks when closed, serialize concurrent size changes, retry transient WebView failures, rebuild bars after quota-field changes, and keep markers centered.
- Single-instance startup now detects holders created under different rights, revalidates the holder after the confirmation dialog, and refuses to start a duplicate when replacement cannot be proven.
- Account/profile responses with null sections and configured display fields that resolve to non-quota values no longer break popup or tooltip rendering.
- Unreadable IDE extension directories are skipped when collecting Codex installation versions.
- Windows locale detection now recognizes Chinese script variants, Hindi, and Indonesian display names.
- Settings files saved as UTF-8 with BOM are accepted, empty event-command strings disable the command, and empty command-array entries are rejected.
- Deferred notifications flush promptly and safely after the user returns, while quotas resetting together produce only one reset notification.
- A rate limit returned by the app-server recovery retry is shown as the current state and arms the requested backoff.
- Backward system-clock jumps re-anchor cooldown, rate-limit, and scheduled-poll state instead of freezing the tray on stale data.
- Popup-triggered fetches shortly before a reset no longer delay the reset-confirming poll.
- The tray continues following theme changes after a transient render failure, keeps sub-100 percentages to two digits, and preserves overage semantics at the elapsed-time clamp.
- Weekly dividers remain on actual local midnights across daylight-saving transitions.
- Drive-root `--codex-home` values remain rooted, verbose diagnostics redact home paths case-insensitively without matching sibling profiles, and older Windows 10 builds fall back when the modern DPI API is unavailable.

## [1.0.1] - 2026-07-16

### Changed

- Model-scoped usage windows use the provider's friendly model name instead of exposing an internal rate-limit identifier.

### Fixed

- When the configured session window is absent, the generic weekly window now stays above model-specific weekly windows and supplies the tray percentage and adaptive-polling signal.

## [1.0.0] - 2026-07-16

### Added

- Initial Codex port: ChatGPT plan usage in the Windows system tray through the local `codex app-server`, with live tray bars, detail popup, smart alerts, event commands, adaptive polling, 13 languages, and multi-instance support through `--codex-home`.
- Automatic Codex CLI update checks at startup and daily by default, with a notification when the installed version changes.
- An always-on, size-rotated, sanitized application log beside the executable, with configurable size and backup count.

### Changed

- The tray icon draws only the available quota bars; a weekly-only account shows one centered bar instead of an empty second line.
- Malformed provider payloads now produce a recoverable error state instead of terminating scheduled polling; invalid windows, percentages, and reset timestamps are isolated safely.
- Custom Codex-home instances use distinct rotating log filenames, preventing concurrent accounts from colliding during rollover.
- Event-command failure dialogs use Codex product identity, successful sign-in re-arms later signed-out notifications, conflicting polling intervals are rejected, and failed single-instance replacement no longer starts a duplicate monitor.
