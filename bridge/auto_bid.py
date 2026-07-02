"""F14 + F22: One-shot 'PDF in, bid out' entry point with v15 accuracy stack.

Pipeline order (v15):
    1.  sheet_sweep   - classify all pages, find structural + schedule pages
    2.  schedule_extractor - extract member schedules from schedule pages
    3.  vision_detect (per-page on every structural page found by sweep)
        - optionally with consensus.merge_consensus across providers
    4.  detection_dedup - collapse duplicate detections by IoU + mark
    5.  schedule_extractor.cross_validate - boost confidence on schedule
        matches, fill missing length_ft from schedule
    6.  column_heights.infer_heights - default-height columns with length=0
    7.  bay_lengths.fill_missing_lengths - bay-derive remaining length=0 beams
    8.  drawing_tagger - write tagged PDF
    9.  bluebeam_import.write_boq_xlsx
    10. pricing.build_priced_bid
    11. auto_review with full extraction provenance for scoring bonuses
"""

from __future__ import annotations
from pathlib import Path
import json

from . import (
    vision_detect, drawing_tagger, bluebeam_import, pricing,
    sheet_rollup, clash_detector, detection_dedup, column_heights,
    schedule_extractor, sheet_sweep, bay_lengths, consensus,
)
from . import paths as _paths
from .auto_review import attach_review
from .pdf_render import render_client_proposal, render_gp_report


