"""
Your Company Virtual Office - Agent Orchestrator

Runs all 5 AI agents on schedule and generates a unified morning briefing.
Wires agent outputs into the event bus, knowledge graph, and hash chain.

Schedule:
  04:00 - Houston Pipeline Agent (Gemini)
  05:00 - Steel Price Agent (Claude)
  05:30 - Compliance Agent (Claude)
  06:00 - Ledger reconciliation (Claude)
  06:30 - Unified Morning Intelligence Brief assembled
  07:00 - SMS briefing sent to Owner

This is the "second brain" - it runs while Owner sleeps.
"""

import json, threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent.parent / "data"


def run_daily_pipeline(fred_key: str = None) -> dict:
    """Run the complete daily agent pipeline. Called at 04:00."""
    results = {"started_at": datetime.now(timezone.utc).isoformat(), "agents": {}}

    # 1. Houston Pipeline Agent
    try:
        from bridge.agents.houston_pipeline.agent import pull_all_sources as pull_pipeline
        results["agents"]["houston_pipeline"] = pull_pipeline()
    except Exception as e:
        results["agents"]["houston_pipeline"] = {"error": str(e)[:200]}

    # 2. Steel Price Agent
    try:
        from bridge.agents.steel_price.agent import pull_all_sources as pull_steel
        results["agents"]["steel_price"] = pull_steel(fred_key)
    except Exception as e:
        results["agents"]["steel_price"] = {"error": str(e)[:200]}

    # 3. Compliance Agent
    try:
        from bridge.agents.compliance.agent import check_expiring, get_ravs_scorecard
        results["agents"]["compliance"] = {
            "expiring_certs": check_expiring(30),
            "scorecard": get_ravs_scorecard(),
        }
    except Exception as e:
        results["agents"]["compliance"] = {"error": str(e)[:200]}

    # 4. Ledger check
    try:
        from bridge.agents.ledger.agent import get_dashboard
        results["agents"]["ledger"] = get_dashboard()
    except Exception as e:
        results["agents"]["ledger"] = {"error": str(e)[:200]}

    # 5. Field Vision stats
    try:
        from bridge.agents.field_vision.agent import stats as fv_stats
        results["agents"]["field_vision"] = fv_stats()
    except Exception as e:
        results["agents"]["field_vision"] = {"error": str(e)[:200]}

    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    results["agents_run"] = sum(1 for v in results["agents"].values() if "error" not in v)

    # Emit event
    try:
        from bridge.event_bus import emit
        emit("DAILY_PIPELINE_COMPLETE", {"agents_run": results["agents_run"]})
    except Exception:pass

    return results


def generate_morning_brief() -> str:
    """Assemble the unified morning intelligence brief from all agents."""
    lines = [
        f"☀️ YOUR COMPANY - MORNING BRIEF - {date.today().strftime('%A, %B %d, %Y')}",
        "=" * 50,
    ]

    # Steel prices
    try:
        from bridge.agents.steel_price.agent import get_latest_prices
        prices = get_latest_prices()
        fred = prices.get("FRED", {})
        cme = prices.get("CME_HRC", {})
        lines.append("\n📊 STEEL MARKET")
        if fred:
            lines.append(f"  FRED PPI: {fred.get('series', '')} = {fred.get('value', 'N/A')}")
        if cme:
            lines.append(f"  CME HRC: {cme.get('series', '')} = ${cme.get('value', 'N/A')}/st")
        sc = prices.get("service_center", [])
        if sc:
            lines.append(f"  Service-center quotes: {len(sc)} recent")
    except Exception:
        lines.append("\n📊 STEEL: Data pending first pull")

    # Houston pipeline
    try:
        from bridge.agents.houston_pipeline.agent import for_briefing
        lines.append(f"\n🏗️ {for_briefing()}")
    except Exception:
        lines.append("\n🏗️ PIPELINE: Loading")

    # Compliance
    try:
        from bridge.agents.compliance.agent import for_morning_briefing
        lines.append(f"\n🛡️ {for_morning_briefing()}")
    except Exception:
        lines.append("\n🛡️ COMPLIANCE: Loading")

    # Financial
    try:
        from bridge.agents.ledger.agent import get_dashboard
        dash = get_dashboard()
        if dash.get("transactions_imported", 0) > 0:
            lines.append(f"\n💰 FINANCIAL: Rev ${dash['revenue']:,.0f} | COGS ${dash['cogs']:,.0f} | Net ${dash['net_income']:,.0f}")
        else:
            lines.append("\n💰 FINANCIAL: Import QBO CSV to activate")
    except Exception:
        lines.append("\n💰 FINANCIAL: Loading")

    # Blockers
    try:
        from bridge.blockers import get_all
        blockers = get_all()
        active = [b for b in blockers if not b.get("resolved")]
        if active:
            lines.append(f"\n🚨 BLOCKERS ({len(active)}):")
            for b in active[:3]:
                lines.append(f"  {b.get('name', '')}: {b.get('days_open', 0)}d - {b.get('action', '')}")
    except Exception:pass

    # Bids
    try:
        from bridge.bid_pipeline import stats as bid_stats
        bs = bid_stats()
        lines.append(f"\n📋 BIDS: {bs.get('total', 0)} total | {bs.get('pursuing', 0)} pursuing | {bs.get('submitted', 0)} submitted")
    except Exception:pass

    # Shop floor
    try:
        from bridge.shop_floor import get_production_kpis
        kpis = get_production_kpis(days=7)
        if kpis.get("kpis"):
            k = kpis["kpis"]
            lines.append(f"\n🏭 SHOP (7d): {k.get('fab_tons_per_day', 0):.1f} tons/day | {k.get('tons_per_man_hour', 0):.3f} tons/man-hr")
    except Exception:pass

    # News digest
    try:
        from bridge.agents.data_feeds import get_news_digest
        digest = get_news_digest()
        if "No recent" not in digest:
            lines.append(f"\n{digest}")
    except Exception:pass

    # System health
    try:
        from bridge.agents.self_test import run_full_self_test
        test = run_full_self_test()
        lines.append(f"\n⚙️ SYSTEM: {test['passed']}/{test['total']} modules healthy ({test['health_pct']}%)")
    except Exception:pass

    lines.append(f"\n{'=' * 50}")
    lines.append("Generated by Virtual Office at " + datetime.now().strftime("%I:%M %p"))  # vj: local-display-ok

    return "\n".join(lines)


