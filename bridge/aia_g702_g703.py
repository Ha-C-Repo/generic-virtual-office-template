"""
AIA G702/G703 Pay Application - Domain Engine

Generates Application for Payment (G702 cover) and Continuation Sheet (G703 detail)
from job-cost ledger. Texas retainage release + 45-day pay-when-paid lag.

Texas Property Code Chapter 53 lien-notice calendar is hard-coded and immovable.
Retainage: typically 5-10% in Texas private construction.
"""
import json
from datetime import date, timedelta
from pathlib import Path

_OUT = Path(__file__).resolve().parent.parent / "output"

# Texas lien law deadlines (Property Code Chapter 53)
TEXAS_LIEN_DEADLINES = {
    "original_contractor_notice": {"days": None, "description": "No pre-lien notice required for original contractors"},
    "subcontractor_notice": {"days": 15, "description": "15th day of 2nd month after labor/materials furnished"},
    "mechanic_lien_affidavit": {"days": 15, "description": "15th day of 4th month after last day of month work performed"},
    "foreclosure_deadline": {"months": 12, "description": "Must file suit within 1 year of lien filing, or 2 years for residential"},
    "retainage_release": {"days": 30, "description": "Owner must release retainage within 30 days of completion (private)"},
}


def generate_sov(line_items):
    """Generate a Schedule of Values (SOV) from line items.
    line_items: list of {description, scheduled_value}
    Returns SOV with numbering."""
    sov = []
    total = 0
    for i, item in enumerate(line_items, 1):
        val = item.get("scheduled_value", 0)
        total += val
        sov.append({
            "number": i,
            "description": item.get("description", f"Item {i}"),
            "scheduled_value": val,
        })
    return {"items": sov, "total_scheduled": round(total, 2)}


def generate_g703(sov_items, work_completed_pct=None, materials_stored=None,
                   retainage_pct=10.0, previous_cert_total=0):
    """Generate AIA G703 Continuation Sheet.
    sov_items: list of {number, description, scheduled_value, pct_complete, materials_stored}
    """
    rows = []
    total_scheduled = 0
    total_completed = 0
    total_stored = 0
    total_retainage = 0

    for item in sov_items:
        scheduled = item.get("scheduled_value", 0)
        pct = item.get("pct_complete", work_completed_pct or 0)
        stored = item.get("materials_stored", 0)
        completed_value = scheduled * (pct / 100)
        total_this_period = completed_value + stored
        retainage = total_this_period * (retainage_pct / 100)
        net = total_this_period - retainage

        total_scheduled += scheduled
        total_completed += completed_value
        total_stored += stored
        total_retainage += retainage

        rows.append({
            "number": item.get("number", 0),
            "description": item.get("description", ""),
            "scheduled_value": round(scheduled, 2),
            "prev_completed": round(item.get("prev_completed", 0), 2),
            "this_period": round(completed_value, 2),
            "materials_stored": round(stored, 2),
            "total_completed": round(completed_value + stored, 2),
            "pct_complete": round(pct, 1),
            "retainage": round(retainage, 2),
        })

    return {
        "rows": rows,
        "totals": {
            "scheduled": round(total_scheduled, 2),
            "completed_to_date": round(total_completed + total_stored, 2),
            "retainage": round(total_retainage, 2),
            "previous_certificates": round(previous_cert_total, 2),
            "current_payment_due": round(total_completed + total_stored - total_retainage - previous_cert_total, 2),
        },
        "retainage_pct": retainage_pct,
    }


def generate_g702(project_name, contractor_name, owner_name, architect_name,
                   application_number, period_to, g703_totals):
    """Generate AIA G702 cover sheet data."""
    return {
        "form": "AIA G702",
        "project": project_name,
        "contractor": contractor_name,
        "owner": owner_name,
        "architect": architect_name,
        "application_number": application_number,
        "period_to": period_to,
        "original_contract_sum": g703_totals.get("scheduled", 0),
        "net_change_by_cos": 0,
        "contract_sum_to_date": g703_totals.get("scheduled", 0),
        "total_completed_stored": g703_totals.get("completed_to_date", 0),
        "retainage": g703_totals.get("retainage", 0),
        "total_earned_less_retainage": g703_totals.get("completed_to_date", 0) - g703_totals.get("retainage", 0),
        "less_previous_certificates": g703_totals.get("previous_certificates", 0),
        "current_payment_due": g703_totals.get("current_payment_due", 0),
        "balance_to_finish": g703_totals.get("scheduled", 0) - g703_totals.get("completed_to_date", 0),
    }


