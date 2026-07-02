"""Variation Prover - evidence package PDF for drawing/spec conflicts (Phase 5).

Accepts a conflict_id and supporting data, reads the visual_diff manifest and
spec_auditor flags, and produces a ReportLab PDF evidence package.

Document number format: NC-YYYY-PROJ-NNN-VAR
  NC   - Your Company prefix
  YYYY - four-digit year
  PROJ - first six chars of bid_number, uppercased
  NNN  - conflict sequence padded to 3 digits (extracted from conflict_id)
  VAR  - literal suffix

Voice rules: zero em-dashes. Hyphens or periods only.
No supplier names. No past client references.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


# ── Document number ────────────────────────────────────────────────────────────

def _make_doc_number(bid_number: str, conflict_id: str) -> str:
    """Return NC-YYYY-PROJ-NNN-VAR formatted doc number."""
    year = datetime.now(timezone.utc).strftime("%Y")
    proj = re.sub(r"[^A-Z0-9]", "", bid_number.upper())[:6] or "PROJ"
    # Extract trailing digits from conflict_id for sequence number
    digits = re.findall(r"\d+", conflict_id)
    seq = digits[-1].zfill(3) if digits else "001"
    return f"NC-{year}-{proj}-{seq}-VAR"


# ── Manifest reader ────────────────────────────────────────────────────────────

def _load_manifest(ghost_overlay_path: str) -> dict:
    """Load _manifest.json written by visual_diff.ghost_overlay()."""
    if not ghost_overlay_path:
        return {}
    p = Path(ghost_overlay_path)
    manifest_path = p.parent / (p.stem + "_manifest.json")
    if not manifest_path.exists():
        log.warning("variation_prover: manifest not found at %s", manifest_path)
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("variation_prover: could not load manifest: %s", e)
        return {}


# ── PDF builder ───────────────────────────────────────────────────────────────

def _navy():
    return colors.HexColor("#1B2A4A")


def _gold():
    return colors.HexColor("#C8A951")


def _build_pdf(
    doc_number: str,
    conflict_id: str,
    project_name: str,
    bid_number: str,
    location: str,
    member_before: str,
    member_after: str,
    cost_delta_usd: float,
    spec_flags: list,
    manifest: dict,
    output_path: Path,
) -> None:
    """Generate the evidence package PDF using ReportLab."""
    styles = getSampleStyleSheet()

    heading_style = ParagraphStyle(
        "NCHeading",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=_navy(),
        spaceAfter=6,
    )
    subheading_style = ParagraphStyle(
        "NCSubheading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=_navy(),
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "NCBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=14,
        spaceAfter=4,
    )
    small_style = ParagraphStyle(
        "NCSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#555555"),
    )
    label_style = ParagraphStyle(
        "NCLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
    )

    story = []
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Header ──
    story.append(Paragraph("YOUR COMPANY, LLC", heading_style))
    story.append(Paragraph("Variation Evidence Package", subheading_style))
    story.append(HRFlowable(width="100%", thickness=2, color=_gold(), spaceAfter=8))

    # ── Document metadata table ──
    meta_data = [
        ["Document No.", doc_number],
        ["Conflict ID", conflict_id],
        ["Project", project_name],
        ["Bid No.", bid_number],
        ["Location", location or "Not specified"],
        ["Generated", now_str],
    ]
    meta_table = Table(meta_data, colWidths=[1.5 * inch, 5 * inch])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), _navy()),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # ── Section 1: Member Change Summary ──
    story.append(Paragraph("1. Member Change Summary", subheading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=_navy(), spaceAfter=6))

    member_data = [
        ["", "Designation"],
        ["Before (Rev 0)", member_before or "Not specified"],
        ["After (Rev 1)", member_after or "Not specified"],
    ]
    member_table = Table(member_data, colWidths=[2 * inch, 4.5 * inch])
    member_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), _navy()),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#FFE8E8")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#E8FFE8")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(member_table)
    story.append(Spacer(1, 8))

    if cost_delta_usd:
        sign = "+" if cost_delta_usd > 0 else ""
        story.append(Paragraph(
            f"<b>Estimated cost impact:</b> {sign}${cost_delta_usd:,.0f}",
            body_style,
        ))
    story.append(Spacer(1, 10))

    # ── Section 2: Visual Diff Evidence ──
    story.append(Paragraph("2. Visual Diff Evidence", subheading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=_navy(), spaceAfter=6))

    if manifest:
        change_pct = manifest.get("change_pct", 0.0)
        changed_px = manifest.get("changed_pixels", 0)
        total_px = manifest.get("total_pixels", 0)
        page = manifest.get("page_num", 0) + 1
        story.append(Paragraph(
            f"Page {page} pixel analysis: {change_pct}% of pixels changed "
            f"({changed_px:,} of {total_px:,} total).",
            body_style,
        ))

        member_tags = manifest.get("member_tags", {})
        added = member_tags.get("added", [])
        removed = member_tags.get("removed", [])

        if added or removed:
            story.append(Spacer(1, 4))
            story.append(Paragraph("<b>Semantic member-level changes:</b>", body_style))
            for tag in added:
                story.append(Paragraph(f"  + {tag}", body_style))
            for tag in removed:
                story.append(Paragraph(f"  - {tag}", body_style))
    else:
        story.append(Paragraph(
            "No visual diff manifest available. Run ghost_overlay() first to generate overlay "
            "PNG and manifest JSON.",
            body_style,
        ))
    story.append(Spacer(1, 10))

    # ── Section 3: Specification Flags ──
    story.append(Paragraph("3. Specification Flags", subheading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=_navy(), spaceAfter=6))

    if spec_flags:
        flag_data = [["Flag", "Severity", "Impact"]]
        for f in spec_flags:
            flag_id = f.get("id") or f.get("flag", "")
            severity = f.get("severity", "")
            impact = f.get("impact") or f.get("impact_desc", "")
            flag_data.append([flag_id, severity, impact])

        flag_table = Table(flag_data, colWidths=[1.6 * inch, 0.8 * inch, 4.1 * inch])
        row_styles = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), _navy()),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
            ("WORDWRAP", (2, 1), (2, -1), "LTR"),
        ]
        # Highlight RED rows
        for i, f in enumerate(spec_flags, start=1):
            if f.get("severity") == "RED":
                row_styles.append(
                    ("BACKGROUND", (1, i), (1, i), colors.HexColor("#FFCCCC"))
                )
        flag_table.setStyle(TableStyle(row_styles))
        story.append(flag_table)
    else:
        story.append(Paragraph("No specification flags provided.", body_style))
    story.append(Spacer(1, 10))

    # ── Section 4: Conflict Classification ──
    story.append(Paragraph("4. Conflict Classification", subheading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=_navy(), spaceAfter=6))

    # Classify conflict type from conflict_id
    conflict_lower = conflict_id.lower()
    if "kzone" in conflict_lower or "k-zone" in conflict_lower or "k zone" in conflict_lower:
        conflict_type = "K-Zone"
        classification_note = (
            "K-Zone conflict: connection geometry has changed. "
            "Verify bolt pattern and cope dimensions match revised member."
        )
    elif "deck" in conflict_lower:
        conflict_type = "Deck Mismatch"
        classification_note = (
            "Deck mismatch: roof or floor deck specification conflicts with structural drawings. "
            "Confirm gauge, span rating, and attachment requirements."
        )
    elif "member" in conflict_lower or "shape" in conflict_lower:
        conflict_type = "Member Change"
        classification_note = (
            "Member section change detected. Verify capacity, connection reuse, "
            "and weight impact on erection and foundation loads."
        )
    else:
        conflict_type = "General Variation"
        classification_note = (
            "Review conflict against current issued-for-construction drawings "
            "and applicable specification sections."
        )

    story.append(Paragraph(f"<b>Type:</b> {conflict_type}", body_style))
    story.append(Paragraph(classification_note, body_style))
    story.append(Spacer(1, 10))

    # ── Section 5: Required Actions ──
    story.append(Paragraph("5. Required Actions", subheading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=_navy(), spaceAfter=6))

    actions = [
        "Confirm revised member designation with engineer of record before fabrication.",
        "Update Tekla model and issue revised shop drawings.",
        "Notify project manager of cost impact and schedule effect.",
        "Retain this document in the project file per Your Company document control procedure.",
    ]
    for i, action in enumerate(actions, start=1):
        story.append(Paragraph(f"{i}. {action}", body_style))
    story.append(Spacer(1, 14))

    # ── Footer ──
    story.append(HRFlowable(width="100%", thickness=1, color=_gold(), spaceAfter=4))
    story.append(Paragraph(
        "Your Company, LLC  |  [COMPANY ADDRESS], Houston TX 77064  "
        "|  [COMPANY PHONE]",
        small_style,
    ))
    story.append(Paragraph(
        f"Document {doc_number}  |  Generated {now_str}  "
        "|  Internal use - not for distribution to owner or GC",
        small_style,
    ))

    doc.build(story)


# ── Public API ─────────────────────────────────────────────────────────────────

def prove_variation(
    conflict_id: str,
    project_name: str = "",
    bid_number: str = "",
    member_before: str = "",
    member_after: str = "",
    spec_flags: list | None = None,
    ghost_overlay_path: str = "",
    cost_delta_usd: float = 0.0,
    location: str = "",
    output_dir: str = "",
) -> dict:
    """Generate a variation evidence package PDF.

    Returns:
        {"success": bool, "pdf_path": str, "doc_number": str, "manifest_loaded": bool}
    """
    if not HAS_REPORTLAB:
        return {"success": False, "error": "reportlab not installed",
                "pdf_path": "", "doc_number": ""}

    if not conflict_id:
        return {"success": False, "error": "conflict_id is required",
                "pdf_path": "", "doc_number": ""}

    doc_number = _make_doc_number(bid_number or "PROJ", conflict_id)
    manifest = _load_manifest(ghost_overlay_path)
    flags = spec_flags or []

    # Resolve output directory
    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = Path(".") / "data" / "variation_packages"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Filename: doc number with hyphens replaced to be filesystem-safe
    safe_name = doc_number.replace(" ", "_") + ".pdf"
    output_path = out_dir / safe_name

    try:
        _build_pdf(
            doc_number=doc_number,
            conflict_id=conflict_id,
            project_name=project_name,
            bid_number=bid_number,
            location=location,
            member_before=member_before,
            member_after=member_after,
            cost_delta_usd=cost_delta_usd,
            spec_flags=flags,
            manifest=manifest,
            output_path=output_path,
        )
        log.info("prove_variation: wrote %s", output_path)
        return {
            "success": True,
            "pdf_path": str(output_path),
            "doc_number": doc_number,
            "manifest_loaded": bool(manifest),
        }
    except Exception as e:
        log.error("prove_variation: PDF build failed: %s", e)
        return {"success": False, "error": str(e), "pdf_path": "", "doc_number": doc_number}
