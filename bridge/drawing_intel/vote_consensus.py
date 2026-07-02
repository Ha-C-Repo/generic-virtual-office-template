"""Three-pass vision voting and consensus logic.

All functions are module-level (no nested classes) per PyInstaller rule.
"""
from __future__ import annotations


def normalize_member_key(member: dict) -> tuple:
    """Return a canonical key for deduplicating members across passes.

    Key: (shape_lower, mark_lower, grid_anchor_lower)
    """
    shape = str(member.get("shape") or member.get("section") or "").strip().upper()
    mark = str(member.get("mark") or "").strip().upper()
    anchor = str(member.get("grid_anchor") or member.get("tile_id") or "").strip().upper()
    return (shape, mark, anchor)


def vote_members(pass_results: list[list[dict]],
                 threshold: int = 2) -> dict:
    """Aggregate members from multiple vision passes by majority vote.

    Args:
        pass_results: list of pass outputs, each a list of member dicts
        threshold:    minimum number of passes that must agree to accept

    Returns dict with keys:
        "accepted":            members reaching threshold
        "flagged":             members below threshold (needs human review)
        "disagreement_report": details on each disputed member
    """
    votes: dict[tuple, list[dict]] = {}
    for pass_idx, members in enumerate(pass_results):
        for m in members:
            key = normalize_member_key(m)
            if key not in votes:
                votes[key] = []
            votes[key].append({**m, "_pass": pass_idx})

    accepted = []
    flagged_keys = []
    for key, instances in votes.items():
        if len(instances) >= threshold:
            best = instances[0]
            best["_vote_count"] = len(instances)
            accepted.append(best)
        else:
            flagged_keys.append(key)

    flagged = [votes[k][0] for k in flagged_keys]
    report = build_disagreement_report(
        {k: votes[k] for k in flagged_keys}
    )
    return {
        "accepted": accepted,
        "flagged": flagged,
        "disagreement_report": report,
    }


def build_disagreement_report(disputed: dict[tuple, list[dict]]) -> list[dict]:
    """Build a human-readable report for members that did not reach consensus.

    Args:
        disputed: mapping of normalized_key -> list of member dicts from each pass

    Returns list of report entries, one per disputed member.
    """
    report = []
    for key, instances in disputed.items():
        shape, mark, anchor = key
        passes_seen = sorted({m.get("_pass", "?") for m in instances})
        report.append({
            "shape": shape,
            "mark": mark,
            "grid_anchor": anchor,
            "vote_count": len(instances),
            "passes_seen": passes_seen,
            "note": "Below consensus threshold - human review required",
            "raw_instances": instances,
        })
    return report


def build_vote_manifest(accepted: list[dict],
                        flagged: list[dict],
                        report: list[dict],
                        pass_metadata: list[dict]) -> dict:
    """Assemble the final vote manifest written by project_syncer.

    Args:
        accepted:       members that reached consensus threshold
        flagged:        members below threshold
        report:         disagreement report from build_disagreement_report()
        pass_metadata:  list of per-pass info dicts (pass_id, dpi, tile_count, model)

    Returns manifest dict suitable for JSON serialisation.
    """
    import datetime
    return {
        "schema_version": "1.0",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "pass_count": len(pass_metadata),
        "pass_metadata": pass_metadata,
        "accepted_count": len(accepted),
        "flagged_count": len(flagged),
        "accepted": accepted,
        "flagged": flagged,
        "disagreement_report": report,
    }
