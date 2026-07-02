"""Virtual Owner auto-review of a bid (v15 scoring rebuild).

After takeoff and pricing, run this against the bid dict. It returns a
verdict using the same benchmarks Virtual Owner uses.

v15 score rebuild (2026-05-22): scoring now supports 95-100 ceiling.
Base score from lbs/SF gate, plus positive bonuses for accuracy
signals (schedule cross-validation, multi-sheet coverage, multi-provider
consensus, Bluebeam human-verified import), minus deductions for any
data quality issues.
"""

from __future__ import annotations
from .gates import TONNAGE_BENCHMARKS, PRICE_BENCHMARKS, _NON_INDUSTRIAL_TYPES


_INDUSTRY_TYPICAL_TONS = {
    "retail_small":     {"min_lbs_sf": 3.5, "typical_lbs_sf": 4.25},
    "retail_big_box":   {"min_lbs_sf": 4.0, "typical_lbs_sf": 5.0},
    "fitness":          {"min_lbs_sf": 5.0, "typical_lbs_sf": 6.0},
    "warehouse":        {"min_lbs_sf": 4.0, "typical_lbs_sf": 5.0},
    "office_multistory":{"min_lbs_sf": 8.0, "typical_lbs_sf": 10.0},
    "dealership":       {"min_lbs_sf": 4.0, "typical_lbs_sf": 5.0},
    "pemb_misc_only":   {"min_lbs_sf": 0.2, "typical_lbs_sf": 0.5},
    "industrial_heavy": {"min_lbs_sf": 8.0, "typical_lbs_sf": 12.0},
}


_SCORE_BONUSES = {
    "schedule_cross_validated":       6,
    "all_required_sheets_covered":    5,
    "multi_provider_consensus":       4,
    "bluebeam_import_source":         8,
    "low_duplicate_ratio":            3,
    "high_avg_confidence":            3,
    "schedule_only_match_low":        2,
}

_SCORE_DEDUCTIONS = {
    "missing_required_sheets":        8,
    "high_duplicate_ratio":           5,
    "low_avg_confidence":             5,
    "schedule_only_match_high":       5,
    "no_schedule_found":              3,
}


def _base_lbs_sf_score(lbs_sf, bench, bt):
    if lbs_sf < bench["low"] * 0.5:
        return ("EXTRACTION_LIKELY_INCOMPLETE", 15,
                f"{lbs_sf:.2f} lbs/SF is more than 50% below the "
                f"{bench['low']} floor for {bt}. Vision likely missed members.")
    if lbs_sf < bench["low"]:
        gap = bench["low"] - lbs_sf
        return ("CAUTION", 55,
                f"{lbs_sf:.2f} lbs/SF is below the {bench['low']} floor for {bt}. "
                f"Gap of {gap:.2f} lbs/SF.")
    if lbs_sf > bench["high"] * 1.5:
        return ("SUSPECT", 25,
                f"{lbs_sf:.2f} lbs/SF is more than 50% above the "
                f"{bench['high']} high benchmark for {bt}.")
    if lbs_sf < bench["mid"]:
        return ("READY", 80,
                f"{lbs_sf:.2f} lbs/SF is in the {bench['low']}-{bench['mid']} "
                f"range. Acceptable.")
    if lbs_sf <= bench["high"]:
        return ("READY", 88,
                f"{lbs_sf:.2f} lbs/SF sits in the mid-to-high band of the "
                f"{bench['low']}-{bench['high']} range.")
    return ("READY", 82,
            f"{lbs_sf:.2f} lbs/SF above {bench['high']} but within tolerance.")


