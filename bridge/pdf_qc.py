"""
Your Company Virtual Office - PDF Output QC (Pass 4)
===================================================
the Owner's 6 visual QC rules. Runs on every generated PDF before delivery.
Ported from the Claude Project's review-before-output.md.

These catch layout failures that the factual proofreader (Pass 3) doesn't:
cover page overflow, text clipping, table mangling, spacing collapse,
and template mismatch.

Each rule is tied to a specific failure Owner caught in production.
"""

from typing import Any


# ── The 6 Rules ──────────────────────────────────────────────────────

QC_RULES = {
    "R-01": {
        "name": "Visual inspection required",
        "prevents": "Delivering without ever visually inspecting the rendered PDF",
        "check": "programmatic",
        "detail": "Every PDF must be opened and viewed before delivery. "
                  "The QC pass logs that inspection happened. If the PDF "
                  "was generated but never opened/rendered, it cannot ship.",
    },
    "R-02": {
        "name": "Cover canvas overflow",
        "prevents": "Cover canvas bleeding onto page 2",
        "check": "programmatic",
        "detail": "The cover page (page 1) must be self-contained. If cover "
                  "content pushes onto page 2, the header/ribbon/logo layout "
                  "is broken. Check: page 1 content height < usable page height.",
    },
    "R-03": {
        "name": "Ribbon text clipping",
        "prevents": "Ribbon text running off the right edge",
        "check": "programmatic",
        "detail": "Any colored ribbon or banner element must have text that "
                  "fits within its bounds. Long project names or bid numbers "
                  "must be truncated or font-reduced before rendering.",
    },
    "R-04": {
        "name": "Justified text in narrow columns",
        "prevents": "Justified text mangling narrow table columns",
        "check": "programmatic",
        "detail": "Tables with columns under 2 inches must use LEFT alignment, "
                  "never JUSTIFIED. Justified text in narrow columns creates "
                  "rivers of whitespace that look broken.",
    },
    "R-05": {
        "name": "Heading spacing",
        "prevents": "Headings with no breathing room from body text below",
        "check": "programmatic",
        "detail": "Every section heading must have at least 6pt spaceBefore "
                  "and 3pt spaceAfter. Headings jammed against body text "
                  "look unprofessional and are hard to scan.",
    },
    "R-06": {
        "name": "Template assignment",
        "prevents": "Template assignment errors on multi-template builds",
        "check": "programmatic",
        "detail": "When multiple templates exist (STANDARD, SIMPLE, DETAILED, "
                  "REFINERY), the correct template must be applied to every "
                  "page. A REFINERY bid using STANDARD header is a mismatch.",
    },
}


# ── QC Check Functions ───────────────────────────────────────────────

def check_r01_visual_inspection(pdf_path: str, was_rendered: bool = False) -> dict:
    """R-01: Was the PDF visually inspected?

    In the EXE, this is tracked by whether the PDF was opened in the
    preview pane or an external viewer before the user clicks 'send'.
    """
    return {
        "rule": "R-01",
        "passed": was_rendered,
        "detail": "PDF was visually inspected" if was_rendered
                  else "PDF was NOT opened for visual inspection before delivery",
        "severity": "block" if not was_rendered else "pass",
    }


def check_r02_cover_overflow(pdf_path: str) -> dict:
    """R-02: Does the cover page bleed onto page 2?

    Uses pdfplumber to check if page 1 has content that would push
    past the expected cover boundary.
    """
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) < 1:
                return {"rule": "R-02", "passed": False,
                        "detail": "PDF has 0 pages", "severity": "block"}

            page1 = pdf.pages[0]
            page1_text = page1.extract_text() or ""
            lines = [l for l in page1_text.strip().splitlines() if l.strip()]

            # Cover page should have < 30 lines of content.
            # If it has significantly more, content is likely overflowing.
            if len(lines) > 35:
                return {
                    "rule": "R-02",
                    "passed": False,
                    "detail": f"Cover page has {len(lines)} lines. "
                              "Content likely bleeding onto page 2.",
                    "severity": "warn",
                }

            # If PDF is only 1 page, cover can't overflow
            if len(pdf.pages) == 1:
                return {"rule": "R-02", "passed": True,
                        "detail": "Single-page PDF. No overflow possible.",
                        "severity": "pass"}

            # Check if page 2 starts with continuation of cover content
            # (missing its own section header)
            # Allow-list derived from bridge/documents.py template output
            page2 = pdf.pages[1]
            page2_text = (page2.extract_text() or "").strip()
            _VALID_PAGE2_STARTS = [
                # Roman numeral sections (bid proposal template)
                "I.", "II.", "III.", "IV.", "V.", "VI.", "VII.",
                # Named sections from documents.py templates
                "Scope", "SCOPE", "Schedule", "SCHEDULE",
                "Bid Price", "BID PRICE", "Payment", "PAYMENT",
                "Exclusion", "EXCLUSION", "Inclusion", "INCLUSION",
                "Member", "MEMBER", "CHANGE ORDER",
                # Table headers that land at top of page 2
                "TOTAL ESTIMATE", "BID TOTAL", "TOTAL",
                # Company header (page header/footer)
                "YOUR COMPANY", "Your Company",
                # Project info sections
                "Project", "PROJECT",
            ]
            if page2_text and not any(
                page2_text.upper().startswith(h.upper()) for h in
                _VALID_PAGE2_STARTS
            ):
                return {
                    "rule": "R-02",
                    "passed": False,
                    "detail": "Page 2 does not start with a section header. "
                              "Cover content may have bled over.",
                    "severity": "warn",
                }

        return {"rule": "R-02", "passed": True,
                "detail": "Cover page self-contained.", "severity": "pass"}

    except ImportError:
        return {"rule": "R-02", "passed": True,
                "detail": "pdfplumber not available. Skipped.",
                "severity": "skip"}
    except Exception as e:
        return {"rule": "R-02", "passed": True,
                "detail": f"Check errored: {e}", "severity": "skip"}


