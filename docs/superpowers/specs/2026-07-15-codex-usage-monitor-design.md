# Usage Monitor for Codex - Provider Port Design

- Date: 2026-07-15 (revision 5, after fourth design review)
- Status: Approved for implementation planning
- Baseline: upstream and fork `main` at `f9224c2667ce7210464590d1e5e3f5d8637c8c69`
- Upstream: https://github.com/jens-duttke/usage-monitor-for-claude
- Fork: https://github.com/ihor-sokoliuk/usage-monitor-for-codex

## Goal

Port the Windows tray usage monitor from Claude (Anthropic OAuth API) to Codex
(local `codex app-server` JSON-RPC over stdio), preserving the polished popup,
tray rendering, notifications, reset-aligned polling, idle privacy, event
commands, and configurability. The result is a native Windows
`UsageMonitorForCodex.exe` that runs beside the official
`UsageMonitorForClaude.exe` with zero shared OS identity.

## Hard Constraints

1. Data comes only from the supported Codex app-server JSON-RPC surface.
   No terminal scraping, no `/status` parsing, no undocumented ChatGPT
   endpoints, and no access to `~/.codex/auth.json` at all - neither its
   contents nor its metadata. Codex credential storage may be `file`,
   `keyring`, `auto`, or `ephemeral` (`AuthCredentialsStoreMode` in the
   Codex config schema), so no file can serve as the authentication
   authority. The app-server's account read is the only auth source of
   truth.
2. Never assume `primary` means five-hour or `secondary` means weekly.
   Periods derive from `windowDurationMins` only; a window may lack a
   duration entirely (`window_duration_mins` is optional in the protocol)
   and must still be displayable.
3. `usedPercent` maps directly to the internal `utilization` (percent used,
   never inverted). `resetsAt` is Unix seconds.
4. Periodic polling stays the source of truth. The `account/updated`
   notification may only mark auth state dirty for an early re-check; it
   never replaces polling.
5. Preserve upstream UI mergeability: keep the `usage_monitor_for_claude`
   package layout and internal module structure; no repository-wide rename,
   no unrelated formatting churn.
6. Build and test with native Windows Python. WSL cannot exercise this Win32
   application.
7. All existing Win32/DPI/tray/polling invariants in the project rules stay
   intact (pywebview logical pixels, `_tray_position`, pinned-drag
   `SetWindowPos`, `WS_EX_TOOLWINDOW`, pystray double-click handler swap,
   `POLL_FAST` cooldown floor, danger-window rule).
8. AI never commits; the user commits manually.

## Decisions Made During Design Review

| Decision | Choice |
|---|---|
| Duration representation | Synthetic field names derived from `windowDurationMins`, with explicit formatting changes (see Section 2) |
| Missing tray/tooltip fields | Auto-substitute absent configured fields with the next detected field in duration order at render time; contract in Section 5 |
| Multi-instance CLI flag | `--codex-home` only; maps to `CODEX_HOME` |
| Settings file | Renamed to `usage-monitor-for-codex-settings.json` |
| Architecture | Claude-shaped adapter over one long-lived app-server child |
| Auth authority | `account/read` via the app-server; no credential-store file access of any kind (revision 2) |
| Multi-account scope | `--codex-home` isolates files/settings; account isolation is documented to require `cli_auth_credentials_store = "file"`, keyring isolation unverified (revision 2) |

## Architecture Overview

```text
UsageMonitorForCodex.exe (tray app)
  app.py / cache.py / popup / tray_icon / formatting   <- unchanged seams
    -> api.py                 (adapter: same name, same dict contracts)
        -> app_server.py      (new: JSONL JSON-RPC transport, one child)
            -> codex app-server (child process, owns auth + network)
    -> codex_cli.py           (renamed from claude_cli.py: discovery only)
```

The security-critical provider boundary consists of `api.py` **and**
`app_server.py` - the transport launches and talks to the authenticated
child, so both modules carry the isolation and audit rules that `api.py`
alone carried upstream.

The monitor makes no outbound API requests of its own - account data is
exchanged with Codex over local stdio, and `requests` is removed from the
dependencies. Outbound network activity is performed by the external Codex
app-server process according to the user's own Codex configuration (which
may define custom base URLs or providers). The claim is deliberately not
"no sockets at all": the embedded pywebview/WebView2 stack may use
loopback mechanisms internally.

## Section 1: Transport (`usage_monitor_for_claude/app_server.py`, new)

Owns exactly one persistent `codex app-server` child process.

- **Discovery**: `shutil.which('codex')` with the upstream `.ps1` ->
  `.cmd`/`.exe` sibling substitution, then the native installer path
  `%LOCALAPPDATA%\Programs\OpenAI\Codex\bin\codex.exe`, then
  `%APPDATA%\npm\codex.cmd|.exe`. A missing CLI is a first-class error
  state (`CodexCliNotFound`), not an unhandled exception.
- **Launch**: `[codex, 'app-server']` with
  `creationflags=CREATE_NO_WINDOW`, stdin/stdout pipes. stderr is piped
  and drained by a dedicated thread into a bounded ring buffer (last 20
  lines); the buffer is reserved for explicit failure diagnostics, is redacted
  (home paths, anything token-shaped), and is never logged automatically.
  Environment: inherited, plus `CODEX_HOME` set to the effective home when
  a custom one is configured.
- **Job object**: immediately after spawn, the child is assigned to a Win32
  Job object created with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, so the
  child dies with the monitor even when the single-instance guard
  terminates the process via `TerminateProcess` (where `atexit` and
  `finally` never run). If creating, configuring, or assigning the Job
  object fails, the freshly spawned child is terminated and transport
  startup fails - the no-orphan guarantee is strict, not best-effort.
  `proc.terminate()` is still called on clean quit/restart paths.
