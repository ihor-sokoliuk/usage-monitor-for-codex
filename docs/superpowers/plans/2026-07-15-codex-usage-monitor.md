# Usage Monitor for Codex - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the Windows tray usage monitor from the Anthropic OAuth API to the local Codex app-server (JSON-RPC over stdio), shipping `UsageMonitorForCodex.exe` that runs beside `UsageMonitorForClaude.exe`.

**Architecture:** A Claude-shaped adapter (`api.py`, same name and dict contracts) over one long-lived `codex app-server` child owned by a new transport module (`app_server.py`). Cache, poll loop, popup, tray, and formatting keep their upstream seams; identity constants, locale values, and build metadata change to the Codex product.

**Tech Stack:** Python 3.10+ (native Windows), unittest, pystray, Pillow, pywebview, PyInstaller. `requests` is removed.

**Spec:** `docs/superpowers/specs/2026-07-15-codex-usage-monitor-design.md` (revision 5, approved). Where this plan and the spec disagree, the spec wins.

## Global Constraints

- **AI never commits.** Every "Suggested manual commit" step is text for the user to run themselves. The executor must never run `git commit`, `git push`, or `git tag`.
- All work happens in a native Windows clone on an NTFS volume. All test/build commands use the Windows venv (`.venv\Scripts\python.exe`). Never run tests or builds with WSL Python, and do not depend on a fixed checkout path.
- Test suite command (must pass at the end of every task): `python -m unittest discover -s tests`
- No source code may access `~/.codex/auth.json` or any credential store - contents, existence, or metadata. Auth state comes only from the app-server account read.
- No outbound API requests from the monitor itself; `requests` must not be imported anywhere after Task 11 Step 7 (the legacy Claude client coexists with the new adapter during Tasks 8-11 so the suite stays green at every task boundary).
- Security-critical provider boundary: `api.py` and `app_server.py` only. No other module talks to the transport.
- Keep the `usage_monitor_for_claude` package name and module layout. No repository-wide rename, no unrelated formatting churn.
- Style: project rules in `.claude/CLAUDE.md` apply (module docstring first, `from __future__ import annotations`, numpydoc, single quotes, 140-160 char lines, hyphens not em dashes, `__all__` in library modules).
- Wire format: JSON-RPC 2.0 semantics with the `"jsonrpc": "2.0"` header omitted on outgoing messages and not required on incoming ones; newline-delimited JSON.
- Never weaken or delete a test to make the suite pass (deleting tests for *removed features* is expected and listed explicitly per task).
- Locale files: keys stay stable except where a task explicitly adds/removes them; template keys never change.

## Implementation outcome (2026-07-16)

The port was implemented on native Windows without agent-created commits. The final automated suite has 935 passing tests (baseline: 902), the live probe used Codex CLI 0.140.0, and the Windows artifact is `UsageMonitorForCodex.exe` 1.0.0.0. `AUTH_ERROR_CODES` remains empty because the live probe produced no exact authentication-error evidence.

The checked-in implementation includes these review corrections to the literal task snippets below:

- `resolve_display_fields()` reserves valid configured fields before filling gaps, then compacts resolved values left. This preserves later explicit selections while still putting a weekly-only window in the first visible slot.
- The poll loop keeps one persistent auth-revision baseline. Failed-state recycling happens before a scheduled provider operation; skipped cache updates roll back the cadence count, and popup refreshes never count.
- Auth-type discriminators are case-normalized before classification and fingerprinting.
- The final documentation uses the audited provider/network/privacy wording, including Codex-child, WebView loopback, event-command, registry, and multi-home file-store boundaries. Those documents supersede older literal prose examples in Task 17.
- The discovery-exclusion proof searches for `probe`; ordinary account-switch tests were renamed so only the deliberately excluded `probe_live_app_server.py` could match.

Automated source/frozen and dual-process smoke checks passed. The official Claude 1.19.0 and Codex 1.0.0 binaries were left running from separate folders for the user-facing tray tooltip, popup, glyph-legibility, pin/drag, and clean-menu-quit observations that require visual interaction.

## Prerequisites (user-performed, before Task 1)

