"""Scoring harness for the member census spike (T2).

Scores the census against the verified set in
takeoff_pipeline/ledger/t2_scoring_set_SP183_B1.csv. Semantics per the
companion md (read it before touching this file):

  presence      census must find the designation
  count_approx  census count within 15 percent of qty_verified
  count_min     census count at or above the floor
  value         SF figure within 2 percent
  value_approx  SF figure within 15 percent
  attribute     scores the router and general-notes extraction; SKIPPED
                in census recall

Rows whose provenance says CONFLICT score as presence only until Ivan
resolves the count (P26: conflicts are logged, never resolved silently).

Outputs: recall, precision, per-designation misses, a one-page report
at takeoff_pipeline/ledger/spike_report.md, and appended rows in
takeoff_pipeline/ledger/accuracy_ledger.csv.

The numbers are reported as computed. Never massaged (Section 07
acceptance: recall at or above 95 percent pre-verify is the TARGET;
the report states the actual).

Counts only, no pricing (P25), no AISC weight math. Standalone.
"""

import csv
import re
from datetime import date, datetime, timezone
from pathlib import Path

from takeoff_pipeline import census, grid_geometry, scale_check, sheet_router

_PKG = Path(__file__).resolve().parent
LEDGER_DIR = _PKG / "ledger"
SCORING_CSV = LEDGER_DIR / "t2_scoring_set_SP183_B1.csv"
REPORT_PATH = LEDGER_DIR / "spike_report.md"
ACCURACY_LEDGER = LEDGER_DIR / "accuracy_ledger.csv"
LEDGER_HEADER = ["date", "job", "test", "metric", "value", "notes"]

DEFAULT_JOB = "SP183_B1"
DEFAULT_PDF = (_PKG.parent / "Bids To Estimate" / "06 South Park 183"
               / "drawings"
               / "Extracted pages from 2026-04-22 Issue For Pricing"
               " - Building 1.pdf")

RECALL_TARGET_PCT = 95.0
COUNT_APPROX_TOL_PCT = 15.0
VALUE_TOL_PCT = 2.0
VALUE_APPROX_TOL_PCT = 15.0

_SF_FIGURE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{4,7})\s?SF")