def auto_bid_from_pdf(
    pdf_path,
    building_sf,
    building_type="retail_small",
    project_name="",
    gc_name="",
    out_dir="/tmp/auto_bid_out",
    finish_type="paint",
    drawing_stage="IFC",
    anchor_rod_count=0,
    connection_pct=None,
    write_review_overlay=True,
    dpi=144,
    use_sheet_sweep=True,
    use_schedule_extractor=True,
    use_consensus=False,
    use_column_height_inference=True,
    use_bay_length_inference=True,
    column_height_override_ft=None,
    stories=1,
):
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bid_number = _paths.suggest_bid_number(project_name or pdf_path.stem)
    pipeline_log = {"bid_number": bid_number, "stages": []}

    if use_sheet_sweep:
        sweep = sheet_sweep.sweep_pdf(pdf_path)
        vision_pages = sweep["vision_pages"] or list(range(min(20, _count_pages(pdf_path))))
        schedule_pages = sweep["schedule_pages"]
        coverage_gaps = sheet_sweep.coverage_gaps(sweep, building_type)
        pipeline_log["stages"].append({
            "stage": "sheet_sweep",
            "vision_pages": vision_pages,
            "schedule_pages": schedule_pages,
            "coverage": sweep["coverage"],
            "coverage_gaps": coverage_gaps,
        })
    else:
        vision_pages = None
        schedule_pages = []
        coverage_gaps = []
        pipeline_log["stages"].append({"stage": "sheet_sweep", "skipped": True})

    schedule = {"rows": [], "by_mark": {}, "row_count": 0, "mark_count": 0}
    if use_schedule_extractor and schedule_pages:
        try:
            schedule = schedule_extractor.extract_schedules_from_pdf(
                pdf_path, page_indices=schedule_pages, dpi=200)
        except Exception as e:
            pipeline_log["stages"].append({"stage": "schedule_extractor", "error": str(e)})
        else:
            pipeline_log["stages"].append({
                "stage": "schedule_extractor",
                "schedule_rows": schedule.get("row_count", 0),
                "schedule_marks": schedule.get("mark_count", 0),
                "pages_scanned": schedule.get("pages_scanned", []),
            })
    else:
        pipeline_log["stages"].append({"stage": "schedule_extractor", "skipped": True})

    detections = _run_vision(pdf_path, vision_pages=vision_pages, dpi=dpi,
                              use_consensus=use_consensus, pipeline_log=pipeline_log)

    raw_count = len(detections)
    detections = detection_dedup.dedup_detections(detections)
    dedup_rep = detection_dedup.dedup_report([{}] * raw_count, detections)
    pipeline_log["stages"].append({"stage": "detection_dedup", **dedup_rep})

    cv = {"matched_count": 0, "plan_only_count": 0, "schedule_only_marks": []}
    if schedule.get("by_mark"):
        cv = schedule_extractor.cross_validate(detections, schedule)
        seen_marks = {(d.get("mark") or "").strip().upper() for d in detections}
        for row in schedule.get("rows", []):
            mk = (row.get("mark") or "").strip().upper()
            if mk and mk not in seen_marks and float(row.get("length_ft") or 0) > 0:
                detections.append({
                    "page": -1, "shape": row.get("shape"),
                    "family": row.get("family") or "",
                    "member_type": row.get("member_type") or "",
                    "mark": row.get("mark"),
                    "length_ft": float(row.get("length_ft") or 0),
                    "qty": int(row.get("qty") or 1),
                    "bbox": [0, 0, 0, 0],
                    "confidence": 0.95,
                    "status": "FromSchedule",
                    "schedule_validated": True,
                })
        pipeline_log["stages"].append({"stage": "schedule_cross_validation", **cv})

    col_rep = {}
    if use_column_height_inference:
        col_rep = column_heights.infer_heights(
            detections, building_type,
            override_height_ft=column_height_override_ft, stories=stories)
        pipeline_log["stages"].append({"stage": "column_height_inference", **col_rep})

    bay_rep = {}
    if use_bay_length_inference:
        bay_summary = bay_lengths.estimate_bay_distances(pdf_path)
        bay_rep = bay_lengths.fill_missing_lengths(detections, bay_summary)
        bay_rep["bay_summary"] = {k: v for k, v in bay_summary.items() if k != "by_page"}
        pipeline_log["stages"].append({"stage": "bay_length_inference", **bay_rep})

    tagged_pdf = out_dir / f"{bid_number}_TAGGED.pdf"
    drawing_tagger.write_tagged_pdf(pdf_path, tagged_pdf, detections)

    overlay_pngs = []
    if write_review_overlay and detections:
        overlay_pngs = drawing_tagger.write_review_overlay(
            tagged_pdf, out_dir / f"{bid_number}_review", detections, dpi=dpi)

    boq_members = drawing_tagger.detections_to_boq_members(detections)
    boq_xlsx = out_dir / f"{bid_number}_BOQ.xlsx"
    bluebeam_import.write_boq_xlsx(boq_members, boq_xlsx)

    bid = pricing.build_priced_bid(
        members=boq_members, building_sf=building_sf,
        deck_sf=building_sf, deck_type="roof_deck",
        anchor_rod_count=anchor_rod_count,
        drawing_stage=drawing_stage, small_project=False,
        connection_pct=connection_pct, finish_type=finish_type,
    )
    bid["building_type"] = building_type
    bid["project_name"] = project_name
    bid["gc_name"] = gc_name
    bid["bid_number"] = bid_number
    bid["sheet_rollup"] = sheet_rollup.rollup_by_sheet(boq_members)
    bid["clash_report"] = clash_detector.detect_clashes(boq_members)

    confs = [float(d.get("confidence") or 0.0) for d in detections]
    avg_conf = round(sum(confs) / len(confs), 3) if confs else 0.0
    providers_seen = set()
    multi_count = 0
    for d in detections:
        for p in (d.get("providers") or []):
            providers_seen.add(p)
        if d.get("agreement", 1) >= 2:
            multi_count += 1
    multi_pct = (multi_count / len(detections)) if detections else 0.0
    sched_only_pct = (
        len(cv.get("schedule_only_marks") or []) /
        max(1, schedule.get("mark_count", 0))
    ) if schedule.get("mark_count") else None
    match_pct = (cv.get("matched_count", 0) / max(1, len(detections))) if detections else None

    bid["extraction"] = {
        "method": "auto_tag",
        "source": "auto_tag",
        "raw_count": raw_count,
        "members_with_length": len(boq_members),
        "valid_count": len(boq_members),
        "low_confidence_count": sum(1 for d in detections if float(d.get("confidence") or 1.0) < 0.7),
        "pdf_path": str(pdf_path),
        "tagged_pdf": str(tagged_pdf),
        "review_overlay_pages": [str(p) for p in overlay_pngs],
        "providers": sorted(providers_seen) if providers_seen else None,
        "multi_provider_pct": round(multi_pct, 3) if providers_seen else None,
        "schedule_match_pct": match_pct,
        "schedule_only_pct": sched_only_pct,
        "schedule_pages": schedule_pages,
        "coverage_checked": use_sheet_sweep,
        "coverage_gaps": coverage_gaps,
        "dedup_collapse_ratio": dedup_rep.get("collapse_ratio"),
        "avg_confidence": avg_conf,
        "column_height_used_ft": col_rep.get("column_height_used_ft"),
        "columns_with_inferred_height": col_rep.get("columns_with_inferred_height"),
        "bay_median_ft": (bay_rep.get("bay_summary") or {}).get("median_bay_ft"),
        "beams_with_inferred_length": bay_rep.get("beams_with_inferred_length"),
    }
    attach_review(bid)

    client_pdf = out_dir / f"{bid_number}_Client.pdf"
    gp_pdf = out_dir / f"{bid_number}_GP.pdf"
    render_client_proposal(bid, client_pdf)
    render_gp_report(bid, gp_pdf)

    summary = {
        "bid_number": bid_number, "project_name": project_name, "gc_name": gc_name,
        "input_pdf": str(pdf_path), "tagged_pdf": str(tagged_pdf),
        "boq_xlsx": str(boq_xlsx), "client_pdf": str(client_pdf), "gp_pdf": str(gp_pdf),
        "review_overlays": [str(p) for p in overlay_pngs],
        "detection_count": len(detections), "priced_member_count": len(boq_members),
        "total_tons": bid.get("tonnage_summary", {}).get("total_tons", 0),
        "grand_total": bid.get("grand_total", 0),
        "verdict": bid.get("auto_review", {}).get("verdict"),
        "score": bid.get("auto_review", {}).get("score"),
    }
    (out_dir / f"{bid_number}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / f"{bid_number}_v15_pipeline.json").write_text(
        json.dumps(pipeline_log, indent=2, default=str), encoding="utf-8")
    return summary