```powershell
# Native Windows clone (once)
git clone https://github.com/ihor-sokoliuk/usage-monitor-for-codex.git
cd usage-monitor-for-codex
git remote add upstream https://github.com/jens-duttke/usage-monitor-for-claude.git
git fetch upstream --tags
git config rerere.enabled true
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## File Map

| File | Action | Responsibility |
|---|---|---|
| `usage_monitor_for_claude/app_server.py` | create | JSONL JSON-RPC transport, one child, job object, TTL, generations, auth revision |
| `usage_monitor_for_claude/api.py` | rewrite | Adapter: normalization, classification, `ProviderFetchResult`, `refresh_profile`, `auth_revision` re-export |
| `usage_monitor_for_claude/codex_cli.py` | rename from `claude_cli.py` | Codex CLI + extension discovery, versions, URLs; no refresh |
| `usage_monitor_for_claude/formatting.py` | modify | digit/minute parsing, label fix, duration sort, `resolve_display_fields`, GPT casing |
| `usage_monitor_for_claude/cache.py` | modify | `ProviderFetchResult` consumption, profile semantics, episode guard, `refresh_profile()` |
| `usage_monitor_for_claude/app.py` | modify | auth-revision watcher, error-state recycle, tray substitution, startup warning, identity |
| `usage_monitor_for_claude/instance_id.py` | modify | `--codex-home` / `CODEX_HOME` / `~/.codex` |
| `usage_monitor_for_claude/settings.py` | modify | settings filename, `~/.codex` path, remove `notify_claude_update` |
| `usage_monitor_for_claude/autostart.py` | modify | Codex registry value name, `--codex-home` command |
| `usage_monitor_for_claude/single_instance.py` | modify | Codex mutex/mapping names |
| `usage_monitor_for_claude/verbose.py` | modify | remove credentials section; CODEX_HOME + Codex CLI rows |
| `usage_monitor_for_claude/tray_icon.py` | modify | `>_` zero-state glyph |
| `usage_monitor_for_claude/popup.py` | modify | class-name type hint, `codex_cli` import |
| `usage_monitor_for_claude/__main__.py` | modify | `--codex-home`, CODEX_HOME env, transport shutdown, titles |
| `usage_monitor_for_claude/__init__.py` | modify | version 1.0.0, docstring |
| `locale/*.json` (13 files) | modify | new keys, removed keys, Codex values |
| `tests/fake_app_server.py` | create | scripted fake child for transport tests |
| `tests/test_app_server.py` | create | transport suite |
| `tests/test_identity.py` | create | identity-collision suite |
| `tests/test_api.py` | rewrite | adapter suite (fixtures) |
| `tests/test_codex_cli.py` | rename from `test_claude_cli.py` | discovery suite |
| `tests/fixtures/codex/` | create | 14 sanitized JSON fixtures + `WIRE_NOTES.md` |
| `tests/integration/probe_live_app_server.py` | create | opt-in live probe (not discovered) |
| `tools/generate_icon.py` | create | one-off .ico generator |
| `usage_monitor_for_codex.spec`, `build.py`, `version_info.py`, `requirements.txt` | modify/rename | build identity |
| `usage_monitor_for_claude.spec`, `usage_monitor_for_claude.ico` | delete | replaced |
| `README.md`, `PRIVACY.md`, `CHANGELOG.md`, `LICENSE`, `docs/*`, `AGENTS.md`, `.claude/CLAUDE.md`, `UPSTREAM_SYNC.md` | modify/create | product docs |

Task order: 1 baseline, 2 probe+fixtures, 3-4 formatting, 5-7 transport, 8-9 adapter (+locale keys), 10 cache, 11 app, 12 identity, 13 codex_cli, 14 tray/icon, 15 locale sweep, 16 build, 17 docs, 18 final verification.

---

### Task 1: Baseline verification on Windows

**Files:** none modified.

- [ ] **Step 1: Run the untouched suite**

Run: `python -m unittest discover -s tests`
Expected: `OK` with 0 failures (record the exact test count; it is the baseline for the Task 18 comparison).

- [ ] **Step 2: Build and smoke the untouched Claude EXE**

Run: `python build.py` then `dist\UsageMonitorForClaude.exe --verbose`
Expected: build succeeds; tray icon appears; quit cleanly via tray menu. This proves the toolchain before any port change.

- [ ] **Step 3: Record baseline**

Note the baseline commit (`git rev-parse HEAD` must equal `f9224c2667ce7210464590d1e5e3f5d8637c8c69`) and the test count in your working notes.

No commit (nothing changed).

---

### Task 2: Live probe, fixtures, and wire pinning

**Files:**
- Create: `tests/integration/probe_live_app_server.py`
- Create: `tests/fixtures/codex/` (14 fixture files plus `WIRE_NOTES.md`, listed below)

**Interfaces:**
- Produces: fixture filenames used verbatim by Tasks 8-9 tests; pinned wire constants (`account/read`, `account/rateLimits/read`, `account/updated`, the refresh parameter name, auth-shaped error codes) recorded at the top of `tests/fixtures/codex/WIRE_NOTES.md`.

- [ ] **Step 1: Write the standalone probe (not matching `test*.py`, so never discovered)**

```python
"""
Live App-Server Probe
======================

Opt-in integration probe: spawns the real ``codex app-server``, performs the
handshake, reads account and rate limits, and prints sanitized JSON shapes.
Run explicitly: ``python tests/integration/probe_live_app_server.py``.
Never run by unittest discovery (filename does not match ``test*.py``).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading

REQUESTS = [
    ('account/read', {'refreshToken': False}),
    ('account/rateLimits/read', {}),
]


def sanitize(value, key=''):
    if isinstance(value, dict):
        return {k: sanitize(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if key in ('email', 'name') and isinstance(value, str):
        return 'user@example.com'
    return value


def main() -> int:
    codex = shutil.which('codex')
    if not codex:
        print('codex CLI not found on PATH', file=sys.stderr)
        return 1

    proc = subprocess.Popen([codex, 'app-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding='utf-8')
    assert proc.stdin is not None and proc.stdout is not None

    def send(message: dict) -> None:
        proc.stdin.write(json.dumps(message) + '\n')
        proc.stdin.flush()

    responses: dict[int, dict] = {}
    arrived = threading.Condition()

    def reader() -> None:
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                print(f'NON-JSON LINE: {line[:80]!r}')
                continue
            if 'id' in msg and ('result' in msg or 'error' in msg):
                with arrived:
                    responses[msg['id']] = msg
                    arrived.notify_all()
            else:
                print(f'SERVER MESSAGE: method={msg.get("method")!r} has_id={"id" in msg}')

    def wait_for(request_id: int) -> bool:
        with arrived:
            return arrived.wait_for(lambda: request_id in responses, timeout=30)

    try:
        threading.Thread(target=reader, daemon=True).start()

        # Official sequence: initialize -> await response -> initialized -> data requests.
        send({'id': 0, 'method': 'initialize', 'params': {'clientInfo': {'name': 'usage-monitor-probe', 'version': '0.0.0'}}})
        if not wait_for(0):
            print('initialize timed out', file=sys.stderr)
            return 1
        send({'method': 'initialized', 'params': {}})

        for index, (method, params) in enumerate(REQUESTS, start=1):
            send({'id': index, 'method': method, 'params': params})
            if not wait_for(index):
                print(f'{method} timed out', file=sys.stderr)
                return 1

        for request_id in sorted(responses):
            print(f'--- response {request_id} ---')
            print(json.dumps(sanitize(responses[request_id]), indent=2))
        return 0
    finally:
        proc.kill()
        proc.wait(timeout=5)
```

- [ ] **Step 2: Run the probe against the live app-server (manual, Windows)**

Run: `python tests\integration\probe_live_app_server.py`
Expected: sanitized JSON for the account read and rate-limits read. Record in `tests/fixtures/codex/WIRE_NOTES.md`: exact method names that worked, exact field casing, the refresh parameter's exact wire name, whether `initialized` was required, and any notification method names observed.

- [ ] **Step 3: Create the 14 fixture files (plus `WIRE_NOTES.md`)**

Save each as `tests/fixtures/codex/<name>.json`. Files 01-03 come from the live probe (sanitized); the rest are hand-authored following the probe's exact casing and the protocol source. Adjust field names to `WIRE_NOTES.md` reality before freezing - the shapes below assume the probe-verified casing, and fixtures 07/09 in particular are illustrative drafts that must be reconciled with the live shapes (`requiresOpenaiAuth`, credits placement).

`01_five_hour_plus_weekly.json`
```json
{"rateLimits": {"primary": {"usedPercent": 12, "windowDurationMins": 300, "resetsAt": 1752600000},
                "secondary": {"usedPercent": 29, "windowDurationMins": 10080, "resetsAt": 1753000000}}}
```

`02_weekly_only_primary.json` (the verified Plus shape)
```json
{"rateLimits": {"primary": {"usedPercent": 29, "windowDurationMins": 10080, "resetsAt": 1753000000},
                "secondary": null}}
```

`03_secondary_null.json`
```json
{"rateLimits": {"primary": {"usedPercent": 55, "windowDurationMins": 300, "resetsAt": 1752600000},
                "secondary": null}}
```

`04_multi_bucket.json`
```json
{"rateLimits": {"primary": {"usedPercent": 12, "windowDurationMins": 300, "resetsAt": 1752600000},
                "secondary": {"usedPercent": 29, "windowDurationMins": 10080, "resetsAt": 1753000000}},
 "rateLimitsByLimitId": {
   "codex":     {"primary": {"usedPercent": 12, "windowDurationMins": 300, "resetsAt": 1752600000},
                 "secondary": {"usedPercent": 29, "windowDurationMins": 10080, "resetsAt": 1753000000}},
   "gpt-5-pro": {"primary": {"usedPercent": 3, "windowDurationMins": 10080, "resetsAt": 1753000000},
                 "secondary": null}}}
```

Note: if `WIRE_NOTES.md` shows `rateLimitsByLimitId` values are flat windows rather than primary/secondary pairs, flatten this fixture accordingly and adjust `_normalize_rate_limits()` in Task 8 to match - the tests encode the *behavior* (either/or source selection, naming), not this exact nesting.

`05_unknown_durations.json`
```json
{"rateLimits": {"primary": {"usedPercent": 10, "windowDurationMins": 90, "resetsAt": 1752600000},
                "secondary": {"usedPercent": 20, "windowDurationMins": 43200, "resetsAt": 1755000000}}}
```

`06_missing_duration.json`
```json
{"rateLimits": {"primary": {"usedPercent": 40, "resetsAt": 1752600000}, "secondary": null}}
```

`07_signed_out_account.json` - the account-read result when not signed in (shape per probe; the protocol carries `requiresOpenaiAuth` alongside the null account):
```json
{"account": null, "requiresOpenaiAuth": true}
```

`08_api_key_account.json` and `08b_bedrock_account.json` (discriminators are camelCase on the wire)
```json
{"account": {"type": "apiKey"}}
```
```json
{"account": {"type": "amazonBedrock"}}
```

`09_credits_metadata.json` - credits are a nested `CreditsSnapshot` object under `rateLimits.credits` (`hasCredits`/`unlimited` booleans, `balance` a nullable string); the adapter must ignore the whole object:
```json
{"rateLimits": {"primary": {"usedPercent": 12, "windowDurationMins": 300, "resetsAt": 1752600000},
                "secondary": null,
                "credits": {"hasCredits": true, "unlimited": false, "balance": "1234"}}}
```

`10_auth_error.json` and `10b_transient_error.json` (JSON-RPC error objects). The `-32001` literal below and everywhere in this plan is a **placeholder**: the real auth-shaped code/data predicate must be captured in `WIRE_NOTES.md` (e.g. by probing while signed out or with an expired session). If no auth-shaped error can be captured, `AUTH_ERROR_CODES` in Task 8 ships **empty** - `auth_expired` then stays unreachable and every unmatched error classifies as transient, which is the spec's safe default.
```json
{"code": -32001, "message": "unauthorized"}
```
```json
{"code": -32603, "message": "internal error"}
```

`11_method_not_found.json`
```json
{"code": -32601, "message": "method not found"}
```

`12_chatgpt_account.json`
```json
{"account": {"type": "chatgpt", "email": "User@Example.com ", "planType": "plus"}}
```

(The email deliberately carries mixed case and a trailing space - Task 8's normalization test depends on it. The spec's "malformed JSON line" fixture is deliberately not a `.json` file: malformed JSON cannot be stored as JSON, so that behavior is driven by the fake child's `malformed` scenario in Task 6.)

- [ ] **Step 4: External-login observation experiment (manual, opt-in)**

With the probe process running, perform by hand: `codex logout` then `codex login` in another terminal (only if you are willing to re-login). Record in `WIRE_NOTES.md` whether the running app-server's next `account/read` reflects the change without a restart, and whether an `account/updated` notification was printed. Do not automate this; skip it if re-login is inconvenient (the child-recycle rules cover both outcomes).

- [ ] **Step 5: Verify the probe is not discovered**

Run: `python -m unittest discover -s tests`
Expected: same test count as Task 1 baseline (the probe filename matches neither `test*.py` nor is imported by any test).

- [ ] **Step 6: Suggested manual commit (user runs)**

```
git add tests/integration tests/fixtures
git commit -m "test: add live app-server probe and sanitized Codex fixtures"
```

---

### Task 3: Formatting - digit/minute parsing, labels, duration sort

**Files:**
- Modify: `usage_monitor_for_claude/formatting.py`
- Test: `tests/test_formatting.py`

**Interfaces:**
- Produces: `parse_field_name(field) -> tuple[int, str, str | None] | None` now accepts digit prefixes (`'30_day'`) and the `'minute'` unit; `tooltip_label`/`popup_label`/`field_period`/`_field_sort_key` handle the new forms; `_TITLE_CASE_EXCEPTIONS` includes `'gpt': 'GPT'`. Consumed by Tasks 4, 8, 11.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_formatting.py`)

```python
class TestExtendedFieldNames(unittest.TestCase):
    """Digit prefixes and the minute unit (Codex window durations)."""

    def test_parse_digit_day(self):
        self.assertEqual(parse_field_name('30_day'), (30, 'day', None))

    def test_parse_digit_hour(self):
        self.assertEqual(parse_field_name('13_hour'), (13, 'hour', None))

    def test_parse_minute_unit(self):
        self.assertEqual(parse_field_name('90_minute'), (90, 'minute', None))

    def test_parse_digit_with_variant(self):
        self.assertEqual(parse_field_name('30_day_gpt_5_pro'), (30, 'day', 'gpt_5_pro'))

    def test_parse_rejects_unknown_unit(self):
        self.assertIsNone(parse_field_name('90_fortnight'))

    def test_field_period_minute(self):
        self.assertEqual(field_period('90_minute'), 90 * 60)

    def test_label_matrix(self):
        cases = [
            ('90_minute', '90m', 'Session (90min)'),
            ('five_hour', '5h', 'Session (5hr)'),
            ('13_hour', '13h', 'Session (13hr)'),
            ('seven_day', '7d', 'Weekly (7 day)'),
            ('30_day', '30d', 'Weekly (30 day)'),
            ('seven_day_gpt_5_pro', '7d GPT 5 Pro', 'Weekly (GPT 5 Pro)'),
        ]
        for field, tooltip, popup in cases:
            with self.subTest(field=field):
                self.assertEqual(tooltip_label(field), tooltip)
                self.assertEqual(popup_label(field), popup)

    def test_sort_by_duration_seconds(self):
        fields = ['30_day', 'seven_day', '90_minute', 'five_hour', 'primary', 'seven_day_gpt_5_pro']
        ordered = sorted(fields, key=_field_sort_key)
        self.assertEqual(ordered, ['90_minute', 'five_hour', 'seven_day', 'seven_day_gpt_5_pro', '30_day', 'primary'])

    def test_existing_relative_order_preserved(self):
        fields = ['seven_day_opus', 'seven_day', 'five_hour']
        self.assertEqual(sorted(fields, key=_field_sort_key), ['five_hour', 'seven_day', 'seven_day_opus'])
```

Add `_field_sort_key` and any missing names to the test module's import from `usage_monitor_for_claude.formatting`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_formatting.TestExtendedFieldNames -v`
Expected: FAIL - `test_parse_digit_day` returns `None` (digits unparsed), `test_parse_minute_unit` returns `None`, `test_label_matrix` fails on `90_minute` (weekly label) and `GPT` casing, `test_sort_by_duration_seconds` misplaces `90_minute` after the day fields.

- [ ] **Step 3: Implement in `formatting.py`**

Change `_UNIT_SUFFIXES` and `_TITLE_CASE_EXCEPTIONS`:

```python
_UNIT_SUFFIXES = {'minute': 'm', 'hour': 'h', 'day': 'd'}
_TITLE_CASE_EXCEPTIONS = {'oauth': 'OAuth', 'api': 'API', 'ai': 'AI', 'gpt': 'GPT'}
```

In `parse_field_name()`, replace the number lookup:

```python
    if parts[0].isdigit():
        number = int(parts[0])
    else:
        number = _NUMBER_WORDS.get(parts[0])
    unit = parts[1]
    if number is None or unit not in _UNIT_SUFFIXES:
        return None
```

In `popup_label()`, replace the suffix/template selection:

```python
    if variant:
        suffix = _title_case_variant(variant)
    elif unit == 'hour':
        suffix = f'{number}hr'
    elif unit == 'minute':
        suffix = f'{number}min'
    else:
        suffix = f'{number} {unit}'

    template_key = 'weekly_label' if unit == 'day' else 'session_label'
    return T[template_key].format(suffix=suffix)
```

In `field_period()`, add the minute branch:

```python
    if unit == 'minute':
        return number * 60
    if unit == 'hour':
        return number * 3600
    if unit == 'day':
        return number * 24 * 3600
    return None
```

Replace `_field_sort_key()` entirely:

```python
def _field_sort_key(field: str) -> tuple[int, int, int, str]:
    """Sort key: shorter period durations first, base before variants, unparseable fields last."""
    period = field_period(field)
    if period is None:
        return (1, 0, 0, field)

    parsed = parse_field_name(field)
    variant = parsed[2] if parsed else None
    variant_order = 0 if variant is None else 1
    return (0, period, variant_order, variant or '')
```

- [ ] **Step 4: Run the full formatting suite**

Run: `python -m unittest tests.test_formatting -v`
Expected: all PASS, including every pre-existing test (the sort change preserves relative order of `five_hour`/`seven_day`/variants; if any existing test asserts the old ordinal internals, adapt its expectation to the same visible order, never to a weaker one).

- [ ] **Step 5: Full suite**

Run: `python -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 6: Suggested manual commit (user runs)**

```
git add usage_monitor_for_claude/formatting.py tests/test_formatting.py
git commit -m "feat: parse digit and minute quota field names with duration-based sorting"
```

---

### Task 4: `resolve_display_fields()` - tray/tooltip auto-substitution helper

**Files:**
- Modify: `usage_monitor_for_claude/formatting.py` (add function + `__all__` entry)
- Test: `tests/test_formatting.py`

**Interfaces:**
- Produces: `resolve_display_fields(configured: list[str], data: dict[str, Any], count: int) -> list[str | None]`. Entries keep their configured string (including `:overage` mode suffix) when the base field exists in `data`; gaps are filled with remaining detected fields (bare name, default mode) in `_field_sort_key` order; exhausted slots are `None`. Consumed by Task 11 (`_render_tray`, `format_tooltip`).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_formatting.py`)

```python
class TestResolveDisplayFields(unittest.TestCase):
    """Auto-substitution of absent configured fields for tray icon and tooltip."""

    DATA_BOTH = {
        'five_hour': {'utilization': 12, 'resets_at': 'x'},
        'seven_day': {'utilization': 29, 'resets_at': 'y'},
    }
    DATA_WEEKLY_ONLY = {'seven_day': {'utilization': 29, 'resets_at': 'y'}}

    def test_both_available_unchanged(self):
        self.assertEqual(resolve_display_fields(['five_hour', 'seven_day'], self.DATA_BOTH, 2),
                         ['five_hour', 'seven_day'])

    def test_missing_field_substituted(self):
        self.assertEqual(resolve_display_fields(['five_hour', 'seven_day'], self.DATA_WEEKLY_ONLY, 2),
                         ['seven_day', None])

    def test_zero_available(self):
        self.assertEqual(resolve_display_fields(['five_hour', 'seven_day'], {}, 2), [None, None])

    def test_configured_duplicates_not_doubled(self):
        self.assertEqual(resolve_display_fields(['seven_day', 'seven_day'], self.DATA_BOTH, 2),
                         ['seven_day', 'five_hour'])

    def test_more_than_two_detected(self):
        data = dict(self.DATA_BOTH)
        data['seven_day_gpt_5_pro'] = {'utilization': 3, 'resets_at': 'z'}
        self.assertEqual(resolve_display_fields(['five_hour', 'missing_field'], data, 2),
                         ['five_hour', 'seven_day'])

    def test_mode_suffix_kept_for_existing_and_default_for_substituted(self):
        self.assertEqual(resolve_display_fields(['five_hour:overage', 'no_such:overage'], self.DATA_BOTH, 2),
                         ['five_hour:overage', 'seven_day'])

    def test_extra_usage_never_selected(self):
        data = {'extra_usage': {'is_enabled': True, 'used_credits': 1, 'monthly_limit': 2},
                'seven_day': {'utilization': 29, 'resets_at': 'y'}}
        self.assertEqual(resolve_display_fields(['five_hour', 'seven_day'], data, 2), ['seven_day', None])

    def test_tooltip_length_count(self):
        self.assertEqual(resolve_display_fields(['five_hour'], self.DATA_BOTH, 1), ['five_hour'])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_formatting.TestResolveDisplayFields -v`
Expected: FAIL with `ImportError`/`NameError` - `resolve_display_fields` does not exist.

- [ ] **Step 3: Implement** (add to `formatting.py`, after `expand_popup_fields`; add `'resolve_display_fields'` to `__all__`)

```python
def resolve_display_fields(configured: list[str], data: dict[str, Any], count: int) -> list[str | None]:
    """Resolve configured display fields against the fields actually present in the data.

    Each configured entry keeps its slot (including a ``:mode`` suffix) when its
    base field exists in *data*.  Slots whose field is absent are filled with the
    remaining detected fields in duration order, using the default mode.  Slots
    with nothing left to show are ``None``.

    Parameters
    ----------
    configured : list[str]
        Configured field entries, e.g. ``['five_hour', 'seven_day:overage']``.
    data : dict
        Usage data dict (quota fields plus ``extra_usage``).
    count : int
        Number of slots to return; the result always has exactly this length.
    """
    detected = []
    for key, value in data.items():
        if key == 'extra_usage' or not isinstance(value, dict):
            continue
        if value.get('utilization') is not None:
            detected.append(key)
    detected.sort(key=_field_sort_key)

    used: set[str] = set()
    slots: list[str | None] = []
    for entry in configured[:count]:
        base = entry.split(':', 1)[0]
        if base in detected and base not in used:
            used.add(base)
            slots.append(entry)
        else:
            slots.append(None)
    while len(slots) < count:
        slots.append(None)

    remaining = [field for field in detected if field not in used]
    for index, slot in enumerate(slots):
        if slot is None and remaining:
            slots[index] = remaining.pop(0)

    return slots
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_formatting.TestResolveDisplayFields -v`
Expected: all PASS.

- [ ] **Step 5: Full suite**

Run: `python -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 6: Suggested manual commit (user runs)**

```
git add usage_monitor_for_claude/formatting.py tests/test_formatting.py
git commit -m "feat: add resolve_display_fields for tray and tooltip auto-substitution"
```

---

### Task 5: Codex CLI discovery for the transport

**Files:**
- Create: `usage_monitor_for_claude/app_server.py` (discovery + exceptions only in this task)
- Test: `tests/test_app_server.py` (new)

**Interfaces:**
- Produces: `discover_codex_command() -> list[str]` (raises `CodexCliNotFound`); exceptions `TransportError(Exception)`, `CodexCliNotFound(TransportError)`, `RpcError(Exception)` with attributes `code: int | None`, `message: str`, `data: Any`. Consumed by Tasks 6-9.

- [ ] **Step 1: Write the failing tests** (create `tests/test_app_server.py`)

```python
"""
App-Server Transport Tests
===========================

Unit tests for the Codex app-server transport: CLI discovery, child
lifecycle, JSON-RPC correlation, and atomic provider operations.  All
child-process tests run against ``tests/fake_app_server.py``.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from usage_monitor_for_claude.app_server import CodexCliNotFound, RpcError, TransportError, discover_codex_command


class TestDiscoverCodexCommand(unittest.TestCase):
    """CLI discovery order: which -> LOCALAPPDATA installer -> npm -> error."""

    def test_which_hit_wins(self):
        with patch('usage_monitor_for_claude.app_server.shutil.which', return_value=r'C:\bin\codex.cmd'):
            self.assertEqual(discover_codex_command(), [r'C:\bin\codex.cmd', 'app-server'])

    def test_ps1_shim_substituted_with_cmd_sibling(self):
        with patch('usage_monitor_for_claude.app_server.shutil.which', return_value=r'C:\bin\codex.ps1'), \
             patch.object(Path, 'is_file', lambda self: self.suffix.lower() == '.cmd'):
            self.assertEqual(discover_codex_command(), [r'C:\bin\codex.cmd', 'app-server'])

    def test_ps1_without_executable_sibling_falls_through(self):
        installer = r'C:\Users\u\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe'
        with patch('usage_monitor_for_claude.app_server.shutil.which', return_value=r'C:\bin\codex.ps1'), \
             patch.dict('os.environ', {'LOCALAPPDATA': r'C:\Users\u\AppData\Local', 'APPDATA': r'C:\Users\u\AppData\Roaming'}), \
             patch.object(Path, 'is_file', lambda self: str(self) == installer):
            self.assertEqual(discover_codex_command(), [installer, 'app-server'])

    def test_localappdata_installer_fallback(self):
        installer = r'C:\Users\u\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe'
        with patch('usage_monitor_for_claude.app_server.shutil.which', return_value=None), \
             patch.dict('os.environ', {'LOCALAPPDATA': r'C:\Users\u\AppData\Local', 'APPDATA': r'C:\Users\u\AppData\Roaming'}), \
             patch.object(Path, 'is_file', lambda self: str(self) == installer):
            self.assertEqual(discover_codex_command(), [installer, 'app-server'])

    def test_npm_fallback(self):
        npm_cmd = r'C:\Users\u\AppData\Roaming\npm\codex.cmd'
        with patch('usage_monitor_for_claude.app_server.shutil.which', return_value=None), \
             patch.dict('os.environ', {'LOCALAPPDATA': r'C:\Users\u\AppData\Local', 'APPDATA': r'C:\Users\u\AppData\Roaming'}), \
             patch.object(Path, 'is_file', lambda self: str(self) == npm_cmd):
            self.assertEqual(discover_codex_command(), [npm_cmd, 'app-server'])

    def test_not_found_raises(self):
        with patch('usage_monitor_for_claude.app_server.shutil.which', return_value=None), \
             patch.dict('os.environ', {'LOCALAPPDATA': r'C:\x', 'APPDATA': r'C:\y'}), \
             patch.object(Path, 'is_file', lambda self: False):
            with self.assertRaises(CodexCliNotFound):
                discover_codex_command()

    def test_exception_hierarchy(self):
        self.assertTrue(issubclass(CodexCliNotFound, TransportError))
        err = RpcError(-32601, 'method not found')
        self.assertEqual((err.code, err.message, err.data), (-32601, 'method not found', None))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_app_server -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'usage_monitor_for_claude.app_server'`.

- [ ] **Step 3: Create `app_server.py` with discovery and exceptions**

```python
"""
App-Server Transport
=====================

Owns the single long-lived ``codex app-server`` child process and speaks
JSON-RPC 2.0 semantics over newline-delimited JSON (the ``jsonrpc`` version
header is omitted on the wire, per the official app-server protocol).

Security-critical module: together with ``api.py`` it forms the provider
boundary.  It never accesses credential files and never logs payloads,
tokens, or email - only method names, durations, and error codes.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

__all__ = ['CHILD_TTL', 'INIT_TIMEOUT', 'RPC_TIMEOUT', 'AppServerTransport', 'CodexCliNotFound', 'RpcError', 'TransportError', 'discover_codex_command']

CHILD_TTL = 600
INIT_TIMEOUT = 30
RPC_TIMEOUT = 10

log = logging.getLogger(__name__)


class TransportError(Exception):
    """Transport-level failure: spawn, handshake, timeout, child death, protocol violation."""


class CodexCliNotFound(TransportError):
    """The codex CLI binary could not be located."""


class RpcError(Exception):
    """A JSON-RPC error response from the app-server."""

    def __init__(self, code: int | None, message: str, data: Any = None) -> None:
        super().__init__(f'{code}: {message}')
        self.code = code
        self.message = message
        self.data = data


def discover_codex_command() -> list[str]:
    """Locate the codex CLI and return the app-server launch command.

    Search order: PATH (with ``.ps1`` shim substituted by a ``.cmd``/``.exe``
    sibling), the native installer under ``%LOCALAPPDATA%``, then the npm
    global directory under ``%APPDATA%``.

    Returns
    -------
    list[str]
        The full argv, e.g. ``['C:\\...\\codex.exe', 'app-server']``.

    Raises
    ------
    CodexCliNotFound
        If no codex binary exists in any known location.
    """
    found = shutil.which('codex')
    if found:
        path = Path(found)
        if path.suffix.lower() == '.ps1':
            # subprocess cannot execute PowerShell scripts; use an executable
            # sibling, or fall through to the installer/npm locations.
            for ext in ('.cmd', '.exe'):
                alt = path.with_suffix(ext)
                if alt.is_file():
                    return [str(alt), 'app-server']
        else:
            return [str(path), 'app-server']

    localappdata = os.environ.get('LOCALAPPDATA')
    if localappdata:
        candidate = Path(localappdata) / 'Programs' / 'OpenAI' / 'Codex' / 'bin' / 'codex.exe'
        if candidate.is_file():
            return [str(candidate), 'app-server']

    appdata = os.environ.get('APPDATA')
    if appdata:
        for name in ('codex.cmd', 'codex.exe'):
            candidate = Path(appdata) / 'npm' / name
            if candidate.is_file():
                return [str(candidate), 'app-server']

    raise CodexCliNotFound('codex CLI not found')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_app_server -v`
Expected: all PASS.

- [ ] **Step 5: Suggested manual commit (user runs)**

```
git add usage_monitor_for_claude/app_server.py tests/test_app_server.py
git commit -m "feat: add codex CLI discovery for the app-server transport"
```

---

### Task 6: Transport core - child lifecycle, RPC correlation, reader thread

**Files:**
- Modify: `usage_monitor_for_claude/app_server.py`
- Create: `tests/fake_app_server.py`
- Test: `tests/test_app_server.py`

**Interfaces:**
- Produces: `AppServerTransport(command=None, *, child_ttl=CHILD_TTL, init_timeout=INIT_TIMEOUT, rpc_timeout=RPC_TIMEOUT, codex_home=None)` with methods `run_operation(body)`, `auth_revision() -> int`, `force_restart() -> None`, `shutdown() -> None`, `stderr_tail() -> list[str]`; operation handles expose `request(method: str, params: dict) -> Any`. Consumed by Tasks 7-11.

- [ ] **Step 1: Create the fake child** (`tests/fake_app_server.py` - full file)

```python
"""
Fake App-Server Child
======================

Scripted stand-in for ``codex app-server`` used by the transport tests.
Reads JSONL requests on stdin and answers per the ``--scenario`` flag.
With ``--log PATH`` every received request line is appended to PATH so
tests can assert request counts across process restarts.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

ACCOUNT = {'account': {'type': 'chatgpt', 'email': 'user@example.com', 'planType': 'plus'}}
LIMITS = {'rateLimits': {'primary': {'usedPercent': 12, 'windowDurationMins': 300, 'resetsAt': 1752600000},
                         'secondary': {'usedPercent': 29, 'windowDurationMins': 10080, 'resetsAt': 1753000000}}}
AUTH_ERROR = {'code': -32001, 'message': 'unauthorized'}


def emit(message: dict) -> None:
    sys.stdout.write(json.dumps(message) + '\n')
    sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', default='normal')
    parser.add_argument('--log', default='')
    args = parser.parse_args()

    data_requests_seen = 0
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue

        if args.log:
            with open(args.log, 'a', encoding='utf-8') as log_file:
                log_file.write(json.dumps(msg) + '\n')   # full message, so tests can assert absent keys like 'jsonrpc'

        method = msg.get('method')
        request_id = msg.get('id')

        if method == 'initialize':
            emit({'id': request_id, 'result': {'serverInfo': {'name': 'fake'}}})
            if args.scenario == 'die-after-init':
                return 1
            continue
        if method == 'initialized':
            continue
        if request_id is None:
            continue

        data_requests_seen += 1

        if args.scenario == 'die-on-first-request' and data_requests_seen == 1:
            return 1
        if args.scenario == 'slow':
            time.sleep(30)
            continue
        if args.scenario == 'malformed' and data_requests_seen == 1:
            sys.stdout.write('this is not json\n')
            sys.stdout.flush()
            continue
        if args.scenario == 'server-request' and data_requests_seen == 1:
            emit({'id': 999, 'method': 'tools/confirm', 'params': {}})
            reply = json.loads(sys.stdin.readline())
            if args.log:
                with open(args.log, 'a', encoding='utf-8') as log_file:
                    log_file.write(json.dumps({'reply_to_999': reply}) + '\n')
        if args.scenario == 'notify' and data_requests_seen == 1:
            emit({'method': 'account/updated', 'params': {}})
        if args.scenario == 'noise' and data_requests_seen == 1:
            emit({'id': 424242, 'result': {'spurious': True}})
        if args.scenario == 'stderr':
            from pathlib import Path as _P
            print(f'warning: config at {_P.home()}\\.codex', file=sys.stderr)   # real home path, so home redaction is exercised
            print('token=abcdefghijklmnopqrstuvwxyz012345', file=sys.stderr)
            sys.stderr.flush()

        if method == 'account/read':
            refresh = bool((msg.get('params') or {}).get('refreshToken'))
            emit({'id': request_id, 'result': ACCOUNT})
            if args.scenario == 'die-after-refresh' and refresh:
                return 1
        elif method == 'account/rateLimits/read':
            if args.scenario in ('auth-error', 'die-after-refresh'):
                emit({'id': request_id, 'error': AUTH_ERROR})
            else:
                emit({'id': request_id, 'result': LIMITS})
        else:
            emit({'id': request_id, 'error': {'code': -32601, 'message': 'method not found'}})

    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 2: Write the failing core tests** (append to `tests/test_app_server.py`)

```python
import json
import sys
import tempfile
import time
from pathlib import Path as _Path

from usage_monitor_for_claude.app_server import AppServerTransport

FAKE = str(_Path(__file__).parent / 'fake_app_server.py')


def fake_command(scenario='normal', log=''):
    cmd = [sys.executable, FAKE, '--scenario', scenario]
    if log:
        cmd += ['--log', log]
    return cmd


def simple_body(op):
    return op.request('account/rateLimits/read', {})


class TestTransportCore(unittest.TestCase):
    """Child lifecycle, correlation, and protocol handling against the fake child."""

    def _transport(self, scenario='normal', log='', **kwargs):
        kwargs.setdefault('init_timeout', 10)
        kwargs.setdefault('rpc_timeout', 3)
        transport = AppServerTransport(command=fake_command(scenario, log), **kwargs)
        self.addCleanup(transport.shutdown)
        return transport

    def test_handshake_and_simple_operation(self):
        transport = self._transport()
        result = transport.run_operation(simple_body)
        self.assertEqual(result['rateLimits']['primary']['usedPercent'], 12)

    def test_handshake_order_and_no_jsonrpc_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = str(_Path(tmp) / 'log.jsonl')
            transport = self._transport(log=log)
            transport.run_operation(simple_body)
            transport.shutdown()
            lines = [json.loads(l) for l in _Path(log).read_text(encoding='utf-8').splitlines()]
            self.assertEqual(lines[0]['method'], 'initialize')
            self.assertEqual(lines[1]['method'], 'initialized')
            raw_lines = _Path(log).read_text(encoding='utf-8')
            self.assertNotIn('jsonrpc', raw_lines)

    def test_rpc_error_raises_rpc_error_not_transport_error(self):
        transport = self._transport('auth-error')
        with self.assertRaises(RpcError) as ctx:
            transport.run_operation(simple_body)
        self.assertEqual(ctx.exception.code, -32001)

    def test_timeout_raises_transport_error(self):
        transport = self._transport('slow', rpc_timeout=1)
        started = time.monotonic()
        with self.assertRaises(TransportError):
            transport.run_operation(simple_body)
        self.assertLess(time.monotonic() - started, 15)

    def test_malformed_line_kills_child_and_classifies(self):
        transport = self._transport('malformed', rpc_timeout=2)
        with self.assertRaises(TransportError):
            transport.run_operation(simple_body)

    def test_server_request_answered_while_client_request_outstanding(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = str(_Path(tmp) / 'log.jsonl')
            transport = self._transport('server-request', log=log)
            result = transport.run_operation(simple_body)
            self.assertIn('rateLimits', result)
            entries = [json.loads(l) for l in _Path(log).read_text(encoding='utf-8').splitlines()]
            replies = [e for e in entries if 'reply_to_999' in e]
            self.assertEqual(len(replies), 1)
            self.assertEqual(replies[0]['reply_to_999']['error']['code'], -32601)
            self.assertEqual(replies[0]['reply_to_999']['id'], 999)

    def test_account_updated_increments_auth_revision(self):
        transport = self._transport('notify')
        before = transport.auth_revision()
        transport.run_operation(simple_body)
        deadline = time.monotonic() + 2
        while transport.auth_revision() == before and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(transport.auth_revision(), before + 1)

    def test_stderr_ring_buffer_is_redacted(self):
        transport = self._transport('stderr')
        transport.run_operation(simple_body)
        time.sleep(0.2)
        tail = '\n'.join(transport.stderr_tail())
        self.assertNotIn(str(_Path.home()), tail)   # the fake child emitted the real home path
        self.assertNotIn('abcdefghijklmnopqrstuvwxyz012345', tail)
        self.assertIn('~', tail)

    def test_cli_not_found_propagates(self):
        transport = AppServerTransport(command=None, init_timeout=2, rpc_timeout=2)
        self.addCleanup(transport.shutdown)
        with patch('usage_monitor_for_claude.app_server.discover_codex_command', side_effect=CodexCliNotFound('missing')):
            with self.assertRaises(CodexCliNotFound):
                transport.run_operation(simple_body)

    def test_job_object_failure_terminates_child_and_fails_startup(self):
        import subprocess as _subprocess
        spawned = []
        real_popen = _subprocess.Popen

        def recording_popen(*args, **kwargs):
            proc = real_popen(*args, **kwargs)
            spawned.append(proc)
            return proc

        transport = self._transport()
        with patch('usage_monitor_for_claude.app_server.subprocess.Popen', side_effect=recording_popen), \
             patch('usage_monitor_for_claude.app_server._assign_kill_on_close_job', side_effect=TransportError('job object failed')):
            with self.assertRaises(TransportError):
                transport.run_operation(simple_body)
        self.assertEqual(len(spawned), 1)
        # Observe cleanup without performing it: the implementation must have
        # killed, waited, and closed - never this test.
        deadline = time.monotonic() + 5
        while spawned[0].poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIsNotNone(spawned[0].poll())
        for stream in (spawned[0].stdin, spawned[0].stdout, spawned[0].stderr):
            self.assertTrue(stream is None or stream.closed)

    def test_spurious_response_with_unknown_id_ignored(self):
        transport = self._transport('noise')
        result = transport.run_operation(simple_body)
        self.assertIn('rateLimits', result)   # correlation survives an unsolicited response

    def test_shutdown_terminates_child(self):
        transport = self._transport()
        transport.run_operation(simple_body)
        transport.shutdown()
        transport.shutdown()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m unittest tests.test_app_server.TestTransportCore -v`
Expected: FAIL with `ImportError` - `AppServerTransport` does not exist yet.

- [ ] **Step 4: Implement the transport** (append to `app_server.py`; add imports `ctypes`, `ctypes.wintypes`, `json`, `re`, `subprocess`, `threading`, `time`, `collections.deque`, `typing.Callable`, `typing.TypeVar`)

```python
STDERR_RING_SIZE = 20
_JOB_KILL_ON_CLOSE = 0x00002000
T_ = TypeVar('T_')


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    class _BASIC(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64),
                    ('LimitFlags', ctypes.wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', ctypes.wintypes.DWORD),
                    ('Affinity', ctypes.c_size_t), ('PriorityClass', ctypes.wintypes.DWORD),
                    ('SchedulingClass', ctypes.wintypes.DWORD)]

    class _COUNTERS(ctypes.Structure):
        _fields_ = [('ReadOperationCount', ctypes.c_uint64), ('WriteOperationCount', ctypes.c_uint64),
                    ('OtherOperationCount', ctypes.c_uint64), ('ReadTransferCount', ctypes.c_uint64),
                    ('WriteTransferCount', ctypes.c_uint64), ('OtherTransferCount', ctypes.c_uint64)]

    _fields_ = [('BasicLimitInformation', _BASIC), ('IoInfo', _COUNTERS),
                ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]


# Explicit argtypes/restype: without them ctypes truncates HANDLEs to c_int,
# which corrupts kernel handles on 64-bit Windows.
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
_kernel32.CreateJobObjectW.argtypes = [ctypes.wintypes.LPCVOID, ctypes.wintypes.LPCWSTR]
_kernel32.CreateJobObjectW.restype = ctypes.wintypes.HANDLE
_kernel32.SetInformationJobObject.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, ctypes.wintypes.DWORD]
_kernel32.SetInformationJobObject.restype = ctypes.wintypes.BOOL
_kernel32.AssignProcessToJobObject.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.HANDLE]
_kernel32.AssignProcessToJobObject.restype = ctypes.wintypes.BOOL
_kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
_kernel32.CloseHandle.restype = ctypes.wintypes.BOOL


def _assign_kill_on_close_job(process_handle: int) -> int:
    """Create a kill-on-close Job object and assign the child to it.

    Returns the job handle (kept open for the child's lifetime).  Any API
    failure raises so the caller can enforce the strict no-orphan guarantee.
    """
    job = _kernel32.CreateJobObjectW(None, None)
    if not job:
        raise TransportError('CreateJobObjectW failed')

    info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = _JOB_KILL_ON_CLOSE
    JobObjectExtendedLimitInformation = 9
    if not _kernel32.SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)):
        _kernel32.CloseHandle(job)
        raise TransportError('SetInformationJobObject failed')

    if not _kernel32.AssignProcessToJobObject(job, process_handle):
        _kernel32.CloseHandle(job)
        raise TransportError('AssignProcessToJobObject failed')

    return job


def _close_job_handle(job: int) -> None:
    """Close a job handle; kill-on-close also reaps anything still inside it."""
    _kernel32.CloseHandle(job)


def _redact(line: str) -> str:
    """Strip the home directory and any token-shaped run from a diagnostic line."""
    home = str(Path.home())
    line = line.replace(home, '~').replace(home.replace('\\', '\\\\'), '~')
    return re.sub(r'[A-Za-z0-9_\-\.=/+]{24,}', '***', line.rstrip('\n'))


class _Pending:
    __slots__ = ('event', 'response')

    def __init__(self) -> None:
        self.event = threading.Event()
        self.response: dict[str, Any] | None = None


class _OperationHandle:
    """Request interface handed to an operation body; pinned to one child generation."""

    def __init__(self, transport: AppServerTransport, generation: int) -> None:
        self._transport = transport
        self._generation = generation

    def request(self, method: str, params: dict[str, Any]) -> Any:
        return self._transport._request(self._generation, method, params)


class AppServerTransport:
    """Owns one ``codex app-server`` child and executes atomic provider operations."""

    def __init__(self, command: list[str] | None = None, *, child_ttl: int = CHILD_TTL,
                 init_timeout: float = INIT_TIMEOUT, rpc_timeout: float = RPC_TIMEOUT,
                 codex_home: str | None = None) -> None:
        self._command = command
        self._child_ttl = child_ttl
        self._init_timeout = init_timeout
        self._rpc_timeout = rpc_timeout
        self._codex_home = codex_home

        self._op_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stdin_lock = threading.Lock()

        self._proc: subprocess.Popen | None = None
        self._job_handle: int | None = None
        self._generation = 0
        self._dead = True
        self._child_started_at = 0.0
        self._next_id = 0
        self._pending: dict[int, _Pending] = {}
        self._auth_revision = 0
        self._stderr_ring: deque[str] = deque(maxlen=STDERR_RING_SIZE)

    # Public API

    def run_operation(self, body: Callable[[_OperationHandle], T_]) -> T_:
        """Execute *body* as one atomic provider operation.

        The operation lock is held throughout.  The child TTL is evaluated only
        here, before the first RPC.  If the child dies mid-operation the whole
        body is repeated exactly once against a fresh child; partial results
        are the body's closure state and must be rebuilt by the body itself.
        """
        with self._op_lock:
            self._ensure_child()
            for attempt in (0, 1):
                with self._state_lock:
                    generation = self._generation
                try:
                    return body(_OperationHandle(self, generation))
                except TransportError:
                    if attempt == 1:
                        raise
                    self._kill_child()
                    self._ensure_child()
            raise TransportError('unreachable')  # pragma: no cover

    def auth_revision(self) -> int:
        with self._state_lock:
            return self._auth_revision

    def force_restart(self) -> None:
        """Kill the child; the next operation spawns a fresh one (error-state recycle)."""
        with self._op_lock:
            self._kill_child()

    def shutdown(self) -> None:
        with self._op_lock:
            self._kill_child()

    def stderr_tail(self) -> list[str]:
        with self._state_lock:
            return list(self._stderr_ring)

    # Child lifecycle (call only while holding _op_lock)

    def _ensure_child(self) -> None:
        with self._state_lock:
            alive = self._proc is not None and not self._dead and self._proc.poll() is None
            expired = alive and (time.monotonic() - self._child_started_at) > self._child_ttl
        if alive and not expired:
            return
        self._kill_child()
        self._spawn()

    def _spawn(self) -> None:
        command = self._command or discover_codex_command()
        env = dict(os.environ)
        if self._codex_home:
            env['CODEX_HOME'] = self._codex_home

        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        try:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding='utf-8', env=env, creationflags=creationflags)
        except OSError as exc:
            raise TransportError(f'spawn failed: {exc}') from exc

        try:
            job = _assign_kill_on_close_job(int(proc._handle))  # type: ignore[attr-defined]  # Popen handle needed for AssignProcessToJobObject
        except TransportError:
            # This child was never installed on the transport, so _kill_child()
            # cannot reach it - clean it up fully right here.
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            raise

        with self._state_lock:
            self._proc = proc
            self._job_handle = job
            self._generation += 1
            self._dead = False
            self._child_started_at = time.monotonic()
            generation = self._generation

        threading.Thread(target=self._reader, args=(proc, generation), daemon=True).start()
        threading.Thread(target=self._drain_stderr, args=(proc,), daemon=True).start()

        from . import __version__
        try:
            init_result = self._request(generation, 'initialize',
                                        {'clientInfo': {'name': 'usage-monitor-for-codex', 'title': 'Usage Monitor for Codex', 'version': __version__}},
                                        timeout=self._init_timeout)
            log.info('initialize -> OK (%s)', type(init_result).__name__)
            self._send_line(json.dumps({'method': 'initialized', 'params': {}}))
        except (TransportError, RpcError) as exc:
            # A spawned child that fails the handshake must never linger.
            self._kill_child()
            raise TransportError(f'handshake failed: {exc}') from exc

    def _kill_child(self) -> None:
        with self._state_lock:
            proc = self._proc
            job = self._job_handle
            self._proc = None
            self._job_handle = None
            self._dead = True
            pending = list(self._pending.values())
            self._pending.clear()
        for entry in pending:
            entry.response = None
            entry.event.set()
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
        if job is not None:
            _close_job_handle(job)

    # RPC plumbing

    def _send_line(self, line: str) -> None:
        with self._state_lock:
            proc = self._proc
        if proc is None or proc.stdin is None:
            raise TransportError('child not running')
        with self._stdin_lock:
            try:
                proc.stdin.write(line + '\n')
                proc.stdin.flush()
            except OSError as exc:
                raise TransportError(f'write failed: {exc}') from exc

    def _request(self, generation: int, method: str, params: dict[str, Any], timeout: float | None = None) -> Any:
        pending = _Pending()
        with self._state_lock:
            if generation != self._generation or self._dead:
                raise TransportError('child generation changed')
            self._next_id += 1
            request_id = self._next_id
            self._pending[request_id] = pending

        started = time.monotonic()
        self._send_line(json.dumps({'id': request_id, 'method': method, 'params': params}))
        if not pending.event.wait(timeout if timeout is not None else self._rpc_timeout):
            with self._state_lock:
                self._pending.pop(request_id, None)
            log.warning('%s -> timeout after %.1fs', method, time.monotonic() - started)
            self._kill_child()
            raise TransportError(f'{method} timed out')

        response = pending.response
        if response is None:
            raise TransportError('child died during request')
        if 'error' in response:
            error = response['error'] or {}
            log.warning('%s -> rpc error %s', method, error.get('code'))
            raise RpcError(error.get('code'), str(error.get('message', '')), error.get('data'))
        log.info('%s -> OK (%.2fs)', method, time.monotonic() - started)
        return response.get('result')

    # Reader threads

    def _reader(self, proc: subprocess.Popen, generation: int) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                log.warning('malformed protocol line from child')
                self._fail_generation(generation)
                return

            if 'id' in msg and ('result' in msg or 'error' in msg):
                with self._state_lock:
                    if generation != self._generation:
                        return
                    pending = self._pending.pop(msg['id'], None)
                if pending is not None:
                    pending.response = msg
                    pending.event.set()
            elif 'id' in msg and 'method' in msg:
                # Server-initiated request: answer method-not-found, never hang it.
                try:
                    self._send_line(json.dumps({'id': msg['id'], 'error': {'code': -32601, 'message': 'method not supported'}}))
                except TransportError:
                    return
            elif msg.get('method') == 'account/updated':
                with self._state_lock:
                    if generation == self._generation:
                        self._auth_revision += 1
            # All other notifications are ignored.
        self._fail_generation(generation)

    def _fail_generation(self, generation: int) -> None:
        with self._state_lock:
            if generation != self._generation:
                return
            self._dead = True
            proc = self._proc
            pending = list(self._pending.values())
            self._pending.clear()
        for entry in pending:
            entry.response = None
            entry.event.set()
        if proc is not None and proc.poll() is None:
            proc.kill()

    def _drain_stderr(self, proc: subprocess.Popen) -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            with self._state_lock:
                self._stderr_ring.append(_redact(line))
```

Notes for the implementer:
- `_kill_child()` acquires only `_state_lock` and is called from `run_operation`/`force_restart`/`shutdown` (all hold `_op_lock`) and from `_request` timeout handling (which runs on the operation thread that already holds `_op_lock` via `run_operation`). The reader thread uses `_fail_generation`, which never takes `_op_lock` - no deadlock.
- The malformed-line path fails the in-flight request with `TransportError` ("child died during request"), satisfying "classified error, never an unexplained timeout".
- Add `'app_server'` handling nowhere else - only `api.py` may import this module (Task 9 enforces by convention; Task 18's grep verifies).

- [ ] **Step 5: Run the core tests**

Run: `python -m unittest tests.test_app_server -v`
Expected: all PASS (discovery + core). The stale-generation acceptance case ("a late response from a previous child never satisfies a new request") is covered structurally: timeouts kill the child (closing its pipe) and Task 7's `test_stale_handle_from_previous_generation_rejected` proves old-generation handles are refused; the `noise` test proves unknown-id responses are ignored.

- [ ] **Step 6: Full suite**

Run: `python -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 7: Suggested manual commit (user runs)**

```
git add usage_monitor_for_claude/app_server.py tests/fake_app_server.py tests/test_app_server.py
git commit -m "feat: app-server transport with job object, reader thread, and redacted diagnostics"
```

---

### Task 7: Transport atomicity - generation retry, TTL boundaries, restart-once

**Files:**
- Modify: `usage_monitor_for_claude/app_server.py` (only if a test exposes a gap)
- Test: `tests/test_app_server.py`

**Interfaces:**
- Consumes: Task 6's `AppServerTransport`.
- Produces: proven atomic-operation guarantees relied on by Tasks 9-10.

- [ ] **Step 1: Write the failing/proving tests** (append to `tests/test_app_server.py`)

```python
class TestAtomicOperations(unittest.TestCase):
    """Whole-operation retry, generation pinning, and TTL boundaries."""

    def _transport(self, scenario, log='', **kwargs):
        kwargs.setdefault('init_timeout', 10)
        kwargs.setdefault('rpc_timeout', 3)
        transport = AppServerTransport(command=fake_command(scenario, log), **kwargs)
        self.addCleanup(transport.shutdown)
        return transport

    def test_child_death_mid_operation_repeats_whole_body_once(self):
        transport = self._transport('die-on-first-request')
        calls = []

        def body(op):
            calls.append('attempt')
            return op.request('account/rateLimits/read', {})

        # Attempt 1: child dies on the first data request -> TransportError inside body.
        # The fake child restarts into the same scenario, so attempt 2 dies too and
        # the operation must fail after exactly two body invocations.
        with self.assertRaises(TransportError):
            transport.run_operation(body)
        self.assertEqual(len(calls), 2)

    def test_partial_results_discarded_and_rebuilt(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = str(_Path(tmp) / 'log.jsonl')
            transport = self._transport('die-after-refresh', log=log)
            state = {'refresh_sent': False}

            def body(op):
                op.request('account/read', {'refreshToken': False})
                if not state['refresh_sent']:
                    state['refresh_sent'] = True
                    op.request('account/read', {'refreshToken': True})   # child dies right after answering
                return op.request('account/rateLimits/read', {})

            # Attempt 1 dies after the refresh-enabled read; attempt 2 (latch set in
            # closure state) skips the refresh and reaches the rate-limits read.
            try:
                transport.run_operation(body)
            except RpcError:
                pass  # the scenario answers rate-limits with an auth error - irrelevant here

            entries = [json.loads(l) for l in _Path(log).read_text(encoding='utf-8').splitlines()]
            refresh_reads = [e for e in entries if e.get('method') == 'account/read' and (e.get('params') or {}).get('refreshToken')]
            self.assertEqual(len(refresh_reads), 1)

    def test_ttl_recycles_only_at_operation_boundary(self):
        transport = self._transport('normal', child_ttl=0)

        def body(op):
            first = op.request('account/rateLimits/read', {})
            time.sleep(0.1)   # child is now "older than TTL" mid-operation
            second = op.request('account/rateLimits/read', {})
            return first, second

        first, second = transport.run_operation(body)   # must not restart mid-operation
        self.assertEqual(first, second)
        generation_after_first = transport._generation
        transport.run_operation(simple_body)             # new operation -> TTL recycle
        self.assertGreater(transport._generation, generation_after_first)

    def test_rpc_error_does_not_trigger_operation_retry(self):
        transport = self._transport('auth-error')
        calls = []

        def body(op):
            calls.append('attempt')
            return op.request('account/rateLimits/read', {})

        with self.assertRaises(RpcError):
            transport.run_operation(body)
        self.assertEqual(len(calls), 1)

    def test_force_restart_spawns_new_generation(self):
        transport = self._transport('normal')
        transport.run_operation(simple_body)
        generation = transport._generation
        transport.force_restart()
        transport.run_operation(simple_body)
        self.assertGreater(transport._generation, generation)

    def test_stale_handle_from_previous_generation_rejected(self):
        transport = self._transport('normal')
        captured = {}

        def body(op):
            captured['op'] = op
            return op.request('account/rateLimits/read', {})

        transport.run_operation(body)
        transport.force_restart()
        transport.run_operation(simple_body)
        with self.assertRaises(TransportError):
            captured['op'].request('account/rateLimits/read', {})
```

- [ ] **Step 2: Run tests**

Run: `python -m unittest tests.test_app_server.TestAtomicOperations -v`
Expected: PASS if Task 6's implementation is exact; any FAIL identifies a real gap - fix `app_server.py` (not the test) until green.

- [ ] **Step 3: Full suite**

Run: `python -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 4: Suggested manual commit (user runs)**

```
git add usage_monitor_for_claude/app_server.py tests/test_app_server.py
git commit -m "test: prove atomic provider operations, TTL boundaries, and generation isolation"
```

---

### Task 8: Adapter normalization - windows, naming, collisions, profile

**Files:**
- Modify (additive): `usage_monitor_for_claude/api.py` - the new adapter code is **added alongside** the existing Claude client; nothing is deleted until Task 11 Step 7, so `cache.py`/`app.py` keep compiling and the full suite stays green after this task
- Test: `tests/test_api.py` - append the new test classes; the Claude-era tests stay green until they are deleted together with the legacy code in Task 11 Step 7

**Interfaces:**
- Consumes: fixtures from Task 2; `AppServerTransport`, `RpcError`, `TransportError`, `CodexCliNotFound` from Tasks 5-6.
- Produces (pure, tested directly): `_normalize_rate_limits(payload: dict) -> dict[str, Any]`, `_parse_account(payload: dict | None) -> dict | None | object` (returns the module sentinel `_UNKNOWN` when the payload is unusable), `_profile_from_account(info) -> dict | None` (`{}` for signed-out, `None` for `_UNKNOWN`), `_model_slug(text) -> str` (kept from upstream). Task 9 builds `fetch_provider_data` on these.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_api.py`)

```python
import json
from pathlib import Path

from usage_monitor_for_claude.api import _UNKNOWN, _normalize_rate_limits, _parse_account, _profile_from_account

FIXTURES = Path(__file__).parent / 'fixtures' / 'codex'


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


class TestNormalizeRateLimits(unittest.TestCase):
    """Window normalization: naming, source selection, collisions, values."""

    def test_five_hour_plus_weekly(self):
        result = _normalize_rate_limits(load('01_five_hour_plus_weekly.json'))
        self.assertEqual(set(result), {'five_hour', 'seven_day'})
        self.assertEqual(result['five_hour']['utilization'], 12.0)
        self.assertEqual(result['seven_day']['utilization'], 29.0)

    def test_used_percent_not_inverted(self):
        result = _normalize_rate_limits(load('02_weekly_only_primary.json'))
        self.assertEqual(result['seven_day']['utilization'], 29.0)   # 29% used, never 71

    def test_weekly_only_primary_named_by_duration_not_slot(self):
        result = _normalize_rate_limits(load('02_weekly_only_primary.json'))
        self.assertEqual(list(result), ['seven_day'])                # 10080 min -> weekly, despite being 'primary'

    def test_null_secondary_skipped(self):
        result = _normalize_rate_limits(load('03_secondary_null.json'))
        self.assertEqual(list(result), ['five_hour'])

    def test_epoch_converts_to_aware_utc_iso(self):
        result = _normalize_rate_limits(load('01_five_hour_plus_weekly.json'))
        self.assertEqual(result['five_hour']['resets_at'], '2025-07-15T17:20:00+00:00')

    def test_keyed_source_ignores_snapshot(self):
        result = _normalize_rate_limits(load('04_multi_bucket.json'))
        self.assertEqual(set(result), {'five_hour', 'seven_day', 'seven_day_gpt_5_pro'})

    def test_empty_keyed_map_falls_back_to_snapshot(self):
        payload = load('01_five_hour_plus_weekly.json')
        payload['rateLimitsByLimitId'] = {}
        self.assertEqual(set(_normalize_rate_limits(payload)), {'five_hour', 'seven_day'})
        payload['rateLimitsByLimitId'] = None
        self.assertEqual(set(_normalize_rate_limits(payload)), {'five_hour', 'seven_day'})

    def test_unknown_durations(self):
        result = _normalize_rate_limits(load('05_unknown_durations.json'))
        self.assertEqual(set(result), {'90_minute', '30_day'})

    def test_word_form_day(self):
        payload = {'rateLimits': {'primary': {'usedPercent': 1, 'windowDurationMins': 1440, 'resetsAt': 1752600000}, 'secondary': None}}
        self.assertEqual(list(_normalize_rate_limits(payload)), ['one_day'])

    def test_digit_form_hour_above_twelve(self):
        payload = {'rateLimits': {'primary': {'usedPercent': 1, 'windowDurationMins': 780, 'resetsAt': None}, 'secondary': None}}
        self.assertEqual(list(_normalize_rate_limits(payload)), ['13_hour'])

    def test_missing_duration_snapshot_uses_slot_name(self):
        result = _normalize_rate_limits(load('06_missing_duration.json'))
        self.assertEqual(list(result), ['primary'])
        self.assertEqual(result['primary']['resets_at'], '2025-07-15T17:20:00+00:00')

    def test_missing_reset_becomes_empty_string(self):
        payload = {'rateLimits': {'primary': {'usedPercent': 40, 'windowDurationMins': 300}, 'secondary': None}}
        self.assertEqual(_normalize_rate_limits(payload)['five_hour']['resets_at'], '')

    def test_missing_duration_keyed_uses_slug(self):
        payload = {'rateLimitsByLimitId': {'codex': {'primary': {'usedPercent': 5}, 'secondary': None}}}
        self.assertEqual(list(_normalize_rate_limits(payload)), ['codex'])

    def test_empty_slug_with_duration_named_period_limit(self):
        payload = {'rateLimitsByLimitId': {'--': {'primary': {'usedPercent': 5, 'windowDurationMins': 10080}, 'secondary': None}}}
        self.assertEqual(list(_normalize_rate_limits(payload)), ['seven_day_limit'])

    def test_snapshot_collision_appends_slot(self):
        payload = {'rateLimits': {'primary': {'usedPercent': 1, 'windowDurationMins': 10080, 'resetsAt': 1},
                                  'secondary': {'usedPercent': 2, 'windowDurationMins': 10080, 'resetsAt': 2}}}
        self.assertEqual(set(_normalize_rate_limits(payload)), {'seven_day', 'seven_day_secondary'})

    def test_keyed_collision_appends_counter(self):
        payload = {'rateLimitsByLimitId': {
            'codex': {'primary': {'usedPercent': 1}, 'secondary': {'usedPercent': 2}}}}
        self.assertEqual(set(_normalize_rate_limits(payload)), {'codex', 'codex_2'})

    def test_credits_metadata_ignored(self):
        result = _normalize_rate_limits(load('09_credits_metadata.json'))
        self.assertEqual(set(result), {'five_hour'})
        self.assertNotIn('extra_usage', result)


class TestProfileNormalization(unittest.TestCase):
    """Account payload -> Claude-shaped profile with fingerprint."""

    def test_chatgpt_account(self):
        profile = _profile_from_account(_parse_account(load('12_chatgpt_account.json')))
        self.assertEqual(profile['account']['email'], 'User@Example.com')
        self.assertEqual(profile['account']['uuid'], 'chatgpt:user@example.com')
        self.assertEqual(profile['organization']['organization_type'], 'plus')

    def test_signed_out_is_empty_dict(self):
        self.assertEqual(_profile_from_account(_parse_account(load('07_signed_out_account.json'))), {})

    def test_missing_email_gives_none_fingerprint(self):
        profile = _profile_from_account(_parse_account(load('08_api_key_account.json')))
        self.assertIsNone(profile['account']['uuid'])
        self.assertEqual(profile['account']['email'], '')

    def test_missing_plan_normalizes_to_empty_string(self):
        profile = _profile_from_account(_parse_account({'account': {'type': 'chatgpt', 'email': 'a@b.c'}}))
        self.assertEqual(profile['organization']['organization_type'], '')
        profile['organization']['organization_type'].replace('_', ' ').title()   # must not raise

    def test_unusable_payload_is_unknown(self):
        self.assertIs(_parse_account(None), _UNKNOWN)
        self.assertIsNone(_profile_from_account(_UNKNOWN))
```

Note: `test_epoch_converts_to_aware_utc_iso` assumes `1752600000` = 2025-07-15T17:20:00Z; verify with `python -c "from datetime import datetime, timezone; print(datetime.fromtimestamp(1752600000, tz=timezone.utc).isoformat())"` and correct the literal if the fixture value differs.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_api -v`
Expected: FAIL with `ImportError` (`_UNKNOWN`, `_normalize_rate_limits` do not exist; old `api.py` still holds the Claude client).

- [ ] **Step 3: Add the adapter to `api.py`** (additive)

Merge rules: keep every existing Claude-client definition (constants, `read_access_token`, `api_headers`, `fetch_usage`, `fetch_profile`, helpers, the `requests` import) untouched; add the code below after them, merging the import lines and extending `__all__` with the new names. The module docstring shown here replaces the old one only in Task 11 Step 7, when the legacy client is deleted.

```python
"""
API Client
===========

Adapter between the app-server transport and the Claude-shaped usage and
profile dicts the rest of the application consumes.  Together with
``app_server.py`` this is the security-critical provider boundary: no other
module talks to the Codex app-server, and no module anywhere touches
credential files.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .app_server import AppServerTransport, CodexCliNotFound, RpcError, TransportError
from .i18n import T

__all__ = ['METHOD_ACCOUNT_READ', 'METHOD_RATE_LIMITS_READ', 'PARAM_REFRESH_TOKEN', 'ProviderFetchResult',
           'auth_revision', 'fetch_provider_data', 'refresh_profile', 'restart_child', 'shutdown_transport']

# Wire methods (pinned against tests/fixtures/codex/WIRE_NOTES.md)
METHOD_ACCOUNT_READ = 'account/read'
METHOD_RATE_LIMITS_READ = 'account/rateLimits/read'
PARAM_REFRESH_TOKEN = 'refreshToken'
METHOD_NOT_FOUND_CODE = -32601
# Auth-shaped JSON-RPC error codes: populate ONLY from verified WIRE_NOTES.md
# evidence (Task 2).  Ships EMPTY on purpose - the official protocol uses
# codes like -32001 for server overload, so guessing here would misclassify
# transient failures as expired sessions.  While empty, auth_expired is
# unreachable and every unmatched error stays transient.
AUTH_ERROR_CODES: frozenset[int] = frozenset()

_KNOWN_DURATION_NAMES = {300: 'five_hour', 10080: 'seven_day'}
_NUMBER_TO_WORD = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six',
                   7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten', 11: 'eleven', 12: 'twelve'}

_UNKNOWN = object()  # account state unavailable this cycle (distinct from signed-out)

_transport: AppServerTransport | None = None


@dataclass(frozen=True)
class ProviderFetchResult:
    """One poll cycle's combined result.

    Attributes
    ----------
    usage : dict
        Claude-shaped usage dict: quota fields on success, or ``error`` plus
        optional flags (``auth_error``, ``no_auth``) on failure.
    profile : dict or None
        Fresh normalized profile, ``{}`` for an authoritative signed-out
        state, or ``None`` when account state was unavailable this cycle.
    recovery_attempted : bool
        True when the refresh-enabled recovery sub-sequence ran (logical OR
        across the operation's internal retry).
    """

    usage: dict[str, Any]
    profile: dict[str, Any] | None
    recovery_attempted: bool = False


def fetch_provider_data(allow_recovery: bool = False) -> ProviderFetchResult:
    """Read account and rate limits as one atomic provider operation."""
    latch = {'attempted': False}
    try:
        transport = _get_transport()

        def body(op: Any) -> ProviderFetchResult:
            try:
                account_info = _read_account(op, refresh=False)
            except RpcError:
                # Only method-not-found escapes _read_account: a required
                # method is missing, so the CLI is incompatible - never a
                # connection error, never silent usage without a profile.
                return ProviderFetchResult(usage={'error': T['codex_cli_too_old']}, profile=None,
                                           recovery_attempted=latch['attempted'])
            profile = _profile_from_account(account_info)
            try:
                usage = _normalize_rate_limits(op.request(METHOD_RATE_LIMITS_READ, {}))
                return ProviderFetchResult(usage=usage, profile=profile, recovery_attempted=latch['attempted'])
            except RpcError as error:
                return _classify_and_recover(op, error, account_info, allow_recovery, latch)

        return transport.run_operation(body)
    except CodexCliNotFound:
        return ProviderFetchResult(usage={'error': T['codex_cli_not_found']}, profile=None, recovery_attempted=latch['attempted'])
    except TransportError:
        return ProviderFetchResult(usage={'error': T['connection_error']}, profile=None, recovery_attempted=latch['attempted'])


def refresh_profile() -> dict[str, Any] | None:
    """Account-only read, independent of the usage cooldown; None on failure."""
    try:
        transport = _get_transport()

        def body(op: Any) -> dict[str, Any] | None:
            return _profile_from_account(_read_account(op, refresh=False))

        return transport.run_operation(body)
    except (TransportError, RpcError):
        return None


def auth_revision() -> int:
    """Monotonic counter of ``account/updated`` notifications (0 before the child starts)."""
    return _transport.auth_revision() if _transport is not None else 0


def restart_child() -> None:
    """Kill the app-server child; the next operation spawns a fresh one."""
    if _transport is not None:
        _transport.force_restart()


def shutdown_transport() -> None:
    """Terminate the app-server child on application exit or restart."""
    if _transport is not None:
        _transport.shutdown()


# Helpers


def _get_transport() -> AppServerTransport:
    # CODEX_HOME is already in os.environ when --codex-home was given
    # (__main__ sets it before any package import), so the child inherits it.
    global _transport
    if _transport is None:
        _transport = AppServerTransport()
    return _transport


def _read_account(op: Any, *, refresh: bool) -> Any:
    """Perform the account read; returns parsed info, None (signed out), or _UNKNOWN.

    Method-not-found re-raises: a missing required method means an
    incompatible CLI and must never be swallowed into _UNKNOWN.
    """
    try:
        return _parse_account(op.request(METHOD_ACCOUNT_READ, {PARAM_REFRESH_TOKEN: refresh}))
    except RpcError as error:
        if error.code == METHOD_NOT_FOUND_CODE:
            raise
        return _UNKNOWN


def _classify_and_recover(op: Any, error: RpcError, account_info: Any,
                          allow_recovery: bool, latch: dict[str, bool]) -> ProviderFetchResult:
    """Classify a failed rate-limits read, running the recovery sub-sequence at most once."""
    profile = _profile_from_account(account_info)

    if error.code == METHOD_NOT_FOUND_CODE:
        return ProviderFetchResult(usage={'error': T['codex_cli_too_old']}, profile=profile, recovery_attempted=latch['attempted'])
    if account_info is None:
        return ProviderFetchResult(usage={'error': T['no_token'], 'no_auth': True}, profile={}, recovery_attempted=latch['attempted'])
    if account_info is _UNKNOWN:
        return ProviderFetchResult(usage=_classify_error(error), profile=None, recovery_attempted=latch['attempted'])
    if account_info['type'] != 'chatgpt':
        return ProviderFetchResult(usage={'error': T['not_chatgpt_auth']}, profile=profile, recovery_attempted=latch['attempted'])

    if allow_recovery and not latch['attempted']:
        # The latch is set before the refresh-enabled request is written, so
        # the operation's internal generation retry can never send a second one.
        latch['attempted'] = True
        try:
            refreshed_info = _read_account(op, refresh=True)
        except RpcError:
            return ProviderFetchResult(usage={'error': T['codex_cli_too_old']}, profile=profile, recovery_attempted=True)
        # Three-valued contract: dict replaces, {} authoritatively replaces
        # with signed-out, None (unknown) preserves what we already have.
        refreshed_profile = _profile_from_account(refreshed_info)
        if refreshed_profile is not None:
            profile = refreshed_profile
        try:
            usage = _normalize_rate_limits(op.request(METHOD_RATE_LIMITS_READ, {}))
            return ProviderFetchResult(usage=usage, profile=profile, recovery_attempted=True)
        except RpcError as retry_error:
            return ProviderFetchResult(usage=_classify_error(retry_error), profile=profile, recovery_attempted=True)

    return ProviderFetchResult(usage=_classify_error(error), profile=profile, recovery_attempted=latch['attempted'])


def _is_auth_error(error: RpcError) -> bool:
    """Exact-code predicate for auth-shaped errors; extend only with WIRE_NOTES.md evidence."""
    return error.code in AUTH_ERROR_CODES


def _classify_error(error: RpcError) -> dict[str, Any]:
    """Map a JSON-RPC error to the usage error dict; unknown never means expired session."""
    if error.code == METHOD_NOT_FOUND_CODE:
        return {'error': T['codex_cli_too_old']}
    if _is_auth_error(error):
        return {'error': T['auth_expired'], 'auth_error': True}
    return {'error': T['connection_error']}


def _parse_account(payload: Any) -> Any:
    """Extract account info; None means signed out, _UNKNOWN means unusable payload."""
    if not isinstance(payload, dict):
        return _UNKNOWN
    account = payload.get('account')
    if account is None:
        return None
    if not isinstance(account, dict):
        return _UNKNOWN
    return {'type': str(account.get('type') or ''),
            'email': str(account.get('email') or ''),
            'plan': str(account.get('planType') or '')}


def _profile_from_account(account_info: Any) -> dict[str, Any] | None:
    """Build the Claude-shaped profile: {} for signed-out, None for unknown."""
    if account_info is _UNKNOWN:
        return None
    if account_info is None:
        return {}

    display_email = account_info['email'].strip()
    normalized_email = display_email.lower()
    fingerprint = f"{account_info['type']}:{normalized_email}" if normalized_email else None
    return {
        'account': {'email': display_email, 'uuid': fingerprint},
        'organization': {'organization_type': account_info['plan']},
    }


def _normalize_rate_limits(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a rate-limits payload into Claude-shaped quota fields.

    Source selection is either/or: a non-empty ``rateLimitsByLimitId`` mapping
    is normalized alone (limit-ID sort order); otherwise the compatibility
    snapshot is used in ``primary``, ``secondary`` order.  Field names derive
    from ``windowDurationMins``, never from slot position, with deterministic
    collision suffixes (slot name for snapshot entries, ``_2``/``_3`` for
    keyed entries).  Credits and any other metadata are dropped.
    """
    candidates: list[tuple[str, bool, str]] = []   # (name, is_keyed, slot)
    entries: list[dict[str, Any]] = []

    keyed = payload.get('rateLimitsByLimitId')
    if isinstance(keyed, dict) and keyed:
        for limit_id in sorted(keyed):
            bucket = keyed[limit_id] or {}
            for slot in ('primary', 'secondary'):
                window = bucket.get(slot)
                entry = _window_entry(window)
                if entry is None:
                    continue
                candidates.append((_field_name(window.get('windowDurationMins'), limit_id, None), True, slot))
                entries.append(entry)
    else:
        snapshot = payload.get('rateLimits') or {}
        for slot in ('primary', 'secondary'):
            window = snapshot.get(slot)
            entry = _window_entry(window)
            if entry is None:
                continue
            candidates.append((_field_name(window.get('windowDurationMins'), None, slot), False, slot))
            entries.append(entry)

    result: dict[str, Any] = {}
    for (candidate, is_keyed, slot), entry in zip(candidates, entries):
        name = candidate
        if name in result and not is_keyed:
            name = f'{candidate}_{slot}'
        if name in result:
            counter = 2
            while f'{candidate}_{counter}' in result:
                counter += 1
            name = f'{candidate}_{counter}'
        result[name] = entry

    return result


def _window_entry(window: Any) -> dict[str, Any] | None:
    """Convert one wire window into a quota entry, or None when absent/empty."""
    if not isinstance(window, dict):
        return None
    percent = window.get('usedPercent')
    if percent is None:
        return None

    resets = window.get('resetsAt')
    resets_at = datetime.fromtimestamp(resets, tz=timezone.utc).isoformat() if isinstance(resets, (int, float)) else ''
    return {'utilization': float(percent), 'resets_at': resets_at}


def _field_name(minutes: Any, limit_id: str | None, slot: str | None) -> str:
    """Derive the internal field name for one window (see module normalization rules)."""
    duration_name = _duration_field_name(minutes)

    if limit_id is not None:
        slug = _model_slug(limit_id)
        if duration_name is None:
            return slug or 'limit'
        if limit_id == 'codex':
            return duration_name
        return f'{duration_name}_{slug or "limit"}'

    return duration_name if duration_name is not None else (slot or 'limit')


def _duration_field_name(minutes: Any) -> str | None:
    """Map a window duration in minutes to a parseable field name, or None."""
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes <= 0:
        return None
    if minutes in _KNOWN_DURATION_NAMES:
        return _KNOWN_DURATION_NAMES[minutes]
    if minutes % 1440 == 0:
        days = minutes // 1440
        return f'{_NUMBER_TO_WORD[days]}_day' if days in _NUMBER_TO_WORD else f'{days}_day'
    if minutes % 60 == 0:
        hours = minutes // 60
        return f'{_NUMBER_TO_WORD[hours]}_hour' if hours in _NUMBER_TO_WORD else f'{hours}_hour'
    return f'{minutes}_minute'


def _model_slug(display_name: str) -> str:
    """Convert a limit ID or display name into a field-name suffix (e.g. ``'gpt-5-pro'`` -> ``'gpt_5_pro'``)."""
    cleaned = ''.join(char if char.isalnum() else ' ' for char in display_name.lower())
    return '_'.join(cleaned.split())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_api -v`
Expected: all PASS.

- [ ] **Step 5: Full suite**

Run: `python -m unittest discover -s tests`
Expected: OK - the legacy client and its tests are untouched, so everything stays green.

- [ ] **Step 6: Suggested manual commit (user runs)**

```
git add usage_monitor_for_claude/api.py tests/test_api.py
git commit -m "feat: add Codex app-server adapter (normalization + profile) alongside the legacy client"
```

---

### Task 9: Adapter classification, recovery latch, and the three new locale keys

**Files:**
- Modify: `usage_monitor_for_claude/api.py` (already complete from Task 8 - this task proves the behavior)
- Modify: all 13 `locale/*.json`
- Test: `tests/test_api.py`, `tests/test_i18n.py`

**Interfaces:**
- Consumes: `fetch_provider_data(allow_recovery)`, `refresh_profile()`, fixtures, `AppServerTransport` + fake child.
- Produces: locale keys `not_chatgpt_auth`, `codex_cli_not_found`, `codex_cli_too_old` in all 13 locales; the `no_auth` flag contract used by Task 11.

- [ ] **Step 1: Add the three keys to all 13 locale files**

Append to each file (before the closing brace, keeping each file's JSON style). Exact values:

| Locale | `not_chatgpt_auth` | `codex_cli_not_found` | `codex_cli_too_old` |
|---|---|---|---|
| en | Signed in without a ChatGPT plan - plan usage requires ChatGPT sign-in. | Codex CLI not found - install Codex and sign in. | Codex CLI is too old for this monitor - please update Codex. |
| de | Ohne ChatGPT-Plan angemeldet - zur Anzeige der Plannutzung ist eine ChatGPT-Anmeldung erforderlich. | Codex CLI nicht gefunden - bitte Codex installieren und sich anmelden. | Codex CLI ist zu alt für diesen Monitor - bitte Codex aktualisieren. |
| es | Sesión iniciada sin un plan de ChatGPT: el uso del plan requiere iniciar sesión con ChatGPT. | No se encontró la CLI de Codex: instala Codex e inicia sesión. | La CLI de Codex es demasiado antigua para este monitor: actualiza Codex. |
| fr | Connecté sans forfait ChatGPT - l'utilisation du forfait nécessite une connexion ChatGPT. | CLI Codex introuvable - installez Codex et connectez-vous. | La CLI Codex est trop ancienne pour ce moniteur - mettez à jour Codex. |
| hi | ChatGPT प्लान के बिना साइन इन किया गया है - प्लान उपयोग के लिए ChatGPT साइन-इन आवश्यक है। | Codex CLI नहीं मिला - Codex इंस्टॉल करें और साइन इन करें। | Codex CLI इस मॉनिटर के लिए बहुत पुराना है - कृपया Codex अपडेट करें। |
| id | Masuk tanpa paket ChatGPT - penggunaan paket memerlukan masuk dengan ChatGPT. | Codex CLI tidak ditemukan - instal Codex dan masuk. | Codex CLI terlalu lama untuk monitor ini - perbarui Codex. |
| it | Accesso effettuato senza un piano ChatGPT - l'utilizzo del piano richiede l'accesso ChatGPT. | Codex CLI non trovata - installa Codex ed effettua l'accesso. | La Codex CLI è troppo vecchia per questo monitor - aggiorna Codex. |
| ja | ChatGPTプランなしでサインインしています - プラン使用状況にはChatGPTサインインが必要です。 | Codex CLIが見つかりません - Codexをインストールしてサインインしてください。 | Codex CLIが古すぎます - Codexを更新してください。 |
| ko | ChatGPT 플랜 없이 로그인되어 있습니다 - 플랜 사용량 확인에는 ChatGPT 로그인이 필요합니다. | Codex CLI를 찾을 수 없습니다 - Codex를 설치하고 로그인하세요. | Codex CLI가 너무 오래되었습니다 - Codex를 업데이트하세요. |
| pt-BR | Conectado sem um plano ChatGPT - o uso do plano exige login no ChatGPT. | Codex CLI não encontrada - instale o Codex e faça login. | A Codex CLI é muito antiga para este monitor - atualize o Codex. |
| uk | Вхід виконано без плану ChatGPT - для перегляду використання плану потрібно ввійти через ChatGPT. | Codex CLI не знайдено - встановіть Codex і ввійдіть. | Версія Codex CLI застаріла для цього монітора - оновіть Codex. |
| zh-CN | 已登录但没有 ChatGPT 套餐 - 查看套餐用量需要登录 ChatGPT。 | 未找到 Codex CLI - 请安装 Codex 并登录。 | Codex CLI 版本过旧 - 请更新 Codex。 |
| zh-TW | 已登入但沒有 ChatGPT 方案 - 查看方案用量需要登入 ChatGPT。 | 找不到 Codex CLI - 請安裝 Codex 並登入。 | Codex CLI 版本過舊 - 請更新 Codex。 |

Add to `tests/test_i18n.py`:

```python
class TestCodexKeys(unittest.TestCase):
    """The Codex error keys exist in every locale."""

    def test_new_keys_in_all_locales(self):
        for locale_file in sorted(LOCALE_DIR.glob('*.json')):
            data = json.loads(locale_file.read_text(encoding='utf-8'))
            for key in ('not_chatgpt_auth', 'codex_cli_not_found', 'codex_cli_too_old'):
                with self.subTest(locale=locale_file.name, key=key):
                    self.assertIn(key, data)
```

- [ ] **Step 2: Write the classification tests** (append to `tests/test_api.py`)

```python
import sys
from unittest.mock import patch

from usage_monitor_for_claude import api as api_module
from usage_monitor_for_claude.api import ProviderFetchResult, fetch_provider_data, refresh_profile
from usage_monitor_for_claude.app_server import AppServerTransport, CodexCliNotFound, RpcError, TransportError
from usage_monitor_for_claude.i18n import T

FAKE = str(Path(__file__).parent / 'fake_app_server.py')


class _FakeOp:
    """Scripted operation handle: maps (method, refresh) to results or exceptions."""

    def __init__(self, script):
        self.script = script
        self.calls = []

    def request(self, method, params):
        refresh = bool(params.get('refreshToken')) if method == 'account/read' else None
        self.calls.append((method, refresh))
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeTransport:
    def __init__(self, script):
        self.op = _FakeOp(script)

    def run_operation(self, body):
        return body(self.op)


def run_adapter(script, allow_recovery=False):
    fake = _FakeTransport(script)
    with patch.object(api_module, '_transport', fake):
        return fetch_provider_data(allow_recovery=allow_recovery), fake.op.calls


CHATGPT = load('12_chatgpt_account.json')
SIGNED_OUT = load('07_signed_out_account.json')
API_KEY = load('08_api_key_account.json')
BEDROCK = load('08b_bedrock_account.json')
LIMITS_OK = load('01_five_hour_plus_weekly.json')
AUTH_ERR = RpcError(-32001, 'unauthorized')
TRANSIENT_ERR = RpcError(-32603, 'internal error')
NOT_FOUND_ERR = RpcError(-32601, 'method not found')


class TestClassification(unittest.TestCase):
    """The Section 4 classification sequence.

    Production AUTH_ERROR_CODES ships empty until WIRE_NOTES.md evidence
    exists; these tests patch -32001 in as a stand-in auth code so the
    auth_expired path is exercisable.
    """

    def setUp(self):
        patcher = patch('usage_monitor_for_claude.api.AUTH_ERROR_CODES', frozenset({-32001}))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_success_carries_usage_and_profile(self):
        result, _ = run_adapter([CHATGPT, LIMITS_OK])
        self.assertIn('five_hour', result.usage)
        self.assertEqual(result.profile['organization']['organization_type'], 'plus')
        self.assertFalse(result.recovery_attempted)

    def test_signed_out(self):
        result, _ = run_adapter([SIGNED_OUT, RpcError(-32001, 'unauthorized')])
        self.assertEqual(result.usage['error'], T['no_token'])
        self.assertTrue(result.usage['no_auth'])
        self.assertEqual(result.profile, {})

    def test_api_key_auth_no_auth_error_flag(self):
        result, _ = run_adapter([API_KEY, RpcError(-32001, 'unauthorized')])
        self.assertEqual(result.usage['error'], T['not_chatgpt_auth'])
        self.assertNotIn('auth_error', result.usage)

    def test_bedrock_auth_same_class(self):
        result, _ = run_adapter([BEDROCK, RpcError(-32001, 'unauthorized')])
        self.assertEqual(result.usage['error'], T['not_chatgpt_auth'])

    def test_method_not_found_is_too_old_never_auth(self):
        result, _ = run_adapter([CHATGPT, RpcError(-32601, 'method not found')])
        self.assertEqual(result.usage['error'], T['codex_cli_too_old'])
        self.assertNotIn('auth_error', result.usage)

    def test_method_not_found_on_account_read_is_too_old(self):
        result, calls = run_adapter([RpcError(-32601, 'method not found')])
        self.assertEqual(result.usage['error'], T['codex_cli_too_old'])
        self.assertEqual(len(calls), 1)   # never proceeds to the rate-limits read

    def test_no_recovery_without_permission(self):
        result, calls = run_adapter([CHATGPT, AUTH_ERR], allow_recovery=False)
        self.assertEqual(result.usage['error'], T['auth_expired'])   # -32001 is auth-shaped; classified directly
        self.assertTrue(result.usage.get('auth_error'))
        self.assertFalse(result.recovery_attempted)
        self.assertEqual(calls, [('account/read', False), ('account/rateLimits/read', None)])

    def test_recovery_sequence_success(self):
        result, calls = run_adapter([CHATGPT, AUTH_ERR, CHATGPT, LIMITS_OK], allow_recovery=True)
        self.assertIn('five_hour', result.usage)
        self.assertTrue(result.recovery_attempted)
        self.assertEqual(calls, [('account/read', False), ('account/rateLimits/read', None),
                                 ('account/read', True), ('account/rateLimits/read', None)])

    def test_recovery_retry_still_auth_shaped(self):
        result, _ = run_adapter([CHATGPT, AUTH_ERR, CHATGPT, AUTH_ERR], allow_recovery=True)
        self.assertEqual(result.usage['error'], T['auth_expired'])
        self.assertTrue(result.usage['auth_error'])
        self.assertTrue(result.recovery_attempted)

    def test_unknown_error_defaults_to_transient_never_auth(self):
        # With recovery allowed, a transient error still runs the sequence and
        # the retry's unknown error classifies as transient, never auth.
        result, calls = run_adapter([CHATGPT, TRANSIENT_ERR, CHATGPT, TRANSIENT_ERR], allow_recovery=True)
        self.assertEqual(result.usage['error'], T['connection_error'])
        self.assertNotIn('auth_error', result.usage)
        self.assertTrue(result.recovery_attempted)
        self.assertEqual(len(calls), 4)
        # Without recovery, an unknown code classifies directly as transient.
        result2, _ = run_adapter([CHATGPT, RpcError(999999, 'mystery')], allow_recovery=False)
        self.assertEqual(result2.usage['error'], T['connection_error'])
        self.assertNotIn('auth_error', result2.usage)

    def test_account_read_error_classifies_from_error_only(self):
        result, calls = run_adapter([RpcError(-32603, 'oops'), TRANSIENT_ERR], allow_recovery=True)
        self.assertEqual(result.usage['error'], T['connection_error'])
        self.assertIsNone(result.profile)
        self.assertEqual(len(calls), 2)   # no recovery without a known ChatGPT account

    def test_transport_failure_maps_to_connection_error(self):
        class _Boom:
            def run_operation(self, body):
                raise TransportError('down')
        with patch.object(api_module, '_transport', _Boom()):
            result = fetch_provider_data()
        self.assertEqual(result.usage['error'], T['connection_error'])
        self.assertIsNone(result.profile)

    def test_cli_not_found_maps_to_message(self):
        class _Missing:
            def run_operation(self, body):
                raise CodexCliNotFound('missing')
        with patch.object(api_module, '_transport', _Missing()):
            result = fetch_provider_data()
        self.assertEqual(result.usage['error'], T['codex_cli_not_found'])


class TestRecoveryLatchAcrossGenerations(unittest.TestCase):
    """The dies-after-refresh scenario: exactly one refresh-enabled read across both attempts."""

    def test_single_refresh_read_across_operation_retry(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            log = str(Path(tmp) / 'log.jsonl')
            transport = AppServerTransport(command=[sys.executable, FAKE, '--scenario', 'die-after-refresh', '--log', log],
                                           init_timeout=10, rpc_timeout=3)
            self.addCleanup(transport.shutdown)
            with patch.object(api_module, '_transport', transport):
                result = fetch_provider_data(allow_recovery=True)

            self.assertTrue(result.recovery_attempted)
            entries = [json.loads(l) for l in Path(log).read_text(encoding='utf-8').splitlines()]
            refresh_reads = [e for e in entries if e.get('method') == 'account/read' and (e.get('params') or {}).get('refreshToken')]
            self.assertEqual(len(refresh_reads), 1)


class TestRefreshProfile(unittest.TestCase):
    def test_refresh_profile_returns_normalized_profile(self):
        fake = _FakeTransport([CHATGPT])
        with patch.object(api_module, '_transport', fake):
            profile = refresh_profile()
        self.assertEqual(profile['account']['uuid'], 'chatgpt:user@example.com')

    def test_refresh_profile_none_on_failure(self):
        class _Boom:
            def run_operation(self, body):
                raise TransportError('down')
        with patch.object(api_module, '_transport', _Boom()):
            self.assertIsNone(refresh_profile())
```

- [ ] **Step 3: Run tests**

Run: `python -m unittest tests.test_api tests.test_i18n -v`
Expected: locale tests PASS after Step 1; classification tests PASS against Task 8's implementation (any FAIL is an implementation gap in `_classify_and_recover` - fix `api.py`, not the tests).

- [ ] **Step 4: Full suite**

Run: `python -m unittest discover -s tests`
Expected: OK (the legacy client still serves `cache.py`/`app.py`; nothing red).

- [ ] **Step 5: Suggested manual commit (user runs)**

```
git add usage_monitor_for_claude/api.py locale tests/test_api.py tests/test_i18n.py
git commit -m "feat: auth classification with once-per-episode recovery and new locale keys"
```

---

### Task 10: Cache integration - ProviderFetchResult, profile semantics, episode guard

**Files:**
- Modify: `usage_monitor_for_claude/cache.py`
- Test: `tests/test_cache.py`

**Interfaces:**
- Consumes: `fetch_provider_data(allow_recovery)`, `refresh_profile()` from `api.py`.
- Produces: `UsageCache.refresh_profile() -> None` (fresh account read, cooldown-independent); `UpdateResult(data)` without `token_refresh`; unchanged `update()`, `ensure_profile()`, `snapshot`, and all cooldown/backoff behavior. Consumed by Task 11.

- [ ] **Step 1: Adapt the existing suite mechanically**

In `tests/test_cache.py`: delete test classes/methods covering removed features (`_try_token_refresh`, `RefreshResult` propagation, `_last_failed_token` blocking, `_profile_token` re-keying). Replace every `patch('usage_monitor_for_claude.cache.fetch_usage', return_value=DATA)` with `patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(DATA))` using this helper at module top:

```python
from usage_monitor_for_claude.api import ProviderFetchResult


def pfr(usage, profile=None, recovery=False):
    return ProviderFetchResult(usage=usage, profile=profile, recovery_attempted=recovery)
```

Replace patches of `cache.fetch_profile` with `patch('usage_monitor_for_claude.cache.adapter_refresh_profile', return_value=PROFILE)`.

- [ ] **Step 2: Write the failing new tests** (append to `tests/test_cache.py`)

```python
class TestProfileSemantics(unittest.TestCase):
    """dict replaces, {} replaces with signed-out, None preserves."""

    PROFILE_A = {'account': {'email': 'a@x.com', 'uuid': 'chatgpt:a@x.com'}, 'organization': {'organization_type': 'plus'}}
    PROFILE_B = {'account': {'email': 'b@x.com', 'uuid': 'chatgpt:b@x.com'}, 'organization': {'organization_type': 'plus'}}
    USAGE_OK = {'five_hour': {'utilization': 10, 'resets_at': ''}}

    def _update(self, cache, usage, profile, recovery=False):
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(usage, profile, recovery)):
            with patch('usage_monitor_for_claude.cache.POLL_FAST', 0):
                return cache.update()

    def test_dict_profile_stored_with_usage(self):
        cache = UsageCache()
        self._update(cache, self.USAGE_OK, self.PROFILE_A)
        self.assertEqual(cache.profile, self.PROFILE_A)

    def test_none_preserves_cached_profile(self):
        cache = UsageCache()
        self._update(cache, self.USAGE_OK, self.PROFILE_A)
        self._update(cache, {'error': 'x'}, None)
        self.assertEqual(cache.profile, self.PROFILE_A)

    def test_empty_dict_replaces_with_signed_out(self):
        cache = UsageCache()
        self._update(cache, self.USAGE_OK, self.PROFILE_A)
        self._update(cache, {'error': 'x', 'no_auth': True}, {})
        self.assertEqual(cache.profile, {})

    def test_profile_stored_even_on_error_cycle(self):
        cache = UsageCache()
        self._update(cache, {'error': 'x'}, self.PROFILE_A)
        self.assertEqual(cache.profile, self.PROFILE_A)


class TestEpisodeGuard(unittest.TestCase):
    """allow_recovery=True exactly once per continuous failing episode."""

    USAGE_OK = {'five_hour': {'utilization': 10, 'resets_at': ''}}
    PROFILE_A = TestProfileSemantics.PROFILE_A
    PROFILE_B = TestProfileSemantics.PROFILE_B

    def _cycle(self, cache, usage, profile, recovery_attempted):
        calls = {}

        def fake_fetch(allow_recovery=False):
            calls['allow_recovery'] = allow_recovery
            return pfr(usage, profile, recovery_attempted)

        with patch('usage_monitor_for_claude.cache.fetch_provider_data', side_effect=fake_fetch):
            with patch('usage_monitor_for_claude.cache.POLL_FAST', 0):
                cache.update()
        return calls['allow_recovery']

    def test_first_failing_cycle_allows_recovery_second_does_not(self):
        cache = UsageCache()
        self.assertTrue(self._cycle(cache, {'error': 'x'}, None, recovery_attempted=True))
        self.assertFalse(self._cycle(cache, {'error': 'x'}, None, recovery_attempted=False))
        self.assertFalse(self._cycle(cache, {'error': 'x'}, None, recovery_attempted=False))

    def test_transient_only_episode_also_consumes_once(self):
        cache = UsageCache()
        self.assertTrue(self._cycle(cache, {'error': 'transient'}, None, recovery_attempted=True))
        self.assertFalse(self._cycle(cache, {'error': 'transient'}, None, recovery_attempted=False))

    def test_success_resets_guard(self):
        cache = UsageCache()
        self._cycle(cache, {'error': 'x'}, None, recovery_attempted=True)
        self._cycle(cache, self.USAGE_OK, self.PROFILE_A, recovery_attempted=False)
        self.assertTrue(self._cycle(cache, {'error': 'x'}, None, recovery_attempted=True))

    def test_fingerprint_change_resets_guard(self):
        cache = UsageCache()
        self._cycle(cache, {'error': 'x'}, self.PROFILE_A, recovery_attempted=True)
        self._cycle(cache, {'error': 'x'}, self.PROFILE_B, recovery_attempted=False)   # new account stored
        self.assertTrue(self._cycle(cache, {'error': 'x'}, self.PROFILE_B, recovery_attempted=True))


import threading   # add to the test module's imports if not already present


class TestSnapshotAtomicity(unittest.TestCase):
    """A concurrent snapshot never observes a half-updated error/profile/version state."""

    def test_error_profile_and_version_change_together(self):
        cache = UsageCache()
        stop = threading.Event()
        violations = []

        def watcher():
            while not stop.is_set():
                snap = cache.snapshot
                if snap.last_error and snap.last_error.startswith('err-'):
                    index = snap.last_error.split('-')[1]
                    email = (snap.profile or {}).get('account', {}).get('email', '')
                    if email != f'u{index}@x':
                        violations.append((snap.last_error, email))

        thread = threading.Thread(target=watcher, daemon=True)
        thread.start()
        try:
            for index in range(200):
                profile = {'account': {'email': f'u{index}@x', 'uuid': f'chatgpt:u{index}@x'},
                           'organization': {'organization_type': ''}}
                with patch('usage_monitor_for_claude.cache.fetch_provider_data',
                           return_value=pfr({'error': f'err-{index}'}, profile)):
                    with patch('usage_monitor_for_claude.cache.POLL_FAST', 0):
                        cache.update()
        finally:
            stop.set()
            thread.join(timeout=5)
        self.assertEqual(violations, [])


class TestRefreshProfileMethod(unittest.TestCase):
    def test_refresh_profile_works_inside_cooldown(self):
        cache = UsageCache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data',
                   return_value=pfr(TestProfileSemantics.USAGE_OK, TestProfileSemantics.PROFILE_A)):
            with patch('usage_monitor_for_claude.cache.POLL_FAST', 0):
                cache.update()
        # Inside the (real) cooldown now: update() would skip, refresh_profile() must not.
        with patch('usage_monitor_for_claude.cache.adapter_refresh_profile', return_value=TestProfileSemantics.PROFILE_B):
            cache.refresh_profile()
        self.assertEqual(cache.profile, TestProfileSemantics.PROFILE_B)

    def test_refresh_profile_none_preserves(self):
        cache = UsageCache()
        with patch('usage_monitor_for_claude.cache.adapter_refresh_profile', return_value=TestProfileSemantics.PROFILE_A):
            cache.refresh_profile()
        with patch('usage_monitor_for_claude.cache.adapter_refresh_profile', return_value=None):
            cache.refresh_profile()
        self.assertEqual(cache.profile, TestProfileSemantics.PROFILE_A)
```

- [ ] **Step 3: Run to verify failures**

Run: `python -m unittest tests.test_cache -v`
Expected: FAIL - `ImportError` on `adapter_refresh_profile` / `fetch_provider_data` in `cache`, `AttributeError: refresh_profile`.

- [ ] **Step 4: Implement in `cache.py`**

Imports become:

```python
from .api import fetch_provider_data, refresh_profile as adapter_refresh_profile
from .settings import MAX_BACKOFF, POLL_FAST, POLL_INTERVAL
```

Delete the `token_refresh` field and its docstring from `UpdateResult` (keep `data`). In `__init__`, delete `self._profile_token` and `self._last_failed_token`; add `self._recovery_attempted = False`. Delete `_try_token_refresh()` entirely. In `_update_locked()`, delete the `_last_failed_token` block.

Replace `ensure_profile()`'s body (same signature, docstring updated):

```python
        if self._profile is not None:
            return

        with self._profile_lock:
            if self._profile is not None:
                return
            if not bypass_rate_limit and time.time() < self._rate_limit_until:
                log.debug('ensure_profile skipped (rate-limit backoff)')
                return
            log.info('refresh_profile (cold path) started')
            self._store_profile(adapter_refresh_profile())
```

Add the new public method and private helpers:

```python
    def refresh_profile(self) -> None:
        """Fetch a fresh account profile, independent of the usage cooldown.

        Backs the auth-revision confirmation and the account-switch probe:
        it never goes through ``update()``, so it is valid inside the
        ``POLL_FAST`` window.
        """
        with self._profile_lock:
            log.info('refresh_profile started')
            self._store_profile(adapter_refresh_profile())

    def _store_profile(self, profile: dict[str, Any] | None) -> None:
        """Store a profile result: dict replaces, {} replaces, None preserves."""
        if profile is None:
            return
        with self._state_lock:
            self._store_profile_locked(profile)
            self._version += 1

    def _store_profile_locked(self, profile: dict[str, Any] | None) -> None:
        """Store under _state_lock; a fingerprint change opens a new recovery episode."""
        if profile is None:
            return
        previous_uuid = (self._profile or {}).get('account', {}).get('uuid') if isinstance(self._profile, dict) else None
        new_uuid = profile.get('account', {}).get('uuid') if profile else None
        if new_uuid != previous_uuid:
            self._recovery_attempted = False
        self._profile = profile
```

Replace `_fetch_and_process()`:

```python
    def _fetch_and_process(self) -> UpdateResult:
        """Fetch usage and profile in one provider operation and process the result."""
        with self._state_lock:
            allow_recovery = not self._recovery_attempted
        log.info('fetch_provider_data started (allow_recovery=%s)', allow_recovery)
        result = fetch_provider_data(allow_recovery=allow_recovery)

        data = result.usage
        if 'error' in data:
            self._record_error_state(data, result.profile, result.recovery_attempted)
            log.warning('fetch -> error: %s', data['error'])
            return UpdateResult(data=data)

        pct_5h = (data.get('five_hour') or {}).get('utilization')
        pct_7d = (data.get('seven_day') or {}).get('utilization')
        log.info('fetch -> OK (5h: %s%%, 7d: %s%%)', pct_5h if pct_5h is not None else '?', pct_7d if pct_7d is not None else '?')
        self._record_success(data, result.profile)
        return UpdateResult(data=data)
```

Delete the upstream `_record_error()` (its only remaining caller is replaced) and add its atomic successor - every error-cycle mutation in **one** `_state_lock` section, so a concurrent `snapshot` can never observe the new error with a stale profile, version, or guard:

```python
    def _record_error_state(self, data: dict[str, Any], profile: dict[str, Any] | None, recovery_attempted: bool) -> None:
        """Apply all error-cycle state atomically under a single _state_lock section."""
        with self._state_lock:
            self._consecutive_errors += 1
            error = data['error']
            server_msg = data.get('server_message')
            if server_msg:
                error += f'\n{server_msg}'
            self._last_error = error

            if data.get('rate_limited'):
                retry_after = data.get('retry_after')
                if retry_after is not None and retry_after > 0:
                    delay = min(max(retry_after, POLL_INTERVAL), MAX_BACKOFF)
                else:
                    delay = min(POLL_INTERVAL * (2 ** max(self._consecutive_errors - 1, 0)), MAX_BACKOFF)
                self._rate_limit_until = time.time() + delay

            # Profile first: a fingerprint change resets the episode guard, and
            # a recovery consumed in this same cycle must survive that reset.
            self._store_profile_locked(profile)
            if recovery_attempted:
                self._recovery_attempted = True
            self._refreshing = False
            self._version += 1
```

Extend `_record_success(self, data, profile)` - inside the existing `_state_lock` block add, after `self._last_failed_token = None` is deleted:

```python
            self._recovery_attempted = False
            self._store_profile_locked(profile)
```

- [ ] **Step 5: Run the cache suite, then the full suite**

Run: `python -m unittest tests.test_cache -v` - Expected: all PASS.
Run: `python -m unittest discover -s tests` - Expected: OK (`app.py` still runs on the legacy client until Task 11).

- [ ] **Step 6: Suggested manual commit (user runs)**

```
git add usage_monitor_for_claude/cache.py tests/test_cache.py
git commit -m "feat: cache stores usage and profile atomically with a recovery episode guard"
```

---

### Task 11: Poll loop - auth revision watcher, recycle, startup warning, tray substitution

**Files:**
- Modify: `usage_monitor_for_claude/app.py`, `usage_monitor_for_claude/formatting.py` (`format_tooltip`)
- Test: `tests/test_app.py`, `tests/test_formatting.py`

**Interfaces:**
- Consumes: `auth_revision()`, `restart_child()` from `api.py`; `cache.refresh_profile()`; `resolve_display_fields()`.
- Produces: poll-loop behavior relied on by the smoke tests; no new public API.

- [ ] **Step 1: Mechanical adaptations in `tests/test_app.py`**

Delete tests for removed features: the `NOTIFY_CLAUDE_UPDATE` notification, `token_refresh` handling, and every token-watcher test that patches `read_access_token` in the poll loop. Where `_make_app()` or tests patch `usage_monitor_for_claude.app.read_access_token` / `api_headers`, patch `usage_monitor_for_claude.app.auth_revision` (default `return_value=0`) instead. Keep all polling/reset/idle/notification invariant tests - they must pass unchanged once the seams compile.

- [ ] **Step 2: Write the failing new tests** (append to `tests/test_app.py`, following the file's `_make_app()` conventions)

```python
from unittest.mock import PropertyMock   # extend the module's existing mock import


class TestAuthRevisionWatcher(unittest.TestCase):
    def test_revision_change_with_switch_forces_update(self):
        app = _make_app()
        app._prev_account_uuid = 'chatgpt:old@x.com'
        with patch.object(app.cache, 'refresh_profile') as refresh, \
             patch.object(type(app.cache), 'profile', new_callable=PropertyMock,
                          return_value={'account': {'uuid': 'chatgpt:new@x.com', 'email': 'new@x.com'}}):
            self.assertTrue(app._account_switched())
            refresh.assert_called_once()

    def test_no_switch_when_fingerprint_is_none(self):
        app = _make_app()
        app._prev_account_uuid = 'chatgpt:old@x.com'
        with patch.object(app.cache, 'refresh_profile'), \
             patch.object(type(app.cache), 'profile', new_callable=PropertyMock,
                          return_value={'account': {'uuid': None, 'email': ''}}):
            self.assertFalse(app._account_switched())


class TestStartupWarning(unittest.TestCase):
    def test_no_auth_notifies_once(self):
        app = _make_app()
        with patch.object(app.icon, 'notify') as notify, \
             patch.object(app.cache, 'update', return_value=UpdateResult(data={'error': 'x', 'no_auth': True})), \
             patch.object(app.cache, 'ensure_profile'):
            app.update()
            app.update()
        self.assertEqual(notify.call_count, 1)


class TestErrorStateRecycle(unittest.TestCase):
    """Recycling counts only scheduled (error-cadence) polls, never popup refreshes."""

    def test_child_recycled_every_tenth_error_cadence_poll(self):
        app = _make_app()
        app._last_response = {'error': 'x', 'auth_error': True}
        with patch('usage_monitor_for_claude.app.restart_child') as restart:
            for _ in range(20):
                app._maybe_recycle_child()
        self.assertEqual(restart.call_count, 2)

    def test_streak_resets_on_success(self):
        app = _make_app()
        with patch('usage_monitor_for_claude.app.restart_child') as restart:
            app._last_response = {'error': 'x', 'no_auth': True}
            for _ in range(9):
                app._maybe_recycle_child()
            app._last_response = {'five_hour': {'utilization': 1, 'resets_at': ''}}
            app._maybe_recycle_child()
            app._last_response = {'error': 'x', 'no_auth': True}
            for _ in range(9):
                app._maybe_recycle_child()
        self.assertEqual(restart.call_count, 0)

    def test_popup_refresh_never_advances_the_counter(self):
        app = _make_app()
        with patch('usage_monitor_for_claude.app.restart_child') as restart, \
             patch.object(app.cache, 'update', return_value=UpdateResult(data={'error': 'x', 'auth_error': True})), \
             patch.object(app.cache, 'ensure_profile'):
            for _ in range(30):
                app.update()   # popup-style refresh path: no recycle counting
        self.assertEqual(restart.call_count, 0)


class TestTraySubstitution(unittest.TestCase):
    def test_weekly_only_renders_weekly_on_top(self):
        app = _make_app()
        app._last_response = {'seven_day': {'utilization': 29, 'resets_at': ''}}
        with patch('usage_monitor_for_claude.app.create_icon_image') as create:
            app._render_tray()
        _, kwargs = create.call_args
        args, _ = create.call_args
        self.assertEqual(args[0], 29)   # pct_top from substituted seven_day
        self.assertEqual(args[1], 0)    # empty second bar
```

Adjust the mock plumbing to the file's existing fixtures (`_make_app` builds a real `UsageMonitorForClaude` with patched dependencies; reuse its idioms, e.g. how existing tests patch `create_icon_image` and `UpdateResult` imports).

Add to `tests/test_formatting.py`:

```python
    def test_tooltip_substitutes_missing_default_fields(self):
        data = {'seven_day': {'utilization': 29, 'resets_at': ''}}
        text = format_tooltip(data)
        self.assertIn('7d: 29%', text)
        self.assertNotIn('5h', text)
```

- [ ] **Step 3: Run to verify failures**

Run: `python -m unittest tests.test_app -v`
Expected: FAIL - `ImportError` (`app` still imports `api_headers`/`read_access_token`), then assertion failures on the new behaviors.

- [ ] **Step 4: Implement in `app.py`**

Imports: replace `from .api import api_headers, read_access_token` with `from .api import auth_revision, restart_child`; drop `NOTIFY_CLAUDE_UPDATE` from the settings import; add `resolve_display_fields` to the formatting import. In `__init__` add:

```python
        self._no_auth_notified = False
        self._auth_error_streak = 0
```

In `update()`: delete the `NOTIFY_CLAUDE_UPDATE ... token_refresh` block. After `self._render_tray()` add only the notification (recycling is a poll-path concern, below):

```python
        if result.data.get('no_auth') and not self._no_auth_notified:
            self._no_auth_notified = True
            self.icon.notify(f"{T['warn_no_token']}\n{T['warn_login']}", T['popup_title'])
```

Add the recycle helper (called only from the scheduled poll path - popup-driven refreshes must never advance the counter, since the spec promises "every 10th *error-cadence poll*"):

```python
    def _maybe_recycle_child(self) -> None:
        """Restart the app-server child every 10th consecutive error-cadence poll.

        Runs only from the poll loop.  While signed out or in an auth-error
        state, a periodic child restart guarantees an external ``codex login``
        is eventually observed even if the child caches auth state.
        """
        if self._last_response.get('auth_error') or self._last_response.get('no_auth'):
            self._auth_error_streak += 1
            if self._auth_error_streak % 10 == 0:
                restart_child()
        else:
            self._auth_error_streak = 0
```

In `poll_loop()`, add directly after the `self.update(force=force_next)` line:

```python
            self._maybe_recycle_child()
```

In `_render_tray()`, replace the two `ICON_FIELDS[...]` lines and entry lookups with:

```python
            slots = resolve_display_fields(ICON_FIELDS, data, 2)
            top_field, top_mode = (slots[0].split(':', 1) + ['utilization'])[:2] if slots[0] else ('', 'utilization')
            bottom_field, bottom_mode = (slots[1].split(':', 1) + ['utilization'])[:2] if slots[1] else ('', 'utilization')
```

(the subsequent `data.get(top_field) or {}` lines work unchanged with `''`).

In `_account_switched()`, replace `self.cache.ensure_profile(bypass_rate_limit=True)` with `self.cache.refresh_profile()`.

In `poll_loop()`, replace the token watcher block (`token_seen = read_access_token()` and the `current_token` paragraph) with:

```python
            revision_seen = auth_revision()
            while self.running and time.time() < target:
                time.sleep(1)

                # React to an account/updated notification between polls: confirm
                # via a cooldown-independent profile refresh; only a confirmed
                # fingerprint change forces an immediate fetch.  An auth-error
                # state retries at once so a fresh login recovers promptly.
                current_revision = auth_revision()
                if current_revision != revision_seen:
                    revision_seen = current_revision
                    if self._account_switched():
                        force_next = True
                        break
                    if self._last_response.get('auth_error') or self._last_response.get('no_auth'):
                        break
```

In `_on_icon_ready()`, delete the `if not api_headers(): icon.notify(...)` pair.

In `formatting.py`, change `format_tooltip()`'s loop header from `for key in TOOLTIP_FIELDS:` to:

```python
    for key in resolve_display_fields(TOOLTIP_FIELDS, data, len(TOOLTIP_FIELDS)):
        if key is None:
            continue
        key = key.split(':', 1)[0]
```

- [ ] **Step 5: Run the suites**

Run: `python -m unittest tests.test_app tests.test_formatting -v` - Expected: all PASS.
Run: `python -m unittest discover -s tests` - Expected: OK.

- [ ] **Step 6: Delete the legacy Claude client**

Nothing references it anymore (cache switched in Task 10, app in this task). From `api.py` delete: the `requests` import, `API_URL_USAGE`, `API_URL_PROFILE`, `CLAUDE_CONFIG_DIR`, `CLAUDE_CREDENTIALS`, `_FALLBACK_USER_AGENT`, `read_access_token()`, `api_headers()`, `fetch_usage()`, `fetch_profile()`, `_merge_scoped_limits()`, `_user_agent()`, `_extract_server_message()`, `_parse_retry_after()`, and their `__all__` entries; install the Codex module docstring from Task 8's code block. From `tests/test_api.py` delete every Claude-era test class (credentials file, `CLAUDE_CONFIG_DIR`, `_merge_scoped_limits`, retry-after parsing) - they test deleted code, which is the one sanctioned reason to remove tests.

Verify: `git grep --untracked -nE "read_access_token|api_headers|_merge_scoped_limits|API_URL_" -- usage_monitor_for_claude tests` - Expected: no output.

- [ ] **Step 7: Full suite**

Run: `python -m unittest discover -s tests` - Expected: OK.

- [ ] **Step 8: Suggested manual commit (user runs)**

```
git add usage_monitor_for_claude/app.py usage_monitor_for_claude/api.py usage_monitor_for_claude/formatting.py tests/test_app.py tests/test_api.py tests/test_formatting.py
git commit -m "feat: app-server-authoritative poll loop; remove the legacy Anthropic client"
```

---

### Task 12: Windows identity - flag, env, mutex, autostart, settings, verbose, class rename

**Files:**
- Modify: `instance_id.py`, `settings.py`, `autostart.py`, `single_instance.py`, `verbose.py`, `app.py`, `popup.py`, `__main__.py`
- Create: `tests/test_identity.py`
- Test: `tests/test_instance_id.py`, `tests/test_settings.py`, `tests/test_autostart.py`, `tests/test_single_instance.py`, `tests/test_verbose.py`

**Interfaces:**
- Produces: `parse_codex_home(argv)` (replaces `parse_config_dir`); `effective_config_dir()` reading `CODEX_HOME` with default `~/.codex`; identity constants listed below; app class `UsageMonitorForCodex`.

- [ ] **Step 1: Write the failing identity test** (new `tests/test_identity.py`)

```python
"""
Identity Collision Tests
=========================

Guards against an upstream merge silently reintroducing any Claude-monitor
OS identity into the Codex product.
"""
from __future__ import annotations

import unittest

from usage_monitor_for_claude.autostart import AUTOSTART_REG_BASE_NAME
from usage_monitor_for_claude.settings import SETTINGS_FILENAME
from usage_monitor_for_claude.single_instance import _MUTEX_BASE_NAME, _PID_MAPPING_BASE_NAME

CLAUDE_LITERALS = {
    'UsageMonitorForClaude_SingleInstance', 'UsageMonitorForClaude_HolderPID',
    'UsageMonitorForClaude', 'usage-monitor-settings.json', 'usage_monitor',
}


class TestIdentityConstants(unittest.TestCase):
    def test_codex_values(self):
        self.assertEqual(_MUTEX_BASE_NAME, 'UsageMonitorForCodex_SingleInstance')
        self.assertEqual(_PID_MAPPING_BASE_NAME, 'UsageMonitorForCodex_HolderPID')
        self.assertEqual(AUTOSTART_REG_BASE_NAME, 'UsageMonitorForCodex')
        self.assertEqual(SETTINGS_FILENAME, 'usage-monitor-for-codex-settings.json')

    def test_never_a_claude_literal(self):
        for value in (_MUTEX_BASE_NAME, _PID_MAPPING_BASE_NAME, AUTOSTART_REG_BASE_NAME, SETTINGS_FILENAME):
            self.assertNotIn(value, CLAUDE_LITERALS)

    def test_pystray_icon_name(self):
        import inspect
        from usage_monitor_for_claude import app
        source = inspect.getsource(app)
        self.assertIn("'usage_monitor_for_codex'", source)
        self.assertNotIn("pystray.Icon(\n            'usage_monitor'", source)
```

- [ ] **Step 2: Run to verify failure** - `python -m unittest tests.test_identity -v` - Expected: FAIL on every Claude value.

- [ ] **Step 3: Apply the identity edits**

`instance_id.py`: rename `parse_config_dir` -> `parse_codex_home`; inside it, replace both `'--config-dir='`/`'--config-dir'` literals with `'--codex-home='`/`'--codex-home'`; `effective_config_dir()` reads `os.environ.get('CODEX_HOME')` with default `Path.home() / '.codex'`; `is_default_config_dir()` compares against `~/.codex`; update `__all__` and both docstrings ("Codex home" wording).

`settings.py`: `SETTINGS_FILENAME = 'usage-monitor-for-codex-settings.json'`; `home_claude = Path.home() / '.claude'` becomes `home_codex = Path.home() / '.codex'` (rename the variable and its two uses); MessageBox titles 'Usage Monitor for Codex - Settings Error'; remove `'notify_claude_update'` from `_BOOL_KEYS`, delete the `NOTIFY_CLAUDE_UPDATE` assignment, and remove it from `__all__`; update the module docstring's search-order paths.

`autostart.py`: `AUTOSTART_REG_BASE_NAME = 'UsageMonitorForCodex'`; `_autostart_command()` emits `--codex-home="..."`; docstrings say Codex.

`single_instance.py`: `_MUTEX_BASE_NAME = 'UsageMonitorForCodex_SingleInstance'`, `_PID_MAPPING_BASE_NAME = 'UsageMonitorForCodex_HolderPID'`; docstring wording.

`verbose.py`: delete `_credentials_status()` and the Credentials section entirely; in the Locale section replace the `CLAUDE_CONFIG_DIR` row with `_row('CODEX_HOME', _redact_home(os.environ.get('CODEX_HOME', '')) or '(not set)')`; header string 'Usage Monitor for Codex'; in the Dependencies section drop `'requests'` from the package tuple.

`app.py`: class `UsageMonitorForClaude` -> `UsageMonitorForCodex`; pystray icon name `'usage_monitor'` -> `'usage_monitor_for_codex'`; `crash_log` title 'Usage Monitor for Codex - Error'; `__all__` updated.

`popup.py`: `TYPE_CHECKING` import and the `app:` parameter annotation renamed to `UsageMonitorForCodex`.

`__main__.py`: import and use `parse_codex_home`; set `os.environ['CODEX_HOME']` (not `CLAUDE_CONFIG_DIR`); error dialog title 'Usage Monitor for Codex - Error'; restart passthrough emits `--codex-home={os.environ["CODEX_HOME"]}`; import the renamed app class; after `webview.start(func=_run_app)` returns, add:

```python
    from usage_monitor_for_claude.api import shutdown_transport
    shutdown_transport()
```

(before the restart-spawn block, so the old child dies before the new instance starts its own).

- [ ] **Step 4: Adapt the identity-adjacent suites**

`tests/test_instance_id.py`: rename every `parse_config_dir` call to `parse_codex_home`, every `--config-dir` literal to `--codex-home`, every `CLAUDE_CONFIG_DIR` env to `CODEX_HOME`, `~/.claude` expectations to `~/.codex`. `tests/test_settings.py`: new filename constant, `~/.codex` search path, delete `notify_claude_update` validation tests. `tests/test_autostart.py`: new value name and `--codex-home` command. `tests/test_single_instance.py`: new mutex/mapping names. `tests/test_verbose.py`: delete credentials-section assertions; assert the `CODEX_HOME` row exists and that the output never mentions `auth.json`, `credentials`, or `CLAUDE_CONFIG_DIR`.

- [ ] **Step 5: Run the suites**

Run: `python -m unittest tests.test_identity tests.test_instance_id tests.test_settings tests.test_autostart tests.test_single_instance tests.test_verbose tests.test_app -v`
Expected: all PASS.
Run: `python -m unittest discover -s tests` - Expected: OK.

- [ ] **Step 6: Suggested manual commit (user runs)**

```
git add usage_monitor_for_claude tests
git commit -m "feat: independent Codex Windows identity (--codex-home, mutex, autostart, settings)"
```

---

### Task 13: `codex_cli.py` - discovery, versions, URLs

**Files:**
- Rename: `usage_monitor_for_claude/claude_cli.py` -> `usage_monitor_for_claude/codex_cli.py` (`git mv`, then edit)
- Rename: `tests/test_claude_cli.py` -> `tests/test_codex_cli.py`
- Modify: `usage_monitor_for_claude/app.py`, `usage_monitor_for_claude/popup.py` (imports)

**Interfaces:**
- Produces: `CODEX_CLI_PATH: Path`, `CHANGELOG_URL = 'https://github.com/openai/codex/releases'`, `PROJECT_URL = 'https://github.com/ihor-sokoliuk/usage-monitor-for-codex'`, `CodexInstallation(name, version, path)`, `cli_version(path) -> str`, `find_installations() -> list[CodexInstallation]`. No refresh machinery.

- [ ] **Step 1: Adapt the test file first (red)**

In `tests/test_codex_cli.py`: change imports to `usage_monitor_for_claude.codex_cli`; delete all `refresh_token` tests; change discovery expectations to the `codex` binary names (`codex.cmd`, `codex.exe`), add a `%LOCALAPPDATA%` installer-path test mirroring Task 5's, change the extension-prefix tests to `openai.chatgpt-` with directory names like `openai.chatgpt-26.707.71524-win32-x64` (version `26.707.71524`), and add:

```python
    def test_version_parse_codex_cli_format(self):
        with patch('usage_monitor_for_claude.codex_cli.subprocess.run') as run:
            run.return_value = MagicMock(stdout='codex-cli 0.140.0\n', returncode=0)
            with TemporaryDirectory() as tmp:
                binary = Path(tmp) / 'codex.exe'
                binary.write_bytes(b'')
                self.assertEqual(cli_version(binary), '0.140.0')
```

Run: `python -m unittest tests.test_codex_cli -v` - Expected: FAIL (module missing).

- [ ] **Step 2: Create `codex_cli.py`** from `claude_cli.py`:

- Module docstring: "Codex CLI - Discovers Codex installations on the system. Does not handle credentials."
- `_discover_cli_path()`: `shutil.which('codex')` with the same `.ps1` substitution; then `%LOCALAPPDATA%\Programs\OpenAI\Codex\bin\codex.exe`; then `%APPDATA%\npm\codex.cmd|.exe`; last-resort return of the LOCALAPPDATA path (so `is_file()` checks fail gracefully).
- `CODEX_CLI_PATH = _discover_cli_path()`; `_EXTENSION_PREFIX = 'openai.chatgpt-'` (same four IDE dirs); dataclass renamed `CodexInstallation`; delete `RefreshResult` and `refresh_token()` entirely.
- `cli_version()`: replace `re.match(...)` on stdout with `re.search(r'(\d+\.\d+\.\d+)', proc.stdout.strip())` (output is `codex-cli 0.140.0`).
- `CHANGELOG_URL`/`PROJECT_URL` as in Interfaces. `__all__` updated.
- `app.py`: `from .codex_cli import PROJECT_URL`; `popup.py`: `from .codex_cli import CHANGELOG_URL, find_installations`.

Note: `app_server.discover_codex_command()` (Task 5) and `codex_cli._discover_cli_path()` deliberately stay separate - the transport raises on absence while the versions section degrades silently, mirroring upstream's split responsibilities.

- [ ] **Step 3: Run the suites**

Run: `python -m unittest tests.test_codex_cli tests.test_popup -v` then `python -m unittest discover -s tests`
Expected: all PASS.

- [ ] **Step 4: Suggested manual commit (user runs)**

```
git add -A usage_monitor_for_claude tests
git commit -m "feat: discover Codex CLI and openai.chatgpt extensions for the versions section"
```

---

### Task 14: Tray glyph and static icon

**Files:**
- Modify: `usage_monitor_for_claude/tray_icon.py`, `usage_monitor_for_claude/app.py` (auth-error status glyph)
- Create: `tools/generate_icon.py`, `usage_monitor_for_codex.ico` (generated, committed)
- Delete: `usage_monitor_for_claude.ico` (in Task 16, together with the spec rename)
- Test: `tests/test_tray_icon.py`, `tests/test_app.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_tray_icon.py`; adapt any existing test that asserts the `'C'` glyph to the new constant)

```python
from usage_monitor_for_claude.tray_icon import ZERO_STATE_GLYPH, create_icon_image   # extend the module's imports


class TestZeroStateGlyph(unittest.TestCase):
    def test_glyph_constant(self):
        self.assertEqual(ZERO_STATE_GLYPH, '>_')

    def test_zero_usage_renders_glyph(self):
        image = create_icon_image(0, 0)
        percent_image = create_icon_image(50, 0)
        self.assertNotEqual(list(image.getdata()), list(percent_image.getdata()))
```

Also add to `tests/test_app.py` (the auth-error tray state is Claude's `C!` upstream and must be distinct too):

```python
class TestErrorGlyph(unittest.TestCase):
    def test_auth_error_status_glyph_is_codex(self):
        app = _make_app()
        app._last_response = {'error': 'x', 'auth_error': True}
        with patch('usage_monitor_for_claude.app.create_status_image') as status:
            app._render_tray()
        status.assert_called_once()
        self.assertEqual(status.call_args[0][0], '>!')
```

- [ ] **Step 2: Run to verify failure** - `python -m unittest tests.test_tray_icon -v` - Expected: FAIL (`ZERO_STATE_GLYPH` undefined).

- [ ] **Step 3: Implement**

In `tray_icon.py`, add below `MARKER_WIDTH`:

```python
# Zero-usage top glyph: the Codex prompt motif, visually distinct from the
# Claude monitor's 'C' so both tray icons can be told apart at a glance.
ZERO_STATE_GLYPH = '>_'
```

and change the zero branch in `create_icon_image()`:

```python
    else:
        text, font = ZERO_STATE_GLYPH, load_font(36)
```

Add `'ZERO_STATE_GLYPH'` to `__all__`.

In `app.py` `_render_tray()`, the auth-error status glyph is also Claude-specific upstream; change:

```python
            self.icon.icon = create_status_image('>!' if data.get('auth_error') else '!', self._light_taskbar)
```

- [ ] **Step 4: Create `tools/generate_icon.py`** (run once manually; commit the output)

```python
"""
Icon Generator
===============

One-off generator for ``usage_monitor_for_codex.ico``.  Renders the Codex
prompt motif over two usage bars on a rounded dark tile and writes a
multi-size ICO.  Run from the repo root: ``python tools/generate_icon.py``.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
OUTPUT = Path(__file__).parent.parent / 'usage_monitor_for_codex.ico'


def build_master() -> Image.Image:
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=48, fill=(30, 30, 30, 255))

    font = None
    for name in ('C:\\Windows\\Fonts\\consolab.ttf', 'C:\\Windows\\Fonts\\arialbd.ttf'):
        try:
            font = ImageFont.truetype(name, 120)
            break
        except OSError:
            continue
    assert font is not None, 'no usable font found'

    bbox = draw.textbbox((0, 0), '>_', font=font)
    draw.text(((SIZE - bbox[2] + bbox[0]) / 2 - bbox[0], 40 - bbox[1]), '>_', fill=(255, 255, 255, 255), font=font)

    draw.rectangle([32, 176, 152, 198], fill=(74, 158, 255, 255))
    draw.rectangle([32, 176, SIZE - 32, 198], outline=(255, 255, 255, 90), width=3)
    draw.rectangle([32, 208, 100, 230], fill=(74, 158, 255, 255))
    draw.rectangle([32, 208, SIZE - 32, 230], outline=(255, 255, 255, 90), width=3)
    return img


if __name__ == '__main__':
    build_master().save(OUTPUT, format='ICO', sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f'wrote {OUTPUT}')
```

Run: `python tools\generate_icon.py` - Expected: `wrote ...usage_monitor_for_codex.ico`; open the file in Explorer and visually confirm legibility at 16px.

- [ ] **Step 5: Run the suites** - `python -m unittest discover -s tests` - Expected: OK.

- [ ] **Step 6: Suggested manual commit (user runs)**

```
git add usage_monitor_for_claude/tray_icon.py usage_monitor_for_claude/app.py tests/test_tray_icon.py tests/test_app.py tools/generate_icon.py usage_monitor_for_codex.ico
git commit -m "feat: Codex prompt tray glyph, distinct error glyph, and generated product icon"
```

---

### Task 15: Locale value sweep - Codex copy in all 13 languages

**Files:**
- Modify: all 13 `locale/*.json`
- Test: `tests/test_i18n.py`

- [ ] **Step 1: Write the failing guard tests** (append to `tests/test_i18n.py`)

```python
class TestCodexCopy(unittest.TestCase):
    """No Claude/Anthropic remnants in any locale value; removed keys are gone."""

    REMOVED_KEYS = {'notify_update_title', 'notify_update', 'server_error', 'http_error'}

    def _values(self, data):
        for value in data.values():
            if isinstance(value, str):
                yield value
            elif isinstance(value, list):
                yield from (v for v in value if isinstance(v, str))

    def test_no_claude_or_anthropic_in_values(self):
        for locale_file in sorted(LOCALE_DIR.glob('*.json')):
            data = json.loads(locale_file.read_text(encoding='utf-8'))
            for value in self._values(data):
                with self.subTest(locale=locale_file.name, value=value[:40]):
                    self.assertNotIn('claude', value.lower())
                    self.assertNotIn('anthropic', value.lower())

    def test_removed_keys_absent_everywhere(self):
        for locale_file in sorted(LOCALE_DIR.glob('*.json')):
            data = json.loads(locale_file.read_text(encoding='utf-8'))
            self.assertFalse(self.REMOVED_KEYS & set(data), locale_file.name)
```

Run: `python -m unittest tests.test_i18n -v` - Expected: FAIL on every locale.

- [ ] **Step 2: Apply the value changes**

In **every** locale file: delete the four removed keys; set `"claude_code": "CODEX"` and `"popup_title": "Usage Monitor for Codex"` (both untranslated); replace the values below per language. Keys not listed keep their existing translations (they contain no product names). `test_reset_*`/`test_threshold_*`/`notify_*`/durations/weekdays/status lines are unchanged.

en.json:

```json
"menu_show": "Show Codex Usage",
"tooltip_title": "Codex Usage",
"connection_error": "Could not communicate with the Codex app-server.",
"no_token": "Not signed in to Codex. Run 'codex login' first.",
"auth_expired": "Codex session expired - run 'codex login' again.",
"auth_expired_label": "Codex Session Expired",
"auth_expired_short": "Run 'codex login' to refresh your session.",
"warn_no_token": "WARNING: Not signed in to Codex!",
"warn_login": "Please install Codex and run 'codex login' first:",
"already_running": "Usage Monitor for Codex v{running_version} is already running.\n\nDo you want to replace the running instance?"
```

de.json: `"Codex-Nutzung anzeigen"`, `"Codex-Nutzung"`, `"Kommunikation mit dem Codex-App-Server nicht möglich."`, `"Nicht bei Codex angemeldet. Zuerst 'codex login' ausführen."`, `"Codex-Sitzung abgelaufen - bitte erneut 'codex login' ausführen."`, `"Codex-Sitzung abgelaufen"`, `"Führe 'codex login' aus, um die Sitzung zu erneuern."`, `"WARNUNG: Nicht bei Codex angemeldet!"`, `"Bitte zuerst Codex installieren und 'codex login' ausführen:"`, `"Usage Monitor for Codex v{running_version} läuft bereits.\n\nMöchtest du die laufende Instanz ersetzen?"`

es.json: `"Mostrar uso de Codex"`, `"Uso de Codex"`, `"No se pudo comunicar con el app-server de Codex."`, `"No has iniciado sesión en Codex. Ejecuta 'codex login' primero."`, `"La sesión de Codex ha expirado: ejecuta 'codex login' de nuevo."`, `"Sesión de Codex expirada"`, `"Ejecuta 'codex login' para renovar tu sesión."`, `"ADVERTENCIA: No has iniciado sesión en Codex."`, `"Instala Codex y ejecuta 'codex login' primero:"`, `"Usage Monitor for Codex v{running_version} ya se está ejecutando.\n\n¿Quieres reemplazar la instancia en ejecución?"`

fr.json: `"Afficher l'utilisation de Codex"`, `"Utilisation de Codex"`, `"Impossible de communiquer avec l'app-server Codex."`, `"Non connecté à Codex. Exécutez d'abord 'codex login'."`, `"Session Codex expirée - exécutez à nouveau 'codex login'."`, `"Session Codex expirée"`, `"Exécutez 'codex login' pour renouveler votre session."`, `"ATTENTION : non connecté à Codex !"`, `"Veuillez d'abord installer Codex et exécuter 'codex login' :"`, `"Usage Monitor for Codex v{running_version} est déjà en cours d'exécution.\n\nVoulez-vous remplacer l'instance en cours ?"`

hi.json: `"Codex उपयोग दिखाएँ"`, `"Codex उपयोग"`, `"Codex app-server से संपर्क नहीं हो सका।"`, `"Codex में साइन इन नहीं है। पहले 'codex login' चलाएँ।"`, `"Codex सत्र समाप्त हो गया - फिर से 'codex login' चलाएँ।"`, `"Codex सत्र समाप्त"`, `"सत्र नवीनीकृत करने के लिए 'codex login' चलाएँ।"`, `"चेतावनी: Codex में साइन इन नहीं है!"`, `"कृपया पहले Codex इंस्टॉल करें और 'codex login' चलाएँ:"`, `"Usage Monitor for Codex v{running_version} पहले से चल रहा है।\n\nक्या आप चल रही इंस्टेंस को बदलना चाहते हैं?"`

id.json: `"Tampilkan Penggunaan Codex"`, `"Penggunaan Codex"`, `"Tidak dapat berkomunikasi dengan app-server Codex."`, `"Belum masuk ke Codex. Jalankan 'codex login' terlebih dahulu."`, `"Sesi Codex kedaluwarsa - jalankan 'codex login' lagi."`, `"Sesi Codex Kedaluwarsa"`, `"Jalankan 'codex login' untuk memperbarui sesi Anda."`, `"PERINGATAN: Belum masuk ke Codex!"`, `"Silakan instal Codex dan jalankan 'codex login' terlebih dahulu:"`, `"Usage Monitor for Codex v{running_version} sudah berjalan.\n\nApakah Anda ingin mengganti instans yang sedang berjalan?"`

it.json: `"Mostra utilizzo di Codex"`, `"Utilizzo di Codex"`, `"Impossibile comunicare con l'app-server di Codex."`, `"Accesso a Codex non effettuato. Esegui prima 'codex login'."`, `"Sessione Codex scaduta - esegui di nuovo 'codex login'."`, `"Sessione Codex scaduta"`, `"Esegui 'codex login' per rinnovare la sessione."`, `"ATTENZIONE: accesso a Codex non effettuato!"`, `"Installa Codex ed esegui prima 'codex login':"`, `"Usage Monitor for Codex v{running_version} è già in esecuzione.\n\nVuoi sostituire l'istanza in esecuzione?"`

ja.json: `"Codexの使用状況を表示"`, `"Codex使用状況"`, `"Codex app-serverと通信できませんでした。"`, `"Codexにサインインしていません。先に「codex login」を実行してください。"`, `"Codexセッションの有効期限が切れました - もう一度「codex login」を実行してください。"`, `"Codexセッション期限切れ"`, `"「codex login」を実行してセッションを更新してください。"`, `"警告: Codexにサインインしていません!"`, `"先にCodexをインストールして「codex login」を実行してください:"`, `"Usage Monitor for Codex v{running_version} は既に実行中です。\n\n実行中のインスタンスを置き換えますか?"`

ko.json: `"Codex 사용량 표시"`, `"Codex 사용량"`, `"Codex app-server와 통신할 수 없습니다."`, `"Codex에 로그인되어 있지 않습니다. 먼저 'codex login'을 실행하세요."`, `"Codex 세션이 만료되었습니다 - 'codex login'을 다시 실행하세요."`, `"Codex 세션 만료"`, `"'codex login'을 실행하여 세션을 갱신하세요."`, `"경고: Codex에 로그인되어 있지 않습니다!"`, `"먼저 Codex를 설치하고 'codex login'을 실행하세요:"`, `"Usage Monitor for Codex v{running_version}이(가) 이미 실행 중입니다.\n\n실행 중인 인스턴스를 교체하시겠습니까?"`

pt-BR.json: `"Mostrar uso do Codex"`, `"Uso do Codex"`, `"Não foi possível comunicar com o app-server do Codex."`, `"Você não está conectado ao Codex. Execute 'codex login' primeiro."`, `"A sessão do Codex expirou - execute 'codex login' novamente."`, `"Sessão do Codex expirada"`, `"Execute 'codex login' para renovar sua sessão."`, `"AVISO: você não está conectado ao Codex!"`, `"Instale o Codex e execute 'codex login' primeiro:"`, `"Usage Monitor for Codex v{running_version} já está em execução.\n\nDeseja substituir a instância em execução?"`

uk.json: `"Показати використання Codex"`, `"Використання Codex"`, `"Не вдалося зв'язатися з app-server Codex."`, `"Ви не ввійшли в Codex. Спочатку виконайте 'codex login'."`, `"Сесія Codex завершилася - виконайте 'codex login' ще раз."`, `"Сесія Codex завершилася"`, `"Виконайте 'codex login', щоб оновити сесію."`, `"УВАГА: ви не ввійшли в Codex!"`, `"Спочатку встановіть Codex і виконайте 'codex login':"`, `"Usage Monitor for Codex v{running_version} вже запущено.\n\nЗамінити запущений екземпляр?"`

zh-CN.json: `"显示 Codex 用量"`, `"Codex 用量"`, `"无法与 Codex app-server 通信。"`, `"尚未登录 Codex。请先运行 'codex login'。"`, `"Codex 会话已过期 - 请重新运行 'codex login'。"`, `"Codex 会话已过期"`, `"请运行 'codex login' 以刷新会话。"`, `"警告：尚未登录 Codex！"`, `"请先安装 Codex 并运行 'codex login'："`, `"Usage Monitor for Codex v{running_version} 已在运行。\n\n是否替换正在运行的实例？"`

zh-TW.json: `"顯示 Codex 用量"`, `"Codex 用量"`, `"無法與 Codex app-server 通訊。"`, `"尚未登入 Codex。請先執行 'codex login'。"`, `"Codex 工作階段已過期 - 請重新執行 'codex login'。"`, `"Codex 工作階段已過期"`, `"請執行 'codex login' 以更新工作階段。"`, `"警告：尚未登入 Codex！"`, `"請先安裝 Codex 並執行 'codex login'："`, `"Usage Monitor for Codex v{running_version} 已在執行中。\n\n是否要取代執行中的執行個體？"`

(Value order per language matches the en.json key order shown above: menu_show, tooltip_title, connection_error, no_token, auth_expired, auth_expired_label, auth_expired_short, warn_no_token, warn_login, already_running.)

Additionally replace `notify_reset` in every locale (upstream says "Claude is ready to use again"):

| Locale | `notify_reset` |
|---|---|
| en | Your quota has been reset. Codex is ready to use again. |
| de | Dein Kontingent wurde zurückgesetzt. Codex ist wieder einsatzbereit. |
| es | Tu cuota se ha restablecido. Codex está listo para usarse de nuevo. |
| fr | Votre quota a été réinitialisé. Codex est de nouveau prêt à l'emploi. |
| hi | आपका कोटा रीसेट हो गया है। Codex फिर से उपयोग के लिए तैयार है। |
| id | Kuota Anda telah direset. Codex siap digunakan kembali. |
| it | La tua quota è stata azzerata. Codex è di nuovo pronto all'uso. |
| ja | クォータがリセットされました。Codexを再び使用できます。 |
| ko | 할당량이 재설정되었습니다. Codex를 다시 사용할 수 있습니다. |
| pt-BR | Sua cota foi redefinida. O Codex está pronto para uso novamente. |
| uk | Вашу квоту скинуто. Codex знову готовий до роботи. |
| zh-CN | 您的配额已重置。Codex 可以再次使用了。 |
| zh-TW | 您的配額已重設。Codex 可以再次使用了。 |

Scan each locale file for any further value containing "Claude"/"Anthropic" the guard test flags (translations sometimes embed the product name where English does not) and apply the same product-name swap.

- [ ] **Step 3: Run the suites**

Run: `python -m unittest tests.test_i18n -v` then `python -m unittest discover -s tests` - Expected: OK. If any test still referenced removed keys (`http_error`, `server_error`), delete those assertions - the keys are gone with the feature.

- [ ] **Step 4: Visual overflow check**

Run: `start http://localhost:8080/usage_monitor_for_claude/popup/dev.html` + `python -m http.server 8080`; cycle every language in the dropdown looking for overflow.

- [ ] **Step 5: Suggested manual commit (user runs)**

```
git add locale tests/test_i18n.py
git commit -m "feat: Codex product copy in all 13 locales, drop update-notification strings"
```

---

### Task 16: Build identity - spec, versions, requirements

**Files:**
- Rename: `usage_monitor_for_claude.spec` -> `usage_monitor_for_codex.spec`; Delete: `usage_monitor_for_claude.ico`
- Modify: `build.py`, `version_info.py`, `usage_monitor_for_claude/__init__.py`, `requirements.txt`

- [ ] **Step 1: Apply the edits**

`usage_monitor_for_codex.spec` (after `git mv`): docstring says Codex; `name='UsageMonitorForCodex'`; `icon='usage_monitor_for_codex.ico'`; `datas`/`hiddenimports`/`excludes` unchanged.

`build.py`: `SPEC = ROOT / 'usage_monitor_for_codex.spec'`; `exe = DIST / 'UsageMonitorForCodex.exe'`; docstring updated.

`version_info.py`: `filevers=(1, 0, 0, 0)`, `prodvers=(1, 0, 0, 0)`, `CompanyName 'Ihor Sokoliuk'`, `FileDescription 'Usage Monitor for Codex'`, `FileVersion '1.0.0.0'`, `InternalName 'UsageMonitorForCodex'`, `OriginalFilename 'UsageMonitorForCodex.exe'`, `ProductName 'Usage Monitor for Codex'`, `ProductVersion '1.0.0.0'`.

`__init__.py`: `__version__ = '1.0.0'`; docstring:

```python
"""
Usage Monitor for Codex
========================

Displays the current Codex usage as a system tray icon.
Left-click the icon to see a detailed usage popup.

Reads account and rate-limit data from the local ``codex app-server``
(requires the Codex CLI, signed in via ``codex login``).  Respects
``CODEX_HOME`` if set, otherwise defaults to ``~/.codex/``.
"""
```

`requirements.txt`:

```
pystray
Pillow
pywebview
pyinstaller
```

- [ ] **Step 2: Verify no `requests` import remains**

Run: `git grep --untracked -n "import requests" -- usage_monitor_for_claude` - Expected: no output.

- [ ] **Step 3: Build and frozen smoke test**

Run: `python -m unittest discover -s tests` (OK), then `python build.py`
Expected: `Build successful!  ...dist\UsageMonitorForCodex.exe`.
Run: `dist\UsageMonitorForCodex.exe --verbose`
Expected: verbose header "Usage Monitor for Codex v1.0.0"; tray icon with `>_` glyph; popup opens; account/plan/windows shown; clean quit. If the frozen EXE fails with a missing stdlib module, remove that module from the spec's `excludes` and rebuild (the `email` caveat may be moot without `requests`, but verify by running, not by assumption).

- [ ] **Step 4: Suggested manual commit (user runs)**

```
git add -A
git commit -m "build: UsageMonitorForCodex.exe identity, version 1.0.0, drop requests"
```

---

### Task 17: Documentation and project rules

**Files:**
- Modify: `README.md`, `PRIVACY.md`, `CHANGELOG.md`, `LICENSE`, `docs/api-reference.md`, `docs/configuration.md`, `docs/event-commands.md`, `.claude/CLAUDE.md`
- Create: `AGENTS.md`, `UPSTREAM_SYNC.md`
- Delete: `docs/automatic-update-check.md`

- [ ] **Step 1: `PRIVACY.md`** (full replacement)

```markdown
# Privacy Policy

**Usage Monitor for Codex** is a local desktop application that monitors your Codex plan usage.

## Data Collection

This application does **not** collect, store, or transmit any personal data.

## Network Communication

The application makes no outbound API requests of its own. Account and usage data is exchanged with
the local `codex app-server` process over standard input/output. That external Codex process performs
network activity according to your own Codex configuration.

## Credentials

The application never reads any credential file - neither its contents nor its metadata. Authentication
is handled entirely by the Codex app-server; the monitor only receives your email, plan type, and usage
percentages, which are kept in memory and never logged or transmitted elsewhere.

## Local Storage

The application does not write any files. All usage data is kept in memory only and discarded when
the application closes. An optional settings file (`usage-monitor-for-codex-settings.json`) is read-only.

## Third-Party Services

The application does not integrate with any analytics, tracking, advertising, or telemetry services.

## Contact

For questions about this privacy policy, please open an issue at
https://github.com/ihor-sokoliuk/usage-monitor-for-codex/issues
```

- [ ] **Step 2: `CHANGELOG.md`** (full replacement)

```markdown
# Changelog

All notable changes to Usage Monitor for Codex are documented here.
This project is a fork of [usage-monitor-for-claude](https://github.com/jens-duttke/usage-monitor-for-claude)
by Jens Duttke; its pre-fork history lives in that repository.

## [Unreleased]

### Added

- Initial release: Codex plan usage in the Windows system tray, read from the local
  `codex app-server` - live tray bars, detail popup, smart alerts, event commands,
  adaptive polling, 13 languages, and multi-instance support via `--codex-home`.
```

- [ ] **Step 3: `LICENSE`**: keep the MIT text and the existing `Copyright (c) ... Jens Duttke` line; add directly below it: `Copyright (c) 2026 Ihor Sokoliuk (Codex port)`.

- [ ] **Step 4: `UPSTREAM_SYNC.md`** (create)

```markdown
# Upstream Sync Ledger

- Upstream: https://github.com/jens-duttke/usage-monitor-for-claude
- Port baseline: f9224c2667ce7210464590d1e5e3f5d8637c8c69
- Last reviewed upstream SHA: f9224c2667ce7210464590d1e5e3f5d8637c8c69

## File map (fork renames upstream paths)

| Upstream | Fork |
|---|---|
| usage_monitor_for_claude/claude_cli.py | usage_monitor_for_claude/codex_cli.py |
| usage_monitor_for_claude.spec | usage_monitor_for_codex.spec |
| usage_monitor_for_claude.ico | usage_monitor_for_codex.ico |
| tests/test_claude_cli.py | tests/test_codex_cli.py |
| (claude update refresh machinery) | (deleted - Codex app-server owns auth) |

## Review flow

1. `git fetch upstream --tags`
2. `git log --oneline --reverse <last-reviewed-sha>..upstream/main -- usage_monitor_for_claude/popup.py usage_monitor_for_claude/popup usage_monitor_for_claude/tray_icon.py usage_monitor_for_claude/formatting.py locale README.md CHANGELOG.md`
3. Classify each commit: UI-only / mixed UI+provider / Claude-backend / docs / irrelevant.
4. Cherry-pick UI-only commits with `git cherry-pick -x`; manually port the UI part of mixed commits.
5. Never resolve a conflict by reintroducing Anthropic endpoints, credential handling,
   Claude identity names, `claude update` behavior, or Claude branding.
6. After every import: full Windows unit suite, rebuild, dual-monitor smoke test.
7. Update the imports table below and the last-reviewed SHA above.

## Imported changes

| Date | Upstream SHA | Method | Notes |
|---|---|---|---|
```

- [ ] **Step 5: `README.md`** - full rewrite keeping the upstream structure. Concrete requirements (write the prose to match; every claim below is load-bearing):

- Title "Usage Monitor for Codex"; tagline "Monitor your Codex rate limits in real time - right from your Windows system tray."; remove the Claude badges and the Agent Monitor tip block.
- Features list keeps the upstream tier order; changed bullets: Zero configuration ("authenticates through your existing Codex sign-in - the local `codex app-server` handles credentials; the monitor never touches them"); Detail popup mentions dynamically detected windows including model-scoped and unusual durations; "Codex versions" bullet (CLI + `openai.chatgpt` IDE extensions); "Automatic token refresh" bullet becomes "Automatic session recovery - on an auth error the monitor asks the app-server to refresh the session once and recovers as soon as you sign in again"; Multi-account bullet uses `--codex-home="<path>"` and states the `cli_auth_credentials_store = "file"` requirement with a note that keyring isolation is untested; tray-fields bullet mentions auto-substitution (weekly-only accounts show the weekly bar on top).
- Security & Transparency section: "No outbound network requests - account data is exchanged with the local `codex app-server` over stdio; the monitor opens no HTTP connections of its own (network activity is performed by your Codex installation per its configuration)"; "Credentials never touched - no credential file is read, not even its metadata"; read-only; no dynamic code execution; no obfuscation; modular architecture with the security-critical boundary isolated in [`api.py`] and [`app_server.py`]; three runtime dependencies (Pillow, pystray, pywebview).
- Requirements: Windows 10/11 x64; Codex CLI installed and signed in (`codex login`); tip about the `!` icon when signed out.
- Quick Start: `UsageMonitorForCodex.exe` from the fork's releases URL.
- How to Use table and progress-bar legend unchanged apart from copy.
- Configuration: `usage-monitor-for-codex-settings.json`, search order `%CODEX_HOME%` -> next to the EXE -> `~/.codex`.
- Building from Source: fork clone URL; run/build/release commands as in Task 16; dev-section note "the internal package keeps the upstream `usage_monitor_for_claude` name deliberately, to keep upstream UI improvements mergeable".
- Credits: "Forked from Jens Duttke's Usage Monitor for Claude" with link.
- Disclaimer: independent community project, not created, endorsed, or supported by OpenAI; "Codex", "ChatGPT", and "OpenAI" are trademarks of OpenAI, used descriptively.

- [ ] **Step 6: `docs/` updates**

`docs/api-reference.md` (full replacement):

```markdown
# API Reference

The monitor reads all data from the local Codex app-server (`codex app-server`),
spoken as JSON-RPC 2.0 semantics over newline-delimited JSON with the
`"jsonrpc": "2.0"` header omitted on the wire.

## Methods used

| Method | Purpose | Notes |
|---|---|---|
| `initialize` / `initialized` | handshake | no optional capabilities requested |
| `account/read` | auth mode, email, plan | `refreshToken: true` only during the once-per-episode session recovery |
| `account/rateLimits/read` | usage windows | `usedPercent` -> percent used; `windowDurationMins` -> field name; `resetsAt` (Unix seconds) -> reset countdown |

## Notifications

`account/updated` marks auth state dirty for an early re-check. All other
notifications are ignored; unexpected server-initiated requests receive a
method-not-found response. Periodic polling remains the source of truth.

## Field naming

Window durations map to field names (`300 -> five_hour`, `10080 -> seven_day`,
`43200 -> 30_day`, `90 -> 90_minute`); buckets other than `codex` get a suffix
(`seven_day_gpt_5_pro`). Names never derive from primary/secondary position.
```

`docs/configuration.md`: rename the settings file everywhere; replace the search-order list (CODEX_HOME -> exe dir -> `~/.codex`); delete the `notify_claude_update` setting section; replace `--config-dir` with `--codex-home` in the multi-instance section and add the file-store requirement sentence. `docs/event-commands.md`: replace Claude/Agent-Monitor examples' product names with Codex equivalents; env var names unchanged. Delete `docs/automatic-update-check.md` and remove its links from README/docs.

- [ ] **Step 7: `AGENTS.md` + `.claude/CLAUDE.md` pointer**

Create `AGENTS.md` with the full current content of `.claude/CLAUDE.md`, then apply these replacements: title "# Project Guidelines"; in Security & Transparency replace the Anthropic bullets with "All app-server method names as top-level constants - no dynamic method construction", "No outbound network requests - all data flows through the local codex app-server child (spawned by `app_server.py`)", "No credential access of any kind - auth state comes only from the app-server account read", "Security-critical code (transport, adapter) isolated in `api.py` and `app_server.py`"; replace the Polling section's token-refresh/account-switch bullets with the revision-5 spec's Section 3/4 mechanisms (per-poll account read, auth revision, child TTL, error-state recycle, episode guard); delete the `claude update` bullet; keep every Popup/DPI/tray/testing/formatting rule verbatim. Replace `.claude/CLAUDE.md` entirely with:

```markdown
# Project Guidelines

All project rules live in [`AGENTS.md`](../AGENTS.md) at the repository root, shared by
every coding agent. Read it fully before making changes; it overrides default behavior,
including the auto-memory system (never write to `~/.claude/projects/.../memory/`).
```

- [ ] **Step 8: Run the full suite** (docs changes must not break anything): `python -m unittest discover -s tests` - Expected: OK.

- [ ] **Step 9: Suggested manual commit (user runs)**

```
git add -A
git commit -m "docs: Codex product documentation, AGENTS.md rules, upstream sync ledger"
```

---

### Task 18: Final verification - suite, greps, build, dual-monitor smoke

**Files:** none (verification only; any fix discovered here goes through red-green in the owning task's files).

- [ ] **Step 1: Full suite + discovery-exclusion proof**

Run: `python -m unittest discover -s tests`
Expected: OK; test count >= Task 1 baseline. Prove the probe is excluded by inspecting the discovered test IDs, not counts (a standalone script contributes zero cases either way):

```powershell
python -m unittest discover -s tests -v 2>&1 | findstr /i probe
```

Expected: no output (no discovered test ID references the probe module).

- [ ] **Step 2: Boundary greps**

All greps use `--untracked` so newly created, not-yet-committed files are covered (plain `git grep` skips untracked files; the user commits manually, so security-critical files may still be untracked here):

```powershell
git grep --untracked -nE "import requests|api\.anthropic\.com" -- usage_monitor_for_claude
git grep --untracked -n "CLAUDE_CONFIG_DIR" -- usage_monitor_for_claude
git grep --untracked -nE "from \.app_server|from usage_monitor_for_claude\.app_server" -- usage_monitor_for_claude | findstr /v api.py
git grep --untracked -niE "auth\.json|credentials" -- usage_monitor_for_claude
```

Expected: the first three produce no output. The fourth may hit docstrings that *state* the no-credential-access guarantee (in `api.py`, `app_server.py`, `verbose.py`); review every hit and confirm none is executable code constructing or checking a credential path - any such hit is a release blocker.

- [ ] **Step 3: Source smoke** - `python -m usage_monitor_for_claude --verbose`: verbose shows CODEX_HOME + Codex CLI rows and no credentials section; tray `>_` glyph; tooltip "Codex Usage"; popup shows email/plan/windows with correct reset times in your Windows clock format; pin+drag works; quit is clean and `codex app-server` disappears from Task Manager.

- [ ] **Step 4: Build + frozen smoke** - `python build.py`; run `dist\UsageMonitorForCodex.exe --verbose`; repeat Step 3's checks; also verify the EXE's Properties > Details shows ProductName "Usage Monitor for Codex" 1.0.0.

- [ ] **Step 5: Dual-monitor smoke** - start the official `UsageMonitorForClaude.exe` from a separate folder while the Codex EXE runs: two distinct tray icons/tooltips; no replace-instance prompt from either; enable autostart on both and confirm two distinct registry values under `HKCU\...\Run`; restart and quit each independently; confirm the Claude monitor's settings file is untouched. Kill the Codex monitor via Task Manager (hard terminate) and confirm its `codex` child dies with it (Job object).

- [ ] **Step 6: Verification hygiene** - `git status` must show no tracked-source modifications caused by the verification itself. Record the Phase-1/2 experiment outcomes (external-login observation) in `UPSTREAM_SYNC.md` notes and, if behavior differs from the spec's assumptions, update the spec.

- [ ] **Step 7: Suggested manual commit (user runs, if any fixture/docs notes changed)**

```
git add -A
git commit -m "chore: record verification outcomes"
```

---

## Post-plan notes

- **Green at every boundary**: Tasks 8-9 add the adapter alongside the legacy Claude client; Task 10 switches the cache, Task 11 switches the app and then deletes the legacy client (Step 6). The full suite passes at the end of every task - no red commits.
- **Wire drift**: if `WIRE_NOTES.md` (Task 2) contradicts any literal in Tasks 6-9 (method names, `refreshToken` param, error codes, keyed-bucket nesting), update the constants and fixtures first, then re-run the affected suites - the tests encode behavior, not wire spelling.
- **Deferred by design** (spec Section 11): token-activity charts, credits display, rate-limit notifications as data, keyring multi-account verification, sessions API, package rename, installer/signing/updater.
