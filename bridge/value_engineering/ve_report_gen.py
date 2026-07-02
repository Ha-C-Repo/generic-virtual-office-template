"""Value engineering report generator.

Combines section optimization and connection standardization into a
single VE proposal summary. The frontend renders this as a card on the
bid screen. The full report can be exported via calc_pack_gen.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from datetime import datetime, timezone

from .section_optimizer import optimize_project
from .connection_standardizer import analyze_bolt_patterns

log = logging.getLogger(__name__)


def generate_ve_report(
    members: list[dict],
    connections: list[dict],
    base_bid_usd: float = 0.0,
    material_cost_per_lb: float = 0.55,
    project_name: str = "",
) -> dict:
    """Generate a complete VE proposal.

    Args:
        members: Takeoff member list.
        connections: Connection list with bolt data.
        base_bid_usd: Original bid amount for comparison.
        material_cost_per_lb: Current material cost.
        project_name: For the report header.

    Returns:
        {
            "project_name": str,
            "base_bid_usd": float,
            "ve_bid_usd": float,
            "total_savings_usd": float,
            "savings_pct": float,
            "section_results": dict,
            "bolt_results": dict,
            "summary_lines": list[str],
            "pe_required": bool (always True),
            "generated_at": str,
        }
    """
    section_results = optimize_project(members, material_cost_per_lb)
    bolt_results = analyze_bolt_patterns(connections)

    total_savings = (section_results["total_cost_savings_usd"]
                     + bolt_results["savings_usd"])
    ve_bid = base_bid_usd - total_savings if base_bid_usd > 0 else 0.0
    savings_pct = (total_savings / base_bid_usd * 100
                   if base_bid_usd > 0 else 0.0)

    lines = []
    lines.append(f"VALUE ENGINEERING PROPOSAL: {project_name}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")  # vj: local-display-ok
    lines.append("")

    if base_bid_usd > 0:
        lines.append(f"Base bid: ${base_bid_usd:,.0f}")
        lines.append(f"VE alternate: ${ve_bid:,.0f}")
        lines.append(f"Savings: ${total_savings:,.0f} ({savings_pct:.1f}%)")
    else:
        lines.append(f"Total VE savings: ${total_savings:,.0f}")

    lines.append("")
    lines.append(f"Section substitutions: "
                 f"{section_results['members_optimizable']} of "
                 f"{section_results['members_checked']} members")
    lines.append(f"Weight savings: "
                 f"{section_results['total_weight_savings_lbs']:,.0f} lbs")
    lines.append(f"Material savings: "
                 f"${section_results['total_cost_savings_usd']:,.0f}")
    lines.append("")
    lines.append(f"Bolt standardization: {bolt_results['proposal']}")
    lines.append("")
    lines.append("PE APPROVAL REQUIRED for all substitutions.")

    return {
        "success": True,
        "project_name": project_name,
        "base_bid_usd": base_bid_usd,
        "ve_bid_usd": round(ve_bid, 2),
        "total_savings_usd": round(total_savings, 2),
        "savings_pct": round(savings_pct, 1),
        "section_results": section_results,
        "bolt_results": bolt_results,
        "summary_lines": lines,
        "pe_required": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