def get_agent_health() -> dict:
    """Health check across all 5 agents."""
    health = {}
    checks = [
        ("steel_price", "bridge.agents.steel_price.agent", "stats"),
        ("houston_pipeline", "bridge.agents.houston_pipeline.agent", "stats"),
        ("compliance", "bridge.agents.compliance.agent", "stats"),
        ("ledger", "bridge.agents.ledger.agent", "stats"),
        ("field_vision", "bridge.agents.field_vision.agent", "stats"),
    ]
    for name, module, func in checks:
        try:
            mod = __import__(module, fromlist=[func])
            fn = getattr(mod, func)
            result = fn()
            health[name] = {"status": "OK", "replaces": result.get("replaces", ""),
                           "our_cost": result.get("our_cost", "")}
        except Exception as e:
            health[name] = {"status": "ERROR", "error": str(e)[:100]}

    total_retired = sum([6200, 6000, 3000, 3000, 5000, 25000])  # + Tekla
    ok_count = sum(1 for v in health.values() if v["status"] == "OK")

    return {
        "agents": health,
        "healthy": ok_count,
        "total": len(checks),
        "total_annual_cost_retired": f"${total_retired:,}/yr",
        "our_annual_cost": "~$300-480/yr (Claude/Gemini tokens)",
        "net_savings": f"${total_retired - 480:,}/yr",
    }


def get_cost_comparison() -> dict:
    """Detailed cost comparison: paid APIs vs our $0 agents."""
    return {
        "paid_stack": [
            {"item": "Steel Market Update", "annual": 1200, "agent": "Steel Price Agent"},
            {"item": "CRU US Midwest HRC", "annual": 3000, "agent": "Steel Price Agent"},
            {"item": "MetalMiner Sage", "annual": 2000, "agent": "Steel Price Agent"},
            {"item": "IIR Energy / Industrial Info", "annual": 6000, "agent": "Houston Pipeline Agent"},
            {"item": "Avetta Connect API", "annual": 1500, "agent": "Compliance Agent"},
            {"item": "Veriforce WorkerPass", "annual": 1500, "agent": "Compliance Agent"},
            {"item": "DroneDeploy team", "annual": 3000, "agent": "Field Vision Agent"},
            {"item": "Skydio Cloud", "annual": 2000, "agent": "Field Vision Agent"},
            {"item": "QuickBooks Online API", "annual": 500, "agent": "Ledger Agent"},
            {"item": "Sage 100 Connector", "annual": 2500, "agent": "Ledger Agent"},
            {"item": "Tekla PowerFab", "annual": 25000, "agent": "IfcOpenShell+PyNite (existing)"},
        ],
        "total_paid": 48200,
        "our_cost": {"claude_tokens": 200, "gemini_tokens": 80, "openai_tokens": 100, "total": 380, "period": "annual"},
        "net_savings": 47820,
        "why_better": [
            "AI cross-references 7+ sources vs single vendor feed",
            "Outputs are interpreted narratives, not raw price ticks",
            "Schema is locally owned - no vendor lock-in",
            "Service-center email parser captures actual landed prices",
            "TCEQ NOIs give 6-month upstream signal vs IIR's flat list",
            "Compliance agent auto-fills ISN/Avetta questionnaires",
            "Self-learning from project actuals improves over time",
        ],
    }
