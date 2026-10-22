# Configuration

No settings file is required. To override defaults, create `usage-monitor-for-codex-settings.json` containing a JSON object with only the keys you want to change.

```json
{
  "poll_interval": 180,
  "bar_fg": "#00cc66",
  "bar_fg_warn": "#ff6600"
}
```

The first existing file wins:

1. The effective Codex home selected by `--codex-home` or `CODEX_HOME`, when it differs from the default home
2. Next to the EXE, or the repository root when running from source
3. `~/.codex/usage-monitor-for-codex-settings.json`

The monitor never creates or modifies the file. Settings are read at startup; use **Restart** from the tray menu after editing.

## Multiple Codex accounts

A separate Codex home isolates settings and child-process state, but an OS keyring can still share credentials machine-wide. Multi-account monitoring therefore requires file-backed credentials in every home. Keyring isolation, including `auto` when it selects a keyring, is not verified.

For each account, open PowerShell and choose a directory that already exists:

```powershell
$home = 'C:\CodexHomes\work'
New-Item -ItemType Directory -Force $home | Out-Null
$config = Join-Path $home 'config.toml'
if (-not (Test-Path -LiteralPath $config)) { New-Item -ItemType File -Path $config | Out-Null }
Start-Process -FilePath notepad.exe -ArgumentList ('"{0}"' -f $config) -Wait
$env:CODEX_HOME = $home
codex login
codex login status
Remove-Item Env:CODEX_HOME
```

In Notepad, add the top-level setting without overwriting the rest of an existing file, save, and close it before running `codex login`:

```toml
cli_auth_credentials_store = "file"
```

Use ChatGPT browser sign-in, not API-key authentication, because this monitor displays ChatGPT plan usage. Then start one monitor per home:

```powershell
.\UsageMonitorForCodex.exe --codex-home="C:\CodexHomes\personal"
.\UsageMonitorForCodex.exe --codex-home="C:\CodexHomes\work"
```

Each instance gets its own tooltip prefix, settings search root, mutex identity, and autostart entry. `--codex-home` alone is not an account-isolation guarantee unless the file-store prerequisite is met.

## Usage field names

Fields are detected dynamically from app-server windows. Common durations are `five_hour` and `seven_day`; other examples include `90_minute`, `13_hour`, and `30_day`. A keyed model limit can add a suffix such as `seven_day_gpt_5_pro`.
The internal suffix remains stable for settings and event variables, while the popup and tooltip use the provider's friendly model name when one is available.

Do not treat those examples as a fixed provider schema. Duration-less keyed windows use a sanitized limit ID, and duration-less snapshot windows use a fallback such as `primary`. Such fields show utilization but have no time marker or dividers because their duration is unknown.

Default ordering uses actual duration in seconds, base fields before equal-duration variants, and unparseable duration-less fields last.

## Alert thresholds

| Key | Default | Description |
|---|---:|---|
| `alert_thresholds_five_hour` | `[50, 80, 95]` | Five-hour usage alerts |
| `alert_thresholds_seven_day` | `[95]` | Seven-day usage alerts, including suffix variants through fallback |
| `alert_time_aware` | `true` | For lower thresholds, alert only when utilization is ahead of elapsed time |
| `alert_time_aware_below` | `90` | Thresholds at or above this value always alert |

Any normalized field can have an exact override. Unknown-duration or unusual-duration fields have no built-in threshold until configured.

```json
{
  "alert_thresholds_30_day": [80, 95],
  "alert_thresholds_seven_day_gpt_5_pro": [50, 80, 95]
}
```

Use an empty array to disable alerts for a field.

## Tooltip fields

| Key | Default |
|---|---|
| `tooltip_fields` | `["five_hour", "seven_day"]` |

The tooltip resolves exactly as many slots as configured. A configured field that is absent is replaced by the next unused detected field in duration order; a substituted field uses ordinary utilization mode. `null`/inactive and malformed entries are never selected. An empty list shows only the tooltip title.

```json
{
  "tooltip_fields": ["five_hour", "seven_day_gpt_5_pro"]
}
```

## Popup fields

| Key | Default | Description |
|---|---|---|
| `popup_fields` | `["*"]` | Ordered popup fields; `"*"` inserts all remaining active fields |

Explicit missing fields are skipped. The wildcard can appear once and preserves duration ordering for the remaining fields.

```json
{
  "popup_fields": ["seven_day_gpt_5_pro", "five_hour", "*"]
}
```

## Compact pinned view

| Key | Default |
|---|---|
| `compact_hide` | `[]` |

Entries can be normalized field names or section keys: `account`, `claude_code`, and `status`. The retained internal key `claude_code` hides the UI's Codex versions section; its name stays unchanged to reduce upstream UI merge conflicts. `extra_usage` is also accepted as an upstream-compatibility key, but Codex v1 does not display credits/extra usage.

```json
{
  "compact_hide": ["account", "claude_code", "status", "seven_day_gpt_5_pro"]
}
```

## Tray icon bars

| Key | Default |
|---|---|
| `icon_fields` | `["five_hour", "seven_day"]` |

Exactly two entries are required. Available configured fields are shown first in configured order, then missing entries are replaced with unused detected fields in duration order. This keeps a generic weekly limit above its model-specific weekly variants when no session limit exists. If nothing remains, the slot is empty. A configured `:overage` suffix is preserved only when that field is available; substituted fields use utilization mode.

