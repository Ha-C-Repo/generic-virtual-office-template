# PLAN.md - Virtual Office v3.3.2 Patch

**Date:** 2026-05-16
**Author:** Architect subagent
**Scope:** Claude for Excel sidebar integration (Scope 1) + Project migration scanner (Scope 2)
**Starting skill count:** 20 | **Ending skill count:** 24

---

## Locked Rate Values (from bridge/bid_rates.py, lines 13-22)

These exact values must appear in EXCEL_INSTRUCTIONS.md. Do not round or paraphrase.

| Key | Value | Unit |
|---|---|---|
| fab_per_ton | 3750 | $/ton |
| erection_per_ton | 970 | $/ton |
| joists_per_ton | 4500 | $/ton |
| roof_deck_per_sf | 3.70 | $/SF |
| composite_deck_per_sf | 3.61 | $/SF |
| anchor_rod_1x20_each | 75 | $/EA |
| ga_overhead_pct | 0.075 | 7.5% |
| net_target_gp_pct | 0.25 | ~25% blended |

GP margins: fab 31%, erection 30%, joists 40%, roof_deck 23%, composite_deck 21%, anchor_rods 31%.

Drawing-stage adders: IFC 0%, DD +5%, BUDGET/SD/CONCEPT +8%.

Payment structure: 30% mobilization / 20% first delivery / 50% SOV.

Small project override: 50% GP target when Owner flags "small" (typically under $200K).

Schedule benchmarks (from bid_rates.py lines 84-92):
- Shop drawings: 2-3 wks (overseas AISC teams)
- Joist fab: 2-3 wks
- Delivery: 3-4 wks with main steel
- Deck: 3-4 wks from PO
- Misc: 1-2 wk procurement + 3-4 wk fab + 2-3 wks after frame
- Anchor rods: 10-14 days from AB plan
- Erection: ~6-7 wks per 116K SF; misc concurrent + 3-5 day punch

Takeoff benchmarks (from bid_rates.py lines 95-102):
- Conventional steel: 6-8 PSF
- Tilt-up: 5-6 PSF
- Joists/girders: 1.5-2 PSF
- Deck SF per SF: 1.0
- Anchor rods per pier: 4
- Tolerance absorbed: 5%

---

## Dependency Graph

```
Group 1 (EXCEL_INSTRUCTIONS.md)
  |
  v
Group 2 (three Excel SKILL.md files) -- depends on Group 1 for rate reference
  |
  v
Group 3 (CROSS_APP_WORKFLOW.md) -- depends on Groups 1+2 existing
  |
  v
Group 4 (registration check, HANDOFF.md update) -- depends on Groups 1-3
  |
  v
Group 5 (migration scanner module + skill) -- independent of Scope 1 but sequenced after
  |
  v
Group 6 (scanner Bridge wiring, MCP slash command, HANDOFF.md final) -- depends on Group 5
```

Groups 1-4 form Scope 1 (atomic commit boundary).
Groups 5-6 form Scope 2 (atomic commit boundary).

---

## Task Sequence

### GROUP 1: Excel Instructions (persistent context document)

**File:** `data/excel/EXCEL_INSTRUCTIONS.md` (new file, new directory)

**Tasks:**
1. Create directory `data/excel/`
2. Write EXCEL_INSTRUCTIONS.md containing:
   - Header: this file is intended to be pasted into the Claude for Excel "Instructions" field
   - Company identity block (Your Company, LLC, Houston TX, structural steel fabricator, 12 employees, est. 2017)
   - All BID_RATES values verbatim from the table above
   - All BID_MARGINS values
   - Drawing-stage adders table
   - Payment structure (30/20/50, NOT 40/20/40)
   - Small project override rule (50% GP when flagged)
   - Schedule benchmarks from SCHEDULE_BENCHMARKS dict
   - Takeoff benchmarks from TAKEOFF_BENCHMARKS dict
   - Voice rules: no em-dashes, no filler, short sentences, specific numbers
   - Zero-fabrication mandate: never make up AISC weights, project names, or dollar amounts
   - No supplier names rule (Vulcraft, Canam, Nucor, Ayamsa never in client output)
   - No PEMB language rule
   - Deck always in scope, engineering folded into rates
   - Two PDFs per bid rule
   - Verified project portfolio (ICD Church, Elite Crossing, Topgolf NB, Carvana Mobile AL only)
   - [FORBIDDEN PROJECT] exclusion
   - CRITICAL: no =CLAUDE.ASK() formula syntax exists. Sidebar chat only.
   - No VBA macros, no Power Query, no Power Pivot

