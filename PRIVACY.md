# Privacy Policy

## Data processed locally

Usage Monitor for Codex displays account email, plan, normalized quota utilization and reset times, and local Codex/IDE extension versions. Provider responses stay in memory. The monitor does not send telemetry, analytics, or crash reports.

## Provider and network communication

The built-in monitor makes no outbound provider/API request. Fixed local `codex app-server` RPCs over stdio supply account and usage data. The external Codex process owns its own authentication, network activity, and state changes according to your Codex configuration. The monitor drops credits metadata and has no active billing, prepaid balance, currency, or extra-usage spending feature.

The separately invoked official `codex update` command may access the network and replace Codex installation files. It runs only after provider operations are serialized and the child is stopped. Disable automatic CLI updates in settings when another package manager owns the installation. Unsupported or failed updates never fall back to another installer.

pywebview and its WebView2 or GTK/WebKit runtime may use local loopback and runtime caches. Opening project links uses your browser. Opt-in event commands can use the network, filesystem, or other applications with the same privileges as the monitor; their effects belong to those configured commands.

## Credentials

The monitor never accesses a credential store: no contents, path construction, existence check, timestamp, watcher, or metadata. All authentication state comes from `account/read`. Recovery asks the app-server for at most one refresh-enabled account read per continuous failure episode.

For multiple accounts, each home requires `cli_auth_credentials_store = "file"` before login. Distinct homes alone do not prove isolation when Codex uses a shared OS keyring. The monitor does not verify keyring isolation or inspect credentials to enforce this prerequisite.

## Local storage and operating-system integration

- The settings filename is `usage-monitor-for-codex-settings.json`. The monitor reads user-created settings but does not create or modify that file.
- A rotating `usage-monitor-for-codex.log` is written beside the frozen EXE or in the source checkout. Custom homes add a stable hash suffix. Logs contain sanitized runtime diagnostics, local helper process IDs and generation numbers, lifecycle reasons and outcomes such as confirmed exit or deferred replacement, shutdown elapsed times, fixed method names, timings, utilization summaries, classifications, update versions, and tracebacks. They exclude emails, tokens, credentials and metadata, raw payloads, raw Codex output, and event-command output. Startup fails visibly if the adjacent log cannot be opened.
- Windows **Start at login** writes a current-user Run registry value; Linux writes an XDG autostart desktop entry. Codex identities are separate from the upstream monitor.
- Single-instance ownership uses per-home Windows kernel objects or Linux lock files. Linux desktop status checks may query session D-Bus services. Unknown lock state defers account notifications.
- Windows Job containment closes child processes with the monitor. Linux requires `/proc` and pidfd-capable kernels and uses a supervisor/control pipe plus subreaper to clean up owned descendants on monitor exit. External SIGKILL/OOM death of the Linux supervisor itself remains a cleanup limitation.

Disable autostart before removal, then delete the application, logs, any settings you created, and any source launcher symlink. The monitor does not remove Codex's own installation or state.

## Contact

Report concerns through this fork's [issue tracker](https://github.com/ihor-sokoliuk/usage-monitor-for-codex/issues). Review diagnostics before sharing them; do not attach private settings, credential material, or unsanitized live probes.