- **Handshake**: send `initialize` (client name `usage-monitor-for-codex`,
  the app version), wait for the response with a 30-second timeout (first
  launch can be slow), then send the `initialized` notification. The
  initialize request declares no optional capabilities - in particular,
  nothing attestation-related is enabled. Only after the handshake are
  data requests accepted.
- **Wire format**: JSON-RPC 2.0 *semantics* with the `"jsonrpc": "2.0"`
  header omitted on the wire, framed as newline-delimited JSON - both per
  the official app-server protocol. The transport omits the header on
  outgoing messages and does not require it on incoming ones. A reader
  thread parses incoming lines and routes responses by `id` into
  per-request events. Per-RPC timeout: 10 seconds.
- **Atomic provider operations**: the public unit of work is a *logical
  provider operation* - `fetch_provider_data()` (up to four RPCs per
  operation attempt: account read, rate-limits read, refresh-enabled
  account read, retry) or `refresh_profile()` (one RPC). The operation
  lock is held for the whole operation, the TTL is evaluated only before
  an operation begins, and every RPC inside an operation is pinned to the
  child generation captured at operation start. If the child dies or is
  replaced mid-operation, all partial results are discarded, the child is
  restarted once, and the entire operation is repeated once from the
  beginning; a second failure fails the cycle. Up to six RPCs total when
  the one whole-operation retry occurs - with at most one refresh-enabled
  read (see the recovery-consumed latch in Section 4). Pairing one
  account's profile with another account's usage is therefore impossible
  by construction.
- **Generation isolation**: every child start increments a generation
  counter carried by the reader thread and pending-request table. On
  timeout the pending request is removed, the child is terminated, and the
  generation is invalidated - a late response from a previous child can
  never satisfy a request issued against its replacement.
- **Malformed JSON line**: a fatal protocol error. The current child is
  terminated and the in-flight request fails with a classified transport
  error - it is never silently skipped into an unexplained timeout.
- **Server-initiated traffic**:
  - Notifications are ignored, with one exception: `account/updated`
    increments a monotonic auth revision counter under the state lock
    (Section 2); the poll loop reacts to revision changes (Section 3).
  - Server-initiated *requests* (messages carrying an `id`) receive a
    JSON-RPC method-not-found error response. The client never leaves a
    server request unanswered and never hangs on one; a unit test proves
    this.
- **Failure policy**: child exit, EOF, malformed line, or RPC timeout
  marks the transport dead. The current operation follows the
  atomic-operation rule above (discard partials, restart once, repeat the
  whole operation once); if the restart or its handshake fails, the
  operation returns an error result and the normal `POLL_ERROR` cadence
  retries later. No retry storms.
- **Child lifetime (TTL)**: the transport records the child's start time.
  When a provider operation begins and the child is older than `CHILD_TTL`
  (600 seconds), the child is restarted before the operation's first RPC.
  This bounds how long a child can serve cached account state after an
  external, error-free account switch (account A -> B while the child
  keeps answering successfully as A) - the error-state recycle rule alone
  never fires in that scenario. The TTL is checked only at operation
  boundaries, so it can never interrupt an operation mid-way or add extra
  polls; the switch is observed at the first provider operation after
  expiry.
- **Locking model** (deadlock-free by construction):
  - *operation lock*: serializes public provider operations and is held
    across all RPCs of one operation.
  - *state lock*: protects the child handle, generation counter, and
    pending-request table.
  - *stdin write lock*: makes each JSONL write atomic; shared by the
    operation path and the reader thread.
  - The reader thread answers server-initiated requests using only the
    stdin write lock - it never acquires the operation lock, so it can
    reply while a client RPC is outstanding.
  - Shutdown never joins the reader thread while holding a lock the reader
    may need.
- **Redaction**: verbose logging records method names, durations, restart
  events, and JSON-RPC error codes only. Never payloads, tokens, or email.

## Section 2: Adapter (`usage_monitor_for_claude/api.py`, same name and contract, new internals)

Exports:

- `fetch_provider_data(allow_recovery: bool = False) -> ProviderFetchResult` -
  the one call per poll cycle, executed as a single atomic provider
  operation (Section 1). Internally: account read (refresh disabled)
  first, then the rate-limits read with the Section 4 classification
  rules; the refresh-enabled recovery sub-sequence runs only when
  `allow_recovery` is True. The adapter is stateless - the *episode guard*
  that decides when recovery is allowed lives in the cache (Section 4).

  ```python
  @dataclass(frozen=True)
  class ProviderFetchResult:
      usage: dict[str, Any]           # Claude-shaped: quota fields, or
                                      # 'error' + optional 'auth_error'
      profile: dict[str, Any] | None  # dict: fresh normalized profile
                                      # {}:   authoritative signed-out
                                      # None: account state unavailable
                                      #       this cycle (transport failure)
      recovery_attempted: bool = False
  ```

  `usage` keeps today's `fetch_usage()` dict contract exactly (the dormant
  `rate_limited` convention stays in the code but no Codex path sets it).
  There is no hidden module-level "last profile" state in `api.py` - the
  cache owns all caching. Profile semantics in the cache: `None` preserves
  the cached profile (unavailable is not signed-out); `{}` replaces it
  (the popup's existing truthiness check then hides the account section,
  and a `None` fingerprint prevents a switch misfire).
- `refresh_profile() -> dict | None` - an account-only read, always fresh,
  independent of the usage cooldown. Used for the auth-revision
  confirmation and the popup's cold path: an `account/updated` notification arriving
  inside the `POLL_FAST` window can still confirm a switch, because the
  confirmation never goes through `cache.update()`.
- `auth_revision() -> int` - a monotonic counter incremented by the
  transport for every `account/updated` notification, guarded by the
  transport's state lock. The poll loop compares it against the last value
  it acted on, so a notification can never be lost to a
  check-and-clear race.

There is no `auth_available()`, no `auth_mtime()`, and no credential-file
access of any kind. Signed-in state is whatever the account read reports.

### Usage normalization rules