def auto_review(bid: dict) -> dict:
    bt = (bid.get("building_type") or "retail_small").lower()
    building_sf = float(bid.get("building_sf") or 0)
    total_tons = float(bid.get("tonnage_summary", {}).get("total_tons") or 0)
    lbs_sf = float(bid.get("lbs_per_sf") or 0)
    dollars_sf = float(bid.get("dollars_per_sf") or 0)
    extraction = bid.get("extraction") or {}

    reasons: list = []
    recommendations: list = []
    bonuses: list = []
    deductions: list = []

    bench = TONNAGE_BENCHMARKS.get(bt, TONNAGE_BENCHMARKS["retail_small"])
    exp_low = (bench["low"] * building_sf) / 2000.0
    exp_mid = (bench["mid"] * building_sf) / 2000.0
    exp_high = (bench["high"] * building_sf) / 2000.0
    price_bench = PRICE_BENCHMARKS.get(bt, PRICE_BENCHMARKS["retail_small"])

    if total_tons == 0 and building_sf > 0:
        reasons.append(f"Zero tons extracted on a {building_sf:,.0f} SF building.")
        recommendations.append("Re-run vision cascade.")
        return _finalize("EXTRACTION_LIKELY_INCOMPLETE", 0, [], [], reasons,
                         recommendations, exp_low, exp_mid, exp_high,
                         total_tons, lbs_sf, dollars_sf, bench, price_bench,
                         extraction, final_score=0)

    verdict, base_score, base_reason = _base_lbs_sf_score(lbs_sf, bench, bt)
    reasons.append(base_reason)

    src = (extraction.get("source") or extraction.get("method") or "").lower()
    if src == "bluebeam_csv":
        bonuses.append({"name": "bluebeam_import_source",
                        "points": _SCORE_BONUSES["bluebeam_import_source"],
                        "reason": "BOQ source is Bluebeam CSV (human-verified markups)."})

    match_pct = extraction.get("schedule_match_pct")
    if isinstance(match_pct, (int, float)) and match_pct >= 0.70:
        bonuses.append({"name": "schedule_cross_validated",
                        "points": _SCORE_BONUSES["schedule_cross_validated"],
                        "reason": f"Member schedule cross-validated {match_pct*100:.0f}% of plan marks."})

    gaps = extraction.get("coverage_gaps")
    if isinstance(gaps, list) and len(gaps) == 0 and extraction.get("coverage_checked"):
        bonuses.append({"name": "all_required_sheets_covered",
                        "points": _SCORE_BONUSES["all_required_sheets_covered"],
                        "reason": "All required sheet categories were scanned."})

    mp_pct = extraction.get("multi_provider_pct")
    providers = extraction.get("providers") or []
    if isinstance(mp_pct, (int, float)) and mp_pct >= 0.50 and len(providers) >= 2:
        bonuses.append({"name": "multi_provider_consensus",
                        "points": _SCORE_BONUSES["multi_provider_consensus"],
                        "reason": f"Multi-provider consensus on {mp_pct*100:.0f}% of detections."})

    dedup_ratio = extraction.get("dedup_collapse_ratio")
    if isinstance(dedup_ratio, (int, float)):
        if dedup_ratio < 0.30:
            bonuses.append({"name": "low_duplicate_ratio",
                            "points": _SCORE_BONUSES["low_duplicate_ratio"],
                            "reason": f"Low duplicate ratio ({dedup_ratio*100:.0f}%)."})
        elif dedup_ratio > 0.70:
            deductions.append({"name": "high_duplicate_ratio",
                               "points": _SCORE_DEDUCTIONS["high_duplicate_ratio"],
                               "reason": f"High duplicate ratio ({dedup_ratio*100:.0f}%)."})

    avg_conf = extraction.get("avg_confidence")
    if isinstance(avg_conf, (int, float)):
        if avg_conf >= 0.85:
            bonuses.append({"name": "high_avg_confidence",
                            "points": _SCORE_BONUSES["high_avg_confidence"],
                            "reason": f"Mean detection confidence {avg_conf:.2f}."})
        elif avg_conf < 0.65:
            deductions.append({"name": "low_avg_confidence",
                               "points": _SCORE_DEDUCTIONS["low_avg_confidence"],
                               "reason": f"Mean detection confidence only {avg_conf:.2f}."})

    sched_only_pct = extraction.get("schedule_only_pct")
    if isinstance(sched_only_pct, (int, float)):
        if sched_only_pct < 0.10:
            bonuses.append({"name": "schedule_only_match_low",
                            "points": _SCORE_BONUSES["schedule_only_match_low"],
                            "reason": f"Only {sched_only_pct*100:.0f}% of schedule rows had no plan match."})
        elif sched_only_pct > 0.30:
            deductions.append({"name": "schedule_only_match_high",
                               "points": _SCORE_DEDUCTIONS["schedule_only_match_high"],
                               "reason": f"{sched_only_pct*100:.0f}% of schedule rows had no plan match."})

    if isinstance(gaps, list) and gaps:
        deductions.append({"name": "missing_required_sheets",
                           "points": _SCORE_DEDUCTIONS["missing_required_sheets"],
                           "reason": f"Missing required sheet categories: {', '.join(gaps)}."})
        recommendations.append(f"Re-run sweep to capture {', '.join(gaps)} pages.")

    if extraction.get("coverage_checked") and not extraction.get("schedule_pages"):
        deductions.append({"name": "no_schedule_found",
                           "points": _SCORE_DEDUCTIONS["no_schedule_found"],
                           "reason": "No member schedule was detected in the drawing set."})

    if dollars_sf > 0 and dollars_sf < price_bench["floor"]:
        reasons.append(f"${dollars_sf:.2f}/SF is below the ${price_bench['floor']}/SF floor.")
        if verdict == "READY":
            verdict = "CAUTION"
        deductions.append({"name": "below_price_floor", "points": 15,
                           "reason": f"${dollars_sf:.2f}/SF below floor ${price_bench['floor']}/SF."})

    cl = bid.get("clash_report") or {}
    if cl.get("any_clashes"):
        n_mark = cl.get("mark_clash_count", 0)
        n_grid = cl.get("grid_clash_count", 0)
        reasons.append(f"Clash detector found {n_mark} mark + {n_grid} grid collisions.")
        if verdict == "READY":
            verdict = "CAUTION"
        deductions.append({"name": "clash_collisions", "points": 8,
                           "reason": f"{n_mark} mark + {n_grid} grid clashes."})

    if extraction.get("method") == "regex" and verdict == "READY":
        verdict = "CAUTION"
        reasons.append("Vision was not used in this run.")
        recommendations.append("Re-run with use_vision=True.")
        deductions.append({"name": "regex_only", "points": 25,
                           "reason": "No vision pass was run."})

    bonus_pts = min(sum(b["points"] for b in bonuses), 20)
    deduct_pts = sum(d["points"] for d in deductions)
    score = max(0, min(100, base_score + bonus_pts - deduct_pts))

    if verdict == "CAUTION" and score >= 90:
        verdict = "READY"
        reasons.append("Verdict upgraded from CAUTION to READY: accuracy bonuses compensate for the lbs/SF gap.")
    if verdict == "READY" and score >= 95:
        reasons.append("HIGH_CONFIDENCE_READY: accuracy signals satisfy 95+ threshold.")

    return _finalize(verdict, base_score, bonuses, deductions, reasons,
                     recommendations, exp_low, exp_mid, exp_high, total_tons,
                     lbs_sf, dollars_sf, bench, price_bench, extraction,
                     final_score=score)


