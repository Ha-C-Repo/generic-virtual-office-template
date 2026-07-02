"""PDF outputs. ReportLab, YOUR COMPANY brand: dark header with the approved
silver-on-dark logo, red accent, Helvetica. No em-dashes in any output. No
supplier names ever appear in these documents."""

import os
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer, Image)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader

from . import config, db, COMPANY, COMPANY_ADDRESS, COMPANY_PHONE

DARK = colors.HexColor("#141414")
# Header band matches the silver-on-dark master's own plate color so the approved
# lockup sits seamlessly with no visible box. Changing the background to suit the
# logo is the one permitted action under the Tier 1 logo rules; the mark itself is
# never altered. #231F20 is the master's plate (sampled), a near-black a hair
# warmer than the #141414 body dark and visually indistinguishable from it.
BAND_DARK = colors.HexColor("#231F20")
RED = colors.HexColor("#C8102E")
GREY = colors.HexColor("#666666")

_styles = getSampleStyleSheet()
H_TITLE = ParagraphStyle("h", parent=_styles["Title"], fontName="Helvetica-Bold",
                         fontSize=16, textColor=colors.white, alignment=0)
BODY = ParagraphStyle("b", parent=_styles["Normal"], fontName="Helvetica", fontSize=9)
SMALL = ParagraphStyle("s", parent=_styles["Normal"], fontName="Helvetica",
                       fontSize=7, textColor=GREY)

# Approved Tier 1 masters, bundled under ShopQC/brand/logos and resolved through
# resource_path so they load in the frozen EXE. The silver-on-dark lockup goes on
# the dark header band; the black-on-transparent mark is kept for any future
# light-background placement. The marks are used as-is, never recreated, stretched,
# skewed, recolored, or outlined (brand/LOGO_RULES.md).
LOGO_DARK = os.path.join("brand", "logos", "Your Company LLC.png")
LOGO_LIGHT = os.path.join("brand", "logos", "your company.png")


def _rget(row, key, default=""):
    """Safe cell read from a sqlite Row or dict; missing or NULL -> default. Lets
    a report render rows from a pre-migration DB or a partial dict without error."""
    try:
        v = row[key]
    except (KeyError, IndexError):
        return default
    return default if v is None else v


def _num(v):
    """Format a stored REAL for a table cell: 50.0 -> '50', 0.43 -> '0.43',
    blank stays blank."""
    if v is None or v == "":
        return ""
    try:
        f = float(v)
    except (ValueError, TypeError):
        return str(v)
    return str(int(f)) if f == int(f) else str(f)


def _doc(path, title):
    return SimpleDocTemplate(path, pagesize=letter, title=title,
                             leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                             topMargin=0.5 * inch, bottomMargin=0.5 * inch)


def _logo(rel, height):
    """The approved mark scaled to `height` with its aspect ratio preserved
    (never stretched or skewed). Returns None if the bundled file cannot be read,
    so a PDF still builds rather than crash the shop floor."""
    try:
        path = config.resource_path(rel)
        iw, ih = ImageReader(path).getSize()
        return Image(path, width=height * (iw / ih), height=height)
    except Exception:
        return None


