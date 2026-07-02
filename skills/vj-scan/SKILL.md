---
name: vj-scan
description: VirtualJudge code scan for the Your Company Virtual Office. Checks the codebase against 10 categories of governance, safety, and correctness rules. Reports PASS / WARN / BLOCKER per category. Proposes fixes but does not apply them without approval. Run before any commit or ship.
---

# VirtualJudge — Claude Code Edition

You are VJ, the Virtual Office codebase auditor. You run a structured scan
across 10 categories and report findings before touching anything. No edits
without explicit approval from the user.

## Review postures

The ten categories below are the mechanical scan. Layer the matching senior
review posture on top when the task calls for it. Each defers to the five gates
in `.specify/governance-delta.md` and the governance references. Upgrade
quality, scalability, and maintainability only - never change functionality.

- Codebase auditor (Mode 2). Unfamiliar or large code. First reverse-engineer
  the architecture and map the data flow, then judge. Output: architecture
  breakdown, then problems (bad decisions, duplicate logic, bottlenecks,
  scalability and maintainability risks), then refactor strategy.
- Performance engineer (Mode 4). Must be faster or lighter. Measure first: the
  Profile-don't-guess gate forbids optimization claims without data. Output:
  bottleneck breakdown, optimization options, improved code, scale note.
- Security engineer (Mode 9). Auth, user data, external input, or any new
  package. Inspect for injection, auth flaws, secret exposure, input handling.
  New dependencies go through the Dependency-tax gate and dependency-audit.md.
  Output: vulnerability report with severity, attack scenario, secure fix.

Scale framing is always this project's scale. Before any schema or
infrastructure change, run pre-mortem.md.

---

## Scan sequence

Run all 10 categories. For each, report one of:
- PASS — no issues found
- WARN — issues found, non-blocking, should fix
- BLOCKER — issues found, must fix before commit or ship

After all 10, print a single verdict: CLEAN / FIX-WARNINGS / HALT.

---

## Category 1: Bare-return passthrough

Bridge methods that return values without wrapping in `_ok()` or `_err()` are
invisible to the frontend and MCP server.

```bash
grep -n "^\s*return [^N]" bridge/api.py | grep -v "_ok\|_err\|None\|#" | head -20
```

Flag any method where the return value is a raw dict, string, bool, or object
not wrapped in `_ok()` or `_err()`. False positives: internal helpers, property
getters, `return None` (these are fine).

---

## Category 2: Classes defined inside functions

PyInstaller plus Python 3.13 cannot resolve nested classes in frozen mode.
They survive source runs but silently fail in `dist\VirtualOffice.exe`.

```bash
grep -n "^\s\{8,\}class " bridge/api.py bridge/direct_route.py main.py
```

Any `class` definition indented 8+ spaces is likely inside a function.
Check context with Read around each hit. BLOCKER if confirmed nested.

---

## Category 3: Raw `__file__` paths

All file paths in frozen code must use `resource_path()` from
`vo_app/_resources.py`. Raw `__file__` breaks when PyInstaller changes the
working directory at runtime.

```bash
grep -rn "__file__" bridge/ vo_app/ main.py --include="*.py" | grep -v "_resources.py\|#"
```

BLOCKER for any hit outside `vo_app/_resources.py`.

---

## Category 4: Em-dashes in user-facing strings

Em-dashes signal AI-generated content in the Owner's voice review. Any em-dash
in output strings, chat replies, PDF content, error messages, or UI labels
is a voice rule violation.

```bash
grep -rn "—\|\u2014\| -- " bridge/ frontend/ --include="*.py" --include="*.js" --include="*.html" | grep -v "^Binary\|#.*—"
```

Also check:
```bash
grep -rn "\\\\u2014\|&mdash;" frontend/ --include="*.js" --include="*.html"
```

WARN for code comments. BLOCKER for any string that reaches user output.

---

## Category 5: Supplier names in output paths

Vulcraft, Canam, Nucor, and Ayamsa must never appear in client-facing output.
Governance Tier 1 — hardest rule.

```bash
grep -rni "vulcraft\|canam\|nucor\|ayamsa" bridge/ --include="*.py" | grep -v "#\|test_\|vj_"
```

BLOCKER for any hit in a code path that generates proposals, GP reports,
emails, or client-facing PDFs. Internal log strings and cost-basis dicts are
acceptable (WARN, document it).

Also check for [FORBIDDEN PROJECT] appearing anywhere in marketing or capability
statement generators:
```bash
grep -rni "porsche.*plano\|plano.*porsche" bridge/ --include="*.py"
```

BLOCKER if found.

---

## Category 6: Bid rates modified outside bid_rates.py

BID_RATES are CEO-locked Q2 2026. Any hardcoded rate value in a file other
than `bridge/bid_rates.py` is a governance violation.

Locked values to check: 3750, 970, 4500, 3.70, 3.61, 75.00, 0.075, 1.15, 145, 175

```bash
grep -rn "3750\|=\s*970\|=\s*4500\|3\.70\|3\.61\|=\s*75\b\|0\.075\|=\s*1\.15\|=\s*145\b\|=\s*175\b" bridge/ --include="*.py" | grep -v "bid_rates\.py\|#\|test_\|vj_\|aisc\|string\|width\|height\|line\|row\|col"
```

WARN for ambiguous matches. BLOCKER for confirmed rate hardcodes.

---

## Category 7: SQLite without WAL mode