Source: the app-server rate-limits read (probe-verified as
`account/rateLimits/read` on Codex CLI 0.140.0; exact wire method names
are pinned by Phase 1 fixtures, and method-not-found is feature-detected -
see Section 4).

- **Source selection is either/or, never merged**: when
  `rateLimitsByLimitId` is a non-empty mapping, only its buckets are
  normalized (in limit-ID sort order) and the compatibility snapshot is
  ignored entirely; when it is null, missing, or empty, only the snapshot
  windows are normalized, in `primary`, `secondary` order. No cross-source
  deduplication exists because the sources are never combined.
- Field name from `windowDurationMins` (never from primary/secondary
  position):
  - Exact known values: `300 -> five_hour`, `10080 -> seven_day` (keeps
    settings keys, threshold defaults, icon defaults, and tests aligned
    with upstream).
  - Whole days: word form for 1-12 (`one_day` ... `twelve_day`), digit
    form above (`30_day`).
  - Whole hours (non-day): word form for 1-12 (`five_hour`), digit form
    above (`13_hour`).
  - Anything else: `<minutes>_minute` (e.g. `90_minute`).
  - Missing duration (`windowDurationMins` absent or null): the field is
    named from the sanitized limit ID alone; a missing-duration snapshot
    window uses its slot name (`primary`/`secondary`); an empty sanitized
    ID falls back to `limit`. Such a field is unparseable by
    `parse_field_name()` by design: it renders with a title-cased label,
    shows percent and reset countdown, has no time marker or dividers, and
    sorts last. It is displayed, never dropped.
- Buckets with a limit ID other than `codex` get a sanitized suffix using
  the `_model_slug()` approach (lowercase, non-alphanumerics to
  underscores), e.g. `seven_day_gpt_5_pro`. The `codex` bucket gets the
  bare period name. A duration-present keyed window whose sanitized limit
  ID is empty is named `<period>_limit` (e.g. `seven_day_limit`).
- **Collision-proof uniqueness** (deterministic, within the selected
  source): windows are processed in the source's fixed order given above.
  If a computed name is already taken by an earlier window, a snapshot
  entry appends its slot name (`seven_day_secondary`) and a keyed entry
  appends `_2`, `_3`, ... in processing order. Two windows can therefore
  never silently merge or overwrite each other, whatever combination of
  missing durations, equal durations, or slug collisions the response
  contains.
- `usedPercent` maps directly to `utilization` as a float. A dedicated test
  proves 29 renders as 29% used, not 71%.
- `resetsAt` (Unix seconds) converts to an aware UTC ISO-8601 string via
  `datetime.fromtimestamp(value, tz=timezone.utc).isoformat()`. A window
  with a percent but no reset timestamp is emitted with `resets_at: ''`
  (displayable, no countdown). Null or missing windows are skipped
  entirely - no empty popup rows.
- Credits / spend-control metadata is dropped by the adapter. It is not
  mapped onto `extra_usage`; the `extra_usage` UI paths stay dormant.
- Verified wire fields (live probe on 0.140.0, cross-checked against the
  protocol source `codex-rs/app-server-protocol/src/protocol/v2/account.rs`):
  `usedPercent`, `windowDurationMins` (optional), `resetsAt` (optional,
  Unix seconds), optional `rateLimitsByLimitId`.

### Formatting changes (`formatting.py`) - explicit, not "unchanged"

Adding durations beyond `five_hour`/`seven_day` requires these concrete
changes:

- `parse_field_name()`: accept a digit prefix in addition to the number
  words; accept `minute` as a third unit. `_UNIT_SUFFIXES` gains
  `'minute': 'm'`.
- `popup_label()`: session-style label (`session_label` template) for
  `minute` and `hour` units; weekly-style (`weekly_label`) for `day`.
  Today's code treats every non-hour unit as weekly, which would mislabel
  `90_minute`.
- `_field_sort_key()`: sort by actual duration in seconds (via
  `field_period()`), with unparseable fields last. Today's hour-vs-rest
  ordinal would sort minutes alongside days. The relative order of
  existing fields (`five_hour` before `seven_day` before variants) is
  preserved and locked by tests.
- Exact label matrix (locked by tests):

  | Field | Tooltip label | Popup label |
  |---|---|---|
  | `90_minute` | `90m` | `Session (90min)` |
  | `five_hour` | `5h` | `Session (5hr)` (unchanged) |
  | `13_hour` | `13h` | `Session (13hr)` |
  | `seven_day` | `7d` | `Weekly (7 day)` (unchanged) |
  | `30_day` | `30d` | `Weekly (30 day)` |
  | `seven_day_gpt_5_pro` | `7d GPT 5 Pro` | `Weekly (GPT 5 Pro)` |

- `_TITLE_CASE_EXCEPTIONS` gains `'gpt': 'GPT'` so limit-ID suffixes
  render with correct capitalization.
- `divider_positions()`: unchanged - sub-day periods other than exactly
  five hours keep the existing "no dividers" behavior.

## Section 3: Profile and Account Switching (app-server-authoritative)

### Profile normalization

The normalized profile - produced by both `fetch_provider_data()` and
`refresh_profile()` from the account read - has the shape the popup and
app already consume:

```python
{
    'account': {
        'email': <email or ''>,
        'uuid': <fingerprint or None>,
    },
    'organization': {
        'organization_type': <plan_type>,   # e.g. 'plus' -> popup renders 'Plus'
    },
}
```

- The fingerprint is `'<auth_type>:<normalized email>'` (email lowercased
  and trimmed). Plan type is deliberately excluded - a plan change is not
  an account switch.
- The protocol guarantees no account ID, and email is optional
  (`email: Option<String>`). When email is absent, `uuid` is `None`:
  the existing switch logic in `app.py` already treats a `None` UUID as
  "no comparison possible", so the "Account switched" notification is
  naturally suppressed instead of misfiring.
- A missing `plan_type` normalizes to `''`, never `None` - the popup calls
  string methods on `organization_type` unconditionally.

