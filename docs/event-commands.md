# Event commands

Event commands run user-selected Windows shell commands when usage events occur. Add them to [`usage-monitor-for-codex-settings.json`](configuration.md), then use **Restart** from the tray menu.

| Setting | Trigger |
|---|---|
| `on_reset_command` | A usage window resets after previously being near exhaustion |
| `on_threshold_command` | A usage field crosses a configured threshold |
| `on_startup_command` | The first successful provider update after app start or Restart |
| `on_double_click_command` | The tray icon is double-clicked |

A value can be one command or an ordered array. Use an empty string or empty
array to disable an event command; array entries must be non-empty strings.

```json
{
  "on_double_click_command": "notepad.exe",
  "on_reset_command": [
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\\on-reset.ps1",
    "mplay32 /play /close C:\\Windows\\Media\\notify.wav"
  ]
}
```

Relative paths resolve from the EXE directory, or from the repository root when running from source.

## Security and network boundary

Commands run with the same Windows user privileges as the monitor. They are deliberately capable of launching programs, reading or writing files, and using the network. Review every command and script before configuring it; never put secrets directly in the JSON settings file.

Automatic event commands are fire-and-forget with output discarded and no visible console window. Commands launched from the **Test event commands** menu or by tray double-click are user-driven: their output is captured, and a nonzero exit displays an error dialog.

The monitor's built-in provider path makes no outbound API request. Any network call made by an event command belongs to that user-configured command. For example, this threshold command intentionally sends a request to a third-party service:

```json
{
  "on_threshold_command": "curl -s -d \"token=<APP_TOKEN>&user=<USER_KEY>&title=%USAGE_MONITOR_TITLE%&message=%USAGE_MONITOR_MESSAGE%\" https://api.pushover.net/1/messages.json"
}
```

## Idle behavior

When `on_reset_command` is configured, the monitor can briefly wake its reset-aligned poll while Windows is idle or locked so the reset is confirmed promptly. If the provider has not applied the reset yet or the app-server is temporarily unavailable, confirmation follows the normal error cadence.

Threshold commands do not wake ordinary idle polling. Desktop notifications that occur while the user is away are deferred until the user returns; event commands themselves are not deferred.

## Test commands

Use **Test event commands** from the tray context menu to run configured commands with sample data. When running from source, or when the packaged EXE is attached to a console with `--verbose`, captured stdout/stderr is also printed.

Testing an event command can perform its real side effects. A push command can send a real message, and a script can modify real files.

## Environment variables

Every command inherits the monitor's environment and receives:

| Variable | Meaning |
|---|---|
| `USAGE_MONITOR_VERSION` | Monitor version |
| `USAGE_MONITOR_EVENT` | `reset`, `threshold`, `startup`, or `double_click` |

### Reset event

| Variable | Meaning |
|---|---|
| `USAGE_MONITOR_VARIANT` | Normalized field that reset, such as `five_hour`, `seven_day`, or `seven_day_gpt_5_pro` |
| `USAGE_MONITOR_UTILIZATION` | Current rounded utilization |
| `USAGE_MONITOR_PREV_UTILIZATION` | Previous rounded utilization |
| `USAGE_MONITOR_RESETS_AT` | Current reset timestamp, or empty when unavailable |
| `USAGE_MONITOR_TITLE` | Localized notification title |
| `USAGE_MONITOR_MESSAGE` | Localized notification body |
| `USAGE_MONITOR_UTILIZATION_FIVE_HOUR` | Compatibility value for `five_hour`; `0` when absent |
| `USAGE_MONITOR_UTILIZATION_SEVEN_DAY` | Compatibility value for `seven_day`; `0` when absent |

### Threshold event

| Variable | Meaning |
|---|---|
| `USAGE_MONITOR_VARIANT` | Normalized field that crossed the threshold |
| `USAGE_MONITOR_UTILIZATION` | Current rounded utilization |
| `USAGE_MONITOR_THRESHOLD` | Threshold crossed |
| `USAGE_MONITOR_RESETS_AT` | Reset timestamp, or empty when unavailable |
| `USAGE_MONITOR_TITLE` | Localized notification title |
| `USAGE_MONITOR_MESSAGE` | Localized notification body |

### Startup and double-click snapshots

For every detected usage field, the monitor emits:

```text
USAGE_MONITOR_UTILIZATION_<FIELD>
USAGE_MONITOR_RESETS_AT_<FIELD>
```

The field name is uppercased. For example, `seven_day_gpt_5_pro` becomes `USAGE_MONITOR_UTILIZATION_SEVEN_DAY_GPT_5_PRO`. A missing reset timestamp is an empty string. Duration-less windows still emit variables even though their UI has no time marker.

The fixed five-hour and seven-day compatibility pairs are always available to reset handling and report `0`/empty values when those windows do not exist. Codex v1 does not emit the retained upstream `USAGE_MONITOR_EXTRA_*` variables because credits metadata is intentionally dropped.

If the tray is double-clicked before the first successful provider update, only the general event/version values are available.

## PowerShell example

Save this as `on-threshold.ps1` next to the EXE:

```powershell
$message = "[$env:USAGE_MONITOR_VARIANT] $env:USAGE_MONITOR_UTILIZATION% used"
Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show($message, $env:USAGE_MONITOR_TITLE) | Out-Null
```

Configure it:

```json
{
  "on_threshold_command": "powershell -NoProfile -ExecutionPolicy Bypass -File .\\on-threshold.ps1"
}
```
