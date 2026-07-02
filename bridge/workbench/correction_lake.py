"""
Correction Lake - Append-Only Storage for AI Takeoff Corrections
=================================================================
Phase 3 of the Sketchdeck parity roadmap (v3.7.0).

Stores every manual correction Joseph or Owner makes in the Review
Workbench. Each record captures the original AI detection and the
user's correction. When the lake reaches 500+ records, it flags for
few-shot prompt update (Phase 4 active learning).

Uses JSONL (one JSON object per line) for safe append-only writes.
No read-modify-write cycle. Safe for concurrent access from the
workbench and background processes.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("correction_lake")

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "corrections"
_LAKE_FILE = _DATA_DIR / "correction_lake.jsonl"


def _ensure_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def record_correction(
    project_id: str,
    original_ai: str,
    corrected: str,
    source_drawing: str = "",
    page_num: int = 0,
    confidence: float = 0.0,
    user: str = "joseph",
    correction_type: str = "shape",
    extra: Optional[dict] = None,
) -> dict:
    """Append a correction record to the lake.

    Args:
        project_id: Bid number or project ID
        original_ai: What the AI detected (e.g., "W12X26")
        corrected: What the user corrected it to (e.g., "W12X30")
        source_drawing: Sheet ID or filename
        page_num: 0-based page number
        confidence: Original AI confidence (0.0-1.0)
        user: Who made the correction
        correction_type: "shape", "quantity", "mark", "connection", "camber"
        extra: Any additional metadata

    Returns:
        {"saved": bool, "record_count": int, "needs_prompt_update": bool}
    """
    _ensure_dir()

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_id": str(project_id),
        "original_ai": str(original_ai),
        "corrected": str(corrected),
        "source_drawing": str(source_drawing),
        "page_num": int(page_num),
        "confidence": float(confidence),
        "user": str(user),
        "correction_type": str(correction_type),
    }
    if extra and isinstance(extra, dict):
        record["extra"] = extra

    try:
        with open(_LAKE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        log.error(f"Failed to write correction: {e}")
        return {"saved": False, "record_count": count_records(),
                "needs_prompt_update": False}

    count = count_records()
    needs_update = count >= 500

    if needs_update:
        log.info(f"Correction lake has {count} records. Flagging for prompt update.")

    return {
        "saved": True,
        "record_count": count,
        "needs_prompt_update": needs_update,
    }


def count_records() -> int:
    """Count total correction records."""
    if not _LAKE_FILE.exists():
        return 0
    try:
        with open(_LAKE_FILE, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def get_records(
    limit: int = 100,
    correction_type: str = "",
    project_id: str = "",
) -> list[dict]:
    """Read correction records with optional filtering.

    Returns most recent records first (tail of file).
    """
    if not _LAKE_FILE.exists():
        return []

    records = []
    try:
        with open(_LAKE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if correction_type and rec.get("correction_type") != correction_type:
                    continue
                if project_id and rec.get("project_id") != project_id:
                    continue
                records.append(rec)
    except Exception as e:
        log.error(f"Failed to read corrections: {e}")

    # Most recent first, limited
    return records[-limit:][::-1]


def get_pattern_summary() -> dict:
    """Analyze correction patterns for active learning.

    Returns summary of most common corrections, grouped by type.
    """
    records = get_records(limit=10000)
    if not records:
        return {"total": 0, "patterns": [], "needs_prompt_update": False}

    # Group by (original, corrected) pairs
    pairs: dict[tuple, int] = {}
    by_type: dict[str, int] = {}
    for rec in records:
        key = (rec.get("original_ai", ""), rec.get("corrected", ""))
        pairs[key] = pairs.get(key, 0) + 1
        ct = rec.get("correction_type", "unknown")
        by_type[ct] = by_type.get(ct, 0) + 1

    # Sort by frequency
    top_patterns = sorted(pairs.items(), key=lambda x: x[1], reverse=True)[:20]
    patterns = [
        {"original": k[0], "corrected": k[1], "count": v}
        for k, v in top_patterns
    ]

    return {
        "total": len(records),
        "by_type": by_type,
        "patterns": patterns,
        "needs_prompt_update": len(records) >= 500,
    }


def clear_lake() -> dict:
    """Clear all correction records. Use with caution."""
    if _LAKE_FILE.exists():
        _LAKE_FILE.unlink()
    return {"cleared": True, "record_count": 0}
