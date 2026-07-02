"""
Your Company Virtual Office - Cash Flow Autopilot / Virtual CFO

Combines: cash flow projection + receivables forecast + payroll burden +
material commitments + insurance premiums into a 30/60/90 day projection.

"You'll be cash-negative June 15 unless you draw LOC or accelerate the AFR pay app."
"""

from datetime import date, timedelta

# Texas commercial construction constants
PAY_WHEN_PAID_LAG = 45  # days
RETAINAGE_PCT = 10.0
PAYROLL_CYCLE_DAYS = 14
INSURANCE_MONTHLY = 8500  # WC + GL + auto estimate for 12-person shop


def project_cash_flow(projects: list = None, bank_balance: float = 0,
                      monthly_overhead: float = 45000,
                      monthly_insurance: float = INSURANCE_MONTHLY,
                      loc_available: float = 0) -> dict:
    """30/60/90 day cash flow projection.

    projects: list of {name, receivable_amount, expected_pay_date,
                       committed_costs, payroll_monthly}
    """
    projects = projects or []
    today = date.today()
    periods = {"30_day": 30, "60_day": 60, "90_day": 90}
    projection = {}

    for period_name, days in periods.items():
        cutoff = today + timedelta(days=days)

        # Inflows
        inflows = []
        for p in projects:
            pay_date_str = p.get("expected_pay_date", "")
            if pay_date_str:
                try:
                    pay_date = date.fromisoformat(pay_date_str)
                    if today <= pay_date <= cutoff:
                        inflows.append({
                            "source": p.get("name", "Unknown"),
                            "amount": p.get("receivable_amount", 0),
                            "date": pay_date_str,
                        })
                except Exception:pass
        total_inflow = sum(i["amount"] for i in inflows)

        # Outflows
        months_in_period = days / 30
        payroll = sum(p.get("payroll_monthly", 0) for p in projects) * months_in_period
        committed = sum(p.get("committed_costs", 0) for p in projects
                       if p.get("commitment_due", "") and p["commitment_due"] <= cutoff.isoformat())
        overhead = monthly_overhead * months_in_period
        insurance = monthly_insurance * months_in_period
        total_outflow = payroll + committed + overhead + insurance

        # Net
        net = total_inflow - total_outflow
        ending_balance = bank_balance + net

        projection[period_name] = {
            "inflows": inflows,
            "total_inflow": round(total_inflow, 2),
            "outflows": {
                "payroll": round(payroll, 2),
                "committed_materials": round(committed, 2),
                "overhead": round(overhead, 2),
                "insurance": round(insurance, 2),
            },
            "total_outflow": round(total_outflow, 2),
            "net": round(net, 2),
            "ending_balance": round(ending_balance, 2),
            "cash_negative": ending_balance < 0,
        }

    # Find first cash-negative date
    cash_negative_date = None
    for period_name in ["30_day", "60_day", "90_day"]:
        if projection[period_name]["cash_negative"]:
            cash_negative_date = period_name
            break

    # Generate recommendations
    recommendations = []
    if cash_negative_date:
        recommendations.append(f"⛔ Cash negative projected in {cash_negative_date.replace('_', ' ')} period")
        # Find largest receivable
        all_inflows = []
        for p in projection.values():
            all_inflows.extend(p.get("inflows", []))
        if all_inflows:
            largest = max(all_inflows, key=lambda x: x["amount"])
            recommendations.append(f"Accelerate: {largest['source']} pay app (${largest['amount']:,.0f} due {largest['date']})")
        if loc_available > 0:
            recommendations.append(f"LOC available: ${loc_available:,.0f} - draw before cash-negative date")
    else:
        recommendations.append("✅ Cash positive through 90-day horizon")

    return {
        "bank_balance": bank_balance,
        "projection": projection,
        "cash_negative_date": cash_negative_date,
        "recommendations": recommendations,
        "loc_available": loc_available,
        "generated_at": date.today().isoformat(),
    }


def revenue_attribution() -> dict:
    """Track ROI of Virtual Office automated actions."""
    try:
        from bridge.audit import query
        from bridge.bid_pipeline import stats as bid_stats

        # Count automated actions
        audit = query(hours=720, limit=5000)  # 30 days
        ai_responses = sum(1 for a in audit if a["action"] == "ai_response")
        emails_drafted = sum(1 for a in audit if a["action"] == "email_sent")
        docs_generated = sum(1 for a in audit if "doc_" in a["action"])
        bids_processed = sum(1 for a in audit if "bid_" in a["action"])
        compliance_checks = sum(1 for a in audit if "compliance" in a.get("detail", "").lower())

        # Estimate time savings (conservative: 5 min per AI response, 15 min per email, 30 min per doc)
        hours_saved = (ai_responses * 5 + emails_drafted * 15 + docs_generated * 30 + bids_processed * 20) / 60

        # Bid stats
        bs = bid_stats()

        return {
            "period": "30 days",
            "automated_actions": {
                "ai_responses": ai_responses,
                "emails_drafted": emails_drafted,
                "documents_generated": docs_generated,
                "bids_processed": bids_processed,
                "compliance_checks": compliance_checks,
            },
            "estimated_hours_saved": round(hours_saved, 1),
            "estimated_value_saved": round(hours_saved * 85, 2),  # $85/hr loaded cost
            "bid_pipeline": bs,
        }
    except Exception as e:
        return {"error": str(e)[:200]}


def for_briefing() -> str:
    """Cash flow summary for morning briefing."""
    try:
        # Build from project cost tracker
        from bridge.cost_tracker import get_all_projects
        projects = get_all_projects()
        active = [p for p in projects if p.get("status") == "ACTIVE"]
        total_est = sum(p.get("est_cost", 0) for p in active)
        total_act = sum(p.get("act_cost", 0) for p in active)
        return f"Cash flow: {len(active)} active projects, ${total_est:,.0f} estimated, ${total_act:,.0f} actual"
    except Exception:
        return "Cash flow: Module loading"