def _finalize(verdict, base_score, bonuses, deductions, reasons,
              recommendations, exp_low, exp_mid, exp_high, total_tons,
              lbs_sf, dollars_sf, bench, price_bench, extraction,
              final_score=None):
    if final_score is None:
        bonus_pts = min(sum(b["points"] for b in bonuses), 20)
        deduct_pts = sum(d["points"] for d in deductions)
        final_score = max(0, min(100, base_score + bonus_pts - deduct_pts))
    return {
        "verdict": verdict,
        "score": final_score,
        "base_score": base_score,
        "bonuses": bonuses,
        "deductions": deductions,
        "reasons": reasons,
        "recommendations": recommendations,
        "expected_tons_range": [round(exp_low, 1), round(exp_high, 1)],
        "expected_mid_tons": round(exp_mid, 1),
        "actual_tons": round(total_tons, 2),
        "actual_lbs_sf": round(lbs_sf, 2),
        "actual_dollars_sf": round(dollars_sf, 2),
        "benchmark_lbs_sf": bench,
        "benchmark_dollars_sf": price_bench,
        "extraction_summary": {
            "source": extraction.get("source") or extraction.get("method"),
            "providers": extraction.get("providers"),
            "schedule_match_pct": extraction.get("schedule_match_pct"),
            "coverage_gaps": extraction.get("coverage_gaps"),
            "dedup_collapse_ratio": extraction.get("dedup_collapse_ratio"),
            "avg_confidence": extraction.get("avg_confidence"),
        },
    }


def attach_review(bid: dict) -> dict:
    bid["auto_review"] = auto_review(bid)
    return bid
