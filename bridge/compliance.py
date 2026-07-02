"""
Your Company Virtual Office - Compliance Module

Re-exports compliance functions from the compliance agent.
"""

from bridge.agents.compliance.agent import (
    get_ravs_scorecard,
    check_expiring,
    stats,
)

# Aliases for bridge compatibility
check_expiring_certs = check_expiring


def _grade_from_pct(pct: float) -> str:
    if pct >= 90: return "A"
    if pct >= 80: return "B"
    if pct >= 70: return "C"
    if pct >= 60: return "D"
    return "F"


def run_compliance_check(project_name: str = "", emr_threshold: float = 1.0) -> dict:
    """Run compliance pre-flight check for a project.

    MC-03 fix: escalated blockers (14+ days open) now lower the headline
    grade. Each escalated blocker subtracts 7 percentage points. This
    prevents the system from reporting "A" while critical compliance
    items (EMR letter, ISN access) have been blocked for over two weeks.
    """
    scorecard = get_ravs_scorecard()
    expiring = check_expiring(30)

    raw_pct = scorecard.get("overall_pct", 0)
    raw_grade = scorecard.get("overall_grade", "?")

    # Pull escalated blockers and penalize the grade.
    # MC-07: penalty is now severity-weighted (high=15, med=7, low=3)
    # rather than flat 7pp per blocker. Cap at -30 so a single snapshot
    # cannot push a real B-grade shop into failure territory.
    escalated_blockers = []
    blocker_penalty = 0.0
    try:
        from bridge.blockers import get_escalated, severity_penalty
        escalated_blockers = get_escalated()
        blocker_penalty = min(sum(severity_penalty(b) for b in escalated_blockers), 30.0)
    except Exception:
        pass

    adjusted_pct = max(0.0, raw_pct - blocker_penalty)
    adjusted_grade = _grade_from_pct(adjusted_pct)

    # Mutate the scorecard dict so downstream consumers see the adjusted view.
    scorecard_adjusted = dict(scorecard)
    scorecard_adjusted["overall_pct"] = round(adjusted_pct, 1)
    scorecard_adjusted["overall_grade"] = adjusted_grade
    scorecard_adjusted["raw_pct"] = raw_pct
    scorecard_adjusted["raw_grade"] = raw_grade
    scorecard_adjusted["blocker_penalty"] = blocker_penalty
    scorecard_adjusted["escalated_blocker_count"] = len(escalated_blockers)
    scorecard_adjusted["escalated_blocker_names"] = [b.get("name", "?") for b in escalated_blockers]
    if escalated_blockers:
        scorecard_adjusted["grade_note"] = (
            f"Grade lowered from {raw_grade} ({raw_pct}%) to {adjusted_grade} "
            f"({adjusted_pct:.1f}%) due to {len(escalated_blockers)} escalated blocker(s)."
        )

    return {
        "scorecard": scorecard_adjusted,
        "expiring_certs": expiring,
        "project": project_name,
        "emr_threshold": emr_threshold,
        "status": adjusted_grade,
        "escalated_blockers": [b.get("name", "?") for b in escalated_blockers],
    }


__all__ = ['run_compliance_check', 'get_ravs_scorecard', 'check_expiring_certs', 'stats']