**Estimated lines:** 120-160
**Risk:** None. New file in new directory. No existing files touched.

---

### GROUP 2: Three Excel SKILL.md Files

**Files:**
- `skills/excel-bom-parser/SKILL.md` (new)
- `skills/excel-bid-pricing-validator/SKILL.md` (new)
- `skills/excel-formula-auditor/SKILL.md` (new)

**Task 2a: excel-bom-parser/SKILL.md**
1. Create directory `skills/excel-bom-parser/`
2. Write SKILL.md with YAML frontmatter (name, description, triggers)
3. Content: how to parse a BOM (bill of materials) from an Excel sheet
   - Column identification heuristics (shape, size, length, qty, weight)
   - AISC shape validation rule: shapes must be verified against the v16.0 database (2,299 shapes). If a shape is not recognized, flag it; do not guess weights.
   - No dollar amounts in output without the Owner's explicit input
   - Output format: structured table with shape, qty, unit weight, total weight, notes
   - Triggers: "parse this BOM", "bill of materials", "member list", "takeoff from Excel"

**Estimated lines:** 60-80

**Task 2b: excel-bid-pricing-validator/SKILL.md**
1. Create directory `skills/excel-bid-pricing-validator/`
2. Write SKILL.md with YAML frontmatter
3. Content: validates bid pricing in an Excel spreadsheet against locked rates
   - Read-only: never modifies cells (hard constraint)
   - Compares rates in spreadsheet against BID_RATES values
   - Flags any rate divergence over 3% without an explicit note
   - Checks drawing-stage adder application
   - Validates payment terms match 30/20/50
   - Checks GP margin targets per line item
   - Checks for supplier name leaks
   - Checks for engineering line item (should not exist)
   - Checks deck is in scope (not optional)
   - Output: validation report with PASS/WARN/FAIL per check
   - Triggers: "validate this bid", "check pricing", "rate check", "bid sanity"

**Estimated lines:** 80-100

**Task 2c: excel-formula-auditor/SKILL.md**
1. Create directory `skills/excel-formula-auditor/`
2. Write SKILL.md with YAML frontmatter
3. Content: audits Excel formulas for correctness
   - Proposes fixes but Owner approves (hard constraint: no silent edits)
   - Checks: circular references, hardcoded values that should be formulas, broken references, inconsistent ranges, SUM ranges that miss rows
   - Structural steel specific: tonnage calculations (weight/ft * length * qty / 2000), area calculations (length * width), bid total formulas (rate * quantity + G&A)
   - Output: list of findings with cell reference, current formula, proposed fix, severity
   - Triggers: "audit formulas", "check my spreadsheet", "formula errors", "Excel audit"

**Estimated lines:** 60-80

**Risk:** None. All new files. SKILL.md files are markdown only. They do NOT require VirtualOffice.spec hidden imports. Skills are bundled via the `datas` entry at VirtualOffice.spec line 37 which copies the entire `skills/` directory as a data asset.

---

### GROUP 3: Cross-App Workflow Document

**File:** `data/excel/CROSS_APP_WORKFLOW.md` (new)

**Tasks:**
1. Write two cross-app workflows:
   - **Workflow A: Excel BOM to Virtual Office bid** - User has a BOM in Excel. Claude for Excel parses it using excel-bom-parser skill. User copies the validated member list into Virtual Office chat. VO runs takeoff, pricing, sanity gates, Virtual Owner review, generates two PDFs.
   - **Workflow B: Virtual Office bid review in Excel** - User receives bid output from VO. Opens the pricing breakdown in Excel. Claude for Excel runs excel-bid-pricing-validator to cross-check. Any WARN/FAIL items go back to VO for correction.
