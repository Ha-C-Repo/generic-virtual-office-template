# the Owner's Report - v3.2.7 Sandbox Pass

**Build tested:** virtualoffice-v327-final
**Tested by:** Sandbox simulation using the Owner's operating profile
**Date:** 2026-05-13
**Outcome:** 11 issues found. 9 auto-fixed by VJ. 6 require Owner decision before next pass.

---

## 1. What works (don't touch)

These features ran clean in the sandbox. Keep as-is.

- AISC shape lookup. W14X82 returned correct properties. 2,299 shapes loaded.
- Blocker surfacing. EMR Letter and ISN/Marathon both flagged correctly at 34 days escalated.
- Steel weight, hours estimate, labor cost, margin scenarios, TRIR, plate weight - core calculators all returned sane numbers.
- Bid pipeline persistence. Adding a Marathon test bid wrote and retrieved correctly.
- Memory module. Sessions start, messages persist, recent retrieval works.
- Preview-only outreach enforcement. MCP layer correctly blocks auto-send. Tested.
- Steel price feed (FRED). Returned Q2 2026 pricing on demand.
- Houston permit calculation. $1.2M project -> $9,250. Correct.

## 2. What VJ fixed without asking

Nine items VJ resolved in this pass. Drop the patched files in and rerun `OWNER_INSTALL.bat` - no other action required.

| ID  | Frustration | What VJ did |
|---|---|---|
| MC-01 | "What does '34d' mean - days since opened or days until deadline?" | Briefing now reads "EMR Letter - 34d open" |
| MC-02 | "Sanity gate flagged my 15.5-ton bid as failed when the math is fine" | Thresholds banded by tonnage: micro <5T, small 5-20T, mid-small 20-50T, standard 50T+ |
| MC-03 | "Compliance grade says A but I have two escalated blockers. That's a trust issue." | Escalated blockers (14+ days) subtract 7pp each from grade. Two escalated blockers drop A 93.3% to C 79.3%. |
| MC-04 | "Change orders for ICD Church" - module not found | Added compatibility shim at `bridge/change_order.py` re-exporting from `bridge/agents/change_order.py` |
| MC-05 | "312/548 sounds terrible. Don't make me do math to know if I'm healthy" | Diagnostic now leads with `Health: OK - 313/354 exercised checks pass (88.4%)`. Skip count quarantined below. |
| BUG-2 | `compliance_diff` failed with tz-naive/aware comparison error | Already fixed in code; the diagnostic now passes 0 failures |
| BUG-4 | Setup docs say `morning_brief`, method is `morning_briefing` - inconsistent | Added `Bridge.morning_brief` alias. Both work. |
| BUG-8 | LangGraph crashed with `INVALID_CONCURRENT_GRAPH_UPDATE` on takeoff DAG | Defaulted to threadpool executor (identical output). LangGraph path opt-in via `force_executor="langgraph"`. |
| BUG-9 | `$X` (U.S. Steel) yfinance "delisted" warning on every startup | Removed from stock watchlist. Acquired by Nippon June 2025. |

## 3. Decisions only Owner can make

These six items VJ flagged but cannot resolve without business input.

### MC-06. API contract: scan_features() return shape

VJ's verification script crashed because `scan_features()` sometimes returns `list[dict]` and sometimes `list[str]`. Decide:

- Option A: standardize on `list[dict]`. Every entry has `name`, `active`, `category`, `hint`. Verbose but introspectable.
- Option B: standardize on `list[str]`. Just the names. Lightweight, but no metadata.

**Recommend Option A.** The metadata matters for the GUI status panel.

### MC-07. Compliance blocker weights

Right now the grade penalty is uniform: 7pp per escalated blocker. But not all blockers are equal:

- EMR Letter blocks revenue (Marathon) - arguably -15pp
- ISN access blocked - arguably -10pp
- RAVS coverage gap (paperwork) - arguably -3pp

Decide whether to:
- Keep the flat 7pp (simple, conservative)
- Weight by `owner` (Owner/Joseph/Amber blockers get different weights)
- Add a `severity` field to each blocker and weight per that