def _count_pages(pdf_path):
    try:
        import fitz
        doc = fitz.open(pdf_path); n = len(doc); doc.close(); return n
    except Exception:
        return 0


def _run_vision(pdf_path, vision_pages, dpi, use_consensus, pipeline_log):
    detections = []
    if not use_consensus:
        if vision_pages is None:
            detections = vision_detect.detect_members_in_pdf(pdf_path, dpi=dpi)
        else:
            detections = _run_vision_on_pages(pdf_path, vision_pages, dpi)
        pipeline_log["stages"].append({
            "stage": "vision_detect", "mode": "cascade",
            "pages": vision_pages, "detections": len(detections),
        })
        return detections

    import fitz, os
    have_gem = bool(os.environ.get("GEMINI_API_KEY"))
    have_ant = bool(os.environ.get("ANTHROPIC_API_KEY"))
    have_oai = bool(os.environ.get("OPENAI_API_KEY"))
    pages_to_scan = vision_pages or list(range(_count_pages(pdf_path)))

    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    all_merged = []
    per_page_log = []

    for pi in pages_to_scan:
        if pi < 0 or pi >= len(doc):
            continue
        page = doc[pi]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        tmp = Path(f"/tmp/_consensus_p{pi:03d}.png")
        pix.save(tmp)
        try:
            pr_results = []; pr_names = []
            if have_gem:
                try:
                    pr_results.append(vision_detect._call_gemini(tmp)); pr_names.append("gemini")
                except Exception as e:
                    per_page_log.append({"page": pi, "gemini_err": str(e)})
            if have_ant:
                try:
                    pr_results.append(vision_detect._call_anthropic(tmp)); pr_names.append("anthropic")
                except Exception as e:
                    per_page_log.append({"page": pi, "anthropic_err": str(e)})
            if have_oai:
                try:
                    pr_results.append(vision_detect._call_openai(tmp)); pr_names.append("openai")
                except Exception as e:
                    per_page_log.append({"page": pi, "openai_err": str(e)})
        finally:
            try: tmp.unlink()
            except Exception: pass

        for pr in pr_results:
            for d in pr:
                bbox_px = d.get("bbox")
                if bbox_px and len(bbox_px) == 4:
                    d["bbox"] = [c / zoom for c in bbox_px]
                d["page"] = pi
                d.setdefault("status", "Tentative")
        merged = consensus.merge_consensus(pr_results, pr_names)
        all_merged.extend(merged)

    doc.close()
    pipeline_log["stages"].append({
        "stage": "vision_detect", "mode": "consensus",
        "providers_attempted": [p for p, ok in
            [("gemini", have_gem), ("anthropic", have_ant), ("openai", have_oai)] if ok],
        "pages": pages_to_scan, "merged_count": len(all_merged),
        "per_page_errors": per_page_log,
    })
    return all_merged


def _run_vision_on_pages(pdf_path, page_indices, dpi):
    import fitz
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    out = []
    for pi in page_indices:
        if pi < 0 or pi >= len(doc):
            continue
        page = doc[pi]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        tmp = Path(f"/tmp/_vision_p{pi:03d}.png")
        pix.save(tmp)
        try:
            dets = vision_detect.detect_members_in_image(tmp)
        finally:
            try: tmp.unlink()
            except Exception: pass
        for d in dets:
            bbox_px = d.get("bbox")
            if bbox_px and len(bbox_px) == 4:
                d["bbox"] = [c / zoom for c in bbox_px]
            d["page"] = pi
            d.setdefault("status", "Tentative")
            out.append(d)
    doc.close()
    return out
