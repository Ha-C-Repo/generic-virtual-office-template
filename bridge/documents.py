"""
Your Company Virtual Office - Document Generation

PDF generators for:
1. Bid Proposal - letterhead, scope, rate table, terms, signature
2. Change Order - project info, change desc, cost impact, signatures

Uses reportlab. Falls back to text export if reportlab unavailable.
"""
import sys
from datetime import date
from pathlib import Path
from bridge.bid_rates import BID_RATES


def _get_output_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "output"
    return Path(__file__).resolve().parent.parent / "output"


_OUT = _get_output_dir()

# Company info (from knowledge base)
COMPANY = {
    "name": "Your Company LLC",
    "address": "[COMPANY ADDRESS], Houston TX 77064",
    "phone": "[COMPANY PHONE]",
    "email": "owner@yourcompany.example.com",
    "isn": "ISN: [ISN ID]",
}

def _get_rates_table() -> dict:
    """Build rate display table from CEO-locked BID_RATES. Never hardcode rates here."""
    return {
        "Structural Steel Fabrication": f"${BID_RATES['fab_per_ton']:,.0f}/ton",
        "Structural Steel Erection":    f"${BID_RATES['erection_per_ton']:,.0f}/ton",
        "Steel Joists (SJI)":           f"${BID_RATES['joists_per_ton']:,.0f}/ton",
        "Roof Deck (1.5B22 Galv)":      f"${BID_RATES['roof_deck_per_sf']:.2f}/SF",
        "Composite Deck (0.6C22)":      f"${BID_RATES['composite_deck_per_sf']:.2f}/SF",
        'Anchor Rods (1"x20")':         f"${int(BID_RATES['anchor_rod_1x20_each'])}/EA",
        "G&A":                          f"{BID_RATES['ga_overhead_pct']*100:.1f}%",
    }

# ═══════════════════════════════════════════════════════════════
# YOUR COMPANY BID RULES - from the Owner's locked business rules
# These are NON-NEGOTIABLE and appear on every proposal.
# ═══════════════════════════════════════════════════════════════

PAYMENT_TERMS = (
    "30% Mobilization - upon approval of shop drawings\n"
    "20% First Delivery - upon first fabricated delivery to site\n"
    "50% Schedule of Values - per AIA G702/G703 through completion"
)

STANDARD_EXCLUSIONS = [
    # ── SCOPE BOUNDARY (AISC Code of Standard Practice §2.1) ──
    "Cold-formed metal framing (CFMF) - CSI 05 4000, by Others",
    "Miscellaneous metals, handrails, ladders, platforms - unless specifically listed in scope",
    "Non-ferrous metals; metal stud framing, purlins, and bracing not shown on S-series drawings",
    # ── COATINGS & FIRE PROTECTION ──
    "Fireproofing / SFRM / intumescent coatings - by Others",
    "Touch-up painting / finish painting / architectural top-coat - by Others",
    "Field painting and primer touch-up after other trades damage shop primer",
    # ── EMBEDS & CONNECTIONS ──
    # BUGFIX 2026-05-21: removed self-contradicting "anchor rods... furnished only
    # for GC placement" - anchor rods ARE in Your Company scope per unit rates.
    # Removed "Engineered connections" line - engineering is folded into fab and
    # erection rates per hard rule, never line-itemed as an exclusion.
    "Embed plates, leveling plates - by Others (furnished for GC placement only when shown on S-series)",
    "Bolts not through structural-steel members (MEP, wood, deck closure attachments)",
    "Holes through members for rebar, MEP penetrations, or items not on structural drawings",
    "Field welding of reinforcing bars to structural steel",
    # ── SITE / GENERAL CONDITIONS ──
    "Shoring, temporary bracing beyond OSHA-required erection bracing",
    "Crane path / road preparation, site access, overhead obstruction removal - by GC",
    "Overhead protection, perimeter screens, sidewalk/street barricades, hoisting for other trades",
    "Concrete, grout, embeds, foundations - by Others",
    # ── INSPECTION & TAX ──
    "Special inspection, third-party NDT - by Owner's testing agency per AISC",
    "Survey of anchor bolts beyond an initial conformance check",
    "Sales tax - not included (verify Texas tax exemption certificate handling)",
    # ── LABOR ──
    "Premium time / overtime / shift work - bid based on standard 40-hour week, single shift",
    "Remobilization for punch-list items after last erection day without remobilization charge",
    # ── DECK ──
    "Roof/floor metal deck closures, pour stops, edge angles - by deck sub unless noted",
    "Gutters, downspouts, flashings, gravel stops, expansion joint covers - by Others",
]

STANDARD_INCLUSIONS = [
    "Structural steel fabrication per approved shop drawings",
    "Structural steel erection with OSHA-compliant rigging and bracing",
    "Steel joist and joist girder supply and erection (SJI-certified)",
    "Metal roof deck and/or composite deck supply and installation",
    "Anchor rod supply and installation",
    "In-house Tekla Structures detailing and shop drawing submission",
    "Shop primer (one coat gray per AISC Code of Standard Practice §6.5)",
    "Delivery to job site (Houston metro - remote sites quoted separately)",
    "Plumbing-up cables and removal of erection aids after completion",
    "Material test reports (MTRs) for all structural steel furnished",
]

CLOSING_LINE = "All work is performed in-house per AISC/AWS/SJI/OSHA standards."

# Texas Prompt Payment Act (Tex. Prop. Code §§ 28.001-28.012)
# These statutory deadlines CANNOT be waived by contract
TEXAS_PROMPT_PAY = {
    "owner_to_gc_days": 35,         # Private projects
    "gc_to_sub_days": 7,            # After GC receives owner payment
    "sub_to_supplier_days": 7,      # After sub receives payment
    "late_interest_monthly": 1.5,   # Percent per month (18% annual)
    "public_owner_days": 30,        # Gov't Code §2251 (public projects)
    "public_gc_to_sub_days": 10,    # Gov't Code §2251 (public projects)
    "reference": "Tex. Prop. Code Ch. 28 (private) / Tex. Gov't Code Ch. 2251 (public)",
}

# Proposal validity
PROPOSAL_VALIDITY_DAYS = 30
CONTRACT_REFERENCE = "Acceptance subject to mutual review of GC's standard subcontract terms per AIA A401-2017 framework."

REFINERY_ADDITIONS = [
    "DISA drug testing compliance for all personnel",
    "ISN/Avetta/Veriforce safety prequalification maintained",
    "Site-specific safety plan per owner requirements",
    "Prevailing wage compliance per project labor agreement (PLA) if applicable",
    "Background checks for all site personnel",
]