### Auth-change detection

No file watching of any kind. Four mechanisms, all app-server-based:

1. **Per-poll account read**: every `cache.update()` cycle calls
   `fetch_provider_data()`, whose account read runs before the rate-limits
   read, inside one atomic provider operation (Section 1).
   `UsageCache._fetch_and_process()` stores `result.usage` and
   `result.profile` atomically under `_state_lock` - a `dict` profile
   replaces the cached one, `{}` (authoritative signed-out) replaces it,
   `None` (account state unavailable) preserves it. This is the defined
   path by which the fresh account result reaches `cache.profile` and the
   existing fingerprint comparison in `app.py`, at poll cadence.
2. **`account/updated` notification**: increments the transport's
   monotonic auth revision. The poll loop's 1-second wait compares
   `auth_revision()` against the last value it acted on; on change it
   confirms via `cache.refresh_profile()` - an account-only read that does
   not go through `cache.update()` and is therefore valid inside the
   `POLL_FAST` cooldown window. `update(force=True)` still happens only
   after a *confirmed* fingerprint change, exactly as upstream.
3. **Child TTL for healthy switches** (Section 1): a child older than
   `CHILD_TTL` is recycled at the next operation boundary. This covers the
   case the error-state rule cannot: an external switch from account A to
   account B while the child keeps successfully serving cached account A -
   no error ever occurs, but the switch is observed at the first provider
   operation after TTL expiry (roughly `CHILD_TTL` plus the polling delay
   under active polling; idle-paused time does not count).
4. **Bounded child recycling in failed states**: whether a long-lived
   app-server observes logins performed by another Codex process (for
   file *or* keyring storage) is unverified; Phase 1 includes an explicit
   verification task (Section 9). Until verified: while the monitor is in
   a signed-out or auth-error state, every 10th error-cadence poll
   restarts the child before classifying, so an external login is
   observed within ~5 minutes at the default `POLL_ERROR = 30` even if
   the child caches auth. If Phase 1 proves live reload works, the
   recycle rules are kept as cheap safety nets; if it proves restart is
   required, the docs say so explicitly.

Cache seam: `ensure_profile()` keeps its locking semantics but loses token
keying - it calls `refresh_profile()` only when no profile is cached (the
popup cold path); freshness otherwise comes from mechanism 1. A new
`cache.refresh_profile()` method wraps the adapter's `refresh_profile()`
under `_profile_lock` and stores the result; it backs mechanism 2 and
`_account_switched()`. The upstream `_profile_token` /
`_last_failed_token` bookkeeping is removed entirely - there is no
blocked-until-credential-change state. Failed auth simply follows the
existing error cadence (`POLL_ERROR`) with the recovery rules of
Section 4.

## Section 4: Errors and Auth Modes

### Classification sequence

Inside `fetch_provider_data()`, when the rate-limits read fails with a
JSON-RPC error:

1. Use this cycle's account read result (which ran first, with token
   refresh **disabled**).
