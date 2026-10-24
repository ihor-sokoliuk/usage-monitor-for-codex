# Usage Monitor for Codex

**Monitor your Codex rate limits in real time - right from your system tray.**

A lightweight Windows tray app with experimental Linux support. It reads ChatGPT plan usage from a local `codex app-server` child and presents the upstream monitor's tray, popup, alerts, and adaptive polling with a Codex-only provider boundary.

![Detail popup showing account info and usage bars](screenshot.png)

## Features

- **Portable on Windows** - one EXE, no installation or Python runtime. Linux runs from source using system GTK and WebKit libraries
- **Zero configuration for one account** - uses your existing Codex ChatGPT sign-in; authentication belongs to the local app-server
- **Live tray icon** - configurable quota bars or two stacked percentages, configurable tooltip, automatic substitution when a quota is absent, and theme-aware colors
- **Detail popup** - account information, all detected usage windows, friendly model labels, reset countdowns, exact field exclusions, and a stale-data indicator. Pin and drag the popup or hide sections in a compact pinned view
- **Codex versions** - reports the native CLI and `openai.chatgpt` extensions found in VS Code, Cursor, and Windsurf
- **Smart alerts** - per-field percentage thresholds, time-aware pace alerts, and reset notifications
- **[Event commands](docs/event-commands.md)** - opt-in commands on quota reset, threshold, startup, or your tray quick action. The former double-click setting remains a compatibility alias
- **Time markers** - compare elapsed time with usage; bars turn red when usage is ahead of pace. Duration-less windows still display utilization and reset text without an invented time marker
- **Automatic session recovery** - requests one app-server refresh per continuous authentication-failure episode and observes subsequent sign-in without reading credential files
- **Adaptive polling** - normal and active cadences, a reduced away/locked cadence capped at ten minutes, reset alignment, transient-error retries, and bounded child refresh. An uncovered visible popup retains normal cadence
- **Automatic Codex CLI updates** - the fixed official `codex update` command runs at startup and daily by default; notifications appear only when the installed version changes
- **Verified helper shutdown** - attempts orderly exit before forced termination and defers replacement or CLI updates when the old helper or its tracked descendants have not exited
- **Multi-account** - separate instances per Codex home, with the file-store prerequisite below
- **13 languages** - English, German, French, Spanish, Portuguese, Italian, Japanese, Korean, Hindi, Indonesian, Simplified Chinese, Traditional Chinese, and Ukrainian
- **[Customizable](docs/configuration.md)** - colors, displayed fields, notifications, polling, rotating logs, CLI updates, and commands

## Security and transparency

The built-in monitor makes no outbound provider/API request. Account and usage data flows only over local stdio to a fixed `codex app-server` command; that external Codex child owns its authentication and network activity. The monitor never constructs or inspects a credential-store path, contents, existence, timestamps, or other metadata. Authentication state comes only from `account/read`.

The provider boundary comprises [`api.py`](usage_monitor_for_claude/api.py), [`app_server.py`](usage_monitor_for_claude/app_server.py), the [Windows process backend](usage_monitor_for_claude/provider_process_windows.py), the [Linux process backend](usage_monitor_for_claude/provider_process_linux.py), and the [Linux supervisor](usage_monitor_for_claude/_linux_supervisor.py). Dependencies remain Pillow, pystray, and pywebview, plus system GTK/WebKit integration on Linux. There is no provider HTTP library, hidden execution, dynamic import, encoded endpoint, or minified application logic.

Each instance writes sanitized rotating logs beside the EXE, or in the source checkout. They include local helper process IDs and lifecycle outcomes such as confirmed exit or deferred replacement, and exclude emails, tokens, credential metadata, raw provider payloads, raw Codex stdout/stderr, and event-command output. Startup fails visibly if the adjacent log cannot be opened.

pywebview and its browser engine may use loopback and runtime caches. The separately invoked `codex update` may use the network and replace CLI files. **Start at login** writes a Windows Run value or Linux XDG autostart entry. User-configured event commands run with your privileges and may access the network or filesystem. See [PRIVACY.md](PRIVACY.md).

## Antivirus warnings

Standalone Python executables can trigger antivirus or SmartScreen warnings. This fork does not promise a signed release. Compare the download's SHA-256 with the checksum published beside that release; a matching checksum establishes which artifact you have, not a guarantee of safety. You can also inspect the source and build it yourself. Report unexpected detections with the release version and detector name, without uploading private logs or settings.

