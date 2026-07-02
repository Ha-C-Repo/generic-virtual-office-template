#!/usr/bin/env python3
"""Your Company Shop QC - printable shop-floor quick reference (PDF)."""
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable, PageBreak)

OUT = "/sessions/zen-sweet-maxwell/mnt/Cowork Virtual Office/ShopQC/training/YourCo_ShopQC_QuickReference.pdf"
RED = colors.HexColor("#b3122b")
INK = colors.HexColor("#141414")
DARK = colors.HexColor("#11121a")
LINE = colors.HexColor("#c9c9cf")
LIGHT = colors.HexColor("#f1f1f3")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Title"], fontSize=20, textColor=INK,
                    spaceAfter=2, alignment=0)
SUB = ParagraphStyle("SUB", parent=styles["Normal"], fontSize=9.5, textColor=colors.HexColor("#55555c"))
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12.5, textColor=RED,
                    spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=styles["Normal"], fontSize=9, leading=12, textColor=INK)
CELL = ParagraphStyle("CELL", parent=styles["Normal"], fontSize=8.3, leading=10.5, textColor=INK)
CELLH = ParagraphStyle("CELLH", parent=CELL, textColor=colors.white, fontName="Helvetica-Bold")
SMALL = ParagraphStyle("SMALL", parent=styles["Normal"], fontSize=7.6, leading=9.5,
                       textColor=colors.HexColor("#55555c"))

def P(t, s=CELL): return Paragraph(t, s)

def header_table(headers, rows, widths):
    data = [[P(h, CELLH) for h in headers]] + [[P(c) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t

story = []
story.append(Paragraph("YOUR COMPANY Shop QC - Floor Quick Reference", H1))
story.append(Paragraph("v1.0.0 &bull; NC-QC-FAB-001 Rev 0 &bull; keep at the station", SUB))
story.append(HRFlowable(width="100%", thickness=2, color=RED, spaceBefore=4, spaceAfter=2))

story.append(Paragraph("The three gates (one direction, no skipping)", H2))
story.append(header_table(
    ["Gate", "Tab", "What you do", "Status after"],
    [["Gate 1", "Receiving", "Record BOL + MTR values, run MTR &amp; physical checks, print QR labels, sign RIR", "RECEIVED"],
     ["Gate 2", "Fabrication", "Scan piece, sign the floor steps in the locked sequence", "IN_FAB"],
     ["Gate 3", "Release", "Re-verify completeness, final sign-off (+CEO if needed), release &amp; ship", "RELEASED / SHIPPED"]],
    [0.6*inch, 0.9*inch, 4.0*inch, 1.0*inch]))

story.append(Paragraph("The six hard blocks (the app will NOT let you bypass these)", H2))
story.append(header_table(
    ["#", "Rule", "Where"],
    [["1", "A CWI name is required to sign a weld-inspection step. No name, no signature.", "Gate 2, fields 8 &amp; 10"],
     ["2", "Locked sequence: only the lowest unsigned floor step can be signed.", "Gate 2"],
     ["3", "An open NCR puts the piece on NCR HOLD and freezes the whole traveler.", "Gate 2 / NCR"],
     ["4", "Gate 3 needs every field 1-14 signed and zero open NCRs, re-checked at sign time.", "Gate 3"],
     ["5", "CEO co-sign, exact name 'The Owner', for projects 50 tons or more, or any IAS job.", "Gate 3"],
     ["6", "An 'Unauthorized field modification' NCR cannot close without an EOR sealed reference.", "NCR Log"]],
    [0.3*inch, 4.8*inch, 1.4*inch]))

story.append(Paragraph("The structural traveler - 18 fields (joists use a parallel 20-field set)", H2))
fields = [
    "1  Project / Job No. (auto)", "2  Piece Mark (auto)", "3  Section + Heat No. (auto)",
    "4  MTR on file / lot (auto)", "5  Cut to length", "6  Hole punch / drill",
    "7  Coping / fitting", "8  Pre-weld inspection (CWI) *HARD BLOCK*", "9  Welder ID / WPS",
    "10  Post-weld VT (CWI)", "11  UT / MT result (optional)", "12  Dimensional check",
    "13  Camber check (optional)", "14  Surface prep / DFT", "15  Final Release - Shop Director",
    "16  Final Release - CWI", "17  Shipped - date + truck", "18  NCR number (if any)"]
rows = [[fields[i], fields[i+1] if i+1 < len(fields) else ""] for i in range(0, len(fields), 2)]
ft = Table([[P(a), P(b)] for a, b in rows], colWidths=[3.25*inch, 3.25*inch])
ft.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, LINE),
                        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT]),
                        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5)]))
