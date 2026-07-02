---
name: vj-self-knowledge
description: >
  Virtual Joseph's expert knowledge of the Your Company Virtual Office
  codebase, including the 471 Bridge methods, frontend wiring, known
  bugs, false-positive patterns, and the fix history through v3.2.7.
  Use this when VJ is asked to scan, fix, diagnose, or explain any
  part of the system; when a user reports a bug; when a method or
  feature can't be found; or when categorizing scan results.
triggers:
  - vj scan
  - vj scan and fix
  - virtual joseph
  - what method does
  - which bridge method
  - is this a real bug
  - false positive
  - diagnose
  - self-diagnose
  - what's broken
  - what changed in
---

# VJ Self-Knowledge

VJ is the operational expert on this codebase. Before declaring an
"issue," VJ must know what's noise and what's real. Before saying a
method doesn't exist, VJ must know the canonical name. Before
suggesting a fix, VJ must know whether someone already tried it.

## 1. Architecture (single source of truth)

```
C:\Users\YourUser\.claude\projects\Cowork Virtual Office\
  main.py                       pywebview launcher, local HTTP server,
                                background pollers
  vo_app/__init__.py            __version__ — bump on every shipped
                                build, currently 3.2.7
  bridge/api.py                 12,199 lines. The Bridge. 471 public
                                methods. Single entry point from JS.
  bridge/emr_predictor.py       EMR math (NCCI primary/excess split)
  bridge/fabrication.py         LOCAL STL/DXF generation. No AI.
  bridge/notifications.py       Background email + bid scanners
  bridge/ai_orchestration/      conductor, corrector, intake, prompts,
                                proofreader, verifier (CoVe is here)
  bridge/exporters/             Tekla XML, Strumis, calc pack
  frontend/index.html           490 lines. Shell + Three.js CDN imports.
  frontend/app.js               3,752 lines. UI, chat, 3D viewer,
                                local intercepts (no LLM round-trip).
  frontend/styles.css           All CSS. v3.2.7 added canvas fill rule.
  skills/                       This directory. SKILL.md per skill.
  data/                         SQLite DBs, JSON configs, CSV
  API Keys/                     Three text files. Loaded at startup.
```

## 2. Method-name aliases (the 471-method problem)

People type natural names. The Bridge has canonical names. Map first,
then complain. Never tell a user "that method doesn't exist" without
checking this table.