## Requirements

- Windows 10/11 64-bit, or a modern Linux desktop with GTK 3, WebKit2, an AppIndicator-compatible tray, `/proc`, and kernel pidfd support
- A current native [Codex CLI](https://github.com/openai/codex) with the required app-server account methods
- ChatGPT browser sign-in through `codex login`

API-key and Amazon Bedrock authentication can be valid for Codex while providing no ChatGPT plan usage; the monitor reports those states explicitly. Missing required account methods means the CLI needs updating. Credits, prepaid balances, billing, currency, and extra-usage spending are not supported Codex features.

## Quick start

Download **UsageMonitorForCodex.exe** from this fork's [latest release](https://github.com/ihor-sokoliuk/usage-monitor-for-codex/releases/latest), place it in a writable folder, and run it. If the tray shows `!`, run `codex login` with ChatGPT sign-in and let the next poll observe the session.

The default instance creates `usage-monitor-for-codex.log` beside the EXE. Custom homes add a stable hash suffix so simultaneous accounts never share a rotating log. To remove the monitor, disable **Start at login**, quit, and delete its EXE, logs, and any settings you created.

### Linux

Linux support is experimental. The real source application has been exercised with GTK/WebKit and AppIndicator under Xvfb/Openbox and D-Bus, using synthetic provider data with networking disabled. That smoke covered three quota fields, startup and quick-action commands, popup pinning, restart, quit, and owned-child cleanup while an unrelated process survived. It does not establish compatibility with real GNOME, KDE, or Wayland sessions or their tray panels. There is no prebuilt Linux binary; the app uses system GTK and WebKit libraries. For Debian/Ubuntu-style distributions:

```bash
sudo apt install python3-venv python3-gi gir1.2-webkit2-4.1 \
                 gir1.2-ayatanaappindicator3-0.1 libayatana-appindicator3-1
git clone https://github.com/ihor-sokoliuk/usage-monitor-for-codex.git
cd usage-monitor-for-codex
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./usage-monitor-for-codex
```

The virtual environment needs `--system-site-packages` to see the distribution's PyGObject. The source launcher resolves its checkout and interpreter from any working directory, including through a symlink:

```bash
mkdir -p ~/.local/bin
ln -s "$(pwd)/usage-monitor-for-codex" ~/.local/bin/usage-monitor-for-codex
```

Enable **Start at login** in the tray menu to create the monitor's XDG desktop entry. Plain GNOME may require an AppIndicator extension. Some panels retain the left-click for a menu; use its first entry to open the popup and **Run Quick Action** for your command. KDE's supported tray path opens the popup on left-click. The app selects X11/XWayland because native Wayland does not allow equivalent popup placement; GTK/WebKit scaling and tray positioning remain desktop-dependent. A pystray AppIndicator deprecation message can originate from its system GTK dependency.

Linux cleanup uses a dedicated supervisor, control-pipe parent-death detection, subreaper ownership, `/proc` ancestry checks, and pidfds. It terminates and reaps owned children on normal shutdown and monitor death. A rare external SIGKILL/OOM kill of the supervisor itself can defeat that cleanup; this differs from Windows' kernel kill-on-close Job guarantee.

## How to use

| Action | Result |
|---|---|
| Hover | Configured usage windows and reset times |
| Left-click | Detail popup, or panel menu on desktops that keep the click |
| Double-click on Windows | Configured quick action |
| Run Quick Action in the menu | Same configured command, including on Linux |
| Right-click | Popup, autostart, command tests, restart, project link, and quit |
| Escape or click outside | Closes an unpinned popup |

### Tray icon not visible?

Windows may hide new icons. In taskbar settings, enable **UsageMonitorForCodex** under the system-tray icon list. On Linux, check that your desktop provides AppIndicator support.

### Reading the progress bars

The fill is percent consumed. Period dividers mark hours or local midnights where applicable. Seven-day bars can instead use [equal sections](docs/configuration.md#weekly-dividers). The vertical marker shows elapsed time; fill ahead of that marker turns red. Reset text gives a countdown and local clock time. A duration-less window has utilization and any supplied reset text, with no marker or dividers.

## Configuration

Create `usage-monitor-for-codex-settings.json` with only overrides. The first existing file wins:

1. A custom home selected by `--codex-home` or `CODEX_HOME`, when it differs from `~/.codex`
2. Next to the EXE, or in the source repository root
3. `~/.codex/usage-monitor-for-codex-settings.json`

The monitor never creates or modifies this settings file. Restart from the tray after edits. See [Configuration](docs/configuration.md) for all active settings.

### Multiple Codex accounts

A home directory alone does not guarantee isolation with a shared OS keyring. For each account, create a distinct Codex home, add `cli_auth_credentials_store = "file"` to its `config.toml` before login, run `codex login` with that `CODEX_HOME`, then pass the same home to the monitor's `--codex-home` option. Keyring isolation, including `auto` when it selects keyring, is not verified. See the [walkthrough](docs/configuration.md#multiple-codex-accounts).

## Building from source

Windows development, Win32 tests, and EXE builds use native Windows Python from an NTFS clone, never WSL or a WSL UNC path:

```powershell
git clone https://github.com/ihor-sokoliuk/usage-monitor-for-codex.git
Set-Location .\usage-monitor-for-codex
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests
python -m usage_monitor_for_claude --verbose
python build.py
.\dist\UsageMonitorForCodex.exe --verbose
```

Linux setup is described above. Run `python -m unittest discover -s tests` from its activated environment; tests for the other platform skip themselves. A passing platform suite establishes only what that suite exercises. Keep real desktop verification distinct from virtual-display tests.

The internal Python package remains `usage_monitor_for_claude` for continuity with upstream. It is not a provider selection switch. For popup-only development, serve the checkout with `python -m http.server 8080` and open `http://localhost:8080/usage_monitor_for_claude/popup/dev.html`; this development server is separate from the provider path.

`python build.py` creates `dist/UsageMonitorForCodex.exe`. Optional local signing uses an ignored `signing.env` with `SIGNING_THUMBPRINT` and `SIGNING_TIMESTAMP_URL`, plus optional `SIGNING_TIMESTAMP_FALLBACK_URL`. The Windows SDK signing tools and your own certificate are required. The build verifies a configured signature and fails if signing or verification fails. No signing credentials are supplied by this fork. Linux runs from source rather than a PyInstaller bundle.

### Release checklist

Release preparation is separate from implementation. The repository owner manages commits, pushes, tags, and publication:

1. Verify the source is current and preserve existing local changes.
2. Update `__version__`, all four version fields in `version_info.py`, and the dated fork changelog section.
3. Run full native suites, source smoke, clean Windows build, frozen smoke, platform lifecycle checks, and independent-monitor identity checks with isolated homes.
4. Scan publishable files for private paths, emails, credentials, settings, logs, raw probes, and artifacts. Git author name/email are public metadata; use a GitHub `noreply` email when privacy is desired.
5. After reviewing the result, the owner can push a matching `codex-vX.Y.Z` tag. The existing Windows release workflow verifies versions, tests, builds, writes checksums, and derives notes from that version's changelog section with a fork README link.

The upstream WinGet publisher/watcher is removed because this fork has no configured WinGet package registration or credentials. No release or deployment is implied by a local build.

## Contributing and upstream updates

Read [AGENTS.md](AGENTS.md) and [UPSTREAM_SYNC.md](UPSTREAM_SYNC.md). This migration rebases the complete fork onto pinned upstream, with explicit Codex adaptations for provider-specific features. Future history operations require owner authorization. Agents do not infer permission to commit, push, publish, or replace a running monitor.

The Codex and upstream Claude monitors keep distinct executable, tray, lock/mutex, autostart, settings, and logging identities. They can run independently; use separate application folders and isolated settings. Upstream references here acknowledge the original project, not an alternate provider mode.

## Credits

Forked from Jens Duttke's [Usage Monitor for Claude](https://github.com/jens-duttke/usage-monitor-for-claude). Its MIT-licensed Windows/Linux platform separation, tray and popup UI, notifications, polling, localization, and provider-neutral fixes form this application's foundation. Historical upstream release notes are retained in [CHANGELOG.md](CHANGELOG.md).

## License

MIT - see [LICENSE](LICENSE).

## Disclaimer

This independent community project is not created, endorsed, or officially supported by OpenAI. Codex, ChatGPT, and OpenAI identify compatibility and are trademarks of OpenAI.
