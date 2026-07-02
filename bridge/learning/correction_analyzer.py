"""
Correction Analyzer - Pattern Detection for Active Learning
=============================================================
Phase 4 of the Sketchdeck parity roadmap (v3.8.0).

Reads the correction lake and detects recurring patterns:
  - Shapes consistently misread from specific PE firms
  - Common OCR errors (e.g., W12X26 misread as W12X2G)
  - Connection types that the AI frequently miscategorizes
  - Camber/stud values that are regularly corrected

When a pattern appears 5+ times, it generates a self_healer rule
automatically. When 500+ corrections accumulate, it generates
updated few-shot prompt examples.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import re
from collections import Counter
from datetime import datetime, timezone

log = logging.getLogger("correction_analyzer")


def analyze_corrections(
    records: list[dict],
    min_pattern_count: int = 5,
) -> dict:
    """Analyze correction records to find recurring patterns.

    Args:
        records: List of correction dicts from the correction lake
        min_pattern_count: Minimum occurrences to qualify as a pattern

    Returns:
        {
            "total_records": int,
            "shape_patterns": [...],   # repeated shape corrections
            "firm_patterns": [...],    # firm-specific errors
            "type_patterns": [...],    # correction type distribution
            "new_rules": [...],        # auto-generated self_healer rules
            "prompt_examples": [...],  # few-shot examples for prompts
            "ready_for_update": bool,  # True if 500+ records
        }
    """
    if not records:
        return {
            "total_records": 0,
            "shape_patterns": [],
            "firm_patterns": [],
            "type_patterns": [],
            "new_rules": [],
            "prompt_examples": [],
            "ready_for_update": False,
        }

    # Count shape correction pairs
    shape_pairs = Counter()
    firm_shape_pairs = Counter()
    type_counts = Counter()

    for rec in records:
        orig = rec.get("original_ai", "").strip().upper()
        corr = rec.get("corrected", "").strip().upper()
        ctype = rec.get("correction_type", "unknown")
        firm = (rec.get("extra", {}) or {}).get("pe_firm", "")

        if orig and corr and orig != corr:
            shape_pairs[(orig, corr)] += 1
            if firm:
                firm_shape_pairs[(firm, orig, corr)] += 1

        type_counts[ctype] += 1

    # Filter to patterns meeting threshold
    shape_patterns = [
        {"original": k[0], "corrected": k[1], "count": v}
        for k, v in shape_pairs.most_common(20)
        if v >= min_pattern_count
    ]

    firm_patterns = [
        {"firm": k[0], "original": k[1], "corrected": k[2], "count": v}
        for k, v in firm_shape_pairs.most_common(20)
        if v >= min_pattern_count
    ]

    type_patterns = [
        {"type": k, "count": v}
        for k, v in type_counts.most_common()
    ]

    # Generate self_healer rules for strong patterns
    new_rules = []
    for sp in shape_patterns:
        if sp["count"] >= min_pattern_count:
            rule = {
                "raw_pattern": sp["original"],
                "corrected": sp["corrected"],
                "count": sp["count"],
                "regex": _build_regex(sp["original"], sp["corrected"]),
                "confidence": min(0.95, 0.5 + sp["count"] * 0.05),
            }
            new_rules.append(rule)

    # Generate few-shot prompt examples from top patterns
    prompt_examples = []
    for sp in shape_patterns[:10]:
        prompt_examples.append({
            "input": f"Drawing label shows: {sp['original']}",
            "output": sp["corrected"],
            "explanation": (
                f"Corrected {sp['count']} times. "
                f"Common OCR/AI misread."
            ),
        })

    return {
        "total_records": len(records),
        "shape_patterns": shape_patterns,
        "firm_patterns": firm_patterns,
        "type_patterns": type_patterns,
        "new_rules": new_rules,
        "prompt_examples": prompt_examples,
        "ready_for_update": len(records) >= 500,
    }


def apply_rules_to_self_healer(new_rules: list[dict]) -> dict:
    """Push discovered patterns into the self_healer as firm-specific rules.

    Args:
        new_rules: List of rule dicts from analyze_corrections()

    Returns:
        {"applied": int, "skipped": int, "errors": list}
    """
    applied = 0
    skipped = 0
    errors = []

    try:
        from bridge.drawing_intel.self_healer import record_correction
    except ImportError as e:
        return {"applied": 0, "skipped": 0,
                "errors": [f"Cannot import self_healer: {e}"]}

    for rule in new_rules:
        try:
            record_correction(
                raw_text=rule["raw_pattern"],
                corrected_shape=rule["corrected"],
                pe_firm="",  # auto-discovered, not firm-specific
                source_drawing="correction_analyzer_auto",
            )
            applied += 1
        except Exception as e:
            errors.append(f"Failed to apply rule {rule['raw_pattern']}: {e}")
            skipped += 1

    log.info(f"Applied {applied} self_healer rules, skipped {skipped}")
    return {"applied": applied, "skipped": skipped, "errors": errors}


def _build_regex(original: str, corrected: str) -> str:
    """Build a regex pattern that catches common OCR-like substitutions.

    Examples:
        W12X2G -> W12X26 (G misread as 6)
        W14X2Z -> W14X22 (Z misread as 2)
    """
    if not original or not corrected:
        return ""

    # Find character-level differences
    pattern = ""
    max_len = max(len(original), len(corrected))
    for i in range(max_len):
        o_ch = original[i] if i < len(original) else ""
        c_ch = corrected[i] if i < len(corrected) else ""
        if o_ch == c_ch:
            pattern += re.escape(o_ch)
        else:
            # Allow either character at this position
            if o_ch and c_ch:
                pattern += f"[{re.escape(o_ch)}{re.escape(c_ch)}]"
            elif o_ch:
                pattern += f"{re.escape(o_ch)}?"
            else:
                pattern += f"{re.escape(c_ch)}?"

    return f"^{pattern}$"


def generate_monthly_digest(records: list[dict]) -> str:
    """Generate a human-readable digest of correction patterns.

    Used for the monthly report to Joseph/Owner.
    """
    if not records:
        return "No corrections recorded this period."

    analysis = analyze_corrections(records, min_pattern_count=3)

    lines = [
        f"Correction Digest: {analysis['total_records']} total corrections",
        "",
    ]

    if analysis["shape_patterns"]:
        lines.append("Recurring shape corrections:")
        for sp in analysis["shape_patterns"][:10]:
            lines.append(
                f"  {sp['original']} -> {sp['corrected']} "
                f"({sp['count']} times)"
            )
        lines.append("")

    if analysis["firm_patterns"]:
        lines.append("Firm-specific patterns:")
        for fp in analysis["firm_patterns"][:5]:
            lines.append(
                f"  {fp['firm']}: {fp['original']} -> {fp['corrected']} "
                f"({fp['count']} times)"
            )
        lines.append("")

    if analysis["type_patterns"]:
        lines.append("Correction types:")
        for tp in analysis["type_patterns"]:
            lines.append(f"  {tp['type']}: {tp['count']}")
        lines.append("")

    if analysis["ready_for_update"]:
        lines.append(
            "500+ corrections accumulated. "
            "Prompt update recommended."
        )

    return "\n".join(lines)