The tray draws only resolved quota slots. One available quota produces one centered bar; two available quotas produce two bars. An empty slot does not create a gray placeholder line.

Available display modes:

| Mode | Behavior |
|---|---|
| `utilization` | Fill in proportion to utilization and show the elapsed-time marker when duration is known |
| `overage` | Fill only the portion by which utilization is ahead of the elapsed-time marker |

```json
{
  "icon_fields": ["five_hour:overage", "seven_day"]
}
```

## Event commands

| Key | Default | Trigger |
|---|---|---|
| `on_reset_command` | none | A detected usage window resets |
| `on_startup_command` | none | First successful provider update after start/restart |
| `on_threshold_command` | none | A field crosses a configured alert threshold |
| `on_double_click_command` | none | Tray icon double-click |

Each value can be one command string or an array of command strings. See [Event Commands](event-commands.md) for execution and data-sharing details.

## Polling

| Key | Default | Description |
|---|---:|---|
| `poll_interval` | `180` | Normal seconds between scheduled updates |
| `poll_fast` | `120` | Minimum successful-fetch spacing and active-use cadence |
| `poll_fast_extra` | `2` | Extra fast polls after usage stops increasing |
| `poll_error` | `30` | Cadence after a transient provider/app-server error |
| `idle_pause` | `300` | Seconds of inactivity before ordinary polling pauses; `0` disables idle pause |

Reset-aligned polls can still run while idle when needed for an `on_reset_command`. During a persistent signed-out or classified authentication-error state, the child is recycled every tenth scheduled error-cadence poll. The ten-minute child TTL independently refreshes healthy and other error states at the next provider-operation boundary.

`poll_fast` must be less than or equal to `poll_interval`. Conflicting overrides are rejected together so the safe defaults remain active.

`max_backoff`, `alert_thresholds_extra_usage`, and `currency_symbol` remain accepted for upstream compatibility, but Codex v1 drops credits metadata and does not emit the legacy `extra_usage` or HTTP `rate_limited` states. Those settings have no provider-visible effect in v1.

## Codex CLI updates

| Key | Default | Description |
|---|---:|---|
| `auto_update_codex_cli` | `true` | Run the official `codex update` command automatically |
| `codex_update_interval` | `86400` | Minimum seconds between update checks; minimum `300` |
| `notify_codex_update` | `true` | Show a Windows notification when the installed version changes |

The first check runs at monitor startup. Later checks run at the configured interval while the monitor is active. Before updating, the monitor stops its local app-server child and serializes the update against provider reads so Windows can replace the CLI safely. The next provider operation starts a fresh child. A successful check that finds no version change does not notify.

`codex update` is part of the installed Codex CLI. It can access the network and replace Codex installation files under the current user's permissions. Set `auto_update_codex_cli` to `false` if another package manager or administrator owns your Codex installation.

## Application log

| Key | Default | Description |
|---|---:|---|
| `log_max_bytes` | `2097152` | Maximum active log size in bytes; minimum `1024` |
| `log_backup_count` | `3` | Number of rotated logs retained; minimum `1` |

The default monitor instance creates `usage-monitor-for-codex.log` in the directory containing `UsageMonitorForCodex.exe`, regardless of the current working directory. A custom `--codex-home` instance adds the same stable, non-identifying hash suffix used by its other OS identities, for example `usage-monitor-for-codex_abc123def456.log`; this prevents concurrent accounts from sharing a rotating file. Source runs use the repository root. Rotated files add `.1`, `.2`, and so on. If the directory is not writable, the monitor shows an error and does not start because silently losing diagnostics would make failures unauditable.

The log contains the sanitized diagnostics available from `--verbose`, startup progress, provider method outcomes and timings, summarized utilization percentages, retry/backoff states, Codex CLI update checks, and crashes. It never records tokens, credential-store data, account email addresses, raw provider JSON, raw Codex stdout/stderr, or event-command output. `--verbose` additionally mirrors log activity to a console; it is not required for file logging.

## Language and time format

| Key | Default | Values |
|---|---|---|
| `language` | Windows display language | `de`, `en`, `es`, `fr`, `hi`, `id`, `it`, `ja`, `ko`, `pt-BR`, `uk`, `zh-CN`, `zh-TW` |
| `time_format` | Windows regional clock | `"24h"` or `"12h"` |

## Colors

Popup colors are strings: `bg`, `fg`, `fg_dim`, `fg_heading`, `fg_link`, `bar_bg`, `bar_fg`, `bar_fg_warn`, `bar_divider`, and `bar_marker`.

Tray themes are `icon_light` and `icon_dark` objects. Each channel is an RGBA array `[R, G, B, A]`; supported channels are `fg`, `fg_half`, `fg_dim`, and `fg_warn`.

```json
{
  "icon_dark": {
    "fg": [0, 0, 0, 255],
    "fg_warn": [224, 80, 80, 255]
  }
}
```


## Weekly pacing

By default, weekly bars retain their calendar-day dividers. Set `"weekly_bar_parts": 5` to divide seven-day bars into five equal sections for workweek pacing. Integers from 1 to 31 are accepted; `1` hides internal dividers. Other quota durations are unchanged.