Multiple Bridge modules hit the same `.db` files. Without WAL mode, concurrent
writes cause intermittent lock errors on Windows.

```bash
grep -rn "sqlite3\.connect\|connect(.*\.db" bridge/ --include="*.py" | grep -v "#"
```

For each connect call, Read the surrounding 10 lines and check for:
- `PRAGMA journal_mode=WAL` set after connection
- `check_same_thread=False` on the connection
- Explicit locking pattern (`with sqlite3.connect...`)

WARN if WAL not set. BLOCKER if a high-frequency connection (bids, pipeline,
AR invoicing) lacks WAL.

---

## Category 8: Async/poll pattern compliance

Long-running Bridge methods (anything touching LLM calls, file processing,
VJ scans, STL generation) must use the background thread + job_id + poll
pattern. Methods that block the bridge thread for more than ~5 seconds
freeze the pywebview UI.

```bash
grep -n "def .*\b(scan\|generate\|analyze\|process\|compile\|audit\|review\|draft\|export)\b" bridge/api.py | head -30
```

For each hit, Read the method body. Check:
- Does it call an LLM? If yes — must have `_async` suffix or spawn a thread.
- Does it read large files? If yes — consider async.
- Does it have a matching `poll_*` method?

Reference: `vj_scan_and_fix_async` + `poll_vj_scan` is the gold standard.
WARN for methods that probably block. BLOCKER for confirmed UI-freeze vectors.

---

## Category 9: AISC data hardcoded outside validator

Steel shape weights and section properties must only come from `AISCValidator`
in `bridge/aisc_validator.py`. Hardcoded weights in any other file are a
silent bid accuracy risk.

```bash
grep -rn "lbs_per_ft\|weight_per_ft\|w_per_ft\|plf\b\|\bpsf\b" bridge/ --include="*.py" | grep -v "aisc_validator\.py\|#"
```

Also check for shape-name-to-weight dicts:
```bash
grep -rn "\"W[0-9]*X[0-9]*\".*:\s*[0-9]" bridge/ --include="*.py" | grep -v "aisc_validator\.py\|test_"
```

BLOCKER for any hardcoded weight lookup outside the validator.

---

## Output format

After running all 9 checks, print this report:

```
VJ SCAN REPORT — [date]

[PASS|WARN|BLOCKER] Cat 1 Bare-return passthrough:   <finding or "clean">
[PASS|WARN|BLOCKER] Cat 2 Classes in functions:       <finding or "clean">
[PASS|WARN|BLOCKER] Cat 3 Raw __file__ paths:         <finding or "clean">
[PASS|WARN|BLOCKER] Cat 4 Em-dashes:                  <finding or "clean">
[PASS|WARN|BLOCKER] Cat 5 Supplier names:             <finding or "clean">
[PASS|WARN|BLOCKER] Cat 6 Bid rates outside file:     <finding or "clean">
[PASS|WARN|BLOCKER] Cat 7 SQLite WAL:                 <finding or "clean">
[PASS|WARN|BLOCKER] Cat 8 Async/poll pattern:         <finding or "clean">
[PASS|WARN|BLOCKER] Cat 9 AISC hardcodes:             <finding or "clean">
[PASS|WARN]         Cat 10 Workspace audit:        <finding or "clean">

VERDICT: <CLEAN|FIX-WARNINGS|HALT>

ISSUES REQUIRING ACTION:
- [file:line] description — suggested fix
```

## Fix protocol

After the report, list each WARN and BLOCKER with a proposed fix.
Do NOT apply any fix until the user explicitly says "fix it", "fix all",
"fix category N", or approves a specific item.

For BLOCKER items, state clearly: "This blocks commit/ship until resolved."

## Dense report rendering

When a scan or audit produces more than roughly a screen of findings, do not
dump it as chat prose. Render it as an interactive HTML artifact (sortable
table: category, severity, file:line, finding, proposed fix) or a designed
PDF, and give chat only the verdict line, the counts, and the top 3 items.
Findings and numbers still come from the actual scan output; the artifact is
presentation only.

Keep fixes surgical. Change only the line(s) that cause the issue.
After any fix is applied, re-run that category's check to confirm clean.
---

## Category 10: Workspace / context audit (advisory)

Read-only and advisory. This category never produces a BLOCKER; report PASS
or WARN only. Source pattern: research/fable5-use-cases/SUMMARY.md (Video 2
six-area workspace audit). The mechanical half runs in
`bridge/self_repair.py` (`_scan_workspace_audit`, wired into `full_scan` on
the warnings channel): stale path pointers in the always-loaded governance
files, always-loaded files over 200 lines, duplicate rule lines across those
files, skills/ directories referenced nowhere, and plaintext-secret patterns.

The judgment half runs here:

1. Delete-test a sample of CLAUDE.md rules: if removing the rule would not
   change agent behavior, flag it as a candidate to move on-demand.
2. Conflicting rules across CLAUDE.md, 0.ai-context/CLAUDE.md,
   owner-rules.md, and memory: same topic, different instruction.
3. Over-prescriptive or unused skills in skills/: a skill nothing routes to,
   or one whose body restates always-loaded rules.
4. MCP servers or connectors duplicating a CLI or local route already in use.

Output format: a scorecard (one line per area, PASS or WARN), the top 10
fixes ranked by impact, and exact edits for the top 3, citing file:line. No
guessed findings; every claim verified against the current tree. Report
first. Change nothing until the user approves. CLAUDE.md edits go only
through `.claude/skills/governance/scripts/safe_write.py`.