| Natural ask | Canonical method |
|---|---|
| compliance status | `compliance_summary` |
| compliance state | `get_compliance` |
| open bids | `list_bids` |
| pipeline | `get_project_pipeline` |
| steel research | `get_steel_research` |
| steel price | `get_steel_price` (by GRADE: A992, A572. Not by shape) |
| shape props / shape lookup | `get_aisc_member_info` |
| 3d model | `generate_3d_view` (NOT `generate_3d_model` — that's the older one) |
| plate weight | `calculate_plate_weight` |
| EMR check | `check_bid_emr` (v3.2.7+ accepts string or float) |
| cold email | (no Bridge method yet — drafted in chat via Claude) |
| scope creep | (no Bridge method yet — handled by skill `change-order`) |
| morning brief | `morning_briefing` |
| daily status | `daily_status` |

When the canonical method takes a non-obvious argument:
- `get_steel_price(grade)` — needs a steel GRADE string. `W14X82` will
  fail with "Grade not found." Translate: shape → grade lookup first.
- `aisc_mass_balance(extracted_tonnage)` — needs a NUMBER, not a list
  of shape names. The name misleads; treat it as "compare a tonnage
  number against expected."
- `generate_scope_narrative(members)` — needs a JSON array of member
  objects, not a CSI section code. If a section code is what the user
  has, look up `bid_documents.py` for the section template instead.

## 3. Known false-positive patterns (DO NOT flag these in vj_scan)

The static analyzer in `vj_scan` is naive. These false alarms must
be filtered before showing the user. If VJ shows these to Owner,
he will lose trust in the scanner.

### `frontend_wiring` false positives
The detector regex-matches `<word>()` calls in app.js and complains
when no function by that bare name is defined. JavaScript method
calls on objects (`.add()`, `.bid()`, `.clear()`, `.hasContext()`,
`.summary()`, `.in()`, `.t()`, `.d()`, `.b()`, `.day()`, `.item()`,
`.stale()`, `.changed()`, `.building()`, `.compliance()`,
`.send_imessage_to_contact()`, `.contextForAI()`, `.updateStatusBar()`,
`.confirm_imessage_send()`) are method calls on objects (Set, Map,
projectBank, etc.), not standalone functions. These are valid code.

### `pipeline_chain` false positive
The detector counts `.success` vs `.ok` occurrences in app.js and
flags the mismatch. All 4 `.success` references are
`r.ok || r.success` defensive checks — they correctly accept either
schema. This is not a bug.

### `diagnostic_warn` mislabeling
These are Bridge methods that emit `WARN` during their self-test.
They are not "issues" — they are functions that have optional
dependencies (vision SDK, Gemini SDK) or non-fatal data gaps. Report
these in a separate "diagnostics" bucket, not under "Issues found."

## 4. Known real bugs and fix history

| Bug | Status | Fixed in | Where |
|---|---|---|---|
| Stray `return;` killed all non-intercepted chat | FIXED | v3.2.6 | `frontend/app.js` line 846 |
| `switchPage('model')` undefined function | FIXED | v3.2.6 | `frontend/app.js` lines 2481, 2546 |
| Anthropic SDK 0.101.0 resolved `claude-sonnet-4-5` to 404'd alias | FIXED | v3.2.6 | All 32 occurrences → `claude-sonnet-4-6` |
| 3D viewer canvas bound to hidden `#three-host` | FIXED | v3.2.7 | `frontend/app.js` `initThreeViewer` |
| 3D viewer used phantom `#three-label` id | FIXED | v3.2.7 | `loadStlBase64`, `loadMultiStlBase64` |
| No CSS rule for canvas inside `#model-viewer-host` | FIXED | v3.2.7 | `frontend/styles.css` |
| `check_bid_emr` crashed on stringy input | FIXED | v3.2.7 | `bridge/api.py` — float coercion added |
| Dashboard hero numbers hardcoded (1500+, $5.9M, 4, 3) | OPEN | — | `frontend/app.js` line 362-363 |
| UI freeze on PDF drop (sync LLM vision on bridge thread) | OPEN | — | `bridge/api.py` `auto_process_drawing` |
| `vj_scan_and_fix` reports false positives | OPEN | — | This skill addresses suppression |
| Method-name inconsistency (471 methods, no manifest) | OPEN | — | This skill documents canonical names |
| Live scan takes 38 sec vs 2.5 sec sandbox | OPEN | — | Needs profiling |
| `py -3` in bat files resolves to Python 3.14 (breaks pythonnet) | OPEN | — | `RUN_VIRTUALOFFICE.bat`, `INSTALL_DEPENDENCIES.bat` |

## 5. Diagnostic playbook

When a user says "X is broken," follow this order:

1. **Reproduce in the Bridge first.** Python REPL, import Bridge,
   call the method. If the Bridge returns `ok=True`, it's a frontend
   bug. If `ok=False`, read `error`. If it throws, it's a real bug.
2. **Check the alias table** (§2 above). The method may exist under
   a different name.
3. **Check the fix history** (§4 above). The bug may have been fixed
   in a later version than the user's running build.
4. **Confirm the user's build version.** Title bar shows it.
   `Select-String -Path app.js -Pattern "<your version marker>"` from
   PowerShell confirms the deployed file is what you think.
5. **Reproduce the error path with `print` instrumentation** if the
   first 4 steps don't localize. Don't guess.

## 6. Scan output contract

When `vj_scan_and_fix` runs, the response shown to the user must:
- Show real bugs as `issues_found`
- Show false-positive categories as `suppressed` (count only, no list)
- Show `diagnostic_warn` entries under `diagnostics` (not issues)
- Show actual auto-fix attempts under `fixes_applied` with the file
  and line that changed
- If `fixes_applied == 0 and issues_found > 0`, the message must say
  "manual review needed" rather than implying success

## 7. What VJ is NOT

- VJ does not catch logic bugs. The Bridge has 471 methods. VJ scans
  for surface-level wiring. Real bugs are caught by tests, by users,
  and by post-mortems.
- VJ does not auto-fix anything destructive. No rewrites of public
  Bridge signatures. No deletion of methods. No mass renames.
- VJ does not modify the Owner's data files (`data/*.json`, `data/*.db`).

## 8. Update protocol for this file

When a new bug is fixed:
1. Add the row to §4 with the version it was fixed in
2. If the bug was caused by a false-positive class, update §3
3. Bump `__version__` in `vo_app/__init__.py`
4. Append the row to CHANGELOG.md

When a new method is added to the Bridge:
1. If it has a natural-language alias, add the row to §2
2. If its argument types are non-obvious, document them under §2

This file is the operational ground truth. If reality diverges from
this file, fix the file.

## 9. Debug sweep protocol (v3.2.7 addition)

When Joseph says "run a debug cycle," "sweep for bugs," or "debug
the build," execute this exact sequence. Do not skip steps.

### Pre-sweep checklist

```batch
:: Run from the virtualoffice\ folder
py -3 --version                                    :: must be 3.13
py -3 -c "import webview; print(webview.__version__)"
py -3 -c "import anthropic; print(anthropic.__version__)"
py -3 -c "import truststore; print('truststore OK')"
py -3 -c "import reportlab; print(reportlab.Version)"
type "%LOCALAPPDATA%\YourCompany\VirtualOffice\launch.log"
```

### Static sweep sequence (run in this order)

**Step 1 - Python syntax, all files:**
```python
find . -name "*.py" | xargs python3 -m py_compile 2>&1 | grep -v "^$"
# Any output = syntax error. Zero output = clean.
```

**Step 2 - JavaScript syntax:**
```batch
node --check frontend/app.js
```

**Step 3 - HTML div balance:**
```python
import re; html=open('frontend/index.html').read()
opens=len(re.findall(r'<div[^>]*>', html))
closes=len(re.findall(r'</div>', html))
print(f'Balance: {opens-closes:+d}')  # must be +0
```

**Step 4 - Em-dash scan (banned per the Owner's voice rules):**
```batch
grep -rn "—" --include="*.py" --include="*.js"
```
Em-dashes in vendor_quote_poller.py regex patterns are intentional
(matching inbound email subjects). Everything else is a violation.

**Step 5 - Double dict definition scan (BUG-001 class):**
```python
import ast, os
for root, dirs, files in os.walk('bridge'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if not f.endswith('.py'): continue
        src = open(os.path.join(root,f)).read()
        tree = ast.parse(src)
        names = [t.id for n in ast.walk(tree)
                 if isinstance(n, ast.Assign)
                 for t in n.targets if isinstance(t, ast.Name)]
        dups = [n for n in set(names) if names.count(n) > 1]
        if dups: print(f'{root}/{f}: duplicate assignments: {dups}')
```
Any output is a P1 bug. The second definition silently wins.

**Step 6 - Silent except scan (BUG-002 class):**
```batch
grep -rn "except Exception: pass\|except: pass" --include="*.py"
```
For each hit: read the guarded block and verify there's no dict
key access (`d['key']`), method call, or arithmetic that could fail
silently. If yes, add a `log.warning()` at minimum.

**Step 7 - Parallel table key sync (BUG-003, BUG-004 class):**
```python
from bridge.bid_sanity_gates import TONNAGE_BENCHMARKS, PRICE_BENCHMARKS
assert set(TONNAGE_BENCHMARKS) == set(PRICE_BENCHMARKS), \
    f'Sync error: {set(TONNAGE_BENCHMARKS) ^ set(PRICE_BENCHMARKS)}'
from bridge.bid_rates import BID_RATES, BID_MARGINS
```
Then cross-reference every `BID_RATES['X']` call against actual keys.

**Step 8 - PyInstaller spec runtime path audit (BUG-005 class):**
```python
# Grep for directories read at runtime:
import subprocess
result = subprocess.run(['grep', '-rn', r'Path(__file__)', '--include=*.py', 'bridge/'],
    capture_output=True, text=True)
# For each hit that reads a directory, verify it's in VirtualOffice.spec datas
spec = open('VirtualOffice.spec').read()
for runtime_dir in ['skills', 'assets', 'data', 'frontend']:
    if runtime_dir not in spec:
        print(f'WARNING: {runtime_dir}/ not in spec datas')
```

**Step 9 - Model string validation (BUG-009 class):**
```python
import subprocess
result = subprocess.run(['grep', '-rn', 'claude-', '--include=*.py'],
    capture_output=True, text=True)
VALID_MODELS = {'claude-sonnet-4-6', 'claude-opus-4-6', 'claude-haiku-4-5-20251001'}
for line in result.stdout.splitlines():
    if '#' in line: continue
    import re
    for m in re.findall(r'claude-[\w.-]+', line):
        if m not in VALID_MODELS:
            print(f'Unknown model: {m} in {line.split(":")[0]}')
```

**Step 10 - TLS gap scan (BUG-006 class):**
```batch
grep -rn "anthropic.Anthropic(" --include="*.py" bridge/
```
Any call that does not pass `http_client=` is a TLS gap candidate
on corporate networks. Should use `call_claude_robust()` or
`call_claude_with_mcps()` rather than constructing clients directly.

### Severity classification

| Finding | Severity | Action |
|---|---|---|
| Duplicate module-level assignment | P1 | Fix before ship |
| Wrong dict key under silent except | P1 | Fix before ship |
| Missing status in penalty table | P2 | Fix before ship |
| Parallel table key mismatch | P2 | Fix before ship |
| Runtime dir missing from spec datas | P2 | Fix before ship |
| TLS gap in new API path | P2 | Fix before ship |
| Nonexistent model string | P3 | Fix, low urgency |
| Em-dash in non-client output | P3 | Fix, low urgency |
| Stale version header (requirements, spec) | P3 | Cosmetic |

### Post-fix verification

For every fix applied:
1. Re-run `python3 -m py_compile` on the changed file.
2. Run a targeted Python assertion that confirms the fix works.
3. Add to CHANGELOG.md with severity, file, and one-line description.
4. Repackage without password: `zip -r output.zip virtualoffice/`

### Known false positives for this sweep

- `bridge/vendor_quote_poller.py` lines 192/209: em-dashes in regex
  are matching inbound email subject lines, not output. Intentional.
- `bridge/self_repair.py` docstrings: em-dashes in internal
  documentation only. Low priority.
- `bridge/ai_model_router.py` module docstring: em-dash in comment
  line 18. Not client-facing.

## 10. v3.2.7 bugs fixed (debug sweep, May 2026)

Added to §4 per update protocol:

| Bug | Severity | Fix | Version | File |
|---|---|---|---|---|
| MATERIAL_COSTS defined twice - second overwrites first (9 keys -> 4 keys) | P1 | Merged into single dict; volatility keys renamed `_low/_high` | v3.2.7 | `bridge/bid_rates.py` |
| BID_RATES["fab"] KeyError under silent except - margin check never ran | P1 | Key corrected to "fab_per_ton" | v3.2.7 | `bridge/bid_scorecard.py` |
| Gate 1 LOW status not penalized in calculate_confidence - scored 100/100 | P2 | Added LOW: -15 to penalty table | v3.2.7 | `bridge/bid_sanity_gates.py` |
| office_multistory missing from PRICE_BENCHMARKS - Gate 3 used retail_small floor | P2 | Added entry floor=$35, mid=$45, ceiling=$60 | v3.2.7 | `bridge/bid_sanity_gates.py` |
| skills/ not in PyInstaller spec datas - all 10 skills absent from EXE | P2 | Added skills/ and assets/ to spec datas | v3.2.7 | `VirtualOffice.spec` |
| call_claude_with_mcps() no TLS fallback - MCP calls fail on corporate proxy | P2 | Added _build_client() with truststore strategy | v3.2.7 | `bridge/claude_connect.py` |
| requirements.txt header said v3.5.2 | P3 | Bumped to v3.2.7 | v3.2.7 | `requirements.txt` |
| VirtualOffice.spec header said v1.0 + wrong psutil Linux imports | P3 | Header bumped; psutil._psutil_linux/posix removed | v3.2.7 | `VirtualOffice.spec` |
| claude-opus-4-7 in T4 tier is nonexistent model | P3 | Redirected to claude-opus-4-6 | v3.2.7 | `bridge/ai_model_router.py` |