def generate_pay_app_pdf(project_name, contractor, owner, architect,
                          app_number, period_to, sov_items, retainage_pct=10,
                          previous_cert=0):
    """Generate complete G702+G703 pay application PDF."""
    # vj: parity-ok (pass 10g classified: mixed J=0.44; needs manual audit)
    _OUT.mkdir(parents=True, exist_ok=True)
    g703 = generate_g703(sov_items, retainage_pct=retainage_pct, previous_cert_total=previous_cert)
    g702 = generate_g702(project_name, contractor, owner, architect,
                          app_number, period_to, g703["totals"])

    filename = f"NC_PayApp_{app_number}_{period_to}.pdf"
    path = _OUT / filename

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet

        doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.5*inch, rightMargin=0.5*inch)
        styles = getSampleStyleSheet()
        story = []

        # G702 Cover
        story.append(Paragraph("APPLICATION AND CERTIFICATE FOR PAYMENT", styles["Title"]))
        story.append(Paragraph(f"AIA Document G702 - Application No. {app_number}", styles["Normal"]))
        story.append(Spacer(1, 12))

        info = [
            ["Project:", project_name, "Application No:", str(app_number)],
            ["Contractor:", contractor, "Period To:", period_to],
            ["Owner:", owner, "Contract Sum:", f"${g702['original_contract_sum']:,.2f}"],
            ["Architect:", architect, "Current Due:", f"${g702['current_payment_due']:,.2f}"],
        ]
        t = Table(info, colWidths=[1.2*inch, 2.5*inch, 1.2*inch, 2.1*inch])
        t.setStyle(TableStyle([
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        story.append(t)
        story.append(Spacer(1, 20))

        # G703 Detail
        story.append(Paragraph("CONTINUATION SHEET - AIA G703", styles["Heading2"]))
        header = ["#", "Description", "Scheduled", "Prev", "This Period", "Stored", "Total", "%", "Retainage"]
        rows_data = [header]
        for r in g703["rows"]:
            rows_data.append([
                str(r["number"]), r["description"][:30],
                f"${r['scheduled_value']:,.0f}", f"${r['prev_completed']:,.0f}",
                f"${r['this_period']:,.0f}", f"${r['materials_stored']:,.0f}",
                f"${r['total_completed']:,.0f}", f"{r['pct_complete']:.0f}%",
                f"${r['retainage']:,.0f}",
            ])
        # Totals row
        tot = g703["totals"]
        rows_data.append(["", "TOTALS", f"${tot['scheduled']:,.0f}", "",
                          f"${tot['completed_to_date']:,.0f}", "", "",
                          "", f"${tot['retainage']:,.0f}"])

        t = Table(rows_data, colWidths=[0.3*inch, 1.5*inch, 0.8*inch, 0.7*inch, 0.8*inch, 0.7*inch, 0.8*inch, 0.5*inch, 0.8*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1a1a1f")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ]))
        story.append(t)

        doc.build(story)
        return {"path": str(path), "filename": filename, "success": True,
                "g702": g702, "g703_totals": g703["totals"]}
    except ImportError:
        # Text fallback
        txt = path.with_suffix(".txt")
        with open(txt, "w", encoding="utf-8") as f:
            f.write(f"PAY APP #{app_number} - {project_name}\n")
            f.write(json.dumps(g702, indent=2))
            f.write("\n\nG703:\n")
            f.write(json.dumps(g703, indent=2))
        return {"path": str(txt), "filename": txt.name, "success": True,
                "g702": g702, "g703_totals": g703["totals"]}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def lien_notice_calendar(project_start_date, role="original_contractor"):
    """Generate Texas lien-law calendar for a project.
    Per handoff: This calendar should be hard-coded and immovable."""
    start = date.fromisoformat(project_start_date)
    calendar = []
    if role != "original_contractor":
        # Subcontractor pre-lien notice
        notice_date = date(start.year, start.month + 2 if start.month <= 10 else 1, 15)
        calendar.append({"event": "Subcontractor Monthly Notice", "date": notice_date.isoformat(),
                        "description": TEXAS_LIEN_DEADLINES["subcontractor_notice"]["description"]})
    # Mechanic's lien affidavit
    ml_date = date(start.year, min(start.month + 4, 12), 15)
    calendar.append({"event": "Mechanic's Lien Affidavit Deadline", "date": ml_date.isoformat(),
                    "description": TEXAS_LIEN_DEADLINES["mechanic_lien_affidavit"]["description"]})
    # Retainage release
    calendar.append({"event": "Retainage Release (30 days post-completion)", "date": "TBD",
                    "description": TEXAS_LIEN_DEADLINES["retainage_release"]["description"]})
    return {"role": role, "project_start": project_start_date, "deadlines": calendar,
            "warning": "Texas Property Code Ch. 53 - these deadlines are statutory and non-negotiable."}
