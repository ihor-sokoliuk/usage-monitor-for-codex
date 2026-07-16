# Changelog

All notable changes to Usage Monitor for Codex are documented here.

This project is a fork of Jens Duttke's [Usage Monitor for Claude](https://github.com/jens-duttke/usage-monitor-for-claude). Its pre-fork release history remains in the upstream repository.

## [Unreleased]

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
