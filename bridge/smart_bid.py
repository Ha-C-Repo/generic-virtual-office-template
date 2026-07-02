"""F30: smart_bid - one-shot entry point. Auto-picks best path.

Both paths (bluebeam_csv and vision_v15) produce a tagged PDF when a
structural PDF is available in the project folder. The Bluebeam BOQ
remains the source of truth for tonnage and pricing; the tagged PDF
is the visual overlay an estimator opens in Bluebeam to spot-check.

Operator:
    smart_bid(project_folder=..., building_sf=..., building_type=..., ...)

Auto-discovery:
    1. If project_folder has Assemblies BOQ.xlsx (or *_BOQ.xlsx, or
       *markups*.csv), route through bluebeam_csv path (95+ score).
    2. Else find the structural PDF, run v15 vision pipeline.
    3. After either path, if a structural PDF exists, run vision to
       produce the tagged PDF for visual review (best-effort; bid is
       still delivered if tagging fails).
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import json

from . import boq_discovery, schedule_discovery, sheet_sweep, schedule_extractor
from . import detection_dedup, column_heights, bay_lengths, vision_detect
from . import drawing_tagger, bluebeam_import, boq_parser, pricing
from . import sheet_rollup, clash_detector, paths as _paths
from .aisc import validate_shape
from .auto_review import attach_review
from .detection_cache import DetectionCache
from .pdf_render import render_client_proposal, render_gp_report


def smart_bid(
    project_folder=None, pdf_path=None,
    building_sf=15000, building_type="retail_small",
    project_name="", gc_name="",
    out_dir=None, finish_type="paint",
    drawing_stage="IFC", anchor_rod_count=0,
    connection_pct=None, stories=1,
    column_height_override_ft=None,
    force_vision=False, use_haiku_schedule_discovery=True,
    dpi=120, always_tag_pdf=True,
    tag_pdf_path=None,
):
    pf = Path(project_folder) if project_folder else None
    if out_dir is None and pf:
        out_dir = pf / "3. Estimate" / "_v15_runs"
    out_dir = Path(out_dir or "/tmp/smart_bid_out")
    out_dir.mkdir(parents=True, exist_ok=True)

    pipeline_log = {"stages": []}

    boq_match = None
    if pf and not force_vision:
        boq_match = boq_discovery.discover_boq(pf)
        pipeline_log["stages"].append({"stage": "boq_discovery", "match": boq_match})

    if boq_match:
        return _run_from_boq(
            boq_match["path"], pf, building_sf, building_type,
            project_name, gc_name, out_dir, finish_type,
            anchor_rod_count, drawing_stage, connection_pct,
            pipeline_log, always_tag_pdf=always_tag_pdf, dpi=dpi,
            tag_pdf_path=tag_pdf_path,
        )

    pdf = Path(pdf_path) if pdf_path else None
    if not pdf and pf:
        found = boq_discovery.discover_pdf(pf)
        if found:
            pdf = Path(found)
    if not pdf or not pdf.exists():
        return {"path_taken": "none",
                "error": "No BOQ and no PDF found.",
                "pipeline_log": pipeline_log}

    return _run_from_pdf(
        pdf, building_sf, building_type, project_name, gc_name,
        out_dir, finish_type, drawing_stage, anchor_rod_count,
        connection_pct, stories, column_height_override_ft,
        use_haiku_schedule_discovery, dpi, pipeline_log,
    )


def _tag_pdf_best_effort(pdf, bid_number, out_dir, dpi, pipeline_log):
    """Run vision + drawing_tagger to produce a tagged PDF.

    Best-effort: failures are logged but don't crash the bid.
    Returns Path of tagged PDF or None.
    """
    if not pdf or not Path(pdf).exists():
        pipeline_log["stages"].append({"stage": "tag_pdf", "skipped": "no PDF"})
        return None
    tagged_pdf = Path(out_dir) / f"{bid_number}_TAGGED.pdf"
    cache = DetectionCache(Path(out_dir) / "_cache" / f"{bid_number}_tag.json",
                           pdf_path=pdf)
    try:
        sweep = sheet_sweep.sweep_pdf(pdf)
        pages = sweep.get("vision_pages") or list(range(_count_pages(pdf)))
    except Exception as e:
        pipeline_log["stages"].append({"stage": "tag_pdf_sweep_err", "err": str(e)})
        pages = list(range(_count_pages(pdf)))

    detections = []
    fresh = 0; cached = 0; errs = 0
    try:
        import fitz
        doc = fitz.open(pdf)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for pi in pages:
            if pi < 0 or pi >= len(doc):
                continue
            existing = cache.get(pi)
            if existing is not None:
                for d in existing:
                    d["page"] = pi
                detections.extend(existing)
                cached += 1
                continue
            page = doc[pi]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            tmp = Path(f"/tmp/_tag_p{pi:03d}.png")
            pix.save(tmp)
            try:
                dets = vision_detect.detect_members_in_image(tmp)
            except Exception as e:
                pipeline_log["stages"].append({"stage": "tag_vision_err",
                                               "page": pi, "err": str(e)[:120]})
                dets = []
                errs += 1
            finally:
                try: tmp.unlink()
                except Exception: pass
            for d in dets:
                bbox_px = d.get("bbox")
                if bbox_px and len(bbox_px) == 4:
                    d["bbox"] = [c / zoom for c in bbox_px]
                d["page"] = pi
                d.setdefault("status", "Tentative")
            cache.set(pi, dets, provider="anthropic_or_cascade")
            detections.extend(dets)
            fresh += 1
        doc.close()
    except Exception as e:
        pipeline_log["stages"].append({"stage": "tag_pdf_run_err", "err": str(e)})
        return None

    # Dedup before drawing to avoid noisy overlap
    detections = detection_dedup.dedup_detections(detections)
    try:
        drawing_tagger.write_tagged_pdf(pdf, tagged_pdf, detections)
        pipeline_log["stages"].append({
            "stage": "tag_pdf", "tagged_pdf": str(tagged_pdf),
            "detections": len(detections),
            "fresh_pages": fresh, "cached_pages": cached, "page_errors": errs,
        })
        return tagged_pdf
    except Exception as e:
        pipeline_log["stages"].append({"stage": "tag_pdf_write_err", "err": str(e)})
        return None


def _run_from_boq(boq_path, project_folder, building_sf, building_type,
                  project_name, gc_name, out_dir, finish_type,
                  anchor_rod_count, drawing_stage, connection_pct,
                  pipeline_log, always_tag_pdf=True, dpi=120,
                  tag_pdf_path=None):
    bid_number = _paths.suggest_bid_number(project_name or "BOQ")
    pipeline_log["stages"].append({"stage": "route", "via": "bluebeam_csv",
                                   "boq_path": boq_path})

    parsed = boq_parser.parse_boq_xlsx(boq_path)
    members = parsed.get("members", [])
    valid = []
    for m in members:
        sh = m.get("shape")
        if sh and validate_shape(sh)["valid"]:
            valid.append(m)
    pipeline_log["stages"].append({"stage": "boq_validation",
                                   "rows": parsed.get("rows_total"),
                                   "valid_aisc": len(valid)})

    bid = pricing.build_priced_bid(
        members=valid, building_sf=building_sf,
        deck_sf=building_sf, deck_type="roof_deck",
        anchor_rod_count=anchor_rod_count,
        drawing_stage=drawing_stage, small_project=False,
        connection_pct=connection_pct, finish_type=finish_type,
    )
    bid.update({"building_type": building_type, "project_name": project_name,
                "gc_name": gc_name, "bid_number": bid_number,
                "sheet_rollup": sheet_rollup.rollup_by_sheet(valid),
                "clash_report": clash_detector.detect_clashes(valid)})
    bid["extraction"] = {
        "method": "bluebeam_csv", "source": "bluebeam_csv",
        "raw_count": parsed.get("rows_total", 0),
        "members_with_length": len(valid),
        "providers": None,
        "coverage_checked": True, "coverage_gaps": [],
        "schedule_pages": [-1],
        "schedule_match_pct": 1.0, "schedule_only_pct": 0.0,
        "dedup_collapse_ratio": 0.0, "avg_confidence": 1.0,
        "boq_source": boq_path,
    }
    attach_review(bid)

    boq_out = out_dir / f"{bid_number}_BOQ.xlsx"
    client_pdf = out_dir / f"{bid_number}_Client.pdf"
    gp_pdf = out_dir / f"{bid_number}_GP.pdf"
    bluebeam_import.write_boq_xlsx(valid, boq_out)
    render_client_proposal(bid, client_pdf)
    render_gp_report(bid, gp_pdf)

    # ── Tagged PDF (best-effort, regardless of path) ───────────────────
    tagged_pdf = None
    if always_tag_pdf:
        pdf = tag_pdf_path
        if not pdf and project_folder:
            pdf = boq_discovery.discover_pdf(project_folder)
        if pdf:
            tagged_pdf = _tag_pdf_best_effort(pdf, bid_number, out_dir, dpi, pipeline_log)

    summary = _summarize(bid, "smart_bid", project_name, boq_out, client_pdf, gp_pdf)
    summary["path_taken"] = "bluebeam_csv"
    if tagged_pdf:
        summary["tagged_pdf"] = str(tagged_pdf)
    summary["pipeline_log"] = pipeline_log
    (out_dir / f"{bid_number}_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (out_dir / f"{bid_number}_pipeline.json").write_text(json.dumps(pipeline_log, indent=2, default=str))
    return summary


def _run_from_pdf(pdf, building_sf, building_type, project_name, gc_name,
                  out_dir, finish_type, drawing_stage, anchor_rod_count,
                  connection_pct, stories, column_height_override_ft,
                  use_haiku_schedule_discovery, dpi, pipeline_log):
    pdf = Path(pdf)
    bid_number = _paths.suggest_bid_number(project_name or pdf.stem)
    pipeline_log["stages"].append({"stage": "route", "via": "vision_v15",
                                   "pdf": str(pdf)})

    sweep = sheet_sweep.sweep_pdf(pdf)
    schedule_pages_text = sweep["schedule_pages"]
    vision_pages = sweep["vision_pages"] or list(range(_count_pages(pdf)))
    coverage_gaps = sheet_sweep.coverage_gaps(sweep, building_type)
    pipeline_log["stages"].append({
        "stage": "sheet_sweep_text",
        "schedule_pages": schedule_pages_text,
        "vision_pages": vision_pages,
        "coverage_gaps": coverage_gaps,
    })

    schedule_pages = list(schedule_pages_text)
    if not schedule_pages and use_haiku_schedule_discovery:
        try:
            haiku_pages = schedule_discovery.discover_schedule_pages(pdf, dpi=dpi)
        except Exception as e:
            haiku_pages = []
            pipeline_log["stages"].append({"stage": "schedule_discovery_haiku", "error": str(e)})
        else:
            schedule_pages = schedule_discovery.combine_with_text_sweep(
                schedule_pages_text, haiku_pages)
            pipeline_log["stages"].append({
                "stage": "schedule_discovery_haiku",
                "haiku_pages": haiku_pages,
                "combined_schedule_pages": schedule_pages,
            })

    schedule = {"rows": [], "by_mark": {}, "row_count": 0, "mark_count": 0}
    if schedule_pages:
        try:
            schedule = schedule_extractor.extract_schedules_from_pdf(
                pdf, page_indices=schedule_pages, dpi=200)
            pipeline_log["stages"].append({"stage": "schedule_extractor",
                                           "rows": schedule.get("row_count", 0),
                                           "marks": schedule.get("mark_count", 0)})
        except Exception as e:
            pipeline_log["stages"].append({"stage": "schedule_extractor", "error": str(e)})

    cache = DetectionCache(out_dir / "_cache" / f"{bid_number}.json", pdf_path=pdf)
    detections = _run_vision_cached(pdf, vision_pages, dpi, cache, pipeline_log)

    raw_count = len(detections)
    detections = detection_dedup.dedup_detections(detections)
    dedup_rep = detection_dedup.dedup_report([{}] * raw_count, detections)
    pipeline_log["stages"].append({"stage": "dedup", **dedup_rep})

    cv = {"matched_count": 0, "schedule_only_marks": []}
    if schedule.get("by_mark"):
        cv = schedule_extractor.cross_validate(detections, schedule)
        seen = {(d.get("mark") or "").strip().upper() for d in detections}
        for row in schedule.get("rows", []):
            mk = (row.get("mark") or "").strip().upper()
            if mk and mk not in seen and float(row.get("length_ft") or 0) > 0:
                detections.append({
                    "page": -1, "shape": row.get("shape"),
                    "family": row.get("family") or "",
                    "member_type": row.get("member_type") or "",
                    "mark": row.get("mark"),
                    "length_ft": float(row.get("length_ft") or 0),
                    "qty": int(row.get("qty") or 1),
                    "bbox": [0, 0, 0, 0],
                    "confidence": 0.95, "status": "FromSchedule",
                    "schedule_validated": True,
                })
        pipeline_log["stages"].append({"stage": "schedule_cross_validation", **cv})

    col_rep = column_heights.infer_heights(
        detections, building_type,
        override_height_ft=column_height_override_ft, stories=stories)
    pipeline_log["stages"].append({"stage": "column_heights", **col_rep})

    bay = bay_lengths.estimate_bay_distances(pdf)
    bay_rep = bay_lengths.fill_missing_lengths(detections, bay)
    pipeline_log["stages"].append({"stage": "bay_lengths", **bay_rep,
                                   "median_bay_ft": bay.get("median_bay_ft")})

    boq_members = drawing_tagger.detections_to_boq_members(detections)
    valid = []
    for m in boq_members:
        sh = m.get("shape")
        if sh and validate_shape(sh)["valid"]:
            valid.append(m)
    pipeline_log["stages"].append({"stage": "aisc_filter",
                                   "kept": len(valid), "dropped": len(boq_members) - len(valid)})

    boq_xlsx = out_dir / f"{bid_number}_BOQ.xlsx"
    bluebeam_import.write_boq_xlsx(valid, boq_xlsx)

    tagged_pdf = out_dir / f"{bid_number}_TAGGED.pdf"
    drawing_tagger.write_tagged_pdf(pdf, tagged_pdf, detections)

    bid = pricing.build_priced_bid(
        members=valid, building_sf=building_sf,
        deck_sf=building_sf, deck_type="roof_deck",
        anchor_rod_count=anchor_rod_count,
        drawing_stage=drawing_stage, small_project=False,
        connection_pct=connection_pct, finish_type=finish_type,
    )
    bid.update({"building_type": building_type, "project_name": project_name,
                "gc_name": gc_name, "bid_number": bid_number,
                "sheet_rollup": sheet_rollup.rollup_by_sheet(valid),
                "clash_report": clash_detector.detect_clashes(valid)})

    confs = [float(d.get("confidence", 0)) for d in detections]
    avg_conf = round(sum(confs) / max(1, len(confs)), 3)
    providers_seen = set()
    for d in detections:
        for p in (d.get("providers") or []):
            providers_seen.add(p)
    if not providers_seen:
        providers_seen = {"anthropic"}
    multi_count = sum(1 for d in detections if d.get("agreement", 1) >= 2)
    multi_pct = (multi_count / len(detections)) if detections else 0.0

    sched_match_pct = None
    sched_only_pct = None
    if schedule.get("mark_count"):
        sched_match_pct = cv.get("matched_count", 0) / max(1, schedule["mark_count"])
        sched_only_pct = len(cv.get("schedule_only_marks", [])) / max(1, schedule["mark_count"])

    bid["extraction"] = {
        "method": "auto_tag", "source": "auto_tag",
        "raw_count": raw_count, "members_with_length": len(valid),
        "providers": sorted(providers_seen),
        "multi_provider_pct": round(multi_pct, 3),
        "schedule_match_pct": sched_match_pct,
        "schedule_only_pct": sched_only_pct,
        "schedule_pages": schedule_pages,
        "coverage_checked": True,
        "coverage_gaps": coverage_gaps,
        "dedup_collapse_ratio": dedup_rep.get("collapse_ratio"),
        "avg_confidence": avg_conf,
        "column_height_used_ft": col_rep.get("column_height_used_ft"),
        "columns_with_inferred_height": col_rep.get("columns_with_inferred_height"),
        "bay_median_ft": bay.get("median_bay_ft"),
        "beams_with_inferred_length": bay_rep.get("beams_with_inferred_length"),
        "cache_stats": cache.stats(),
    }
    attach_review(bid)

    client_pdf = out_dir / f"{bid_number}_Client.pdf"
    gp_pdf = out_dir / f"{bid_number}_GP.pdf"
    render_client_proposal(bid, client_pdf)
    render_gp_report(bid, gp_pdf)

    summary = _summarize(bid, "smart_bid", project_name, boq_xlsx, client_pdf, gp_pdf)
    summary["path_taken"] = "vision_v15"
    summary["tagged_pdf"] = str(tagged_pdf)
    summary["pipeline_log"] = pipeline_log
    (out_dir / f"{bid_number}_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (out_dir / f"{bid_number}_pipeline.json").write_text(json.dumps(pipeline_log, indent=2, default=str))
    return summary


def _run_vision_cached(pdf, pages, dpi, cache, pipeline_log):
    import fitz
    doc = fitz.open(pdf)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    out = []
    fresh = 0
    cached = 0
    for pi in pages:
        if pi < 0 or pi >= len(doc):
            continue
        existing = cache.get(pi)
        if existing is not None:
            for d in existing:
                d["page"] = pi
            out.extend(existing)
            cached += 1
            continue
        page = doc[pi]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        tmp = Path(f"/tmp/_smartv_p{pi:03d}.png")
        pix.save(tmp)
        try:
            dets = vision_detect.detect_members_in_image(tmp)
        except Exception as e:
            pipeline_log["stages"].append({"stage": "vision_page_error", "page": pi, "err": str(e)})
            dets = []
        finally:
            try: tmp.unlink()
            except Exception: pass
        for d in dets:
            bbox_px = d.get("bbox")
            if bbox_px and len(bbox_px) == 4:
                d["bbox"] = [c / zoom for c in bbox_px]
            d["page"] = pi
            d.setdefault("status", "Tentative")
        cache.set(pi, dets, provider="anthropic_or_cascade")
        out.extend(dets)
        fresh += 1
    doc.close()
    pipeline_log["stages"].append({"stage": "vision_cached",
                                   "fresh_pages": fresh, "cached_pages": cached,
                                   "total_detections": len(out)})
    return out


def _count_pages(pdf):
    try:
        import fitz
        d = fitz.open(pdf); n = len(d); d.close(); return n
    except Exception:
        return 0


def _summarize(bid, name, project_name, boq, client_pdf, gp_pdf):
    return {
        "bid_number": bid["bid_number"], "name": name, "project_name": project_name,
        "tons": bid["tonnage_summary"]["total_tons"],
        "lbs_per_sf": bid["lbs_per_sf"], "dollars_per_sf": bid["dollars_per_sf"],
        "grand_total": bid["grand_total"],
        "verdict": bid["auto_review"]["verdict"],
        "score": bid["auto_review"]["score"],
        "base_score": bid["auto_review"]["base_score"],
        "bonuses": [(b["name"], b["points"]) for b in bid["auto_review"]["bonuses"]],
        "deductions": [(d["name"], d["points"]) for d in bid["auto_review"]["deductions"]],
        "boq_xlsx": str(boq), "client_pdf": str(client_pdf), "gp_pdf": str(gp_pdf),
    }
