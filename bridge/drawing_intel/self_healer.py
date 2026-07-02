"""
Drawing Intel: Self-Healing Parser
====================================
When the system encounters non-standard shape notations (e.g. "82-W14"
instead of "W14X82"), it learns the pattern and auto-generates a
normalization rule for that PE firm.

After 3 corrections from the same firm, a firm-specific rule is created
and applied automatically to all future drawings.

Storage: SQLite table in data/learning_store.db
"""

import logging
import re
import sqlite3
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "learning_store.db"


def _ensure_db():
    """Create learning_store tables if they don't exist."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS shape_corrections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_text TEXT NOT NULL,
        corrected_shape TEXT NOT NULL,
        pe_firm TEXT DEFAULT '',
        project TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS firm_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pe_firm TEXT NOT NULL,
        pattern TEXT NOT NULL,
        replacement TEXT NOT NULL,
        confidence INTEGER DEFAULT 0,
        auto_generated INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(pe_firm, pattern)
    )""")
    conn.commit()
    return conn


def record_correction(raw_text: str, corrected_shape: str,
                      pe_firm: str = "", project: str = "") -> dict:
    """Record a shape correction. After 3 corrections of the same
    pattern from the same firm, auto-generate a normalization rule.

    Args:
        raw_text: What the AI extracted (e.g. "82-W14")
        corrected_shape: What it should be (e.g. "W14X82")
        pe_firm: PE firm name for firm-specific rules
        project: Project name for context

    Returns:
        {recorded: True, auto_rule_created: bool, ...}
    """
    conn = _ensure_db()

    # Record the correction
    conn.execute(
        "INSERT INTO shape_corrections (raw_text, corrected_shape, pe_firm, project) "
        "VALUES (?, ?, ?, ?)",
        (raw_text, corrected_shape, pe_firm, project)
    )
    conn.commit()

    # Check if we have 3+ corrections of the same pattern from this firm
    auto_rule = False
    if pe_firm:
        count = conn.execute(
            "SELECT COUNT(*) FROM shape_corrections "
            "WHERE raw_text=? AND corrected_shape=? AND pe_firm=?",
            (raw_text, corrected_shape, pe_firm)
        ).fetchone()[0]

        if count >= 3:
            # Auto-generate a normalization rule
            pattern = _generate_regex_pattern(raw_text, corrected_shape)
            if pattern:
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO firm_rules "
                        "(pe_firm, pattern, replacement, confidence, auto_generated) "
                        "VALUES (?, ?, ?, ?, 1)",
                        (pe_firm, pattern, corrected_shape, count)
                    )
                    conn.commit()
                    auto_rule = True
                    log.info(f"Auto-generated rule for {pe_firm}: "
                            f"{raw_text} -> {corrected_shape}")
                except Exception as e:
                    log.warning(f"Failed to create auto-rule: {e}")

    conn.close()

    return {
        "recorded": True,
        "raw_text": raw_text,
        "corrected_shape": corrected_shape,
        "pe_firm": pe_firm,
        "auto_rule_created": auto_rule,
    }


def normalize_with_firm_rules(raw_shape: str, pe_firm: str = "") -> dict:
    """Normalize a shape designation using firm-specific rules first,
    then fall back to general normalization.

    Args:
        raw_shape: Raw text from AI extraction
        pe_firm: PE firm name to check for firm-specific rules

    Returns:
        {original, normalized, method, rule_used}
    """
    # vj: parity-ok (pass 10g classified: mixed J=0.62; needs manual audit)
    conn = _ensure_db()

    # Check firm-specific rules first
    if pe_firm:
        rules = conn.execute(
            "SELECT pattern, replacement, confidence FROM firm_rules "
            "WHERE pe_firm=? ORDER BY confidence DESC",
            (pe_firm,)
        ).fetchall()

        for pattern, replacement, confidence in rules:
            try:
                if re.match(pattern, raw_shape, re.IGNORECASE):
                    conn.close()
                    return {
                        "original": raw_shape,
                        "normalized": replacement,
                        "method": "firm_rule",
                        "pe_firm": pe_firm,
                        "confidence": confidence,
                    }
            except re.error:
                continue

    # Check correction history for exact matches
    row = conn.execute(
        "SELECT corrected_shape, COUNT(*) as cnt FROM shape_corrections "
        "WHERE raw_text=? GROUP BY corrected_shape ORDER BY cnt DESC LIMIT 1",
        (raw_shape,)
    ).fetchone()

    conn.close()

    if row:
        return {
            "original": raw_shape,
            "normalized": row[0],
            "method": "history_match",
            "occurrences": row[1],
        }

    # Fall back to general normalization
    from bridge.aisc_validator import _normalize_shape
    normalized = _normalize_shape(raw_shape)
    return {
        "original": raw_shape,
        "normalized": normalized,
        "method": "general",
    }


def get_firm_rules(pe_firm: str = "") -> dict:
    """List all firm-specific normalization rules."""
    conn = _ensure_db()

    if pe_firm:
        rows = conn.execute(
            "SELECT pe_firm, pattern, replacement, confidence, auto_generated "
            "FROM firm_rules WHERE pe_firm=?", (pe_firm,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT pe_firm, pattern, replacement, confidence, auto_generated "
            "FROM firm_rules ORDER BY pe_firm"
        ).fetchall()

    conn.close()

    return {
        "rules": [
            {"pe_firm": r[0], "pattern": r[1], "replacement": r[2],
             "confidence": r[3], "auto_generated": bool(r[4])}
            for r in rows
        ],
        "total": len(rows),
    }


def _generate_regex_pattern(raw: str, corrected: str) -> Optional[str]:
    r"""Generate a regex pattern that maps raw notation to corrected shape.

    Examples:
        "82-W14" -> r"^(\d+)-W(\d+)$"  (reversed W-shape)
        "W14 82" -> r"^W(\d+)\s+(\d+)$"  (missing X)
    """
    # Reversed notation: "82-W14" → "W14X82"
    m = re.match(r'^(\d+)[- ](W\d+)$', raw)
    if m:
        return r'^(\d+)[- ](W\d+)$'

    # Missing X separator: "W14 82"
    m = re.match(r'^(W\d+)\s+(\d+)$', raw)
    if m:
        return r'^(W\d+)\s+(\d+)$'

    # Lowercase: "w14x82"
    if raw.lower() == corrected.lower():
        return None  # handled by general normalization

    # Dot separator: "W14.82"
    m = re.match(r'^(W\d+)\.(\d+)$', raw)
    if m:
        return r'^(W\d+)\.(\d+)$'

    return None
