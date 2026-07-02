"""
Your Company Virtual Office - Dual-Account Token Router

Two Claude subscriptions available:
  1. Joseph's API account - for heavy processing (takeoff, batch, background agents)
  2. the Owner's Claude app - for conversational queries via MCP server

Routing logic:
  HEAVY (API account): AI takeoff, document processing, batch steel pulls,
                       daily agent pipeline, spec parsing, BOM generation
  LIGHT (Claude app):  Morning brief, bid pipeline query, compliance check,
                       knowledge graph search, production log, price lookup

This maximizes token efficiency by using each subscription for what it's best at.
"""

import json, sqlite3, threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from collections import defaultdict

_DB = Path(__file__).resolve().parent.parent / "data" / "token_usage.db"
_lock = threading.Lock()

# Classification of tasks by weight
HEAVY_TASKS = {
    "takeoff_from_pdf", "compose_full_bid", "auto_respond_to_bid",
    "parse_spec", "extract_submittals", "run_takeoff",
    "pull_steel_prices", "pull_houston_pipeline", "run_daily_agents",
    "pull_rss_news", "fetch_price_emails", "parse_price_sheet",
    "generate_brief_context",
    # Saturday-6 additions: scan tasks that batch over many records
    "M365_mail_scan", "scan_for_bids", "process_drone_images",
    "auto_process_drawing", "audit_spec_book", "backtest_project",
}

LIGHT_TASKS = {
    "get_morning_brief", "get_pipeline", "get_latest_steel_prices",
    "get_best_steel_price", "get_ravs_scorecard", "check_expiring_certs",
    "get_calibrated_estimate", "get_production_board", "log_production",
    "get_cash_flow_projection", "knowledge_query", "get_financial_dashboard",
    "get_ar_aging", "get_agent_health", "run_self_test",
    "get_project_pipeline", "get_houston_news", "get_chain_capability",
    "analyze_bid", "match_opportunity", "verify_hash_chain",
    "get_shop_kpis", "get_production_board", "get_event_log",
    # Saturday-6 additions: conversational reads that don't batch
    "compliance_check", "morning_briefing", "morning_brief",
    "list_blockers", "blockers_summary", "feature_status",
    "list_bids", "get_bid", "bid_pipeline_summary",
    "aisc_lookup", "validate_shape", "bolt_count", "steel_weight",
    "hours_estimate", "labor_cost", "bid_total", "margin_scenario",
    # Content generation - Owner-side light tasks
    "linkedin_post", "draft_linkedin_post", "linkedin_list_formats",
    "linkedin_fingerprint_check", "draft_outreach", "draft_refinery_outreach",
}

# Saturday-6: aliases - common alternate names users type that should
# route the same as their canonical version. Resolved before lookup.
TASK_ALIASES = {
    "morning_briefing": "get_morning_brief",
    "morning_brief":    "get_morning_brief",
    "compliance":       "compliance_check",
    "compliance_status": "compliance_check",
    "scan_bids":        "scan_for_bids",
    "mail_scan":        "M365_mail_scan",
    "bid_summary":      "bid_pipeline_summary",
}

# Account configuration
ACCOUNTS = {
    "joseph_api": {
        "name": "Joseph's API Account",
        "type": "api",
        "handles": "heavy",
        "note": "Anthropic API - pay-per-token, best for batch/background",
    },
    "owner_app": {
        "name": "the Owner's Claude App",
        "type": "claude_app",
        "handles": "light",
        "note": "Claude desktop subscription - flat rate, best for conversation",
    },
}


def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS token_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account TEXT NOT NULL, task TEXT NOT NULL,
            task_weight TEXT DEFAULT 'light',
            est_tokens INTEGER DEFAULT 0,
            logged_at TEXT NOT NULL
        );
    """)
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_token_account ON token_log(account)")
    except Exception:
        pass  # column may not exist in older schema
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_token_date ON token_log(logged_at)")
    except Exception:
        pass  # column may not exist in older schema
    c.commit(); c.close()
_init()


def route_task(task_name: str) -> dict:
    """Determine which account should handle this task.

    Saturday-6: resolves aliases (e.g. 'morning_briefing' -> 'get_morning_brief')
    before lookup, so callers can use natural names without breaking routing.
    """
    # Resolve alias if present
    canonical = TASK_ALIASES.get(task_name, task_name)
    if canonical in HEAVY_TASKS:
        account = "joseph_api"
        weight = "heavy"
    elif canonical in LIGHT_TASKS:
        account = "owner_app"
        weight = "light"
    else:
        # Unknown tasks default to API (safer for unexpected heavy loads)
        account = "joseph_api"
        weight = "unknown"

    return {
        "task": task_name,
        "canonical": canonical,
        "routed_to": account,
        "account_info": ACCOUNTS[account],
        "weight": weight,
    }


def log_usage(account: str, task: str, est_tokens: int = 0):
    """Log token usage for tracking."""
    weight = "heavy" if task in HEAVY_TASKS else "light"
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        c = _conn()
        c.execute("INSERT INTO token_log (account,task,task_weight,est_tokens,logged_at) VALUES (?,?,?,?,?)",
                  (account, task, weight, est_tokens, now))
        c.commit(); c.close()


def get_usage_report(days: int = 30) -> dict:
    """Token usage report by account and task weight."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()  # vj: duration-math
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM token_log WHERE logged_at >= ?", (cutoff,)).fetchall()
        c.close()

    by_account = defaultdict(lambda: {"count": 0, "est_tokens": 0, "tasks": defaultdict(int)})
    for r in rows:
        acct = r["account"]
        by_account[acct]["count"] += 1
        by_account[acct]["est_tokens"] += r["est_tokens"]
        by_account[acct]["tasks"][r["task"]] += 1

    return {
        "period_days": days,
        "accounts": dict(by_account),
        "total_calls": len(rows),
        "routing_efficiency": {
            "heavy_to_api": sum(1 for r in rows if r["task_weight"] == "heavy" and r["account"] == "joseph_api"),
            "light_to_app": sum(1 for r in rows if r["task_weight"] == "light" and r["account"] == "owner_app"),
        },
    }


def get_routing_table() -> dict:
    """Show the complete task routing table."""
    return {
        "heavy_tasks": {t: "joseph_api" for t in sorted(HEAVY_TASKS)},
        "light_tasks": {t: "owner_app" for t in sorted(LIGHT_TASKS)},
        "heavy_count": len(HEAVY_TASKS),
        "light_count": len(LIGHT_TASKS),
        "accounts": ACCOUNTS,
        "strategy": "Heavy processing (takeoff, batch agents, document parsing) → Joseph's API account. "
                    "Conversational queries (briefs, lookups, logs) → the Owner's Claude app subscription. "
                    "This maximizes value from both subscriptions.",
    }