# ═══════════════════════════════════════════════════════════════
# CSI DIVISION 05 - default scope table rows
# ═══════════════════════════════════════════════════════════════
# Each row is (csi_code, item, status, notes). Status is one of
# INCLUDED / EXCLUDED / BY OTHERS. Callers can override the whole
# list via the csi_scope kwarg for project-specific tables.
CSI_DIVISION_05_DEFAULT = [
    ("05 05 13", "Shop and Field Painting / Shop Primer", "INCLUDED",
     "One coat gray shop primer per AISC Code of Standard Practice Section 6.5; HDG per project drawings for exterior exposed steel"),
    ("05 12 00", "Structural Steel Framing", "INCLUDED",
     "W-shapes (ASTM A992 Gr 50), HSS columns and braces (ASTM A500 Gr B/C), connections, anchor bolts"),
    ("05 21 00", "Steel Joist Framing", "INCLUDED",
     "K-series open-web steel joists per SJI specifications"),
    ("05 31 00", "Steel Decking", "INCLUDED",
     "Galvanized vented metal roof deck and/or composite floor deck per drawings"),
    ("05 40 00", "Cold-Formed Metal Framing (CFMF)", "EXCLUDED",
     "CSI 05 4000 - by Others. Cee studs, zee purlins, light-gauge headers, framed wall panels not in Your Company scope"),
    ("05 50 00", "Metal Fabrications", "INCLUDED",
     "Misc steel allowance (typical lintels, hanger braces, fur-down framing, brace angle assemblies)"),
    ("05 51 00", "Metal Stairs", "BY OTHERS",
     "Pre-engineered stairs by Others. Stair supports and stair landing connections to structural steel by Your Company"),
    ("05 73 00", "Decorative Metal / Canopies", "EXCLUDED",
     "Decorative canopy and architectural metal systems by Others per drawing notes"),
    ("-", "Shop Drawings, Detailing, PE Stamps", "INCLUDED",
     "Tekla Structures detailing, Texas PE-stamped shop and erection drawings, AISC submittal package"),
]

CSI_FOOTNOTE = (
    "All structural steel is fabricated to ASTM specifications cited on project "
    "General Steel Notes and erected per AISC Code of Standard Practice. Steel "
    "permanently exposed to the exterior or in unconditioned space is hot-dip "
    "galvanized after fabrication when required by project drawings."
)

# ═══════════════════════════════════════════════════════════════
# COMPANY CAPABILITIES - shop equipment, engineering, compliance
# ═══════════════════════════════════════════════════════════════
COMPANY_CAPABILITIES = [
    ("Shop equipment",
     "4 x Miller Millermatic 255 MIG welders; Squickmons Q35Y-25 punch and shear "
     "(100-180 pcs/hr); Arc Pro CNC plasma cutter (40-100 pcs/hr); in-house SQ-2 "
     "joist shop with 50-state stamping authority"),
    ("Engineering",
     "In-house Tekla Structures detailing; Texas PE-stamped shop drawings; "
     "licensed architect on team"),
    ("Compliance",
     "AISC structural steel fabrication; AWS D1.1 welding with CWI on staff; "
     "SJI-certified joist fabrication; ISNetworld ID [ISN ID]"),
]

# ═══════════════════════════════════════════════════════════════
# AIA G702/G703 SOV milestones - percentages of the 50% SOV pool
# ═══════════════════════════════════════════════════════════════
# These sum to 50% (the SOV portion after 30% mob + 20% first delivery).
# Amounts are computed from base_bid at render time.
SOV_MILESTONES = [
    ("Shop Drawings Approved",   0.05, "Upon GC and EOR approval of shop drawings"),
    ("Fabrication 50% Complete", 0.10, "Half of structural tonnage cut, drilled, and assembled"),
    ("Fabrication 100% Complete",0.10, "All structural tonnage complete and shop-primed"),
    ("Steel Erected, Plumbed",   0.10, "All W-shapes, HSS, braces erected and plumbed"),
    ("Joists / Deck Installed",  0.10, "All joists set, roof and composite deck installed"),
    ("Punch List / Closeout",    0.05, "Punch list complete, final inspection, closeout submittals"),
]

# ═══════════════════════════════════════════════════════════════
# SCHEDULE & ASSUMPTIONS - default lead times and reference standards
# ═══════════════════════════════════════════════════════════════
SCHEDULE_ASSUMPTIONS_DEFAULT = [
    ("Shop drawings",       "2-3 weeks from notice to proceed (in-house Tekla detailing + overseas AISC review)"),
    ("Joist fabrication",   "2-3 weeks from approved shop drawings"),
    ("Steel delivery",      "3-4 weeks with main steel from approved shop drawings"),
    ("Roof and composite deck", "3-4 weeks from purchase order"),
    ("Anchor rod delivery", "10-14 days from approved anchor bolt plan"),
    ("Erection duration",   "Confirmed on award based on GC site logistics, pier turnover, and weather window"),
    ("Quantity tolerance",  "Plus or minus 5% absorbed at DD stage; reconciled to actuals at IFC"),
    ("Reference standards", "AISC 360, AISC 303 Code of Standard Practice, AWS D1.1, SJI K-Series, IBC 2018, ASCE 7-16"),
]