def _header(title, sub=""):
    # Dark band: silver-on-dark logo at the left, document title to its right, red
    # accent rule beneath. The logo carries the wordmark, so the legal name sits in
    # the small line below instead of being repeated in the band.
    logo = _logo(LOGO_DARK, 0.5 * inch)
    title_para = Paragraph(title, H_TITLE)
    if logo is not None:
        row, widths = [[logo, title_para]], [2.3 * inch, 5.0 * inch]
    else:
        row, widths = [[title_para]], [7.3 * inch]
    t = Table(row, colWidths=widths, rowHeights=[0.75 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BAND_DARK),
        ("LINEBELOW", (0, 0), (-1, -1), 3, RED),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    parts = [t, Spacer(1, 4),
             Paragraph(f"{COMPANY} | {COMPANY_ADDRESS} | {COMPANY_PHONE}"
                       + (f" | {sub}" if sub else ""), SMALL),
             Spacer(1, 10)]
    return parts


def _grid(data, widths, header_row=True):
    t = Table(data, colWidths=widths, repeatRows=1 if header_row else 0)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header_row:
        style += [("BACKGROUND", (0, 0), (-1, 0), DARK),
                  ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    t.setStyle(TableStyle(style))
    return t


def _sig_block(rows):
    """rows: list of (label, name, date)."""
    data = [["", "Name", "Date"]] + [[lab, nm or "", dt or ""] for lab, nm, dt in rows]
    return _grid(data, [2.4 * inch, 3.0 * inch, 1.9 * inch])


def rir_pdf(path, project, rir_row, bol_rows):
    doc = _doc(path, "Receiving Inspection Record")
    el = _header("RECEIVING INSPECTION RECORD (RIR)",
                 "NC-QC-FAB-001 Sections 4.1 / 4.2 - AISC 207-25")
    el.append(Paragraph(
        f"<b>Project:</b> {project['name']} | <b>Job No.:</b> {project['job_number']} "
        f"| <b>Lot:</b> {rir_row['lot_number'] or 'N/A'}", BODY))
    el.append(Spacer(1, 8))
    data = [["#", "Section", "Grade", "Heat No.", "Fy", "Fu", "CE", "Qty", "MTR"]]
    for b in bol_rows:
        data.append([_rget(b, "line_number"), _rget(b, "section"),
                     _rget(b, "astm_grade"), _rget(b, "heat_number"),
                     _num(_rget(b, "fy", None)), _num(_rget(b, "fu", None)),
                     _num(_rget(b, "ce", None)), _rget(b, "quantity_received"),
                     "YES" if _rget(b, "mtr_verified") else "NO"])
    el.append(_grid(data, [0.35 * inch, 1.4 * inch, 1.0 * inch, 1.3 * inch,
                           0.55 * inch, 0.55 * inch, 0.6 * inch, 0.55 * inch,
                           0.5 * inch]))
    el.append(Spacer(1, 10))
    checks = json.loads(rir_row["all_checks_json"])
    cdata = [["Check", "Result"]] + [[k, "PASS" if v else "FAIL"]
                                     for k, v in checks.items()]
    el.append(_grid(cdata, [5.3 * inch, 1.7 * inch]))
    el.append(Spacer(1, 14))
    el.append(_sig_block([("Receiving Inspector", rir_row["signed_by"],
                           rir_row["signed_date"])]))
    doc.build(el)
    return path


def _piece_variant(piece):
    """Read the traveler variant off a piece row or dict, defaulting to
    STRUCTURAL so legacy rows and partial dicts still render."""
    try:
        return piece["traveler_type"] or "STRUCTURAL"
    except (KeyError, IndexError):
        return "STRUCTURAL"


def _traveler_cell_value(row, ncr_field, ncr_numbers):
    """Value to print for a traveler row. The NCR-list substitution must land on
    the variant's NCR field (18 structural, 20 joist), never a literal: on the
    joist traveler field 18 is the CWI Final-Release row, so a hardcoded 18 would
    overwrite a Gate 3 release cell with NCR ids. Every other row prints its own
    stored value."""
    if row["field_number"] == ncr_field and ncr_numbers:
        return ", ".join(str(n) for n in ncr_numbers)
    return row["value"] or ""


def traveler_pdf(path, project, piece, t_rows, ncr_numbers):
    doc = _doc(path, "Piece Traveler")
    joist = _piece_variant(piece) == "JOIST"
    sub = "NC-QC-FAB-001 Section 8" + (
        " + SJI Spec 100-2020 (joist variant)" if joist else "")
    el = _header("PIECE TRAVELER", sub)
    el.append(Paragraph(
        f"<b>Piece:</b> {piece['piece_id']} | <b>Section:</b> {piece['section']} "
        f"| <b>Variant:</b> {'JOIST (SJI)' if joist else 'STRUCTURAL'} "
        f"| <b>Heat:</b> {piece['heat_number'] or 'N/A'} "
        f"| <b>Status:</b> {piece['status']}", BODY))
    el.append(Spacer(1, 8))
    ncr_field = db.spec_meta(_piece_variant(piece))["ncr_auto"]
    data = [["#", "Field", "Value / Result", "Signed By", "Date"]]
    for r in t_rows:
        data.append([r["field_number"], r["field_name"],
                     _traveler_cell_value(r, ncr_field, ncr_numbers),
                     r["signed_by"] or "", (r["timestamp"] or "")[:10]])
    el.append(_grid(data, [0.35 * inch, 2.5 * inch, 2.2 * inch,
                           1.35 * inch, 0.9 * inch]))
    doc.build(el)
    return path


def ncr_pdf(path, rows, title="NONCONFORMANCE REPORT LOG"):
    doc = _doc(path, "NCR Log")
    el = _header(title, "NC-QC-FAB-001 Section 9")
    data = [["NCR", "Piece", "Gate", "Category", "Description", "Status",
             "Disposition", "Closed By"]]
    for r in rows:
        data.append([r["id"], r["piece_id"] or "(lot)", r["gate"], r["category"],
                     Paragraph(r["description"][:300], BODY), r["status"],
                     r["disposition"] or "", r["closed_by"] or ""])
    el.append(_grid(data, [0.4 * inch, 1.15 * inch, 0.4 * inch, 1.15 * inch,
                           2.0 * inch, 0.75 * inch, 0.75 * inch, 0.7 * inch]))
    doc.build(el)
    return path


def release_cert_pdf(path, project, piece, rel):
    doc = _doc(path, "Final Release Certificate")
    el = _header("FINAL RELEASE CERTIFICATE",
                 "NC-QC-FAB-001 Gate 3 - AISC 207-25")
    el.append(Spacer(1, 6))
    variant = ("joist (SJI Spec 100-2020)" if _piece_variant(piece) == "JOIST"
               else "structural")
    el.append(Paragraph(
        f"This certifies that piece <b>{piece['piece_id']}</b> "
        f"({piece['section']}, Heat {piece['heat_number'] or 'N/A'}) for project "
        f"<b>{project['name']}</b> (Job {project['job_number']}) has completed all "
        f"three quality gates of NC-QC-FAB-001 Rev 0 on the {variant} traveler. "
        f"All required traveler fields are signed and zero nonconformances remain "
        f"open on this piece.", BODY))
    el.append(Spacer(1, 16))
    sigs = [("Shop Director", rel["shop_director_sign"], rel["release_date"]),
            ("CWI", rel["cwi_sign"], rel["release_date"])]
    if rel["ceo_sign"]:
        sigs.append(("CEO (>=50T / IAS)", rel["ceo_sign"], rel["release_date"]))
    el.append(_sig_block(sigs))
    doc.build(el)
    return path


def manifest_pdf(path, project, truck_ref, pieces):
    doc = _doc(path, "Shipping Manifest")
    el = _header("SHIPPING MANIFEST", f"Truck / Load: {truck_ref}")
    el.append(Paragraph(
        f"<b>Project:</b> {project['name']} | <b>Job No.:</b> "
        f"{project['job_number']} | <b>Pieces:</b> {len(pieces)}", BODY))
    el.append(Spacer(1, 8))
    data = [["Piece ID", "Section", "Heat No.", "Released"]]
    for p in pieces:
        data.append([p["piece_id"], p["section"], p["heat_number"] or "",
                     p["release_date"] or ""])
    el.append(_grid(data, [2.3 * inch, 1.9 * inch, 1.6 * inch, 1.5 * inch]))
    doc.build(el)
    return path


def project_summary_pdf(path, project, counts, open_ncrs):
    doc = _doc(path, "Project Summary")
    el = _header("PROJECT QC SUMMARY", f"Job {project['job_number']}")
    data = [["Metric", "Count"],
            ["Pieces received", counts.get("RECEIVED", 0)],
            ["Pieces in fabrication", counts.get("IN_FAB", 0)],
            ["Pieces on NCR hold", counts.get("NCR_HOLD", 0)],
            ["Pieces released", counts.get("RELEASED", 0)],
            ["Pieces shipped", counts.get("SHIPPED", 0)],
            ["Open NCRs", open_ncrs]]
    el.append(_grid(data, [4.5 * inch, 2.5 * inch]))
    doc.build(el)
    return path