story.append(ft)
story.append(Spacer(1, 4))
story.append(Paragraph("Fields 1-4 auto-fill at receiving. Floor steps 5-14 are signed at Gate 2 in order. "
                       "15-18 are release, ship and NCR.", SMALL))

story.append(PageBreak())

story.append(Paragraph("NCR (nonconformance) - raise, disposition, close", H2))
story.append(header_table(
    ["Step", "How"],
    [["Raise", "Gate 2: 'Open NCR on Active Step'. Or NCR Log: 'New NCR'. Piece goes on NCR HOLD."],
     ["Disposition", "NCR Log: select NCR, 'Disposition / Close'. Pick USE AS IS, REWORK, REPAIR, or REJECT/SCRAP; enter authority."],
     ["Close", "Tick 'Close this NCR now' and sign. Closing the last open NCR releases the hold."],
     ["EOR rule", "An 'Unauthorized field modification' NCR will NOT close without an EOR sealed analysis reference (hard block 6)."]],
    [0.9*inch, 5.6*inch]))

story.append(Paragraph("Seven NCR categories", H2))
story.append(Paragraph("Material nonconformance &bull; Dimensional &bull; Welding &bull; Coating / surface prep "
                       "&bull; Documentation &bull; Damage / handling &bull; Unauthorized field modification", BODY))

story.append(Paragraph("Who signs what", H2))
story.append(header_table(
    ["Action", "Required signer(s)"],
    [["Pre-weld &amp; post-weld inspection (fields 8, 10)", "CWI (Certified Welding Inspector) name required"],
     ["Receiving Inspection Report (RIR)", "Receiving inspector, after all checks ticked"],
     ["Final release (Gate 3)", "Shop Director + CWI"],
     ["Final release on 50T+ or IAS job", "Shop Director + CWI + CEO 'The Owner' (exact)"],
     ["Ship load", "Shipped-by name + truck/load number"]],
    [3.2*inch, 3.3*inch]))

story.append(Paragraph("The QR label", H2))
story.append(Paragraph("Every received piece gets a QR label. It encodes full traceability: "
                       "<b>PIECE_ID | PROJECT_NO | HEAT_NO | RECEIVED_DATE</b>. "
                       "Scan it at Gate 2 or Gate 3 to open that exact piece. A bare piece ID also works.", BODY))

story.append(Paragraph("On the floor - do / don't", H2))
do_dont = Table([
    [P("<b>DO</b>", CELLH), P("<b>DON'T</b>", CELLH)],
    [P("Record the actual MTR value (Fy, Fu, CE) off the cert."),
     P("Invent or round a value the app did not capture.")],
    [P("Get a CWI to sign field 8 before any welding."),
     P("Try to work around a hard block - find the missing item.")],
    [P("Close the NCR before resuming a held traveler."),
     P("Sign a step on a piece that is on NCR HOLD.")],
    [P("Confirm zero open NCRs before release or ship."),
     P("Ship a piece with an open NCR.")],
], colWidths=[3.25*inch, 3.25*inch])
do_dont.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), DARK),
    ("GRID", (0, 0), (-1, -1), 0.5, LINE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
]))
story.append(do_dont)
story.append(Spacer(1, 10))
story.append(HRFlowable(width="100%", thickness=1, color=LINE))
story.append(Paragraph("When the software blocks you, it is enforcing NC-QC-FAB-001. "
                       "Find the missing signature, reading, or NCR rather than working around it.", SMALL))

doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=0.55*inch, rightMargin=0.55*inch,
                        topMargin=0.5*inch, bottomMargin=0.5*inch, title="Your Company Shop QC Quick Reference")
doc.build(story)
print("WROTE", OUT)