def generate_proposal(project_name, gc_name, gc_company, scope_text,
                      tonnage="TBD", total_estimate="TBD",
                      terms="Net 30", notes="", bid_number="",
                      template="STANDARD", member_schedule=None,
                      weight_summary=None, labor_breakdown=None,
                      joist_tons: float = 0, roof_deck_sf: float = 0,
                      composite_deck_sf: float = 0, anchor_count: int = 0,
                      project_meta: dict = None,
                      csi_scope: list = None,
                      include_csi_table: bool = True,
                      include_capabilities: bool = True,
                      include_sov_detail: bool = True,
                      include_schedule_table: bool = True,
                      extra_exclusions: list = None,
                      schedule_assumptions: list = None,
                      render_path: str = "", frame_image_path: str = "") -> dict:
    """Generate a bid proposal PDF using the active template.

    Templates: STANDARD, SIMPLE, DETAILED, REFINERY

    Optional quantity kwargs (joist_tons, roof_deck_sf, composite_deck_sf,
    anchor_count) trigger an ITEMIZED Section A + Section B pricing table
    with quantities x unit rates = extended amounts. If all are zero, the
    legacy "unit rates only" table is rendered (backward compatible).

    Optional project_meta dict may contain: address, owner, eor, architect,
    drawing_set_date. When provided, these populate extra rows in the
    project info table (matches the revised NSL-001 layout).
    """
    # vj: parity-ok (pass 10g classified: dispatcher J=0.26; disjoint shapes)
    _OUT.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in project_name if c.isalnum() or c in " -_")[:40].strip()
    filename = f"NC_Proposal_{safe}_{date.today().isoformat()}.pdf"
    path = _OUT / filename

    # Load saved template preference if not specified
    if template == "STANDARD":
        try:
            import json
            prefs_file = Path(__file__).resolve().parent.parent / "data" / "user_prefs.json"
            if prefs_file.exists():
                prefs = json.loads(prefs_file.read_text())
                template = prefs.get("bid_template", "STANDARD")
        except Exception:
            pass

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # ── FONT REGISTRATION ──
        # the Owner's bid font is Calibri. Try to register it from the system
        # so the PDF renders in Calibri on the Owner's Windows box; fall back
        # to Helvetica on machines without Calibri (clean, conservative).
        BODY_FONT = "Helvetica"
        BOLD_FONT = "Helvetica-Bold"
        for candidate_path in [
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/Calibri.ttf",
            "/Library/Fonts/Calibri.ttf",
            "/usr/share/fonts/truetype/calibri/calibri.ttf",
        ]:
            try:
                from pathlib import Path as _PP
                if _PP(candidate_path).exists():
                    pdfmetrics.registerFont(TTFont("Calibri", candidate_path))
                    bold_path = candidate_path.replace("calibri.ttf", "calibrib.ttf").replace("Calibri.ttf", "Calibrib.ttf")
                    if _PP(bold_path).exists():
                        pdfmetrics.registerFont(TTFont("Calibri-Bold", bold_path))
                        BODY_FONT = "Calibri"
                        BOLD_FONT = "Calibri-Bold"
                    break
            except Exception:
                continue

        doc = SimpleDocTemplate(str(path), pagesize=letter,
                                leftMargin=0.6*inch, rightMargin=0.6*inch,
                                topMargin=0.5*inch, bottomMargin=0.55*inch)
        styles = getSampleStyleSheet()
        story = []

        # ── BRAND COLORS - the Owner's Navy + Gold ──
        # Locked from his bid document brand spec (Calibri/Navy/Gold).
        # Molten orange retained ONLY as a thin steel accent rule, not body copy.
        NAVY        = colors.HexColor("#1F2A44")   # primary header band
        NAVY_BRIGHT = colors.HexColor("#2A3A5C")   # subhead, table header alt
        NAVY_DEEP   = colors.HexColor("#14203A")   # signature band
        GOLD        = colors.HexColor("#C9A961")   # accent rule, total row, marks
        GOLD_DEEP   = colors.HexColor("#A88A48")   # gold for borders
        CREAM       = colors.HexColor("#F7F5F0")   # alt row band, subtle bg
        CHARCOAL    = colors.HexColor("#1A1A1A")   # body text
        CHAR_70     = colors.HexColor("#5C5C5C")   # secondary text
        CHAR_50     = colors.HexColor("#888888")   # tertiary text / footer
        CONFIDENTIAL_RED = colors.HexColor("#B71C1C")

        # ── STYLES (Calibri-equivalent typography) ──
        # Navy/Gold pairing - clean, bank-grade, professional.
        company_style = ParagraphStyle('co', parent=styles['Normal'], fontSize=18,
                                        textColor=colors.white, spaceAfter=0,
                                        fontName=BOLD_FONT, leading=20, alignment=TA_LEFT)
        co_meta_style = ParagraphStyle('cometa', parent=styles['Normal'], fontSize=8.5,
                                        textColor=colors.HexColor("#D4D4D4"),
                                        fontName=BODY_FONT, leading=11, alignment=TA_LEFT)
        title_style   = ParagraphStyle('ptitle', parent=styles['Heading1'],
                                        fontSize=15, spaceBefore=14, spaceAfter=4,
                                        textColor=NAVY, fontName=BOLD_FONT,
                                        leading=18, alignment=TA_LEFT)
        ref_style     = ParagraphStyle('ref', parent=styles['Normal'], fontSize=10,
                                        textColor=GOLD_DEEP, fontName=BOLD_FONT,
                                        spaceAfter=10)
        section_style = ParagraphStyle('sec', parent=styles['Heading2'],
                                        fontSize=11, spaceBefore=10, spaceAfter=6,
                                        textColor=NAVY, fontName=BOLD_FONT,
                                        leading=14, alignment=TA_LEFT)
        body_style    = ParagraphStyle('body', parent=styles['Normal'], fontSize=10,
                                        spaceAfter=3, leading=13.5, fontName=BODY_FONT,
                                        textColor=CHARCOAL)
        body_bold     = ParagraphStyle('bodyB', parent=body_style, fontName=BOLD_FONT,
                                        textColor=NAVY)
        small_style   = ParagraphStyle('small', parent=styles['Normal'], fontSize=8.5,
                                        textColor=CHAR_70, fontName=BODY_FONT,
                                        leading=11)
        center_style  = ParagraphStyle('center', parent=styles['Normal'], fontSize=7.5,
                                        alignment=TA_CENTER, textColor=CHAR_50,
                                        fontName=BODY_FONT)
        confidential_style = ParagraphStyle('conf', parent=styles['Normal'], fontSize=7,
                                              alignment=TA_CENTER, textColor=CONFIDENTIAL_RED,
                                              fontName=BOLD_FONT, leading=9)

        # ═══ HEADER BAND - Navy with white type ═══════════════════════
        # Full-width navy band with company name + address/phone/ISN
        hdr_text_left = Paragraph("YOUR COMPANY, LLC", company_style)
        hdr_text_meta = Paragraph(
            f'{COMPANY["address"]}<br/>'
            f'{COMPANY["phone"]} &nbsp;·&nbsp; {COMPANY["email"]} &nbsp;·&nbsp; {COMPANY["isn"]}',
            co_meta_style
        )
        # Right side: gold "BID PROPOSAL" label
        hdr_label_style = ParagraphStyle('hl', parent=styles['Normal'], fontSize=14,
                                           textColor=GOLD, fontName=BOLD_FONT,
                                           alignment=TA_RIGHT, leading=16)
        hdr_label_meta = ParagraphStyle('hlm', parent=styles['Normal'], fontSize=9,
                                          textColor=colors.HexColor("#D4D4D4"),
                                          fontName=BODY_FONT, alignment=TA_RIGHT, leading=11)
        hdr_label = Paragraph("BID PROPOSAL", hdr_label_style)
        ref_short = bid_number if bid_number else "Reference: TBD"
        hdr_label_sub = Paragraph(ref_short, hdr_label_meta)

        # Two-column header band content
        hdr_left_cell  = [hdr_text_left, Spacer(1, 2), hdr_text_meta]
        hdr_right_cell = [hdr_label, Spacer(1, 2), hdr_label_sub]

        header_table = Table(
            [[hdr_left_cell, hdr_right_cell]],
            colWidths=[4.6*inch, 2.7*inch],
            rowHeights=[0.85*inch],
        )
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), NAVY),
            ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING',  (0,0), (0,0), 16),
            ('LEFTPADDING',  (1,0), (1,0), 4),
            ('RIGHTPADDING', (1,0), (1,0), 16),
            ('TOPPADDING',   (0,0), (-1,-1), 10),
            ('BOTTOMPADDING',(0,0), (-1,-1), 10),
        ]))
        story.append(header_table)

        # ── GOLD RULE under header (signature accent) ──
        gold_rule = Table([['']], colWidths=[7.3*inch], rowHeights=[2.5])
        gold_rule.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), GOLD)]))
        story.append(gold_rule)
        story.append(Spacer(1, 16))

        # ═══ TITLE + INFO BLOCK ═══════════════════════════════════════
        story.append(Paragraph("STRUCTURAL STEEL PROPOSAL", title_style))
        if bid_number:
            story.append(Paragraph(f"Bid Reference: {bid_number}", ref_style))
        else:
            story.append(Spacer(1, 6))

        # Project info - 2-column key/value grid with navy keys, gold separator
        info_data = [
            ["DATE",     date.today().strftime('%B %d, %Y'),
             "PROJECT",  project_name],
            ["TO",       f"{gc_name}",
             "COMPANY",  gc_company],
        ]
        if tonnage != "TBD":
            info_data.append(["EST. TONNAGE", f"{tonnage} tons", "", ""])
        # Optional project_meta: address, owner, eor, architect, drawing_set_date
        # Added 2026-05-21 to close the metadata gap between GUI output and the
        # full bid template. All keys optional; only rendered if provided.
        _pm = project_meta or {}
        if _pm.get("address"):
            info_data.append(["ADDRESS", _pm["address"], "", ""])
        if _pm.get("owner"):
            owner_val = _pm["owner"]
            if _pm.get("owner_project_no"):
                owner_val = f"{owner_val} (Project #{_pm['owner_project_no']})"
            info_data.append(["OWNER", owner_val, "", ""])
        if _pm.get("eor") or _pm.get("architect"):
            info_data.append([
                "EOR", _pm.get("eor", ""),
                "ARCHITECT", _pm.get("architect", ""),
            ])
        if _pm.get("drawing_set_date") or _pm.get("drawing_set_label"):
            label = _pm.get("drawing_set_label", "Issue for Proposal")
            d = _pm.get("drawing_set_date", "")
            dwg_val = f"{d} {label}".strip()
            info_data.append(["DWG SET", dwg_val, "", ""])
        info_table = Table(info_data, colWidths=[1.0*inch, 2.7*inch, 0.9*inch, 2.7*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME',  (0,0), (0,-1), BOLD_FONT),
            ('FONTNAME',  (2,0), (2,-1), BOLD_FONT),
            ('FONTSIZE',  (0,0), (-1,-1), 9),
            ('TEXTCOLOR', (0,0), (0,-1), GOLD_DEEP),
            ('TEXTCOLOR', (2,0), (2,-1), GOLD_DEEP),
            ('TEXTCOLOR', (1,0), (1,-1), CHARCOAL),
            ('TEXTCOLOR', (3,0), (3,-1), CHARCOAL),
            ('FONTNAME',  (1,0), (1,-1), BODY_FONT),
            ('FONTNAME',  (3,0), (3,-1), BODY_FONT),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LINEBELOW', (0,-1), (-1,-1), 0.5, colors.HexColor("#E0DAC8")),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 12))

        # -- ILLUSTRATIVE PROJECT RENDER (client proposal only) --
        # Drawing-anchored render from the Cowork steel-render pipeline
        # (Gemini, conditioned on this job's structural drawings). Client
        # proposal only; never on the -GP report. Always labeled illustrative.
        if render_path:
            try:
                from reportlab.platypus import Image as _RLImage
                from pathlib import Path as _IP
                _rp = _IP(render_path)
                if _rp.exists():
                    _content_w = 7.3 * inch
                    try:
                        from reportlab.lib.utils import ImageReader as _IR
                        _iw, _ih = _IR(str(_rp)).getSize()
                        _img_h = _content_w * (float(_ih) / float(_iw))
                    except Exception:
                        _img_h = _content_w * 0.5
                    _max_h = 3.4 * inch
                    if _img_h > _max_h:
                        _img_w = _max_h * (_content_w / _img_h)
                        _img_h = _max_h
                    else:
                        _img_w = _content_w
                    story.append(_RLImage(str(_rp), width=_img_w, height=_img_h))
                    _name = _rp.name.lower()
                    _is_tekla = any(_t in _name for _t in ("tekla", "viewport"))
                    # Only the pipeline's own <name>_MODEL.png earns the estimate-grade
                    # provenance caption; a coincidental "model" in a filename does not.
                    _is_model = _rp.stem.lower().endswith("_model") and not _is_tekla
                    if _is_tekla:
                        _cap = ("Tekla structural model viewport. Member-accurate frame "
                                "geometry from this project's detailing model.")
                    elif _is_model:
                        _cap = ("In-house structural model viewport from the verified "
                                "takeoff. Estimate-grade geometry, not a detailing model.")
                    else:
                        _cap = "Illustrative rendering. Not a photograph of a completed building."
                    story.append(Paragraph(_cap, small_style))
                    story.append(Spacer(1, 12))
            except Exception:
                pass  # render is optional; never block proposal generation

        # ═══ TEMPLATE-SPECIFIC SECTIONS ═══════════════════════════════

        # ── SCOPE (all except SIMPLE) ──
        if template != "SIMPLE":
            story.append(Paragraph("SCOPE OF WORK", section_style))
            story.append(Paragraph("<b>Includes:</b>", body_bold))
            for item in STANDARD_INCLUSIONS:
                story.append(Paragraph(f"&nbsp;&nbsp;•&nbsp;&nbsp;{item}", body_style))
            if scope_text and scope_text.strip():
                story.append(Spacer(1, 6))
                story.append(Paragraph("<b>Project-Specific Scope:</b>", body_bold))
                for line in scope_text.split("\n"):
                    if line.strip():
                        story.append(Paragraph(f"&nbsp;&nbsp;{line.strip()}", body_style))
            story.append(Spacer(1, 10))

        # ── CSI DIVISION 05 SCOPE TABLE (all except SIMPLE, when enabled) ──
        # Added 2026-05-21: structured CSI breakdown matching the revised
        # NSL-001 layout. Default rows come from CSI_DIVISION_05_DEFAULT;
        # callers can override via csi_scope kwarg for project-specific tables.
        if template != "SIMPLE" and include_csi_table:
            story.append(Paragraph("SCOPE OF WORK - CSI DIVISION 05", section_style))
            _csi_rows = csi_scope if csi_scope else CSI_DIVISION_05_DEFAULT
            csi_data = [["CSI", "Item", "Status", "Notes"]]
            for code, item, status, notes_txt in _csi_rows:
                csi_data.append([code, item, status, Paragraph(notes_txt, small_style)])
            csi_table = Table(
                csi_data,
                colWidths=[0.7*inch, 2.0*inch, 0.85*inch, 3.75*inch],
            )
            csi_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), NAVY),
                ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                ('FONTNAME',   (0,0), (-1,0), BOLD_FONT),
                ('FONTSIZE',   (0,0), (-1,0), 9),
                ('LINEBELOW',  (0,0), (-1,0), 1.5, GOLD),
                ('FONTNAME',   (0,1), (-1,-1), BODY_FONT),
                ('FONTSIZE',   (0,1), (-1,-1), 8.5),
                ('TEXTCOLOR',  (0,1), (-1,-1), CHARCOAL),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CREAM]),
                ('VALIGN',     (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING',  (0,0), (-1,-1), 5),
                ('RIGHTPADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(csi_table)
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<i>{CSI_FOOTNOTE}</i>", small_style))
            story.append(Spacer(1, 10))

        # ── CAPABILITIES BLOCK (all except SIMPLE, when enabled) ──
        if template != "SIMPLE" and include_capabilities:
            story.append(Paragraph("CAPABILITIES", section_style))
            cap_data = []
            for label, desc in COMPANY_CAPABILITIES:
                cap_data.append([label, Paragraph(desc, body_style)])
            cap_table = Table(cap_data, colWidths=[1.4*inch, 5.9*inch])
            cap_table.setStyle(TableStyle([
                ('FONTNAME', (0,0), (0,-1), BOLD_FONT),
                ('FONTSIZE', (0,0), (0,-1), 9.5),
                ('TEXTCOLOR',(0,0), (0,-1), GOLD_DEEP),
                ('VALIGN',   (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING',  (0,0), (-1,-1), 4),
                ('LINEBELOW',(0,0), (-1,-2), 0.25, colors.HexColor("#E0DAC8")),
            ]))
            story.append(cap_table)
            story.append(Spacer(1, 10))

        # ── MEMBER SCHEDULE (DETAILED and REFINERY only) ──
        if template in ("DETAILED", "REFINERY") and member_schedule:
            story.append(Paragraph("MEMBER SCHEDULE", section_style))
            sched_data = [["Mark", "Shape", "Length", "Qty", "Unit Wt", "Line Wt"]]
            for m in member_schedule:
                sched_data.append([
                    m.get("mark", ""), m.get("shape", ""),
                    f"{m.get('length_ft', '')}′", str(m.get("qty", 1)),
                    f"{m.get('weight_per_ft', '')} plf",
                    f"{m.get('line_weight_lbs', 0):,.0f} lbs"
                ])
            sched_table = Table(sched_data, colWidths=[0.8*inch, 1.2*inch, 0.8*inch, 0.5*inch, 1*inch, 1.2*inch])
            sched_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), NAVY),
                ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                ('FONTNAME',   (0,0), (-1,0), BOLD_FONT),
                ('FONTNAME',   (0,1), (-1,-1), BODY_FONT),
                ('FONTSIZE',   (0,0), (-1,-1), 9),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CREAM]),
                ('LINEBELOW', (0,0), (-1,0), 1.5, GOLD),
                ('LINEBELOW', (0,-1), (-1,-1), 0.5, GOLD_DEEP),
                ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
                ('TEXTCOLOR', (0,1), (-1,-1), CHARCOAL),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(sched_table)
            story.append(Spacer(1, 10))

        # ── PRICING TABLE (STANDARD, DETAILED, REFINERY) ──
        # When any quantity > 0 is passed, render itemized Section A + B
        # with Quantity x Unit Rate = Extended (matches revised NSL-001).
        # Otherwise fall back to the legacy unit-rates-only table.
        _struct_tons_num = 0.0
        try:
            _struct_tons_num = float(str(tonnage).replace(",", "")) if tonnage and tonnage != "TBD" else 0.0
        except (ValueError, TypeError):
            _struct_tons_num = 0.0
        _has_itemized = (_struct_tons_num > 0) and any(
            float(x or 0) > 0
            for x in (joist_tons, roof_deck_sf, composite_deck_sf, anchor_count)
        )

        if template != "SIMPLE" and _has_itemized:
            story.append(Paragraph("PRICING", section_style))

            # Section A - Structural Frame
            fab_rate = BID_RATES["fab_per_ton"]
            erect_rate = BID_RATES["erection_per_ton"]
            fab_ext = _struct_tons_num * fab_rate
            erect_ext = _struct_tons_num * erect_rate
            sec_a_total = fab_ext + erect_ext

            sec_a_data = [
                ["Section A - Structural Frame", "QUANTITY", "UNIT RATE", "EXTENDED"],
                ["Structural Steel Fabrication",
                 f"{_struct_tons_num:.1f} tons",
                 f"${fab_rate:,.0f}/ton",
                 f"${fab_ext:,.0f}"],
                ["Structural Steel Erection",
                 f"{_struct_tons_num:.1f} tons",
                 f"${erect_rate:,.0f}/ton",
                 f"${erect_ext:,.0f}"],
                ["Subtotal - Section A", "", "", f"${sec_a_total:,.0f}"],
            ]

            # Section B - Joists, Deck, Allocations
            joist_rate = BID_RATES["joists_per_ton"]
            roof_rate = BID_RATES["roof_deck_per_sf"]
            comp_rate = BID_RATES["composite_deck_per_sf"]
            anchor_rate = BID_RATES["anchor_rod_1x20_each"]

            joist_ext = float(joist_tons or 0) * joist_rate
            roof_ext = float(roof_deck_sf or 0) * roof_rate
            comp_ext = float(composite_deck_sf or 0) * comp_rate
            anchor_ext = float(anchor_count or 0) * anchor_rate
            sec_b_total = joist_ext + roof_ext + comp_ext + anchor_ext

            sec_b_data = [
                ["Section B - Joists, Deck, Allocations", "QUANTITY", "UNIT RATE", "EXTENDED"],
            ]
            if joist_tons:
                sec_b_data.append([
                    "Steel Joists (SJI K-series)",
                    f"{float(joist_tons):.1f} tons",
                    f"${joist_rate:,.0f}/ton",
                    f"${joist_ext:,.0f}",
                ])
            if roof_deck_sf:
                sec_b_data.append([
                    "Roof Deck (1.5B22 galvanized vented)",
                    f"{float(roof_deck_sf):,.0f} SF",
                    f"${roof_rate:.2f}/SF",
                    f"${roof_ext:,.0f}",
                ])
            if composite_deck_sf:
                sec_b_data.append([
                    "Composite Floor Deck (3-inch 20ga galv)",
                    f"{float(composite_deck_sf):,.0f} SF",
                    f"${comp_rate:.2f}/SF",
                    f"${comp_ext:,.0f}",
                ])
            if anchor_count:
                sec_b_data.append([
                    'Anchor Rods (1"x20" F1554 Gr.55)',
                    f"{int(anchor_count)} EA",
                    f"${int(anchor_rate)}/EA",
                    f"${anchor_ext:,.0f}",
                ])
            sec_b_data.append(["Subtotal - Section B", "", "", f"${sec_b_total:,.0f}"])

            base_bid = sec_a_total + sec_b_total

            def _build_pricing_table(rows):
                tt = Table(rows, colWidths=[3.5*inch, 1.2*inch, 1.3*inch, 1.3*inch])
                tt.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), NAVY),
                    ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                    ('FONTNAME',   (0,0), (-1,0), BOLD_FONT),
                    ('FONTSIZE',   (0,0), (-1,0), 10),
                    ('LINEBELOW',  (0,0), (-1,0), 1.5, GOLD),
                    ('FONTNAME',   (0,1), (-1,-2), BODY_FONT),
                    ('FONTSIZE',   (0,1), (-1,-1), 10),
                    ('TEXTCOLOR',  (0,1), (-1,-2), CHARCOAL),
                    ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, CREAM]),
                    ('BACKGROUND', (0,-1), (-1,-1), CREAM),
                    ('FONTNAME',   (0,-1), (-1,-1), BOLD_FONT),
                    ('TEXTCOLOR',  (0,-1), (-1,-1), NAVY),
                    ('LINEABOVE',  (0,-1), (-1,-1), 0.75, GOLD_DEEP),
                    ('ALIGN',      (1,0), (-1,-1), 'RIGHT'),
                    ('TOPPADDING', (0,0), (-1,-1), 5),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                    ('LEFTPADDING',  (0,0), (-1,-1), 8),
                    ('RIGHTPADDING', (0,0), (-1,-1), 8),
                ]))
                return tt

            story.append(_build_pricing_table(sec_a_data))
            story.append(Spacer(1, 6))
            story.append(_build_pricing_table(sec_b_data))
            story.append(Spacer(1, 6))

            # BASE BID gold row
            base_data = [["BASE BID", "", "", f"${base_bid:,.0f}"]]
            base_table = Table(base_data, colWidths=[3.5*inch, 1.2*inch, 1.3*inch, 1.3*inch])
            base_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), GOLD),
                ('TEXTCOLOR',  (0,0), (-1,-1), NAVY),
                ('FONTNAME',   (0,0), (-1,-1), BOLD_FONT),
                ('FONTSIZE',   (0,0), (-1,-1), 12),
                ('ALIGN',      (-1,0), (-1,-1), 'RIGHT'),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LEFTPADDING',  (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ('LINEABOVE',  (0,0), (-1,-1), 1.5, NAVY),
            ]))
            story.append(base_table)
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                "G&amp;A overhead absorbed into unit rates. Sales tax not included. "
                "Pricing valid 30 days from date of proposal. All work performed "
                "in-house per AISC/AWS/SJI/OSHA standards.",
                small_style,
            ))
            story.append(Spacer(1, 12))

        elif template != "SIMPLE":
            story.append(Paragraph("UNIT RATES - Q2 2026", section_style))
            rate_data = [["ITEM", "RATE"]]
            for item, rate in _get_rates_table().items():
                rate_data.append([item, rate])
            if tonnage != "TBD":
                rate_data.append(["Estimated Tonnage", f"{tonnage} tons"])
            rate_data.append(["TOTAL ESTIMATE", str(total_estimate)])

            t = Table(rate_data, colWidths=[4*inch, 3.3*inch])
            t.setStyle(TableStyle([
                # Header row - navy with white type, gold underline
                ('BACKGROUND', (0,0), (-1,0), NAVY),
                ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                ('FONTNAME',   (0,0), (-1,0), BOLD_FONT),
                ('FONTSIZE',   (0,0), (-1,0), 10),
                ('LINEBELOW',  (0,0), (-1,0), 1.5, GOLD),
                # Body rows
                ('FONTNAME',   (0,1), (-1,-2), BODY_FONT),
                ('FONTSIZE',   (0,1), (-1,-1), 10),
                ('TEXTCOLOR',  (0,1), (-1,-2), CHARCOAL),
                ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, CREAM]),
                ('LINEABOVE',  (0,1), (-1,1), 0.25, colors.HexColor("#E0DAC8")),
                # TOTAL row - gold band, navy text
                ('BACKGROUND', (0,-1), (-1,-1), GOLD),
                ('TEXTCOLOR',  (0,-1), (-1,-1), NAVY),
                ('FONTNAME',   (0,-1), (-1,-1), BOLD_FONT),
                ('FONTSIZE',   (0,-1), (-1,-1), 11),
                ('LINEABOVE',  (0,-1), (-1,-1), 1.5, NAVY),
                # Alignment
                ('ALIGN',      (1,0), (1,-1), 'RIGHT'),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('LEFTPADDING',  (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ]))
            story.append(t)
            story.append(Spacer(1, 12))
        else:
            # SIMPLE template - one line summary
            story.append(Paragraph("BUDGET ESTIMATE", section_style))
            big_total = ParagraphStyle('big', parent=body_style, fontSize=14,
                                         textColor=NAVY, fontName=BOLD_FONT, leading=18)
            story.append(Paragraph(
                f"Structural steel fabrication and erection: <b>{total_estimate}</b>",
                big_total))
            if tonnage != "TBD":
                story.append(Paragraph(f"Estimated tonnage: {tonnage} tons", body_style))
            story.append(Spacer(1, 12))

        # ── 3D STRUCTURE IMAGE (before EXCLUSIONS) ──
        # Estimate-grade 3D structural-frame image placed on the pricing page,
        # ahead of EXCLUSIONS, so the buyer sees the steel structure next to the
        # quantities. Client proposal only. Always labeled estimate-grade.
        if frame_image_path:
            try:
                from reportlab.platypus import Image as _RLImage2
                from pathlib import Path as _FP
                _fp = _FP(frame_image_path)
                if _fp.exists():
                    story.append(Paragraph("STRUCTURAL STEEL FRAME (3D MODEL)", section_style))
                    _cw = 7.3 * inch
                    try:
                        from reportlab.lib.utils import ImageReader as _IR2
                        _iw, _ih = _IR2(str(_fp)).getSize()
                        _ih2 = _cw * (float(_ih) / float(_iw))
                    except Exception:
                        _ih2 = _cw * 0.6
                    _mh = 3.2 * inch
                    if _ih2 > _mh:
                        _iw2 = _mh * (_cw / _ih2); _ih2 = _mh
                    else:
                        _iw2 = _cw
                    story.append(_RLImage2(str(_fp), width=_iw2, height=_ih2))
                    story.append(Paragraph(
                        "Estimate-grade 3D structural model of the steel frame. "
                        "Illustrative, not a detailing model.", small_style))
                    story.append(Spacer(1, 12))
            except Exception:
                pass

        # ── EXCLUSIONS (all except SIMPLE) ──
        if template != "SIMPLE":
            story.append(Paragraph("EXCLUSIONS", section_style))
            # Project-specific exclusions render FIRST (e.g. AHJER canopy,
            # specific stair systems) followed by STANDARD_EXCLUSIONS.
            _extra = extra_exclusions or []
            for ex in list(_extra) + STANDARD_EXCLUSIONS:
                # Use × (multiplication sign) in red for clean exclusion mark
                story.append(Paragraph(
                    f'<font color="#B71C1C"><b>×</b></font>&nbsp;&nbsp;{ex}',
                    body_style))
            story.append(Spacer(1, 10))

        # ── COMPLIANCE MATRIX (REFINERY only) ──
        if template == "REFINERY":
            story.append(Paragraph("COMPLIANCE & SAFETY", section_style))
            for item in REFINERY_ADDITIONS:
                story.append(Paragraph(
                    f'<font color="#C9A961"><b>✓</b></font>&nbsp;&nbsp;{item}',
                    body_style))
            story.append(Spacer(1, 10))

        # ── PAYMENT TERMS (all templates) ──
        story.append(Paragraph("PAYMENT TERMS AND SCHEDULE OF VALUES", section_style))

        # Compute the base bid for SOV from itemized math when available;
        # otherwise fall back to total_estimate parsed.
        _base_for_sov = 0.0
        try:
            if _has_itemized:
                _base_for_sov = sec_a_total + sec_b_total
            else:
                _base_for_sov = float(str(total_estimate).replace("$", "").replace(",", ""))
        except (ValueError, TypeError, NameError):
            _base_for_sov = 0.0

        # Payment Structure - 30/20/50 summary table with computed dollars
        _mob_pct = 0.30
        _del_pct = 0.20
        _sov_pct = 0.50
        if _base_for_sov > 0 and template != "SIMPLE" and include_sov_detail:
            ps_data = [
                ["Milestone", "Percent", "Amount", "Trigger"],
                ["Mobilization", "30%", f"${_base_for_sov*_mob_pct:,.0f}",
                 "Upon approval of Your Company shop drawings"],
                ["First Delivery", "20%", f"${_base_for_sov*_del_pct:,.0f}",
                 "Upon first fabricated delivery on site"],
                ["Schedule of Values (itemized below)", "50%", f"${_base_for_sov*_sov_pct:,.0f}",
                 "Per AIA G702/G703 through completion"],
            ]
            ps_table = Table(ps_data, colWidths=[2.8*inch, 0.8*inch, 1.3*inch, 2.4*inch])
            ps_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), NAVY),
                ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                ('FONTNAME',   (0,0), (-1,0), BOLD_FONT),
                ('FONTSIZE',   (0,0), (-1,0), 9.5),
                ('LINEBELOW',  (0,0), (-1,0), 1.5, GOLD),
                ('FONTNAME',   (0,1), (-1,-1), BODY_FONT),
                ('FONTSIZE',   (0,1), (-1,-1), 9),
                ('TEXTCOLOR',  (0,1), (-1,-1), CHARCOAL),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CREAM]),
                ('ALIGN',      (1,0), (2,-1), 'RIGHT'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING',  (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(ps_table)
            story.append(Spacer(1, 8))

            # Itemized 50% SOV pool (AIA G702/G703)
            story.append(Paragraph(
                "<b>50% Schedule of Values - Itemized Milestone Draws (AIA G702/G703)</b>",
                body_style,
            ))
            sov_rows = [["Milestone Draw", "% of Total", "Amount", "Trigger"]]
            for label, pct, trigger in SOV_MILESTONES:
                sov_rows.append([
                    label,
                    f"{pct*100:.1f}%",
                    f"${_base_for_sov*pct:,.0f}",
                    trigger,
                ])
            sov_total_pct = sum(p for _, p, _ in SOV_MILESTONES)
            sov_rows.append([
                "Total SOV Pool",
                f"{sov_total_pct*100:.1f}%",
                f"${_base_for_sov*sov_total_pct:,.0f}",
                "",
            ])
            sov_table = Table(sov_rows, colWidths=[2.4*inch, 0.9*inch, 1.2*inch, 2.8*inch])
            sov_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), NAVY_BRIGHT),
                ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                ('FONTNAME',   (0,0), (-1,0), BOLD_FONT),
                ('FONTSIZE',   (0,0), (-1,0), 9),
                ('LINEBELOW',  (0,0), (-1,0), 0.75, GOLD),
                ('FONTNAME',   (0,1), (-1,-2), BODY_FONT),
                ('FONTSIZE',   (0,1), (-1,-1), 8.5),
                ('TEXTCOLOR',  (0,1), (-1,-1), CHARCOAL),
                ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, CREAM]),
                ('BACKGROUND', (0,-1), (-1,-1), CREAM),
                ('FONTNAME',   (0,-1), (-1,-1), BOLD_FONT),
                ('LINEABOVE',  (0,-1), (-1,-1), 0.5, GOLD_DEEP),
                ('ALIGN',      (1,0), (2,-1), 'RIGHT'),
                ('TOPPADDING', (0,0), (-1,-1), 3.5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
                ('LEFTPADDING',  (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(sov_table)
            story.append(Spacer(1, 10))
        else:
            # Legacy 3-line summary for callers that don't pass base_bid
            for line in PAYMENT_TERMS.split("\n"):
                story.append(Paragraph(line, body_style))
            story.append(Spacer(1, 4))

        # ── SCHEDULE AND ASSUMPTIONS table (all except SIMPLE, when enabled) ──
        if template != "SIMPLE" and include_schedule_table:
            story.append(Paragraph("<b>Schedule and Assumptions</b>", body_style))
            _sa_rows = schedule_assumptions if schedule_assumptions else SCHEDULE_ASSUMPTIONS_DEFAULT
            sa_data = []
            for label, desc in _sa_rows:
                sa_data.append([label, Paragraph(desc, small_style)])
            sa_table = Table(sa_data, colWidths=[1.7*inch, 5.6*inch])
            sa_table.setStyle(TableStyle([
                ('FONTNAME', (0,0), (0,-1), BOLD_FONT),
                ('FONTSIZE', (0,0), (0,-1), 9),
                ('TEXTCOLOR',(0,0), (0,-1), GOLD_DEEP),
                ('VALIGN',   (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ('LEFTPADDING',  (0,0), (-1,-1), 4),
                ('LINEBELOW',(0,0), (-1,-2), 0.25, colors.HexColor("#E0DAC8")),
            ]))
            story.append(sa_table)
            story.append(Spacer(1, 6))

        story.append(Paragraph("Pricing valid for 30 days from date of proposal.", small_style))
        story.append(Paragraph("Sales tax not included.", small_style))

        if notes:
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"<b>Notes:</b> {notes}", body_style))

        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<i>{CLOSING_LINE}</i>", body_style))
        story.append(Spacer(1, 18))

        # ── SIGNATURE BLOCK - gold rule + side-by-side blocks ──
        gold_sig_rule = Table([['']], colWidths=[7.3*inch], rowHeights=[1])
        gold_sig_rule.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), GOLD_DEEP)]))
        story.append(gold_sig_rule)
        story.append(Spacer(1, 14))

        sig_data = [
            ['SUBMITTED BY:', '', 'ACCEPTED BY:'],
            ['', '', ''],
            ['', '', ''],
            ['_' * 36, '', '_' * 36],
            ['The Owner, CEO', '', 'Authorized Signature'],
            ['Your Company, LLC', '', gc_company or '__________________'],
            ['', '', ''],
            ['Date: ' + date.today().strftime('%m/%d/%Y'), '', 'Date: __________'],
        ]
        sig_table = Table(sig_data, colWidths=[3.4*inch, 0.5*inch, 3.4*inch])
        sig_table.setStyle(TableStyle([
            ('FONTNAME',  (0,0), (-1,0), BOLD_FONT),
            ('FONTSIZE',  (0,0), (-1,0), 9),
            ('TEXTCOLOR', (0,0), (-1,0), GOLD_DEEP),
            ('FONTNAME',  (0,3), (-1,3), BODY_FONT),
            ('FONTSIZE',  (0,3), (-1,3), 9),
            ('TEXTCOLOR', (0,3), (-1,3), CHARCOAL),
            ('FONTNAME',  (0,4), (0,4), BOLD_FONT),
            ('FONTNAME',  (2,4), (2,4), BOLD_FONT),
            ('FONTSIZE',  (0,4), (-1,-1), 9),
            ('TEXTCOLOR', (0,4), (-1,-1), CHARCOAL),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ]))
        story.append(sig_table)
        story.append(Spacer(1, 16))

        # ── CONFIDENTIAL footer band ──
        story.append(Paragraph(
            "CONFIDENTIAL - This proposal contains pricing and methodology proprietary to Your Company, LLC.",
            confidential_style
        ))
        story.append(Spacer(1, 4))

        # ── FOOTER (version dynamically pulled, no longer stale) ──
        try:
            from vo_app import __version__ as _vo_ver
        except ImportError:
            _vo_ver = "unknown"
        story.append(Paragraph(
            f"Generated by Your Company Virtual Office v{_vo_ver} &nbsp;·&nbsp; "
            f"{date.today().strftime('%Y-%m-%d')} &nbsp;·&nbsp; Template: {template}",
            center_style
        ))

        # Snapshot flowables BEFORE doc.build() drains the list by reference.
        # Without this, story == [] after build and R-03/R-04 get nothing.
        _qc_flowables = list(story)
        _qc_tables = [f for f in story if hasattr(f, '_colWidths')]
        _qc_styles = [
            s for s in [title_style, section_style, body_style, body_bold]
            if hasattr(s, 'name')
        ]
        _qc_detected = {
            "color": "#1F2A44",     # NAVY - all templates currently use this
            "has_ribbon": template != "SIMPLE",
        }

        doc.build(story)

        # ── Pass 4: Visual QC (the Owner's 6 rules) ────────────────────
        try:
            from bridge.pdf_qc import run_pdf_qc
            qc = run_pdf_qc(
                str(path),
                was_rendered=False,
                flowables=_qc_flowables,
                tables=_qc_tables,
                styles_used=_qc_styles,
                expected_template=template,
                detected_elements=_qc_detected,
            )
        except Exception:
            qc = {"verdict": "SKIP", "summary": "QC module not available"}

        # ── Pass 5: Voice calibration (the Owner's 10 voice rules) ─────
        voice_qc = {"verdict": "SKIP"}
        try:
            from harnesses.operational import VoiceCalibrationHarness
            # Check all text content that went into the proposal
            all_text = " ".join([
                scope_text or "",
                project_name or "",
                gc_company or "",
            ])
            if all_text.strip():
                voice_qc = VoiceCalibrationHarness.check(all_text)
        except Exception:
            pass

        return {"path": str(path), "filename": filename, "success": True,
                "template": template, "qc": qc, "voice_qc": voice_qc}

    except ImportError:
        # Fallback: text file
        txt_path = path.with_suffix(".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"YOUR COMPANY LLC - BID PROPOSAL\n{'='*50}\n")
            f.write(f"Date: {date.today()}\nTo: {gc_name}, {gc_company}\n")
            f.write(f"Project: {project_name}\n\nSCOPE:\n{scope_text}\n\n")
            f.write("INCLUDES:\n")
            for item in STANDARD_INCLUSIONS:
                f.write(f"  • {item}\n")
            f.write("\nRATES:\n")
            for item, rate in _get_rates_table().items():
                f.write(f"  {item}: {rate}\n")
            f.write(f"\nTonnage: {tonnage}\nTotal: {total_estimate}\n")
            f.write(f"\nPAYMENT TERMS:\n{PAYMENT_TERMS}\n")
            f.write(f"\nEXCLUSIONS:\n")
            for ex in STANDARD_EXCLUSIONS:
                f.write(f"  ✗ {ex}\n")
            f.write(f"\n{CLOSING_LINE}\n")
        return {"path": str(txt_path), "filename": txt_path.name, "success": True,
                "note": "reportlab not installed - generated text file instead"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_change_order(project_name, co_number, description,
                          cost_impact, schedule_impact="None",
                          requested_by="", notes="",
                          skip_visual_qc: bool = True) -> dict:
    """Generate a change order document. Returns {path, success}.

    Item 3 fix: skip_visual_qc defaults to True for COs because
    change orders are generated programmatically (no human viewing the
    PDF in a preview pane before it runs). R-01 was blocking all
    API-driven CO generation. The other 5 QC rules still execute.
    Pass skip_visual_qc=False to enforce the visual inspection gate
    (e.g. if the CO is being previewed in the desktop EXE).
    """
    # vj: parity-ok (pass 10g classified: mixed J=0.40; needs manual audit)
    _OUT.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in project_name if c.isalnum() or c in " -_")[:30].strip()
    # MC-NEW-05 fix: strip any leading 'CO-' or 'CO' prefix the caller may
    # have included, since the format string adds 'NC_CO' itself.
    co_num_clean = str(co_number).strip()
    for prefix in ("CO-", "CO"):
        if co_num_clean.upper().startswith(prefix):
            co_num_clean = co_num_clean[len(prefix):]
            break
    filename = f"NC_CO{co_num_clean}_{safe}_{date.today().isoformat()}.pdf"
    path = _OUT / filename

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        doc = SimpleDocTemplate(str(path), pagesize=letter,
                                leftMargin=0.75*inch, rightMargin=0.75*inch)
        styles = getSampleStyleSheet()
        story = []

        hdr = ParagraphStyle('hdr', parent=styles['Title'], fontSize=16,
                              textColor=colors.HexColor("#FF5F00"))
        story.append(Paragraph("YOUR COMPANY LLC", hdr))
        story.append(Paragraph(COMPANY["address"], styles["Normal"]))
        story.append(Spacer(1, 16))
        story.append(Paragraph(f"CHANGE ORDER #{co_number}", styles["Heading1"]))
        story.append(Spacer(1, 8))

        info = [
            ["Project", project_name],
            ["CO Number", str(co_number)],
            ["Date", date.today().strftime("%B %d, %Y")],
            ["Requested By", requested_by or "Owner"],
        ]
        t = Table(info, colWidths=[1.5*inch, 4.5*inch])
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 16))

        story.append(Paragraph("DESCRIPTION OF CHANGE", styles["Heading2"]))
        story.append(Paragraph(description, styles["Normal"]))
        story.append(Spacer(1, 12))

        story.append(Paragraph("COST IMPACT", styles["Heading2"]))
        story.append(Paragraph(str(cost_impact), styles["Normal"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"Schedule Impact: {schedule_impact}", styles["Normal"]))
        if notes:
            story.append(Spacer(1, 8))
            story.append(Paragraph(f"Notes: {notes}", styles["Normal"]))
        story.append(Spacer(1, 30))

        story.append(Paragraph("APPROVALS", styles["Heading2"]))
        story.append(Spacer(1, 16))
        for role in ["Contractor (Your Company)", "Owner/GC Representative"]:
            story.append(Paragraph(f"{'_'*40}  Date: {'_'*15}", styles["Normal"]))
            story.append(Paragraph(role, styles["Normal"]))
            story.append(Spacer(1, 16))

        # Snapshot before doc.build() drains the list
        _qc_flowables = list(story)
        _qc_tables = [f for f in story if hasattr(f, '_colWidths')]
        _qc_styles = [s for s in [hdr, styles["Heading1"], styles["Heading2"],
                                   styles["Normal"]] if hasattr(s, 'name')]

        doc.build(story)

        # ── Pass 4: Visual QC ────────────────────────────────────────
        try:
            from bridge.pdf_qc import run_pdf_qc
            qc = run_pdf_qc(
                str(path),
                was_rendered=False,
                flowables=_qc_flowables,
                tables=_qc_tables,
                styles_used=_qc_styles,
                skip_visual_qc=skip_visual_qc,
            )
        except Exception:
            qc = {"verdict": "SKIP", "summary": "QC module not available"}

        return {"path": str(path), "filename": filename, "success": True,
                "qc": qc}
    except ImportError:
        txt_path = path.with_suffix(".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"CHANGE ORDER #{co_number}\n{'='*40}\n")
            f.write(f"Project: {project_name}\nDate: {date.today()}\n")
            f.write(f"Description: {description}\nCost: {cost_impact}\n")
        return {"path": str(txt_path), "filename": txt_path.name, "success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