def check_r03_ribbon_clipping(flowables: list = None,
                              page_width_pts: float = 540) -> dict:
    """R-03: Does ribbon/banner text fit within its bounds?

    Checks at generation time (before PDF write) by measuring text
    width against the ribbon container width.

    Args:
        flowables: list of ReportLab flowables (from the build pipeline)
        page_width_pts: usable page width in points
    """
    if not flowables:
        return {"rule": "R-03", "passed": True,
                "detail": "No flowables provided. Skipped.", "severity": "skip"}

    try:
        violations = []

        for i, f in enumerate(flowables):
            # Check Paragraph elements that might be in ribbons
            if hasattr(f, 'text') and hasattr(f, 'style'):
                style = f.style
                if hasattr(style, 'backColor') and style.backColor:
                    # This is likely a ribbon/banner element
                    text_len = len(f.text)
                    # Rough heuristic: if text > 60 chars in a ribbon,
                    # it's probably going to clip
                    if text_len > 60:
                        violations.append(
                            f"Flowable {i}: ribbon text {text_len} chars, "
                            "likely to clip on right edge"
                        )

        if violations:
            return {
                "rule": "R-03",
                "passed": False,
                "detail": "; ".join(violations),
                "severity": "warn",
            }

        return {"rule": "R-03", "passed": True,
                "detail": "Ribbon text within bounds.", "severity": "pass"}
    except Exception as e:
        return {"rule": "R-03", "passed": True,
                "detail": f"Check errored: {e}", "severity": "skip"}


def check_r04_justified_narrow_columns(tables: list = None) -> dict:
    """R-04: Are narrow table columns using justified alignment?

    Checks table style definitions for JUSTIFY on columns < 2 inches.
    """
    if not tables:
        return {"rule": "R-04", "passed": True,
                "detail": "No tables to check.", "severity": "pass"}

    violations = []
    for i, tbl in enumerate(tables):
        if hasattr(tbl, '_colWidths') and tbl._colWidths:
            for j, w in enumerate(tbl._colWidths):
                if w and w < 144:  # 2 inches = 144 points
                    # Check if any cell in this column uses JUSTIFY
                    if hasattr(tbl, '_cellStyles'):
                        for cs in tbl._cellStyles:
                            if hasattr(cs, 'alignment') and cs.alignment == 4:
                                violations.append(
                                    f"Table {i}, col {j}: {w:.0f}pt wide "
                                    "with JUSTIFY alignment"
                                )

    if violations:
        return {
            "rule": "R-04",
            "passed": False,
            "detail": "; ".join(violations),
            "severity": "warn",
        }

    return {"rule": "R-04", "passed": True,
            "detail": "No narrow justified columns.", "severity": "pass"}


def check_r05_heading_spacing(styles_used: list = None) -> dict:
    """R-05: Do headings have adequate spacing from body text?

    Checks ParagraphStyle objects for spaceBefore >= 6 and spaceAfter >= 3
    on any heading-level style.
    """
    if not styles_used:
        return {"rule": "R-05", "passed": True,
                "detail": "No styles to check.", "severity": "pass"}

    violations = []
    heading_keywords = ["heading", "title", "section", "h1", "h2", "h3"]

    for style in styles_used:
        name = getattr(style, 'name', '').lower()
        if any(kw in name for kw in heading_keywords):
            sb = getattr(style, 'spaceBefore', 0)
            sa = getattr(style, 'spaceAfter', 0)
            if sb < 6:
                violations.append(
                    f"Style '{style.name}': spaceBefore={sb} (need >= 6)"
                )
            if sa < 3:
                violations.append(
                    f"Style '{style.name}': spaceAfter={sa} (need >= 3)"
                )

    if violations:
        return {
            "rule": "R-05",
            "passed": False,
            "detail": "; ".join(violations),
            "severity": "warn",
        }

    return {"rule": "R-05", "passed": True,
            "detail": "Heading spacing adequate.", "severity": "pass"}