2. Each workflow: step-by-step with which tool handles which step
3. Explicit handoff points between Excel sidebar and VO desktop app
4. Reinforce: no VBA, no Power Query, no Power Pivot, no =CLAUDE.ASK() formula

**Estimated lines:** 80-100
**Risk:** None. New file.

---

### GROUP 4: Registration Verification and HANDOFF.md Update

**Tasks:**

1. **VirtualOffice.spec** - NO CHANGES NEEDED.
   Skills are markdown files bundled via the existing `datas` entry at line 37:
   `(str(Path('skills').resolve()), 'skills')`.
   This already copies the entire skills/ directory recursively. New skill subdirectories
   are automatically included. No hidden imports needed for markdown-only skills.

2. **SkillRegistry verification** - Before committing, grep for SkillRegistry or
   skill_registry in the bridge/ directory to confirm it auto-discovers skill directories
   by scanning the skills/ folder. If it uses a hardcoded list, that list must be updated.
   This is a STOP-AND-ASK gate.

3. **HANDOFF.md** - Update the existing file at `C:\Tools\virtualoffice\HANDOFF.md`:
   - Add a "Phase 7 / v3.3.2 - Scope 1: Claude for Excel" section documenting:
     - Three new Excel skills (excel-bom-parser, excel-bid-pricing-validator, excel-formula-auditor)
     - EXCEL_INSTRUCTIONS.md location and purpose (`data/excel/EXCEL_INSTRUCTIONS.md`)
     - CROSS_APP_WORKFLOW.md location (`data/excel/CROSS_APP_WORKFLOW.md`)
     - Skill count now 23 (after Scope 1)
     - Note: no Python bridge methods for Excel skills, sidebar chat only
     - Note: no formula-based Claude calls, no VBA, no Power Query

**Estimated lines changed:** ~30-40 lines added to HANDOFF.md. Zero lines in VirtualOffice.spec.

**Risk:** HANDOFF.md is noted in CLAUDE.local.md as "history is read-only" for past entries.
We are ADDING a new section, not editing past entries. This is safe.

---

### COMMIT BOUNDARY: Scope 1

Commit all of Groups 1-4 as one atomic commit.
Message pattern: `feat: Claude for Excel sidebar integration - 3 skills, instructions, cross-app workflows [v3.3.2 Scope 1]`
Skill count: 20 -> 23

---

### GROUP 5: Migration Scanner Module + Skill

**Files:**
- `skills/project-migration-scanner/SKILL.md` (new)
- `bridge/project_migration/__init__.py` (new)
- `bridge/project_migration/scanner.py` (new)

**Task 5a: SKILL.md**
1. Create directory `skills/project-migration-scanner/`
2. Write SKILL.md with YAML frontmatter (name, description, triggers)
3. Content:
   - Two-pass architecture description (Pass 1 read-only, Pass 2 copy-only with approval)
   - Triggers: "scan projects", "migrate files", "organize project folders", "find project files"
   - Pass 1 output: inventory of files found, classified by project, type (drawing, estimate, proposal, compliance, vendor_doc, client_doc, unknown)
   - Pass 2 output: copy manifest showing what was copied where, originals untouched
   - Known project names for fuzzy matching (from scope doc)
   - Known vendor names (flag as vendor_doc, do not copy)
   - Fuzzy match threshold: 70%. Below that, file goes to unknown list.
   - API Keys/ folder exclusion (absolute, no exceptions)
   - Client docs require per-project Owner approval before copy

**Estimated lines:** 80-100

**Task 5b: bridge/project_migration/__init__.py**
1. Create directory `bridge/project_migration/`
2. Write minimal __init__.py with docstring and version string

**Estimated lines:** 5-10

