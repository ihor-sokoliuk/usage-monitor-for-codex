# Codex app-server reference

The monitor reads provider data from a local `codex app-server` child. The protocol uses JSON-RPC 2.0 semantics over newline-delimited JSON, with the `"jsonrpc": "2.0"` member omitted on the wire.

`codex app-server` is an experimental Codex interface. The monitor treats unknown errors as transient and reports method-not-found on required account methods as an outdated Codex CLI.

## Implementation boundary

| Module | Responsibility |
|---|---|
| [`api.py`](../usage_monitor_for_claude/api.py) | Normalize responses and classify provider states |
| [`app_server.py`](../usage_monitor_for_claude/app_server.py) | Fixed JSONL RPCs, generation-atomic operations, and child lifecycle policy |
| [`provider_process_windows.py`](../usage_monitor_for_claude/provider_process_windows.py) | Windows process spawning, Job ownership, and wait handles |
| [`provider_process_linux.py`](../usage_monitor_for_claude/provider_process_linux.py) | Linux supervisor spawning and control-pipe integration |
| [`_linux_supervisor.py`](../usage_monitor_for_claude/_linux_supervisor.py) | Linux descendant ownership, pidfd signals, and reaping |

## Methods used

| Method | Purpose | Monitor behavior |
|---|---|---|
| `initialize` / `initialized` | Start the connection | Declares no optional capabilities |
| `account/read` | Read auth mode, email, and plan | Normally sends `refreshToken: false`; one recovery-enabled read per continuous failing episode may send `true` |
| `account/rateLimits/read` | Read usage windows | Maps percent used, optional duration, and optional reset time into UI quota fields |

The normal poll performs one account read followed by one rate-limit read as a single logical provider operation. A child restart never mixes responses from different child generations.

## Notifications and server requests

`account/updated` increments a monotonic authentication revision. The poll loop uses a revision change as an early account re-check hint; periodic polling remains authoritative.

Other notifications are ignored. An unexpected server-initiated request receives a method-not-found response so neither side waits indefinitely.

## Rate-limit source selection

The response can provide a compatibility snapshot in `rateLimits` and keyed buckets in `rateLimitsByLimitId`.

- A non-empty `rateLimitsByLimitId` mapping is normalized by itself, in sorted limit-ID order.
- Otherwise the monitor uses the snapshot's `primary` then `secondary` window.
- The two sources are never merged.
- Null windows are skipped.
- Credits metadata is ignored in v1.

Each window uses `usedPercent` directly as percent consumed. `resetsAt` is a Unix timestamp converted to an aware ISO-8601 value; a missing reset becomes an empty string. `windowDurationMins` is optional.
For non-default keyed buckets, a non-empty `limitName` is retained as display metadata so the UI can show the provider's model name instead of an internal metered-limit ID.

## Field naming

Known duration names use number words where available:

| Minutes | Field |
|---:|---|
| 90 | `90_minute` |
| 300 | `five_hour` |
| 780 | `13_hour` |
| 10080 | `seven_day` |
| 43200 | `30_day` |

For keyed buckets, a non-`codex` limit ID is sanitized and appended to a duration name, for example `seven_day_gpt_5_pro`. A keyed window without a duration uses the sanitized limit ID alone; an empty sanitized suffix falls back to `limit` or `<period>_limit`. These stable internal field names drive settings and event variables, while popup and tooltip labels prefer `limitName` when the provider supplies it.

For snapshot windows, a missing duration falls back to its `primary` or `secondary` slot name. That fallback is deliberately displayable but unparseable, so it has a label and percentage without a time marker or dividers.

Names are collision-proof within the selected source. A duplicate snapshot name gains a slot suffix such as `_secondary`; duplicate keyed names gain `_2`, `_3`, and so on.

## Account states

ChatGPT authentication supplies the plan usage displayed by this monitor. Signed-out, API-key, Amazon Bedrock, and method-not-found states are classified separately. Unknown app-server error codes remain transient unless live wire evidence establishes an exact authentication-error predicate.

The monitor never reads `auth.json`, an OS keyring, or credential-store metadata. All account state comes from `account/read`.

## Child lifecycle

A logical poll pins one app-server generation across every required RPC and retries the whole operation at most once after child death. A ten-minute TTL is checked between operations; it never interrupts an operation in progress. Account and usage snapshots enter the cache atomically. Signed-out/authentication-error scheduled polls recycle the child every tenth error-cadence poll; manual popup refreshes do not advance that counter.

Windows contains the child in a kill-on-close Job object. Linux uses a dedicated supervisor, an inherited control pipe, a subreaper, `/proc` ancestry checks, and pidfds to terminate and reap its owned descendants when the monitor exits. Linux requires a modern kernel with pidfd support. A monitor crash or SIGKILL closes the control pipe; externally killing the supervisor itself with SIGKILL, including an OOM kill, remains a containment limitation compared with the Windows Job object.

Shutdown first attempts orderly EOF-driven exit, then bounded forced cleanup if needed. A replacement or CLI update is deferred unless the old helper and its observed descendants are confirmed gone. Sanitized diagnostics record local helper process IDs, generations, lifecycle reasons and outcomes, and shutdown elapsed times.

The separately invoked official `codex update` command is serialized against provider operations after child shutdown. It is an updater, not a provider RPC or authentication-recovery mechanism.
