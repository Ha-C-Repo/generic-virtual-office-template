"""
Output Proofreader
===================
Last gate before any AI-touched content reaches the user. Catches:

  • Generated DOCX/PDF/HTML files: parses them back, extracts numeric claims,
    cross-checks against the verified facts manifest. Mismatch → refuse to deliver.
  • Plain-text responses: scans for unsourced numbers (anything matching
    a number pattern that isn't tagged with a citation).
  • Email drafts (especially outreach): in addition to the above, runs the
    "preview-only" gate - the proofreader is the second line of defense
    after the MCP server's force-flag.

Hard rule: if the proofreader finds an unverifiable number, the call returns
with status='BLOCKED'. The caller must address findings before delivery.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from .intake import FactsManifest


@dataclass
class ProofreadReport:
    status:    str          # CLEAR | WARN | BLOCKED
    issues:    list[str] = field(default_factory=list)
    verified_numbers: list[dict] = field(default_factory=list)
    unverified_numbers: list[dict] = field(default_factory=list)
    summary:   str = ""


# Numbers we ALWAYS allow without provenance - context-free constants
_WHITELIST_NUMBERS = {
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    100, 1000,    # percentage/scaling base
    24, 60, 365,  # time units
    40,           # FLSA threshold
    1.5,          # FLSA multiplier
}

# Patterns that look like numbers in prose.
# Use lookahead/lookbehind to require word boundaries on BOTH sides - must not
# be embedded in larger tokens like "A992" or "ISO9001". The lookbehind for
# digits prevents partial matches inside multi-digit tokens.
_NUMBER_RE = re.compile(r"(?<![A-Za-z_0-9])(\$?-?\d{1,3}(?:,\d{3})*(?:\.\d+)?)(?![A-Za-z_0-9])")


def _spans_covered_by_string_facts(text: str, manifest: FactsManifest) -> list[tuple[int, int]]:
    """Find every character range in `text` that matches a string-valued fact.

    The proofreader's number regex doesn't know that "15" inside "May 15, 2026"
    is part of a date - it just sees a digit. But if the manifest carries
    `bid_due_date='May 15, 2026'` as a string fact, the entire span is
    provenance-attested and any number falling inside it is already verified.

    We scan all string-valued facts (dates, names, addresses, designations)
    and collect their match positions in the text. Numeric facts are handled
    by the existing has_provenance() path and don't need masking here.

    Returns:
        Sorted list of (start, end) char-offset tuples - possibly overlapping,
        which is fine because we only need a "is position p inside any span"
        test, not span arithmetic.
    """
    spans: list[tuple[int, int]] = []
    for fact in manifest.facts:
        # Numeric facts are handled by has_provenance - skip here
        try:
            float(fact.value)
            continue
        except (TypeError, ValueError):
            pass
        s = str(fact.value).strip()
        # Length guard with two tiers:
        #
        #   • len(s) <= 1 → always skip. A 1-char fact like phase="A"
        #     would mask every "A" in the output - too aggressive, and
        #     1-char strings can't carry meaningful provenance anyway.
        #
        #   • 2-3 char strings → only allow if the string contains at
        #     least one alphabetic character. This admits real-world
        #     short codes like "W14", "B-7", "A1B", "S-1", "A.5" (WBS
        #     codes, member tags, structural designations, grid lines)
        #     while rejecting punctuated numeric fragments like "1-7"
        #     or "(7)" that don't represent real identifiers.
        #
        # Pure numeric strings ("3.2", "247") were already filtered by
        # the float() check above. A 2-3 char string with at least one
        # letter is a code-style identifier and safe to mask - even if
        # the digits inside were extractable (today's regex already
        # excludes digits that touch letters, but future regex tweaks
        # shouldn't be able to silently break this protection).
        if len(s) <= 1:
            continue
        if len(s) < 4 and not any(c.isalpha() for c in s):
            continue
        # Find every occurrence of the fact value in the output text.
        # Case-insensitive so "May 15, 2026" matches "may 15, 2026" too.
        start = 0
        s_lower = s.lower()
        text_lower = text.lower()
        while True:
            idx = text_lower.find(s_lower, start)
            if idx < 0:
                break
            spans.append((idx, idx + len(s)))
            start = idx + 1
    spans.sort()
    return spans


def _is_position_covered(pos: int, spans: list[tuple[int, int]]) -> bool:
    """True if `pos` falls inside any (start, end) span. O(n) - fine for our scale."""
    return any(start <= pos < end for start, end in spans)


def _extract_numbers_from_text(text: str) -> list[tuple[str, int]]:
    """Find every numeric substring + its character offset."""
    out = []
    for m in _NUMBER_RE.finditer(text):
        raw = m.group(1).replace(",", "").lstrip("$").lstrip("-")
        try:
            v = float(raw)
            if v.is_integer():
                v = int(v)
            out.append((v, m.start()))
        except ValueError:
            continue
    return out


def _read_docx(path: Path) -> str:
    try:
        import docx   # python-docx
    except ImportError:
        return ""
    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def _read_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""
    text_parts = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
    except Exception:
        return ""
    return "\n".join(text_parts)


def proofread_output(
    content:   str | Path,
    manifest:  FactsManifest,
    kind:      str = "text",        # text | docx | pdf | email | outreach
    is_outreach_preview: bool = False,
    extra_verified_values: list[float] | None = None,
) -> ProofreadReport:
    """Final pre-delivery check. Returns CLEAR/WARN/BLOCKED.

    extra_verified_values: numeric values the verifier (stage 4) already
    approved - typically derivations like 26 = 8+12+6 that aren't direct
    facts in the manifest but were proven correct. Without this, the
    proofreader would flag legitimate verified derivations as unsourced.
    """
    report = ProofreadReport(status="CLEAR")
    extras = set(extra_verified_values or [])

    # 1. Resolve content to plain text
    if isinstance(content, Path):
        if kind == "docx" or content.suffix.lower() == ".docx":
            text = _read_docx(content)
        elif kind == "pdf" or content.suffix.lower() == ".pdf":
            text = _read_pdf(content)
        else:
            text = content.read_text(encoding="utf-8", errors="ignore")
        if not text:
            report.status = "BLOCKED"
            report.issues.append(f"Could not read {content} for proofreading "
                                  f"(library missing or parse error). Refusing to deliver "
                                  f"unparseable file.")
            report.summary = "BLOCKED: file unreadable for proofread"
            return report
    else:
        text = str(content)

    # 2. Outreach-specific check: must be flagged preview unless explicitly approved
    if kind == "outreach" and not is_outreach_preview:
        report.status = "BLOCKED"
        report.issues.append("Outreach content was not flagged as preview - refusing "
                              "to deliver. Outreach must go through confirm_refinery_outreach() "
                              "with explicit user approval.")
        report.summary = "BLOCKED: outreach without preview flag"
        return report

    # 3. Numeric content check
    # Build "covered spans" from string-valued facts (dates, names, addresses).
    # A number whose offset falls inside a string-fact span is provenance-
    # attested by the surrounding string and must not be flagged.
    string_fact_spans = _spans_covered_by_string_facts(text, manifest)

    numbers = _extract_numbers_from_text(text)
    for value, pos in numbers:
        if value in _WHITELIST_NUMBERS:
            continue
        # Numbers inside a string-fact span (e.g. "15" inside "May 15, 2026"
        # when bid_due_date='May 15, 2026' is a fact) are covered by that
        # fact's provenance. Record them as verified-by-string-fact.
        if _is_position_covered(pos, string_fact_spans):
            report.verified_numbers.append({
                "value": value, "matched_fact": "covered_by_string_fact",
                "page": None, "line": None, "position_in_output": pos,
            })
            continue
        # Year numbers are allowed (1900-2100)
        try:
            iv = int(value)
            if 1900 <= iv <= 2100:
                continue
        except (TypeError, ValueError):
            pass
        # Confidence scores (0.0-1.0) - allowed in JSON-rendered output
        try:
            fv = float(value)
            if 0.0 <= fv <= 1.0 and not float(fv).is_integer():
                continue   # decimal between 0 and 1, not a whole number
        except (TypeError, ValueError):
            pass
        # Pre-verified derivations from orchestration result
        if any(abs(float(value) - ev) < 0.001 for ev in extras):
            report.verified_numbers.append({
                "value": value, "matched_fact": "orchestration_verified_derivation",
                "page": None, "line": None, "position_in_output": pos,
            })
            continue
        # Look for a Fact match in the manifest
        matched = manifest.has_provenance(value)
        if matched is not None:
            report.verified_numbers.append({
                "value": value, "matched_fact": matched.key,
                "page": matched.page, "line": matched.line,
                "position_in_output": pos,
            })
        else:
            # Check AISC weight rule for any nearby designation
            window = text[max(0, pos - 30): pos + 20]
            aisc_match = re.search(r"W\d+X(\d+(?:\.\d+)?)", window)
            if aisc_match and abs(float(aisc_match.group(1)) - float(value)) < 0.001:
                # Canonical AISC value - allowed
                report.verified_numbers.append({
                    "value": value, "matched_fact": "AISC_canonical",
                    "page": None, "line": None, "position_in_output": pos,
                })
                continue
            report.unverified_numbers.append({
                "value": value, "position_in_output": pos,
                "context": text[max(0, pos - 40): pos + 40],
            })
            report.issues.append(f"Unverified number {value} in output (context: "
                                  f"\"...{text[max(0,pos-30):pos+30]}...\")")

    # 4. Decision
    if report.unverified_numbers:
        report.status = "BLOCKED"
        report.summary = (f"BLOCKED: {len(report.unverified_numbers)} unverified number(s) "
                          f"in output of {len(numbers)} total numeric values")
    else:
        report.summary = (f"CLEAR: all {len(report.verified_numbers)} numeric "
                          f"value(s) cite verified facts")

    return report
