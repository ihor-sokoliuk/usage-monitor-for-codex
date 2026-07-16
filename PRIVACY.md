# Privacy Policy

**Usage Monitor for Codex** is a local Windows application that displays Codex ChatGPT plan usage.

## Data processed locally

The monitor processes the information needed for its UI and notifications: authentication mode/state, account email, plan type, rate-limit identifiers, utilization percentages, window durations and reset times, app-server errors, and account-update notifications. Raw provider responses are kept in memory and discarded when the monitor exits.

The built-in application has no telemetry or analytics and does not send this data to the project author, advertisers, or analytics services.

## Provider and network communication

The built-in monitor makes no outbound provider/API request. It starts a local `codex app-server` child and exchanges account and usage messages over the child's standard input/output using newline-delimited JSON.

The Codex child is a separate OpenAI program. It authenticates and performs network activity according to your Codex configuration and may update Codex-owned credentials, logs, or other state. The monitor does not inspect those stores. By default the monitor also invokes the official `codex update` command at startup and daily; that CLI command may access the network and replace Codex installation files. Automatic updates and their notifications can be disabled independently in the settings file. pywebview/WebView2 may also use local loopback communication or runtime caches internally.

Optional event commands are user-supplied programs, not built-in provider communication. They run with the monitor's user privileges and can access files, programs, or networks exactly as specified by the user.

## Credentials

Monitor code never constructs or inspects a credential-file/keyring location and never reads credential contents, existence, timestamps, or other metadata. It does not request or accept an API key or token. The selected `CODEX_HOME` is passed to the child as its configuration root; authentication state, email, and plan information still come only from the local app-server's account response.

When session recovery is needed, the monitor asks the app-server to perform one refresh-enabled account read. The app-server, not the monitor, owns any resulting credential or network activity.

## Local storage and Windows integration

The monitor does not persist raw provider responses and does not create or modify its optional `usage-monitor-for-codex-settings.json`; that file is created by the user and read at startup.

The default monitor instance writes `usage-monitor-for-codex.log` next to its executable (or in the repository root in source mode). Custom `--codex-home` instances add a stable hash suffix derived from the effective configuration directory, preventing multiple accounts from sharing a rotating file without disclosing the directory itself. This size-rotated log contains sanitized system/runtime diagnostics, provider method names and outcomes, request timings, summarized utilization percentages, retry/error states, updater versions/outcomes, and crash traces. It does not contain tokens, credential-store contents or metadata, account email addresses, raw provider JSON, raw Codex stdout/stderr, or event-command output. The size and retained backup count are configurable.

Enabling **Start with Windows** writes an autostart value under the current user's Windows Run registry key, and disabling it removes that value.

The packaged runtime, WebView2, Windows, and the spawned Codex child may create temporary, cache, log, or state files as part of their own operation. These are outside the monitor's provider-data storage behavior.

## Contact

For privacy questions, open an issue at:
https://github.com/ihor-sokoliuk/usage-monitor-for-codex/issues