**Task 5c: bridge/project_migration/scanner.py**
1. Write the two-pass scanner module
2. Key design decisions:
   - Use `pathlib.Path` throughout
   - Use `resource_path()` from `vo_app/_resources.py` for any path that needs frozen-mode compatibility
   - Use `_project_root()` pattern from `bridge/project_syncer.py` (lines 51-58) to locate project directories
   - Use `_atomic_write()` pattern from `bridge/project_syncer.py` (lines 35-45) for writing manifest JSON
   - Fuzzy matching: use `difflib.SequenceMatcher` (stdlib). NO new pip dependency. Threshold 0.70.
   - File classification: regex patterns for drawings (*.pdf with structural keywords), estimates, proposals, compliance docs, vendor docs
   - Vendor detection: match against known vendor names list
   - Return `_ok()`/`_err()` dicts (import from bridge.api at call time to avoid circular import)
   - All open() calls must use `encoding='utf-8'` explicitly

3. **Module constants:**
   ```python
   KNOWN_PROJECTS = [
       "ICD Church", "ICD", "Elite Crossing", "Fulshear", "Fulshear Central",
       "Topgolf", "New Braunfels", "Carvana", "Marathon", "Galveston",
       "Kinder Morgan", "Pasadena", "Your Company",
   ]

   KNOWN_VENDORS = [
       "Nucor", "Nucor-Yamato", "Brown-Strauss", "JH Botts", "Squickmons",
       "A&M Nut",
   ]
   VENDOR_KEYWORDS = ["price list", "catalog", "material list"]

   SKIP_DIRS = {"API Keys", "__pycache__", ".git", "node_modules", "dist", "build", ".venv", "env"}
   ```

4. **Pass 1: `scan_pass1(root_dir: str, max_depth: int = 5, max_files: int = 10000) -> dict`**
   - Walk the directory tree under root_dir
   - Skip directories in SKIP_DIRS (hard constraint: API Keys/ is never touched)
   - Respect max_depth and max_files for safety on large trees
   - For each file: extract filename, extension, parent folder name
   - Normalize both candidate and project names to lowercase before fuzzy matching
   - Fuzzy match against KNOWN_PROJECTS using `difflib.SequenceMatcher.ratio()`
   - Classify file type (drawing, estimate, proposal, compliance, vendor_doc, client_doc, unknown)
   - Flag vendor documents (match KNOWN_VENDORS + VENDOR_KEYWORDS)
   - Flag client documents (match patterns: "proposal", "quote", "contract", "agreement" in filename)
   - Build inventory dict:
     ```python
     {
         "projects": {"ICD Church": [{"path": ..., "type": ..., "match_score": ...}], ...},
         "unknown": [{"path": ..., "type": ..., "best_match": ..., "best_score": ...}],
         "vendor_docs": [{"path": ..., "vendor": ...}],
         "client_docs": [{"path": ..., "project": ..., "needs_approval": True}],
         "stats": {"total_files": N, "matched": N, "unmatched": N, "vendor": N, "client": N},
         "scan_root": root_dir,
         "scan_timestamp": "ISO-8601",
     }
     ```
   - NEVER modify any file. Read-only. Hard constraint.
   - Return: `_ok(inventory)` or `_err(msg)`

5. **Pass 2: `scan_pass2(inventory: dict, approved_projects: list[str]) -> dict`**
   - Takes the inventory from Pass 1 and a list of approved project names
   - NEVER runs without explicit call. Never triggered automatically from Pass 1.
   - For each approved project: copy files to the 9-folder structure
     (from HANDOFF.md lines 199-210: 1.Bid-Invite/, 2.Drawings/, 3.Estimate/, etc.)
   - File-to-folder routing based on type classification:
     - drawing -> 2.Drawings/
     - estimate -> 3.Estimate/
     - proposal -> 4.Proposal/
     - compliance -> 5.Compliance/
     - unknown -> Project OS/ (with "unclassified" subfolder)
   - Copy only (shutil.copy2). Never move. Originals stay in place.
   - Client docs: only copy if the project appears in approved_projects list
   - Vendor docs: never copy to project folders. Flag in output manifest.
   - Write copy manifest JSON to `data/migration_manifests/<timestamp>_manifest.json`
   - Return: `_ok({"copied": N, "skipped": N, "errors": [...], "manifest_path": str})`