def load_scoring_set(path=None) -> list:
    rows = []
    with open(path or SCORING_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["scoring"] = row["scoring"].strip().lower()
            row["is_conflict"] = "CONFLICT" in (row.get("provenance") or "")
            rows.append(row)
    return rows


def partition_scoring_rows(rows):
    """Split scoring rows into (attribute, presence_like, value_like,
    unrecognized). Every row lands in exactly one bucket; a misspelled
    or new scoring value goes to unrecognized and is REPORTED, never
    silently dropped from a recall denominator."""
    attribute, presence_like, value_like, unrecognized = [], [], [], []
    for r in rows:
        s = r["scoring"]
        if s == "attribute":
            attribute.append(r)
        elif s in ("presence", "count_approx", "count_min"):
            presence_like.append(r)
        elif s in ("value", "value_approx"):
            value_like.append(r)
        else:
            unrecognized.append(r)
    return attribute, presence_like, value_like, unrecognized


def _hits(job, db_path, where, params) -> list:
    c = census._conn(db_path)
    try:
        return [dict(r) for r in c.execute(
            f"SELECT * FROM census_hits WHERE job = ? AND ({where})",
            (job, *params)).fetchall()]
    finally:
        c.close()


def _match_row(row, aggregates, job, db_path, sheet_ctx, grid) -> dict:
    """Find census evidence for one scoring row. Returns found flag,
    census count (when one is countable), and the evidence string.
    sheet_ctx carries foundation_sheets, plan_sheets, notes_sheets from
    the router; grid carries the Engine B footprint measurement. Every
    YES must carry its basis in the evidence string; the report prints
    it."""
    desig = row["designation"].strip().upper()
    norm = census.normalize_designation(desig)
    foundation_sheets = sheet_ctx["foundation_sheets"]

    if row["item_class"] in ("joist", "joist_girder"):
        agg = next((a for a in aggregates
                    if a["designation_norm"] == norm
                    and a["item_class"] == "JST"), None)
        if agg:
            count = agg["schedule_qty"] or agg["plan_count"]
            return {"found": True, "count": count,
                    "evidence": f"JST hits on {', '.join(agg['sheets'])},"
                                f" confidence {agg['confidence']}"}
        return {"found": False, "count": None, "evidence": ""}

    if desig == "COLUMNS":
        col = [a for a in aggregates if a["item_class"] == "COL"]
        counted = [a for a in col if a["schedule_qty"]]
        if counted:
            qty = sum(a["schedule_qty"] for a in counted)
            return {"found": True, "count": qty,
                    "evidence": "COL schedule QTY sum across "
                    + ", ".join(a["designation"] for a in counted)}
        if col:
            # A1 type-only schedule: column SIZES are present, but the
            # schedule carries no quantity column. The member count is
            # not on a schedule; it is read from the foundation plan and
            # verified by Ivan. The text census cannot produce it, and
            # the scorecard says so rather than inventing a total.
            types = ", ".join(sorted(a["designation"] for a in col))
            return {"found": True, "count": None,
                    "evidence": f"column TYPES present from a base-plate "
                    f"or column schedule ({types}); member count not on "
                    "a schedule, count from the foundation plan, Ivan "
                    "verify"}
        if foundation_sheets:
            marks = ",".join("?" for _ in foundation_sheets)
            hss = _hits(job, db_path,
                        "item_class = 'BEAM' AND designation LIKE 'HSS%'"
                        f" AND source_kind = 'PLAN' AND sheet IN ({marks})",
                        tuple(foundation_sheets))
            if hss:
                return {"found": True, "count": len(hss),
                        "evidence": f"{len(hss)} HSS plan callouts on "
                                    "the foundation plan (column tags; "
                                    "text census counts callout text, "
                                    "not members)"}
        return {"found": False, "count": None, "evidence": ""}

    if "ANCHOR" in desig:
        anch = _hits(job, db_path, "item_class = 'ANCH'", ())
        if anch:
            return {"found": True, "count": len(anch),
                    "evidence": f"{len(anch)} anchor rod text hits on "
                    + ", ".join(sorted({h['sheet'] for h in anch}))}
        return {"found": False, "count": None, "evidence": ""}

    if "LADDER" in desig:
        rows = _hits(job, db_path,
                     "raw_text LIKE '%LADDER%'"
                     " OR designation LIKE '%LADDER%'", ())
        # General-notes boilerplate ("roof ladder assemblies shall...")
        # exists on jobs with no ladder in scope. Presence needs a hit
        # on a plan or detail sheet, and the cage attribute is reported
        # as verified or not, never silently assumed.
        notes_sheets = set(sheet_ctx["notes_sheets"])
        substantive = [h for h in rows if h["sheet"] not in notes_sheets]
        if substantive:
            caged = [h for h in substantive
                     if "CAGE" in h["raw_text"].upper()]
            cage_note = ("CAGE text present"
                         if caged else
                         "no CAGE text anywhere; cage attribute "
                         "UNVERIFIED, ladder presence only")
            return {"found": True, "count": None,
                    "evidence": "ladder text on "
                    + ", ".join(sorted({h['sheet'] for h in substantive}))
                    + f" ({cage_note})"}
        if rows:
            return {"found": False, "count": None,
                    "evidence": "ladder text only in general notes "
                                "boilerplate; not counted as presence"}
        return {"found": False, "count": None, "evidence": ""}

    if "EMBED" in desig:
        rows = _hits(job, db_path,
                     "raw_text LIKE '%EMBED%'"
                     " OR designation LIKE '%EMBED%'", ())
        if rows:
            return {"found": True, "count": None,
                    "evidence": f"{len(rows)} embed text hits on "
                    + ", ".join(sorted({h['sheet'] for h in rows}))}
        return {"found": False, "count": None, "evidence": ""}

    if desig.endswith(" SF") or "SF" in desig.split():
        # Engine B: the footprint comes from grid geometry, not a
        # printed figure. Building reads the floor/foundation plan,
        # deck the roof framing plan.
        # Strictly the requested footprint: a BUILDING SF row is never
        # answered with the deck footprint or the reverse. A missing
        # section falls through to the printed-figure path, never a
        # silent cross-source substitution.
        section = "building" if "BUILDING" in desig else "deck"
        m = grid.get(section) if grid else None
        if m and m.get("area_sf"):
            return {"found": True, "count": m["area_sf"],
                    "evidence": f"grid-geometry footprint "
                    f"{m['length_ft']:g} x {m['width_ft']:g} ft = "
                    f"{m['area_sf']:g} SF on {m['sheet']} (Engine B), "
                    f"confidence {m['confidence']}"}
        # Fallback: the largest SF figure printed on a PLAN sheet,
        # target-blind. Most structural sets do not print one.
        plan_sheets = set(sheet_ctx["plan_sheets"])
        figs = []
        for h in _hits(job, db_path,
                       "designation LIKE '%SF%' AND item_class = 'MISC'",
                       ()):
            m = _SF_FIGURE.search(h["designation"])
            if m and h["sheet"] in plan_sheets:
                figs.append((float(m.group(1).replace(",", "")), h))
        if figs:
            best = max(figs, key=lambda fh: fh[0])
            others = sorted({f for f, _ in figs if f != best[0]})
            return {"found": True, "count": best[0],
                    "evidence": f"largest SF figure on plan sheets, "
                                f"target-blind: {best[0]:g} on "
                                f"{best[1]['sheet']}"
                    + (f"; other figures seen: {others}" if others
                       else "")}
        return {"found": False, "count": None,
                "evidence": "no SF figure on any plan sheet"}

    return {"found": False, "count": None,
            "evidence": "no matcher for this designation"}


def _score_count(row, found, count):
    """Count/value scoring per the semantics table. Returns (status,
    note). Status: PASS, FAIL, PRESENCE_ONLY, or NOT_SCORED."""
    scoring = row["scoring"]
    if row["is_conflict"]:
        return ("PRESENCE_ONLY",
                "provenance CONFLICT; presence only until Ivan resolves")
    if scoring == "presence":
        return ("NOT_SCORED", "presence row, no count semantics")
    if count is None:
        return ("FAIL", "no countable census evidence") if found else \
               ("FAIL", "designation not found")
    target = float(row["qty_verified"] or 0)
    if target <= 0:
        return ("NOT_SCORED", "no qty_verified on row")
    diff_pct = abs(count - target) / target * 100.0
    if scoring == "count_approx":
        ok = diff_pct <= COUNT_APPROX_TOL_PCT
        return ("PASS" if ok else "FAIL",
                f"census {count:g} vs verified {target:g}"
                f" ({diff_pct:.1f} pct off, tol {COUNT_APPROX_TOL_PCT:g})")
    if scoring == "count_min":
        ok = count >= target
        return ("PASS" if ok else "FAIL",
                f"census {count:g} vs floor {target:g}")
    if scoring == "value":
        ok = diff_pct <= VALUE_TOL_PCT
        return ("PASS" if ok else "FAIL",
                f"figure {count:g} vs verified {target:g}"
                f" ({diff_pct:.1f} pct off, tol {VALUE_TOL_PCT:g})")
    if scoring == "value_approx":
        ok = diff_pct <= VALUE_APPROX_TOL_PCT
        return ("PASS" if ok else "FAIL",
                f"figure {count:g} vs verified {target:g}"
                f" ({diff_pct:.1f} pct off, tol {VALUE_APPROX_TOL_PCT:g})")
    return ("NOT_SCORED", f"unknown scoring value '{scoring}'")


def _score_attributes(rows, router_result, page_texts, job, db_path):
    """Attribute rows score the T1 router and notes extraction, outside
    census recall. Conservative: anything uncertain is reported, not
    assumed."""
    out = []
    all_text = "\n".join(page_texts).upper()
    for row in rows:
        desig = row["designation"].strip().upper()
        if desig == "STAGE=IFC":
            stages = sorted({s for e in router_result["sheets"]
                             for s in e.get("stages", [])})
            # PASS only when an issued-for-construction string exists.
            # A different stage string is evidence AGAINST the claim,
            # so it is REVIEW with both shown, never a silent PASS.
            ifc = [s for s in stages if "CONSTRUCTION" in s]
            if ifc:
                out.append((row, "PASS",
                            f"construction issue string found: {ifc}"))
            elif stages:
                out.append((row, "REVIEW",
                            "claimed IFC, but the title block stage "
                            f"strings are {stages}; confirm with Ivan"))
            else:
                out.append((row, "FAIL", "no stage string extracted"))
        elif desig == "FINISH=PAINT":
            found = "PAINT" in all_text
            out.append((row, "PASS" if found else "FAIL",
                        "PAINT present in sheet text"
                        if found else "no PAINT text found"))
        elif desig == "CAMBER=NONE":
            camber = _hits(job, db_path,
                           "raw_text LIKE '%CAMBER%'", ())
            if not camber:
                out.append((row, "PASS",
                            "zero camber callouts anywhere"))
            else:
                ctx = "; ".join(sorted({h["raw_text"].strip()[:60]
                                        for h in camber})[:3])
                negated = all("NO CAMBER" in h["raw_text"].upper()
                              or "WITHOUT CAMBER" in h["raw_text"].upper()
                              for h in camber)
                out.append((row, "PASS" if negated else "REVIEW",
                            f"camber text present: {ctx}"))
        else:
            out.append((row, "NOT_SCORED",
                        "needs human judgment; not scored by the spike"))
    return out


def _append_ledger(rows) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    new_file = not ACCURACY_LEDGER.exists()
    with open(ACCURACY_LEDGER, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(LEDGER_HEADER)
        w.writerows(rows)


def run(pdf_path=None, job=DEFAULT_JOB, db_path=None,
        scoring_csv=None) -> dict:
    """Full spike run: route, scale check, census, score, report."""
    import fitz

    pdf_path = Path(pdf_path or DEFAULT_PDF)
    if not pdf_path.exists():
        raise FileNotFoundError(f"test drawing set not found: {pdf_path}")

    router_result = sheet_router.route(pdf_path)
    scales = scale_check.check_pdf(pdf_path, router_result)
    census_summary = census.run_census(pdf_path, job, db_path,
                                       router_result)
    aggregates = census.aggregate(job, db_path)
    grid = grid_geometry.measure(pdf_path, router_result)

    doc = fitz.open(str(pdf_path))
    try:
        page_texts = [p.get_text() for p in doc]
    finally:
        doc.close()

    sheet_ctx = {
        "foundation_sheets": [
            e["sheet_number"] for e in router_result["sheets"]
            if e["sheet_number"]
            and (e["title_hint"] == "FOUNDATION"
                 or e["category"] == "FOUNDATION")
            and "PLAN" in (e["sheet_title"] or "").upper()],
        "plan_sheets": [
            e["sheet_number"] for e in router_result["sheets"]
            if e["sheet_number"]
            and "PLAN" in (e["sheet_title"] or "").upper()],
        "notes_sheets": [
            e["sheet_number"] for e in router_result["sheets"]
            if e["sheet_number"]
            and e["title_hint"] == "GENERAL_NOTES"],
    }

    scoring_rows = load_scoring_set(scoring_csv)
    (attribute_rows, presence_rows, value_rows,
     unrecognized_rows) = partition_scoring_rows(scoring_rows)

    scorecard = []
    for row in presence_rows + value_rows:
        m = _match_row(row, aggregates, job, db_path, sheet_ctx, grid)
        status, note = _score_count(row, m["found"], m["count"])
        scorecard.append({"row": row, "found": m["found"],
                          "count": m["count"], "evidence": m["evidence"],
                          "count_status": status, "count_note": note})

    presence_cards = [c for c in scorecard
                      if c["row"] in presence_rows]
    found_presence = [c for c in presence_cards if c["found"]]
    designation_recall = (len(found_presence) / len(presence_cards) * 100
                          if presence_cards else 0.0)
    found_all = [c for c in scorecard if c["found"]]
    full_recall = (len(found_all) / len(scorecard) * 100
                   if scorecard else 0.0)
    misses = [c for c in scorecard if not c["found"]]

    # Precision on the JST class only: the 8 verified tags are the one
    # exhaustive, text-verified ground truth (takeoff.xlsx Joist
    # Inventory B1). Full precision needs Ivan's complete census.
    verified_jst = {census.normalize_designation(r["designation"])
                    for r in scoring_rows
                    if r["item_class"] in ("joist", "joist_girder")}
    census_jst = {a["designation_norm"] for a in aggregates
                  if a["item_class"] == "JST"}
    jst_tp = census_jst & verified_jst
    jst_precision = (len(jst_tp) / len(census_jst) * 100
                     if census_jst else 0.0)

    attributes = _score_attributes(attribute_rows, router_result,
                                   page_texts, job, db_path)

    conflicts = []
    c = census._conn(db_path)
    try:
        conflicts = [dict(r) for r in c.execute(
            "SELECT * FROM conflicts WHERE job = ?", (job,)).fetchall()]
    finally:
        c.close()

    result = {
        "job": job,
        "pdf": str(pdf_path),
        "router": router_result,
        "scales": scales,
        "census": census_summary,
        "aggregates": aggregates,
        "grid": grid,
        "scorecard": scorecard,
        "designation_recall_pct": round(designation_recall, 1),
        "full_recall_pct": round(full_recall, 1),
        "jst_precision_pct": round(jst_precision, 1),
        "census_jst": sorted(census_jst),
        "misses": misses,
        "attributes": attributes,
        "conflicts": conflicts,
        "unrecognized_rows": unrecognized_rows,
    }
    _write_report(result)
    _write_ledger_rows(result)
    return result


def _write_report(r) -> None:
    today = date.today().isoformat()
    lines = []
    add = lines.append
    add(f"# T2 Census Spike Report - {r['job']} - {today}")
    add("")
    add(f"Test set: `{r['pdf']}`")
    add(f"Scoring set: `{SCORING_CSV.name}` "
        "(semantics in the companion md)")
    add("")
    add("## Headline numbers, as computed, not massaged")
    add("")
    tgt = RECALL_TARGET_PCT
    dr = r["designation_recall_pct"]
    add(f"- Designation recall (primary metric, presence-scorable rows): "
        f"**{dr:g} percent** against the {tgt:g} percent Section 07 "
        f"target. {'MEETS target.' if dr >= tgt else 'BELOW target.'}")
    add(f"- Recall including SF value rows: {r['full_recall_pct']:g} "
        "percent")
    add(f"- JST-class precision (only class with exhaustive ground "
        f"truth): {r['jst_precision_pct']:g} percent "
        f"(census found: {', '.join(r['census_jst']) or 'none'})")
    add(f"- Census hits stored: {r['census']['hits']} "
        f"({r['census']['schedule_hits']} schedule, "
        f"{r['census']['plan_hits']} plan) in "
        f"`{Path(r['census']['db_path']).name}`")
    add(f"- Conflicts logged, never silently resolved: "
        f"{len(r['conflicts'])}")
    scanned = r["census"]["scanned_sheets"]
    add(f"- Scanned sheets routed out (4x rasterization owns them): "
        f"{', '.join(scanned) if scanned else 'none'}")
    add("")
    if r["unrecognized_rows"]:
        add("## WARNING: unrecognized scoring values")
        add("")
        add("These rows carry scoring values this harness does not "
            "know. They are EXCLUDED from every recall denominator and "
            "must be fixed in the scoring csv, not ignored:")
        for row in r["unrecognized_rows"]:
            add(f"- {row['designation']}: scoring '{row['scoring']}'")
        add("")
    add("## Scorecard")
    add("")
    add("Every YES carries its evidence basis. A YES without readable "
        "evidence would be a number nobody can verify.")
    add("")
    add("| designation | scoring | found | evidence | count check |")
    add("|---|---|---|---|---|")
    for cdd in r["scorecard"]:
        row = cdd["row"]
        add(f"| {row['designation']} | {row['scoring']}"
            f"{' (CONFLICT)' if row['is_conflict'] else ''} | "
            f"{'YES' if cdd['found'] else 'NO'} | "
            f"{cdd['evidence'] or '-'} | "
            f"{cdd['count_status']}: {cdd['count_note']} |")
    add("")
    if r["misses"]:
        add("## Misses, per designation")
        add("")
        for cdd in r["misses"]:
            add(f"- {cdd['row']['designation']} "
                f"({cdd['row']['scoring']}): not found by the text "
                "census")
    else:
        add("## Misses")
        add("")
        add("None. Every scorable designation was found.")
    add("")
    add("## Scale check (T3)")
    add("")
    for s in r["scales"]:
        if s["status"] == "OK":
            m = s["measure"]
            add(f"- {s['sheet']}: OK. Bubbles span {m['span_pt']} pt, "
                f"measured {m['measured_ft']:g} ft vs printed "
                f"{m['stated_ft']:g} ft ({m['diff_pct']:g} pct off)")
        elif s["status"] == "FLAG":
            det = s.get("measure") or s.get("reason")
            add(f"- {s['sheet']}: FLAG. {det}")
        else:
            add(f"- {s['sheet']}: NO_CHECK ({s['reason']})")
    add("")
    add("## Attribute rows (score the router and notes extraction; "
        "excluded from census recall)")
    add("")
    for row, status, note in r["attributes"]:
        add(f"- {row['designation']}: {status}. {note}")
    add("")
    add("## Conflicts (P26)")
    add("")
    if r["conflicts"]:
        for cf in r["conflicts"]:
            add(f"- {cf['note']}")
    else:
        add("None logged on this run. The scoring set's anchor-rod "
            "CONFLICT (Ivan 64 EA floor vs takeoff 160 EA) lives in the "
            "scoring csv and scores as presence only until Ivan "
            "resolves it.")
    add("")
    add("## Honest caveats")
    add("")
    add("- The text census counts callout TEXT OBJECTS. A member tagged "
        "once with leader fan-out, or tagged on two sheets, is not a "
        "member count. Count semantics here are evidence for Ivan, not "
        "a takeoff quantity.")
    add("- COLUMNS: the base plate schedule is read and its column "
        "SIZES classified COL (A1), but it carries no quantity column, "
        "so census produces no column member count. The count comes "
        "from the foundation plan and Ivan verifies it. The scorecard "
        "shows the types found, never a fabricated total.")
    add("- Base plates: the same schedule lists plate SIZES, not a "
        "count. Census emits no base-plate count from it; the count is "
        "derived one per verified column downstream (P29), so it is an "
        "honest null pending the column count, never a per-type total. "
        "Plan callout plates are counted normally.")
    add("- Building and deck SF come from grid geometry (Engine B): the "
        "two largest orthogonal overall dimensions define a bounding-"
        "box footprint. v1 is bounding-box only and flags a non-"
        "rectangular plan for verification; it never reconstructs a "
        "polygon, and the area is Ivan's to confirm, never a price.")
    add("- Full precision needs a complete verified census. The JST "
        "class is scored because its inventory is text-verified and "
        "exhaustive; other classes are listed for eyeball review in "
        "census.db.")
    add("")
    add(f"Generated {datetime.now(timezone.utc).isoformat()} by "
        "takeoff_pipeline/score_spike.py. Counts only, no AISC weight "
        "math (schema section 4), zero P25 tokens.")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_ledger_rows(r) -> None:
    today = date.today().isoformat()
    job = r["job"]
    rows = [
        [today, job, "census_spike_T2", "designation_recall_pct",
         r["designation_recall_pct"],
         f"target {RECALL_TARGET_PCT:g} pre-verify per Section 07"],
        [today, job, "census_spike_T2", "full_recall_pct",
         r["full_recall_pct"], "includes SF value rows"],
        [today, job, "census_spike_T2", "jst_precision_pct",
         r["jst_precision_pct"],
         "JST class only; exhaustive text-verified ground truth"],
        [today, job, "census_spike_T2", "census_hits",
         r["census"]["hits"],
         f"{r['census']['schedule_hits']} schedule"
         f" / {r['census']['plan_hits']} plan"],
        [today, job, "census_spike_T2", "conflicts",
         len(r["conflicts"]), "logged, never silently resolved"],
        [today, job, "scale_check_T3", "flagged_sheets",
         sum(1 for s in r["scales"] if s["status"] == "FLAG"),
         "mismatch beyond 2 pct"],
        [today, job, "sheet_router_T1", "scanned_sheets",
         len(r["census"]["scanned_sheets"]),
         "routed to 4x rasterization, not processed here"],
    ]
    col_types = [a for a in r["aggregates"] if a["item_class"] == "COL"]
    uncounted = [a for a in col_types if not a["schedule_qty"]]
    rows.append([today, job, "census_spike_T2", "col_types_uncounted",
                 len(uncounted),
                 "column sizes on a no-QTY schedule; member count from "
                 "the foundation plan, Ivan (A1)"])
    plate_types = [a for a in r["aggregates"] if a["item_class"] == "PLATE"]
    plate_uncounted = [a for a in plate_types
                       if not a["schedule_qty"] and not a["plan_count"]]
    rows.append([today, job, "census_spike_T2", "plate_types_uncounted",
                 len(plate_uncounted),
                 "base plate sizes on a no-QTY schedule; count derived "
                 "one per column downstream (P29), Ivan (A1)"])
    grid = r.get("grid") or {}
    for metric, key in (("building_sf", "building"), ("deck_sf", "deck")):
        m = grid.get(key)
        rows.append([today, job, "grid_geometry_B", metric,
                     m["area_sf"] if m else "none",
                     (f"{m['length_ft']:g}x{m['width_ft']:g} ft, "
                      f"confidence {m['confidence']}") if m
                     else "no measurable grid footprint on the plan"])
    if r["unrecognized_rows"]:
        rows.append([today, job, "census_spike_T2",
                     "unrecognized_scoring_rows",
                     len(r["unrecognized_rows"]),
                     "EXCLUDED from recall denominators; fix the csv"])
    _append_ledger(rows)


def main() -> int:
    r = run()
    print(f"designation recall: {r['designation_recall_pct']:g} pct "
          f"(target {RECALL_TARGET_PCT:g})")
    print(f"full recall incl SF rows: {r['full_recall_pct']:g} pct")
    print(f"JST precision: {r['jst_precision_pct']:g} pct")
    print(f"misses: {[c['row']['designation'] for c in r['misses']]}")
    print(f"report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