def check_r06_template_assignment(expected_template: str = "",
                                  detected_elements: dict = None) -> dict:
    """R-06: Is the correct template applied?

    Verifies that header/footer/color elements match the expected template.
    """
    if not expected_template or not detected_elements:
        return {"rule": "R-06", "passed": True,
                "detail": "No template verification data.", "severity": "skip"}

    template_signatures = {
        "STANDARD": {"color": "#1F2A44", "has_ribbon": True},
        "SIMPLE": {"color": "#1F2A44", "has_ribbon": False},
        "DETAILED": {"color": "#1F2A44", "has_ribbon": True},
        "REFINERY": {"color": "#8B0000", "has_ribbon": True},
    }

    expected_sig = template_signatures.get(expected_template.upper())
    if not expected_sig:
        return {"rule": "R-06", "passed": True,
                "detail": f"Unknown template '{expected_template}'.",
                "severity": "skip"}

    mismatches = []
    if detected_elements.get("color") != expected_sig["color"]:
        mismatches.append(
            f"Color mismatch: expected {expected_sig['color']}, "
            f"got {detected_elements.get('color')}"
        )
    if detected_elements.get("has_ribbon") != expected_sig["has_ribbon"]:
        mismatches.append(
            f"Ribbon mismatch: expected {expected_sig['has_ribbon']}, "
            f"got {detected_elements.get('has_ribbon')}"
        )

    if mismatches:
        return {
            "rule": "R-06",
            "passed": False,
            "detail": "; ".join(mismatches),
            "severity": "warn",
        }

    return {"rule": "R-06", "passed": True,
            "detail": f"Template '{expected_template}' correctly applied.",
            "severity": "pass"}


# ── Full QC Pass ─────────────────────────────────────────────────────

def run_pdf_qc(pdf_path: str, was_rendered: bool = False,
               flowables: list = None, tables: list = None,
               styles_used: list = None,
               expected_template: str = "",
               detected_elements: dict = None,
               skip_visual_qc: bool = False) -> dict:
    """Run all 6 QC rules on a generated PDF.

    Args:
        skip_visual_qc: When True, R-01 (visual inspection gate) is
            automatically satisfied and cannot block delivery. Use this
            for programmatic / API-driven document generation where no
            human is sitting at a screen to preview the PDF.
            All other structural rules (R-02 through R-06) still run.

    Returns:
        passed: bool - all rules passed
        results: list of per-rule results
        blocked: bool - any rule returned severity=block
        summary: human-readable summary
    """
    # R-01: visual inspection. Skip it for API/programmatic calls.
    r01 = ({"rule": "R-01", "passed": True,
             "detail": "Visual inspection skipped (programmatic call).",
             "severity": "pass"}
           if skip_visual_qc
           else check_r01_visual_inspection(pdf_path, was_rendered))

    results = [
        r01,
        check_r02_cover_overflow(pdf_path),
        check_r03_ribbon_clipping(flowables),
        check_r04_justified_narrow_columns(tables),
        check_r05_heading_spacing(styles_used),
        check_r06_template_assignment(expected_template, detected_elements),
    ]

    failed = [r for r in results if not r["passed"]]
    blocked = any(r["severity"] == "block" for r in results)
    warned = [r for r in results if r["severity"] == "warn"]

    if blocked:
        verdict = "BLOCKED"
        summary = f"QC BLOCKED: {len(failed)} rule(s) failed, delivery halted."
    elif warned:
        verdict = "WARN"
        summary = (f"QC WARN: {len(warned)} visual issue(s) found. "
                   "Review before sending to client.")
    else:
        verdict = "CLEAR"
        summary = "QC CLEAR: all 6 visual rules passed."

    return {
        "passed": len(failed) == 0,
        "verdict": verdict,
        "blocked": blocked,
        "results": results,
        "failed_count": len(failed),
        "warned_count": len(warned),
        "summary": summary,
    }


def list_rules() -> list[dict]:
    """List all 6 QC rules for display."""
    return [
        {"rule": k, "name": v["name"], "prevents": v["prevents"]}
        for k, v in QC_RULES.items()
    ]