6. **Gate 4 recalibration note:** After Pass 2 completes, if 3+ real projects provide
   ratio data (tonnage/SF, $/SF), recalibrate Gate 4 ranges. Only runs after Pass 2
   completion and only if sufficient data is available. This is documented but not
   auto-triggered.

**Estimated lines:** scanner.py ~250-300, __init__.py ~8

**Risks:**
- **R1: Fuzzy matching false positives.** A file named "marathon_notes.txt" in an unrelated context could match "Marathon" at >70%. Mitigation: the unknown list captures borderline cases, and Pass 2 requires explicit project approval.
- **R2: Fuzzy match threshold may be too high for normalized variants.** "Fulshear Central" vs "fulshear" may give ratio ~0.67 which would MISS. STOP-AND-ASK before finalizing. Consider lowering to 0.65 or adding alias expansion. Must test all 13 known names against each other.
- **R3: Large directory trees.** If root_dir is a high-level path, scan could take long. max_depth (default 5) and max_files (default 10000) provide safety bounds with early exit.
- **R4: No new pip dependencies.** difflib.SequenceMatcher, shutil.copy2, pathlib are all stdlib. No requirements.txt changes needed.
- **R5: Windows encoding.** All file reads/writes use encoding='utf-8'. Path objects handle Unicode natively. The mcp_server.py stdin loop (line 1510: `for line in sys.stdin:`) does NOT set explicit UTF-8 encoding, which could cause issues with non-ASCII project names on Windows cp1252 consoles. This is a pre-existing issue. Document it but do not fix in this patch.

---

### GROUP 6: Scanner Bridge Wiring + MCP Slash Command

**Files modified:**
- `bridge/api.py` - add `run_migration_scan_pass1()` method
- `mcp_server.py` - add scan_projects tool definition + _TOOL_BRIDGE_MAP entry
- `HANDOFF.md` - final update with Scope 2 additions

**Task 6a: Bridge method in bridge/api.py**
1. Grep for a good insertion point (near project-related methods, e.g., near `sync_project` or `intake_bid_from_invite`)
2. Add method:
   ```python
   def run_migration_scan_pass1(self, root_dir: str = "") -> dict:
       """Run Pass 1 of the project migration scanner (read-only inventory)."""
       from bridge.project_migration.scanner import scan_pass1
       if not root_dir:
           return _err("root_dir is required - provide the directory to scan")
       return scan_pass1(root_dir)
   ```
3. Return shape: `_ok(inventory)` or `_err(msg)` - standard Bridge contract
4. Lazy import of scanner to avoid circular import risk

**Estimated lines added:** 8-12
**Risk:** bridge/api.py is the monolith (~8,500 lines per HANDOFF.md). Use Grep to find insertion point near project-related methods. Do not read the entire file.

**Task 6b: MCP tool definition in mcp_server.py**
1. Add tool definition to LEGACY_MCP_TOOLS list (near the end, after Phase 5 entries):
   ```python
   # Phase 7 / v3.3.2
   {
       "name": "scan_projects",
       "description": "Run Pass 1 of the project migration scanner. Read-only scan that inventories files by walking a directory tree and fuzzy-matching filenames to known Your Company projects. Returns a categorized inventory with matched projects, unknown files, vendor docs, and client docs.",
       "inputSchema": {
           "type": "object",
           "properties": {
               "root_dir": {"type": "string", "description": "Root directory path to scan for project files"}
           },
           "required": ["root_dir"],
       },
   },
   ```

2. Add entry to `_TOOL_BRIDGE_MAP` dict (at line ~1258, after the Phase 5 entries):
   ```python
   # Phase 7 / v3.3.2
   "scan_projects": "run_migration_scan_pass1",
   ```

3. **Pre-edit check:** Grep for `assert.*len.*LEGACY` or `assert.*len.*MCP_TOOLS` in mcp_server.py. If a hardcoded count assertion exists, update it. Currently found: `assert len(DISPATCHER_TOOLS) == 12` at line 1123. The LEGACY_MCP_TOOLS list does not appear to have a count assertion, but verify before editing.