2. Classify distinctly:
   - **No account**: not signed in -> `{'error': T['no_token']}`
     ("Not signed in to Codex. Run `codex login` first.").
   - **API-key account** or **non-ChatGPT provider** (e.g. AmazonBedrock,
     both defined in the protocol): -> `{'error': T['not_chatgpt_auth']}`
     ("Signed in without a ChatGPT plan - plan usage requires ChatGPT
     sign-in."). No `auth_error` flag; never rendered as plan usage.
   - **ChatGPT account**: proceed to recovery (below).
3. **Recovery** (only when the caller passed `allow_recovery=True`): call
   the account read with token refresh **enabled** (`GetAccountParams`
   supports requesting a proactive token refresh), then retry the
   rate-limits read once. The result reports `recovery_attempted=True`.
   **Recovery-consumed latch**: the latch is scoped to the entire public
   provider operation and survives its one internal generation retry - it
   becomes true the moment the refresh-enabled account request is
   *written*, so a repeated operation attempt must not send another
   refresh-enabled request. `ProviderFetchResult.recovery_attempted` is
   the logical OR across both attempts. When `allow_recovery=False`, this
   step is skipped entirely and the original rate-limits error is
   classified directly by the step 4 rule.
4. If the retry still fails, classify from the **actual JSON-RPC error**,
   not from the account type. "Auth-shaped" is defined by the verified
   error codes/data captured in the Phase 1 fixtures - never by message
   substring guessing. An error matching those codes becomes
   `{'error': T['auth_expired'], 'auth_error': True}`; any unknown or
   unmatched error (transient network failure inside the child, server
   error, malformed backend response) defaults to `T['connection_error']`
   without the `auth_error` flag - unknown never means "expired session".

**Episode guard (owned by the cache, not the adapter)**: an "episode" is a
continuous failing-rate-limits state, regardless of how the failures
classify - a run of unknown/transient errors is one episode too, so
error-cadence polling can never trigger a proactive refresh every 30
seconds. The cache passes `allow_recovery=True` only when no recovery has
been attempted in the current episode, and sets its guard flag from
`result.recovery_attempted`. The guard resets when any cycle succeeds or
when the stored profile fingerprint changes (both observable inside the
cache). Classification reads always run with refresh disabled.

### Other error states

- **Missing CLI**: `codex_cli_not_found` ("Codex CLI not found - install
  Codex and sign in.").
- **Method-not-found** on a required method: `codex_cli_too_old`
  ("Codex CLI is too old for this monitor - update Codex."). This is
  feature detection: the monitor never misreports an incompatible CLI as
  an expired session, and it does not rely solely on a documented minimum
  version.
- **Timeout / child crash / malformed protocol line**:
  `T['connection_error']` (value re-worded to reference the Codex
  app-server). All errors feed the existing `consecutive_errors` counter
  and `POLL_ERROR` cadence.
- **Startup**: no pre-flight credential check exists anymore. The first
  poll's classification produces the signed-out state, and the existing
  startup warning notification fires once when that first classification
  reports not-signed-in.
- **Removed entirely**: `claude update` refresh (`refresh_token()`,
  `RefreshResult`), `NOTIFY_CLAUDE_UPDATE` setting, the update
  notification, `UpdateResult.token_refresh`, and the cache's
  `_try_token_refresh()` (replaced by the episode guard above - the
  adapter performs the RPC sequence, the cache decides when it may run).
- **Locale**: existing keys are reused with Codex-appropriate values;
  three keys are added (`not_chatgpt_auth`, `codex_cli_not_found`,
  `codex_cli_too_old`), translated in all 13 locale files. Template keys
  (`session_label`, `weekly_label`, `notify_threshold_generic`, ...) are
  unchanged.

## Section 5: Cache and Poll-Loop Seams

Unchanged (the point of the design): `POLL_FAST` cooldown floor,
`update(force=True)` only after a confirmed account switch, the
danger-window invariant, `_align_to_reset()`, backoff handling, snapshot
immutability, idle pause and deferred notifications, threshold and reset
alerts, event-command semantics (user-driven captures output, automatic
stays silent).

Changed:

- `cache.py`: `_fetch_and_process()` calls
  `fetch_provider_data(allow_recovery=...)` driven by the episode guard
  (Section 4) and stores `usage` and `profile` atomically under
  `_state_lock` - a `dict` profile replaces the cached one, `{}` replaces
  it with the signed-out state, `None` preserves it;
  `UpdateResult.data` keeps its exact contract for callers. A new
  `refresh_profile()` method (under `_profile_lock`) backs the
  auth-revision confirmation and `_account_switched()`. The
  `read_access_token` / `refresh_token` imports and the failed-token
  bookkeeping are removed.
- `app.py`: per-poll fingerprint comparison (Section 3), `auth_revision()`
  comparison in the wait loop, removal of the update-notification block,
  tray/tooltip field auto-substitution (below), identity strings.
- **Tray/tooltip auto-substitution** - explicit contract:

  ```python
  def resolve_display_fields(configured: list[str], data: dict, count: int) -> list[str | None]
  ```

  Returns exactly `count` elements. Each configured entry (mode suffixes
  like `five_hour:overage` are parsed off and re-attached) keeps its slot
  when the field exists in `data`; empty slots are filled with the
  remaining detected fields in duration order; slots with nothing left are
  `None`. Substituted fields always use the default `utilization` mode.
  The icon renders `None` as an empty bar and takes its percentage glyph
  from the first non-`None` slot; the tooltip simply skips `None`.
  Substitution applies uniformly to default and explicit configurations
  (an explicitly named absent field is substituted too; a future opt-out
  sentinel can be added if users ask). Tests cover: zero available
  fields, one available, two available, configured duplicates, missing
  configured fields, and more than two multi-bucket fields.
- Event-command env vars keep their names and dynamic per-field emission.
  The reset command's hardcoded `USAGE_MONITOR_UTILIZATION_FIVE_HOUR` /
  `SEVEN_DAY` pair reports `0`/`''` when a window does not exist (upstream
  semantics, no churn).

## Section 6: Independent Windows Identity

| Surface | Claude monitor | Codex monitor |
|---|---|---|
| Executable / spec / build.py output | `UsageMonitorForClaude.exe`, `usage_monitor_for_claude.spec` | `UsageMonitorForCodex.exe`, `usage_monitor_for_codex.spec` |
| version_info.py | ProductName "Usage Monitor for Claude", CompanyName "Jens Duttke", 1.19.0 | ProductName "Usage Monitor for Codex", InternalName/OriginalFilename `UsageMonitorForCodex`, CompanyName "Ihor Sokoliuk", version 1.0.0 |
| `__version__` | 1.19.0 | 1.0.0 |
| Mutex / shared memory | `UsageMonitorForClaude_SingleInstance` / `UsageMonitorForClaude_HolderPID` | `UsageMonitorForCodex_SingleInstance` / `UsageMonitorForCodex_HolderPID` |
| Autostart registry value | `UsageMonitorForClaude` | `UsageMonitorForCodex` |
| pystray icon name | `usage_monitor` | `usage_monitor_for_codex` |
| Settings file | `usage-monitor-settings.json` | `usage-monitor-for-codex-settings.json`; search: `CODEX_HOME` -> exe dir -> `~/.codex` |
| Multi-instance flag / env var | `--config-dir` / `CLAUDE_CONFIG_DIR` | `--codex-home` / `CODEX_HOME` (also exported to the app-server child) |
| Tray glyph at zero usage | `C` | `>_` (Codex prompt motif); bars, warn colors, and the exhausted glyph (U+2715) unchanged |
| Static icon | `usage_monitor_for_claude.ico` | `usage_monitor_for_codex.ico`, generated once by `tools/generate_icon.py` (Pillow, committed for reproducibility), output committed |
| Project URL / changelog URL | jens-duttke repos, Claude Code changelog | `https://github.com/ihor-sokoliuk/usage-monitor-for-codex`, `https://github.com/openai/codex/releases` |
| Dialog and crash titles, tooltip, menu, popup copy | "... for Claude", "Claude Usage" | "... for Codex", "Codex Usage" |

Details:

- **Locale files**: all 13 keep their keys (including `claude_code` as the
  versions-section key - key renames buy nothing and cost mergeability);
  values get product-name swaps ("Claude" -> "Codex", "Claude Code" ->
  "Codex CLI", Anthropic references removed) plus the three new keys.
- **App class**: `UsageMonitorForClaude` -> `UsageMonitorForCodex`
  (mechanical rename in `app.py`, `__main__.py`, `popup.py` type hint,
  tests). Package and module names stay.
- **`instance_id.py`**: same structure; `parse_config_dir()` becomes
  `parse_codex_home()` parsing `--codex-home` (both `=` and space forms,
  same quote/env-var/`~` handling); `effective_config_dir()` reads
  `CODEX_HOME` with default `~/.codex`; same hash-suffix scheme.
- **`__main__.py`**: resolves `--codex-home` into `CODEX_HOME` before other
  package imports (same ordering constraint as today); restart passthrough
  uses `--codex-home`.
- **`codex_cli.py`** (renamed from `claude_cli.py`): discovers the native
  `codex` binary (which -> `%LOCALAPPDATA%\Programs\OpenAI\Codex\bin` ->
  npm), parses `codex --version` (output format `codex-cli 0.140.0`),
  scans the same four IDE extension directories for the `openai.chatgpt-`
  prefix (verified format: `openai.chatgpt-26.707.71524-win32-x64`).
  `refresh_token()` and update parsing are deleted, not ported. The rename
  is recorded in the sync ledger file map.
- **`verbose.py`**: the credentials section is removed entirely (no
  credential-store access, not even existence checks); replaced by
  `CODEX_HOME` and Codex CLI path/version rows. WebView2/.NET/DPI/locale
  diagnostics unchanged.
- **`settings.py`**: `SETTINGS_FILENAME` constant updated; search paths
  swap `~/.claude` for `~/.codex`; `notify_claude_update` removed from
  `_BOOL_KEYS` and exports.
- **License and attribution**: the MIT license is preserved with the
  upstream copyright line intact (fork copyright added alongside), and the
  README credits the upstream project explicitly.
- **Disclaimer**: the README states the project is independent and not
  created, endorsed, or supported by OpenAI; "Codex", "ChatGPT", and
  "OpenAI" are used descriptively (mirroring the upstream Anthropic
  disclaimer).

### Multi-account scope (qualified)

`--codex-home` isolates settings, mutex, autostart, and the child's
`CODEX_HOME`. Whether separate `CODEX_HOME` values isolate *accounts*
depends on the Codex credential store: with `keyring` (or `auto`
resolving to keyring) storage, credentials may be shared machine-wide.
The README documents that running one monitor per account requires
`cli_auth_credentials_store = "file"` in each Codex home's config, and
that keyring-based multi-account isolation is untested. Verified
keyring isolation is a non-goal (Section 11).

## Section 7: Coexistence Guarantees

- Both EXEs run simultaneously from separate folders with nothing shared:
  distinct mutexes (no cross-product replace-instance prompt), distinct
  autostart values, distinct settings files, distinct process names,
  visually distinct tray icons (different zero-state glyph).
- A dedicated unit test asserts the Codex identity constants (mutex base,
  PID-mapping base, autostart value name, settings filename, pystray name)
  differ from the literal upstream Claude values, so an upstream merge can
  never silently reintroduce a collision.
- Recommended install layout documented in the README: separate folders,
  e.g. `C:\Tools\UsageMonitorForClaude\` and `C:\Tools\UsageMonitorForCodex\`.

## Section 8: Build Location and Commands

- Development, tests, and builds run in a native Windows clone on an NTFS
  volume. A WSL clone may remain an investigation/planning copy, but no builds
  or test runs use WSL Python or `\\wsl.localhost` UNC paths. The design does
  not depend on a fixed checkout path.
- Commands (native Windows Python 3.10+):

  ```powershell
  python -m venv .venv
  .venv\Scripts\activate
  pip install -r requirements.txt
  python -m unittest discover -s tests
  python -m usage_monitor_for_claude --verbose   # source smoke test
  python build.py                                 # -> dist\UsageMonitorForCodex.exe
  dist\UsageMonitorForCodex.exe --verbose         # frozen smoke test
  ```

- `requirements.txt` drops `requests` (no direct HTTP remains). The spec
  file's `excludes` list is re-verified after the removal with a clean
  frozen-EXE smoke test (the `email`-module caveat was driven by
  urllib3/requests).
- Source entry point stays `python -m usage_monitor_for_claude` in v1; the
  README dev section states the package name is retained deliberately for
  upstream mergeability.

## Section 9: Testing Strategy

TDD throughout: every behavior change starts with a failing `unittest`
test. No live account data in unit tests.

**Phase 1 verification tasks** (live, manual, before fixtures are frozen):

- Pin the exact wire method names and response field casing against Codex
  CLI 0.140.0 (probe-verified: `account/read`, `account/rateLimits/read`,
  `usedPercent`, `windowDurationMins`, `resetsAt`).
- Determine whether a running app-server observes an external
  `codex login` (file and keyring stores) without a restart; record the
  result in the spec and adjust the recycle rules/docs per Section 3.
  This experiment is strictly manual and opt-in: the implementer performs
  the logins by hand, and no automated step may log the user out, change
  the credential-store configuration, or initiate a login.

**Fixtures** (`tests/fixtures/codex/*.json`, captured from the live
app-server then sanitized):

1. Normal five-hour plus weekly windows
2. Weekly-only window in `primary` (the verified Plus account shape)
3. `secondary: null`
4. Multi-bucket `rateLimitsByLimitId` including a non-`codex` limit ID
5. Durations outside the known set (90 -> `90_minute`, 43200 -> `30_day`)
6. Window with a missing `windowDurationMins` (limit-ID fallback naming)
7. Missing login (no account)
8. API-key auth and non-ChatGPT provider auth
9. Credits / spend-control metadata present (adapter must ignore it)
10. JSON-RPC error object (auth-shaped and non-auth-shaped variants)
11. JSON-RPC method-not-found error
12. Malformed JSON line

**Unit suites**:

- `test_api.py` (rewritten): every fixture through the adapter - direct
  `usedPercent` mapping (not-inverted test), 10080 -> `seven_day`,
  epoch -> aware ISO-8601, either/or source selection (non-empty keyed map
  ignores the snapshot; null/missing/empty keyed map uses the snapshot),
  null windows skipped, missing `resetsAt` -> `''`, missing-duration
  fallback naming, suffix sanitization, the collision-proof uniqueness
  chain within a source (missing durations, equal durations, slug
  collisions, empty slug), credits excluded; `ProviderFetchResult` carries
  usage and profile together with no module-level state and the
  `dict`/`{}`/`None` profile semantics; the full classification sequence
  (signed-out, API-key, non-ChatGPT provider, recovery only with
  `allow_recovery=True` and reported via `recovery_attempted`,
  classify-from-actual-error with unknown-defaults-to-transient,
  method-not-found -> `codex_cli_too_old`); fingerprint normalization,
  `None` fingerprint when email is absent, and `plan_type` normalizing
  to `''`.
- `test_formatting.py` (extended): `parse_field_name` digit-prefix and
  `minute`-unit cases; the exact label matrix from Section 2;
  duration-seconds sort order including the preserved relative order of
  existing fields; `resolve_display_fields` - all six cases from
  Section 5 plus mode-suffix handling.
- `test_app_server.py` (new): transport against a fake child
  (`tests/fake_app_server.py`, a Python script speaking JSONL on stdio) -
  handshake order; request correlation under interleaved responses;
  timeout with generation isolation (a late response from the previous
  child never satisfies a new request); atomic provider operations - child
  exit between the RPCs of one operation discards partial results and
  repeats the whole operation exactly once, TTL expiry mid-operation never
  triggers a restart (checked only at operation boundaries), no result
  ever mixes generations, and a child dying immediately after the
  refresh-enabled account request results in exactly one refresh-enabled
  read across both generations (the recovery-consumed latch);
  restart-once after child exit;
  dead-after-second-failure; child TTL recycle at an operation boundary;
  the `jsonrpc` header omitted on outgoing messages and not required on
  incoming ones; malformed JSON line kills the child and returns a
  classified error; an unexpected server request receives a
  method-not-found response *while a client request is outstanding* (the
  locking-model deadlock case), and the client never hangs;
  `account/updated` increments the monotonic auth revision; Job-object
  assignment failure terminates the child and fails startup; stderr ring
  buffer capture and redaction; clean shutdown; CLI-not-found.
- `test_cache.py` (adapted): `_fetch_and_process()` stores usage and
  profile atomically from one `ProviderFetchResult` with the
  `dict`/`{}`/`None` semantics; `refresh_profile()` works inside the
  `POLL_FAST` cooldown; the episode guard - `allow_recovery=True` exactly
  once per continuous failing episode (including all-transient episodes),
  reset on success and on a stored-fingerprint change; removal of
  failed-token blocking (error cadence governs retries); all
  cooldown/backoff invariants.
- `test_app.py` (adapted): per-poll fingerprint switch detection;
  suppressed switch notification when the fingerprint is `None`;
  `auth_revision()` change confirmed via `cache.refresh_profile()` with
  `update(force=True)` only on a confirmed switch; bounded child-recycle
  rule in signed-out/auth-error state; tray auto-substitution; existing
  polling/reset/idle/notification invariants stay green with Codex-shaped
  fixtures.
- Identity test (new): Codex constants differ from the hardcoded upstream
  Claude literals (Section 7).
- `test_tray_icon.py` (adapted): zero-usage glyph is `>_`; bar and warn
  rendering unchanged.
- `test_claude_cli.py` -> `test_codex_cli.py` (adapted): `codex` binary
  discovery including the `%LOCALAPPDATA%` installer path, `codex-cli
  X.Y.Z` version parsing, `openai.chatgpt-` extension scanning;
  refresh-token tests deleted with the feature.
- `test_instance_id.py`, `test_autostart.py`, `test_single_instance.py`,
  `test_settings.py`, `test_verbose.py` (adapted): `--codex-home` parsing,
  `CODEX_HOME` resolution, Codex identity names, renamed settings file,
  removed `notify_claude_update`, removed credentials diagnostics.
- `test_i18n.py`: all 13 locales contain `not_chatgpt_auth`,
  `codex_cli_not_found`, and `codex_cli_too_old`.

**Integration**: one opt-in live probe under `tests/integration/`,
talking to the real app-server and asserting response shape, never values
or identity. Exclusion from the normal suite is guaranteed by filename,
not directory placement: the file deliberately does not match unittest
discovery's `test*.py` pattern (e.g. `probe_live_app_server.py`) and is
run explicitly by path. The implementation plan verifies the exclusion by
comparing the discovered test count with and without the probe present.

**Smoke** (manual checklist in the implementation plan): source run with
`--verbose`, EXE build, frozen run, visual check of the `>_` glyph at
real tray sizes on both light and dark taskbars, then the dual-monitor
test - both EXEs running, distinct tray icons/tooltips/popups,
independent restart, quit, and autostart, no mutex prompt, no settings
cross-talk, and a final `git status` proving verification modified no
tracked source.

## Section 10: Selective Upstream Sync

- `UPSTREAM_SYNC.md` ledger at the repo root records: the baseline
  (`f9224c2`), the file map (`claude_cli.py -> codex_cli.py`,
  `usage_monitor_for_claude.spec -> usage_monitor_for_codex.spec`,
  `usage_monitor_for_claude.ico -> usage_monitor_for_codex.ico`, deleted
  refresh machinery), the last-reviewed upstream SHA, and one row per
  imported change with source SHA and import method (cherry-pick `-x` or
  manual port).
- One-time setup (run manually by the user):

  ```bash
  git remote add upstream https://github.com/jens-duttke/usage-monitor-for-claude.git
  git fetch upstream --tags
  git config rerere.enabled true
  ```

- Per-review flow: log UI-relevant paths since the last reviewed SHA,
  classify each commit (UI-only / mixed UI+provider / Claude-backend /
  docs / irrelevant), cherry-pick focused UI commits with `-x`, manually
  port the UI part of mixed commits. Never resolve a conflict by
  reintroducing Anthropic endpoints, credential handling, Claude identity
  names, `claude update` behavior, or Claude branding.
- After every import: full Windows unit suite, rebuild, dual-monitor smoke.
- GitHub's one-click "Sync fork" is never used.

## Section 11: First-Release Non-Goals

- Token-activity charts (the token-usage read method)
- Credits / spend-control display (adapter drops the data)
- Subscribing to rate-limit update notifications as a data source
  (`account/updated` is consumed only as an auth-change hint; rate-limit
  notifications are ignored entirely in v1)
- Verified multi-account isolation with keyring credential storage
  (documented file-store requirement instead)
- The account sessions API (add/list/switch) and attestation features
- Earned rate-limit reset redemption
- Workspace messages
- WSL-specific Codex CLI selection
- Full internal package rename
- Installer, code signing, automatic updater
- The dormant `rate_limited` / `extra_usage` code paths stay in place,
  unexercised, for upstream mergeability

## Section 12: Documentation Deliverables

- `README.md`: Codex product identity throughout - features (including the
  auto-substituted tray fields and multi-instance via `--codex-home` with
  the file-store requirement for multi-account), security story ("the
  monitor makes no outbound API requests of its own - account data is
  exchanged with the local Codex app-server over stdio, and that external
  process performs network activity according to your Codex
  configuration"), requirements (Codex CLI installed and signed in), quick
  start, how-to-use, building, release steps, upstream credit, and the
  OpenAI independence disclaimer.
- `PRIVACY.md`: network section rewritten (the monitor makes no outbound
  API requests of its own; the local Codex app-server child handles
  authentication and network access per the user's Codex configuration),
  credentials section
  rewritten (no credential file is ever accessed - contents or metadata;
  auth state comes from the app-server), issue URL updated.
- `docs/api-reference.md`: rewritten around the app-server methods used.
- `docs/configuration.md`: renamed settings file, `--codex-home`, removed
  `notify_claude_update`.
- `docs/event-commands.md`: examples updated for Codex context.
- `docs/automatic-update-check.md`: removed with the feature.
- `CHANGELOG.md`: starts fresh for the new product (`[Unreleased]` then
  `1.0.0`); upstream history removed; fork origin credited in the README;
  LICENSE keeps the upstream MIT copyright with the fork's line added.
- Root `AGENTS.md` carries the full project rules (updated for the Codex
  provider boundary: security-critical code isolated in `api.py` and
  `app_server.py`); `.claude/CLAUDE.md` becomes a short synchronized
  pointer to it so both agents receive the same rules.

## Acceptance Criteria

1. No source code accesses `~/.codex/auth.json` or any credential store in
   any way - contents, existence, or metadata. Auth state comes only from
   the app-server.
2. The monitor makes no outbound API requests of its own - account data is
   exchanged with Codex over local stdio, and `requests` is not a
   dependency.
3. A weekly-only `primary` window displays as weekly (label, period, sort,
   time marker), not as five-hour.
4. Null windows produce no popup rows, tooltip lines, or tray bars; a
   window with a missing duration is still displayed (label from its limit
   ID, no time marker).
5. `usedPercent = 29` displays as 29% used.
6. Epoch reset times render correctly in the user's Windows clock format.
7. A weekly-only account shows the weekly bar and percentage as the tray
   top field with no 0% ghost bar.
8. App-server timeouts, child crashes, malformed protocol lines, and
   unexpected server-initiated requests never freeze or crash the tray
   process; the child is killed with the monitor in all exit paths,
   including single-instance replacement (strict Job-object guarantee).
9. Missing CLI, too-old CLI (method-not-found), not-signed-in, and
   non-ChatGPT auth (API key or third-party provider) each produce their
   distinct, actionable message; non-ChatGPT auth is never shown as plan
   usage.
10. A transient rate-limits failure on a valid ChatGPT account is not
    misclassified as an expired session; `auth_expired` requires an
    auth-shaped error after the single refresh-and-retry recovery.
11. Existing threshold, reset, idle-deferral, event-command, stale-data,
    popup, and tray tests remain green after fixture adaptation; no test is
    weakened or removed to pass.
12. `UsageMonitorForClaude.exe` and `UsageMonitorForCodex.exe` run
    simultaneously with distinct mutexes, autostart values, process names,
    tooltips, icons, and settings; neither disturbs the other.
13. `dist\UsageMonitorForCodex.exe` builds with native Windows Python and
    launches on Windows 10/11 x64.

## Risks and Mitigations

- **Wire-format or method-name drift between Codex CLI versions**:
  fixtures are captured per CLI version; the adapter tolerates both
  `rateLimitsByLimitId` and snapshot-only responses; method-not-found is
  feature-detected into a distinct "update Codex" error; the opt-in
  integration probe catches drift early.
- **External account changes not observed by a long-lived child**: the
  child TTL bounds staleness in healthy states (an error-free A -> B
  switch is observed at the first provider operation after TTL expiry,
  roughly `CHILD_TTL` plus the polling delay, excluding idle-paused time),
  the error-state recycle rule bounds it in signed-out/auth-error states,
  and the Phase 1 verification task determines whether either is even
  needed. Together they bound staleness regardless of the outcome.
- **Keyring credential storage**: no file can indicate auth state (handled
  by app-server-authoritative auth), and multi-account isolation is
  documented to require file storage.
- **Orphaned child on hard termination**: the kill-on-close Job object is
  a strict startup requirement, covering `TerminateProcess` paths.
- **The reads may trigger network activity in the child**: a normal poll
  cycle performs two local IPC requests (account, then rate limits), and
  the first failing ChatGPT cycle of an episode up to four (account, rate
  limits, refresh-enabled account read, retry) - where upstream made one
  HTTP request. The `POLL_FAST` cooldown preserves the polling-cycle
  *frequency*, not the request count. Classification reads never request
  token refresh and the episode guard allows recovery once per episode, so
  error-cadence polling cannot cause refresh storms.
- **13-language locale updates**: values are mostly proper-noun swaps plus
  three new keys; `test_i18n.py` enforces completeness, and the popup dev
  page (`dev.html`) is used to spot overflow.
