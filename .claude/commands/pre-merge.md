---
allowed-tools: Read, Edit, Bash, Grep, Glob, WebFetch, WebSearch, Agent
description: Maintainer pre-merge gate - audit a PR (or staged changes), output review comments, then CHANGELOG entry
argument-hint: [PR-URL or #NN]
disable-model-invocation: true
---

Maintainer-only. This is the **last line of defense** before code enters `main`.

Argument: `$ARGUMENTS`

Argument handling:
- If `$ARGUMENTS` contains a PR URL or `#NN` reference → audit that pull request via `gh`.
- If `$ARGUMENTS` is empty → audit the locally staged changes (your own work).

Mindset: **adversarial**. Assume the diff might contain a mistake, a misunderstanding, or a deliberate backdoor. Your job is to disprove that assumption before merging. Do not skip steps. Do not accept claims at face value. Verify everything against primary sources.

Users of this app handle their own Codex authentication and trust the binary to be safe at a glance. A single malicious or careless merge breaks that trust permanently.

---

## Step 0: Identify and load the change set

### If a PR was provided in `$ARGUMENTS`

1. Extract the PR number from the URL or `#NN` reference.
2. Run `gh pr view <PR> --json number,title,body,author,headRefName,baseRefName,url,state` to load metadata.
3. Run `gh pr diff <PR>` to load the actual diff.
4. Run `gh pr checks <PR>` to verify CI status.
5. Read the linked Issue or Discussion (if any) via `gh issue view` or `gh api`.
6. Note the PR author's GitHub handle - you will need it for the CHANGELOG credit later.

### If no PR was provided

1. Run `git diff --staged`. If empty, also check `git status` and ask the user what to audit.
2. Treat the user's prior conversation context as the "PR description".

Record the **stated intent** of the change in one or two sentences. You will check every line against this intent.

## Step 1: Verify the diff against the stated intent

Read **every** changed line. For each non-trivial change, walk through the code path manually:
- Given realistic input, what does the function actually do?
- Does the implementation match what the PR claims?
- Are there side effects beyond what the PR describes?

Critical questions for every change - answer each one:
- Is this change actually necessary for the stated goal? Could the goal be achieved with less surface area?
- What edge cases could break this? (boundary values, malicious input, race conditions, concurrent events, missing/null fields)
- What if the function is invoked in an unexpected order or state?
- Does anything in the diff feel "extra" - touching files or code with no obvious connection to the stated goal? **Treat unexplained scope creep as a red flag.**

## Step 2: Intensive security audit

Treat the code as untrusted. Actively try to find a way to abuse it.

### Reasoning principle (applies to every subsection below)

Do **not** treat enumerated function or library names as a checklist - an attacker can pick any name not on the list, wrap a known function in a self-written helper, compose lower-level primitives, or route a call through a transitive dependency. Reason about **capabilities** (what the code is able to cause to happen), not about names.

For every new or changed function in the diff, walk into the calls it makes. Stop the recursion only when reaching:
- (a) **pre-existing project code** that was already audited before this PR (trust within prior audit),
- (b) the **Python standard library** (note any capability the leaf exercises),
- (c) an **existing locked dependency** (note any capability the leaf exercises).

If the recursion lands on a *new* function defined in the same diff, recurse further. The example function names listed in each subsection below are non-exhaustive starting hints - they are not a complete list of dangerous symbols. The actual check is always: does **any** leaf, regardless of name, exercise the capability in question?

The dependency gate below pins the set of leaves to a closed universe. Without that gate, this reasoning principle does not work - so always run the gate first.

### Dependencies and build surface (run this FIRST as a gate)

Every later check in this audit assumes the set of available primitives (network, code execution, filesystem) is closed. New dependencies expand that set in ways the audit cannot fully predict, so they must be ruled out or scrutinized **before** anything else.

- **Default stance: no new dependencies.** Any addition to `requirements.txt`, any new third-party top-level `import`, or any new entry in `usage_monitor_for_codex.spec`'s `hiddenimports`/`datas` is a finding by default. Demand a justification tied directly to the stated PR goal. CLAUDE.md mandates "minimal, well-known dependencies only" - the bar for a new one is high.
- For each new dependency that survives that bar:
  - `WebFetch` the PyPI page: maintainer identity, release history, download counts, last update, signed releases.
  - Inspect the source repository: stars/forks, recent commit cadence, issue tracker activity, who controls the namespace.
  - Recurse into transitive dependencies - they can do networking/exec/filesystem just as effectively as the top-level dep.
  - Look for typosquats and lookalikes (`requests` vs `request`, `urllib3` vs `urlib3`, `Pillow` vs `Pyllow`).
- Changes to `usage_monitor_for_codex.spec`, `version_info.py`, `.github/workflows/*`, or any CI/build script are **high-risk surfaces in their own right** - a malicious PR can hide payload in build configuration that never appears in the source diff. Verify every line is justified by the stated PR goal.
- The diff must not contain vendored third-party code (a `vendor/` directory, a copy-pasted module from elsewhere). Any such inclusion is a finding.

### Credential and provider safety

**Capability check:** does any monitor code access a Codex credential store in any way?

- Reject credential contents, path construction, existence checks, metadata, timestamps, or watchers. Authentication state must come only from `account/read`.
- Trace fixed account/rate-limit RPCs through `api.py`, `app_server.py`, and the explicit platform lifecycle backend. Method names must be constants or literals; no dynamic method assembly or undocumented RPC is allowed.
- Preserve one generation across a logical operation, at-most-once whole-operation retry after child death, and atomic cache profile/usage updates. Check lock ordering, bounded shutdown, and parent-death cleanup on both platforms.
- No emails, tokens, credentials or credential metadata, raw payloads, raw Codex stdout/stderr, or event-command output in logs. Review exception strings, traceback formatting and diagnostic helper call sites as well as the happy path.
- Credits metadata must be dropped; dormant upstream extra-usage/prepaid/currency markup must remain unreachable from normalized Codex data.

### Network and execution boundaries

The built-in monitor makes no outbound provider/API request. Account and usage data flows only over local stdio to the fixed Codex app-server command. The external Codex child owns its authentication and network behavior.

Trace every changed I/O leaf, including webview navigation, browser links, subprocess calls and configured commands. The separately invoked fixed official `codex update` is serialized after child shutdown; it may use the network and replace the CLI. Webview loopback/runtime caches and opt-in user commands have their own documented boundaries. No new provider HTTP client, endpoint, credential path, encoded destination, release scraper or fallback installer is allowed.

### Code execution

**Capability check:** does any leaf compile, evaluate, deserialize, dynamically import, or hand control to externally-supplied bytes/strings/files? Does any leaf spawn an OS process, shell, or helper executable?

Non-exhaustive starting hints (use them as search anchors, not as a complete list): `eval`, `exec`, `compile`, `__import__`, `importlib.*`, `runpy.*`, `code.InteractiveInterpreter`, `ast.parse` followed by `exec`, `pickle.loads`, `marshal.loads`, `shelve`, `yaml.load` without `SafeLoader`, `subprocess.*`, `os.system`, `os.popen`, `os.exec*`, `os.spawn*`, `shell=True`, `pty.spawn`, `multiprocessing` with arbitrary callables, `ctypes` calls into Win32 process-creation APIs (`CreateProcessW`, `ShellExecuteW`, `WinExec`, `system`).

Project-specific: for event commands, trace exactly which commands can run, how arguments are passed, whether shell metacharacters are quoted, and whether environment variables or settings values can inject behavior.

### Filesystem

**Capability check:** does any leaf cause a side effect on the filesystem or registry? Side effects include writing, appending, creating, deleting, renaming, truncating, changing permissions, changing ownership, changing timestamps, creating links, locking, or memory-mapping with write access.

Non-exhaustive starting hints: `open(..., mode_with_write)` (any of `'w'/'a'/'x'/'r+'/'w+'/'a+'`), `io.open` likewise, `os.write` on an open fd, `os.fdopen`, `os.remove`, `os.unlink`, `os.rename`, `os.replace`, `os.link`, `os.symlink`, `os.mkdir`, `os.makedirs`, `os.rmdir`, `os.chmod`, `os.chown`, `os.utime`, `os.truncate`, `shutil.*` (copy/move/rmtree/chown), `pathlib.Path` write/touch/mkdir/rename/replace/unlink/rmdir/chmod/symlink_to/hardlink_to, `tempfile.mkstemp`/`NamedTemporaryFile(delete=False)`/`mkdtemp`, `mmap` opened for write, `fcntl`, `ctypes` calls into Win32 file APIs (`CreateFileW`, `WriteFile`, `DeleteFileW`, `MoveFileW`, `CopyFileW`, `SetFileAttributesW`).

Registry: any `winreg.SetValue*`, `winreg.DeleteValue`, `winreg.DeleteKey*`, `winreg.CreateKey*`, `winreg.SaveKey`, or `ctypes` calls into `advapi32` registry APIs (`RegSetValueExW`, `RegDeleteValueW`, `RegCreateKeyExW`, etc.).

Documented monitor writes include adjacent sanitized rotating logs, OS notification/autostart integration, and platform single-instance ownership state. Settings are read without modification. Event commands are an explicit user execution surface. Codex child/updater behavior is external and documented. Any new write target needs justification tied to the requested change; credential stores are always outside monitor access.

### Obfuscation
- Any base64, hex, or other encoded strings? Decode and inspect.
- Any unusually long string literals that do not look like normal code or text?
- Any indirect string construction (`chr()`, `ord()`, list-of-chars assembly, `"".join([...])` of suspicious bytes, `bytes.fromhex`, `codecs.decode`, ROT13 / `str.translate` with a custom table)?
- Any reflection-style attribute lookups (`getattr(module, name_from_input)`, `__getattribute__`, `operator.attrgetter` with runtime input) that resolve a callable from a string?

### Test integrity
- Are tests added that actually exercise the new behavior, or do they trivially pass (`assertTrue(True)`, no assertions, mocked-away core logic)?
- Have existing tests been weakened, removed, skipped (`@unittest.skip`), or had their assertions softened?
- Run `python -m unittest discover -s tests` (after activating the virtual environment) and confirm all tests pass.

## Step 3: External verification (web research)

For every factual claim about external behavior, verify against primary sources. Use `WebFetch` and `WebSearch`.

Examples of claims to verify:
- Windows APIs (`ctypes.windll.*`, `winreg.*`, `SystemParametersInfoW`, etc.) - check Microsoft Learn for the exact signature and behavior.
- Codex app-server behavior - check pinned OpenAI protocol/source documentation and sanitized wire fixtures.
- Tool installation paths (e.g. "Codex installed via npm lives at...") - check official installer docs.
- Library behavior (pywebview, pystray, Pillow) - check upstream documentation or source.
- Any new dependency - check its PyPI page, source repository, and recent issues.

If a claim cannot be verified against a primary source, treat it as suspect. Add it to the findings.

For complex verifications you may delegate via the `Agent` tool, but **always read and judge the agent's findings yourself** - do not delegate the decision.

## Step 4: Decision point

Collect every issue you found in Steps 1-3 with file path and line number.

### If you found ANY issue → output review comment, STOP

**Do NOT add a CHANGELOG entry.** Output a single markdown block formatted as a PR review comment that the maintainer can paste directly into the PR. Use this template (only include sections that have findings):

````markdown
## Pre-merge review

Thanks for the contribution! Before this can be merged, please address the following:

### Security
- **`<file>:<line>`** - <concrete description of the issue and what should change>

### Correctness
- **`<file>:<line>`** - <concrete description>

### Tests
- **`<file>:<line>`** - <concrete description>

### Scope
- **`<file>:<line>`** - <concrete description>

### Documentation
- **`<file>:<line>`** - <concrete description>

### Style (per [CLAUDE.md](.claude/CLAUDE.md))
- **`<file>:<line>`** - <concrete description>

### Unverified claims
- <claim from the PR description that could not be confirmed against a primary source - explain what was checked and what is missing>

Once these are addressed, please push an update and I will re-review.
````

Rules for the comment:
- Tone is respectful but firm. Contributors are welcome, but security-relevant findings are not negotiable.
- Every bullet must reference a concrete file and line, plus a clear "what should change".
- Do not paraphrase or hide a security issue under a softer category - call it out under **Security**.
- Do not include sections that have no findings (omit empty headers).
- After printing the markdown block, **stop**. Do not proceed to Step 5.

### If you found NO issues → proceed to Step 5

## Step 5: CHANGELOG entry (only if Step 4 found nothing)

### Decide whether an entry is needed

User-facing change? → entry required
- New feature, bug fix, behavior change, UI change

Internal-only? → no entry
- Refactor, code style, `CLAUDE.md` updates, doc-only changes that do not affect users

For fixes: identify the latest release tag with `git describe --tags --abbrev=0` and run `git log --oneline <latest-tag>..HEAD` to check whether the bug existed in that release. If the bug was introduced **after** the latest release tag, no entry - it never reached users.

### Propose or verify the entry

Propose an entry under `## [Unreleased]` in `CHANGELOG.md`, grouped as **Added / Changed / Fixed / Removed**. Review remains read-only unless the owner separately requests the edit.

- Write from the user's perspective - what changed, not how.
- One bullet per logical change, one sentence.
- Hyphens for dashes; never em or en dashes.
- Never mention `CLAUDE.md` changes (invisible to users).
- If the change implements a Discussion or resolves an Issue, link it in the entry text, e.g. `- [Feature name](https://github.com/ihor-sokoliuk/usage-monitor-for-codex/discussions/12) - description`.

### Contributor credit

If this is a contributor PR (Step 0 captured the GitHub handle) or a contributor-reported bug, append a thanks line:

- Code contribution: `(thanks to [@handle](https://github.com/handle) for the contribution)`
- Bug report only: `(thanks to [@handle](https://github.com/handle) for reporting [#NN](https://github.com/ihor-sokoliuk/usage-monitor-for-codex/issues/NN))`

Use the handle captured in Step 0 - never guess.

### Verify

- `git diff CHANGELOG.md` shows only the intended entry?
- Entry is in the correct group (Added / Changed / Fixed / Removed)?
- No mention of bugs introduced and fixed within the current unreleased period?

If satisfied, show the proposed changelog entry and hand it to the owner without staging or committing.

---

## Final checklist before merge

Answer **yes** to every line. If any answer is "no" or "not sure", do not merge.

- [ ] The diff does exactly what the PR description claims, and nothing more.
- [ ] No credentials can leak via logs, errors, or telemetry.
- [ ] Built-in provider data uses only fixed local Codex app-server RPCs over stdio; no credential-store access or provider HTTP is present.
- [ ] No new code execution, filesystem write, or obfuscation surface.
- [ ] All new dependencies are verified as trustworthy via primary sources.
- [ ] All factual claims about external systems are verified against primary sources.
- [ ] All tests pass and actually exercise the new behavior.
- [ ] CHANGELOG entry (if needed) is correct, in the right group, with proper credit.