4. **Encoding note:** mcp_server.py reads stdin via `for line in sys.stdin:` (line 1510) without explicit UTF-8 encoding. Non-ASCII characters in file paths returned by the scanner could cause encoding errors when serialized back through stdout. This is pre-existing. Document but do not fix in this patch.

**Estimated lines added:** 15-20 in mcp_server.py

**Task 6c: VirtualOffice.spec hidden imports**
- **No changes needed.** `collect_submodules('bridge')` at VirtualOffice.spec line 18 already recursively collects all bridge submodules. Since `bridge/project_migration/` is a subpackage of `bridge/`, it is auto-collected. Verified by reading VirtualOffice.spec.

**Task 6d: HANDOFF.md final update**
1. Extend the Phase 7 section added in Group 4 with Scope 2 additions:
   - project-migration-scanner skill added (skill #24)
   - bridge/project_migration/ package created: __init__.py + scanner.py
   - Two-pass architecture: Pass 1 always read-only, Pass 2 copy-only with explicit approval
   - Bridge method: `run_migration_scan_pass1(root_dir)` in bridge/api.py
   - MCP tool: `scan_projects` mapped to `run_migration_scan_pass1` via _TOOL_BRIDGE_MAP
   - Fuzzy match uses difflib.SequenceMatcher (stdlib), threshold 0.70
   - Known project names: 13 entries. Known vendor names: 6 entries + 3 keywords.
   - No new pip dependencies added
   - Final skill count: 24

**Estimated lines added:** 20-30 to HANDOFF.md

---

### COMMIT BOUNDARY: Scope 2

Commit all of Groups 5-6 as one atomic commit.
Message pattern: `feat: project migration scanner - two-pass architecture with fuzzy matching [v3.3.2 Scope 2]`
Skill count: 23 -> 24

---

## Risk Register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Fuzzy match threshold too high for normalized variants ("Fulshear Central" vs "fulshear" ~0.67) | MEDIUM | Normalize to lowercase before comparison. Test all 13 known names. STOP-AND-ASK before finalizing threshold. Consider alias expansion or lowering to 0.65. |
| R2 | bridge/api.py circular import if scanner.py imports _ok/_err from bridge.api at module level | LOW | scanner.py must use lazy import (import inside function body), or define its own return helpers locally. |
| R3 | mcp_server.py tool count assertion breaks when adding scan_projects | LOW | Grep for assert statements near LEGACY_MCP_TOOLS before editing. Only DISPATCHER_TOOLS has a count assertion (line 1123, ==12). LEGACY_MCP_TOOLS appears unguarded, but verify. |
| R4 | Large directory scan blocks the UI thread if called from frontend | MEDIUM | For v3.3.2, the scanner is Bridge + MCP only (no frontend wiring). MCP calls run in a separate process. If frontend wiring is added later, must use the async job pattern (return job_id, spawn daemon thread, add poll method). |
| R5 | SkillRegistry uses hardcoded list instead of directory scanning | LOW | Grep for SkillRegistry in bridge/ before Group 4 commit. If hardcoded, update the list. This is a STOP-AND-ASK gate. |
| R6 | HANDOFF.md "history is read-only" constraint | LOW | We add a new section, not edit past entries. Explicitly safe per the constraint wording in CLAUDE.local.md. |
| R7 | data/excel/ directory tracking | NONE | data/ directory contents are mixed. The excel/ subdirectory contains reference docs that should be tracked. No .gitignore change needed. |
| R8 | Non-ASCII file paths in Windows scanner output | MEDIUM | All open() calls in scanner.py use encoding='utf-8'. Path objects handle Unicode. The mcp_server.py stdin encoding gap is pre-existing and documented. |
| R9 | VirtualOffice.spec needs no updates for this patch | NONE | Confirmed: line 37 bundles skills/ (all SKILL.md files), line 18 collects bridge submodules (scanner.py). No spec changes required. |
| R10 | bid_rates.py is CEO-locked | NONE | This patch only READS bid_rates.py values to embed in EXCEL_INSTRUCTIONS.md. Never modifies the file. |
| R11 | Self-test must remain 91/91 after all changes | BLOCKER | Run self test after each commit boundary. If it drops, do not proceed. |

---

## Stop-and-Ask Conditions

1. **Before Group 4 commit:** Verify SkillRegistry discovery mechanism by grepping for SkillRegistry or skill_registry in bridge/. If it uses a hardcoded skill name list, that list must be updated with the three new Excel skill names and the migration scanner skill name.

2. **Before Group 5 implementation:** Confirm fuzzy match threshold. Run a quick test in Python:
   ```python
   from difflib import SequenceMatcher
   for a, b in [("fulshear central", "fulshear"), ("icd church", "icd"), ("topgolf", "topgolf new braunfels")]:
       print(f"{a!r} vs {b!r}: {SequenceMatcher(None, a, b).ratio():.3f}")
   ```
   If any known-project pair that SHOULD match scores below 0.70, adjust threshold or add alias expansion.

3. **Before Group 6 mcp_server.py edit:** Check for assertion counts (`assert len(LEGACY_MCP_TOOLS) == ...`). If present, update the count. Currently only DISPATCHER_TOOLS has a count guard at line 1123.

4. **After Scope 1 commit:** Run `self test` in chat. Must remain 91/91.

5. **After Scope 2 commit:** Run `self test` in chat. Must remain 91/91.

6. **After both scopes:** Run `vj scan and fix`. Must be clean before shipping.

7. **If any output contains supplier names:** Stop immediately. Vulcraft, Canam, Nucor, Ayamsa, and all others from the vendor list must never appear in client-facing content. The EXCEL_INSTRUCTIONS.md must list this rule but not include supplier names as examples in the instruction text itself (use "no supplier names" not "do not mention Vulcraft..." where clients could see).

---

## Files Created (New)

| File | Group | Type | Est. Lines |
|---|---|---|---|
| data/excel/EXCEL_INSTRUCTIONS.md | 1 | Markdown reference doc | 120-160 |
| skills/excel-bom-parser/SKILL.md | 2 | Skill definition | 60-80 |
| skills/excel-bid-pricing-validator/SKILL.md | 2 | Skill definition | 80-100 |
| skills/excel-formula-auditor/SKILL.md | 2 | Skill definition | 60-80 |
| data/excel/CROSS_APP_WORKFLOW.md | 3 | Markdown reference doc | 80-100 |
| skills/project-migration-scanner/SKILL.md | 5 | Skill definition | 80-100 |
| bridge/project_migration/__init__.py | 5 | Python package init | 5-10 |
| bridge/project_migration/scanner.py | 5 | Python module | 250-300 |

## Files Modified (Existing)

| File | Group | Change | Est. Lines Added |
|---|---|---|---|
| HANDOFF.md | 4, 6 | Add Phase 7 / v3.3.2 section | 50-70 |
| bridge/api.py | 6 | Add run_migration_scan_pass1() method | 8-12 |
| mcp_server.py | 6 | Add scan_projects tool def + _TOOL_BRIDGE_MAP entry | 15-20 |

## Files NOT Modified (Confirmed Safe)

| File | Reason |
|---|---|
| VirtualOffice.spec | skills/ bundled via datas line 37; bridge/ collected via line 18. No changes needed. |
| bridge/bid_rates.py | CEO-locked. Read-only for rate values. Never edited in this patch. |
| requirements.txt | No new pip dependencies. difflib, shutil, pathlib are stdlib. |
| frontend/app.js | No frontend wiring for Excel skills (sidebar-only) or scanner (MCP-only for now). |
| main.py | No startup changes. Scanner is invoked on-demand via Bridge, not at boot. |

---

## Estimated Total New Lines

| Scope | New lines | Modified lines |
|---|---|---|
| Scope 1 (Groups 1-4) | ~450-520 | ~35 (HANDOFF.md) |
| Scope 2 (Groups 5-6) | ~350-420 | ~45 (api.py + mcp_server.py + HANDOFF.md) |
| **Total** | **~800-940** | **~80** |