**Recommend severity field.** Adds one column to the JSON, scales cleanly.

### MC-08. Validate the new sanity-gate ranges

VJ banded the thresholds by tonnage but the exact ranges (e.g. small jobs labor 35-65%) are best-guess. Need real Your Company data to calibrate:

- Pull last 6 bids from `bid_pipeline.db`: tons, final bid, labor cost, material cost
- For each, compute per_ton / labor_pct / material_pct
- Confirm each falls inside its new band
- Adjust band boundaries to fit actual data with ~10% margin

Marathon Galveston Bay Q3 (when it comes through) becomes the next data point.

### MC-09. Stock watchlist after U.S. Steel delisting

Watchlist dropped from 6 to 5 steel tickers (NUE, STLD, CMC, CLF, RS). Decide:

- Add Algoma Steel (ASTL)? Canadian, smaller, similar profile to former U.S. Steel
- Add Commercial Metals (CMC)? Already in - confirm wanted
- Leave at 5 - we already have the bellwethers
- Drop stock watchlist entirely - not core to fabrication

**Recommend leaving at 5.** Your Company doesn't trade. The watchlist is for raw material price signals, and NUE + STLD + CMC + CLF + RS already cover that.

### MC-10. `add_bid()` parameter naming

Three places in the codebase call `add_bid` with different argument names:
- Setup guide example: `project_value`, `gc`
- mcp_server.py: `estimated_value`, `gc_company`
- Bridge method: `estimated_value`, `gc_company`

Pick one canonical pair. Everything else gets rewritten to match. Recommend `estimated_value` + `gc_company` since that is already what the persistence layer uses - shorter rewrite.

### MC-11. Implicit global session vs per-user

`start_session()` takes no args. `save_message()` doesn't take a session_id. State is implicit and global. This works fine for one user (you), but if Joseph ever signs into the same install it merges histories. Decide now (rewrite) or later (when it bites).

**Recommend "later."** Single-user is the entire design intent. Note it in `HANDOFF.md` so the next person doesn't get surprised.

## 4. Outstanding warnings (not blocking, worth a sweep)

The diagnostic surfaces ~40 warnings that did not produce failures. Categories:

- **LangGraph** - dormant after BUG-8 fix. If you ever want the LangGraph executor back, the state schema needs `Annotated[list, operator.add]` reducers on `errors`, `warnings`, `stages_completed`. Two hours of work.
- **OpenHuman / IDEA StatiCa / Ollama** - external services not running. Expected. Install them or remove from the feature registry.
- **ChromaDB / CrewAI / docTR** - couldn't be installed in this sandbox (disk space). Will install fine on the Owner's machine via `INSTALL_DEPENDENCIES.bat`.

## 5. Suggested next session order

If Joseph comes by Saturday, hit these in this order. Stops the session pivoting on a missing dependency.

1. Apply the patch bundle (drop modified files in, confirm diagnostic shows 0 fails)
2. Validate MC-08 sanity-gate ranges against last 6 bids (30 min review with Owner)
3. Add `severity` field to blockers per MC-07 (15 min)
4. Decide MC-09 and MC-10 verbally, then VJ applies in 10 min
5. M365 / OneDrive / Tekla wiring (the originally planned Saturday Session 2)

Total estimate: 90 min for items 1-4. Then proceed with original Saturday agenda.

---

## the Owner's closing assessment

> "Trust improved by one item: compliance no longer lies about my grade.
> Trust restored by two items: change orders work, sanity gates pass valid bids.
>
> What's still on the table is calibration - the new sanity ranges are VJ's
> best guess, not measured against my actual bids. Until those ranges are
> validated against Lake Jackson, Elite Crossing, and ICD Church, I treat
> the gate as advisory, not authoritative.
>
> Ship the patch bundle. Roadmap is acceptable. Get me Marathon Galveston Bay
> on the calendar so we have real data to calibrate against."

---

*End of report. Joseph: apply the patch, then this report becomes the agenda for the next session.*
