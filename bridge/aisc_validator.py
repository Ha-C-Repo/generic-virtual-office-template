"""
Your Company Virtual Office - AISC Validation Gate (Gemini Architecture)
======================================================================
Uses pandas + AISC v16.0 for deterministic validation.
Every AI-extracted shape passes through this gate.

Three validation stages:
  1. Existence Check: Is this a real AISC shape?
  2. Engineering Viability: L/r slenderness ratio check
  3. Mass Balance: Does extracted tonnage match member sum?

"NEVER let the LLM do this math." - Gemini Research Report
"""

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

_VALIDATOR = None


class AISCValidator:
    """Pandas-based AISC shape validator with engineering checks."""

    def __init__(self, database_path: str = "",
                 standards_filter: list[str] | None = None):
        """Load AISC database with optional standards partitioning.

        standards_filter: list of standard codes to load (default ["AISC"]).
        When the master CSV has a 'standard' column, only rows matching the
        filter are loaded. This prevents accidentally serving a UK Universal
        Beam (BS 4-1) or Eurocode IPE on a Houston petrochemical bid if
        international shapes are ever ingested. AISC-only is the safe default.
        Pass None to load every standard (dangerous for production bids).
        """
        import pandas as pd

        if not database_path:
            # Master is canonical (2,299 shapes, has 'standard' partition column).
            # Legacy CSVs moved to data/legacy/ in v3.5.6 - kept as a graceful
            # fallback so the validator still loads if the master ever goes
            # missing. Order: master -> legacy/merged -> legacy/minimal.
            data_dir = Path(__file__).parent.parent / "data"
            master = data_dir / "aisc_master.csv"
            v16 = data_dir / "legacy" / "aisc_shapes_merged.csv"
            legacy = data_dir / "legacy" / "aisc_shapes.csv"
            if master.exists():
                database_path = str(master)
            elif v16.exists():
                database_path = str(v16)
            elif legacy.exists():
                database_path = str(legacy)
            else:
                raise FileNotFoundError(
                    f"No AISC database found. Looked in {master}, {v16}, {legacy}."
                )

        self.db = pd.read_csv(database_path)

        # Standards partitioning: filter to AISC-only by default. Legacy CSVs
        # without a 'standard' column are treated as AISC (backward-compat).
        if "standard" in self.db.columns and standards_filter is not None:
            allowed = set(s.upper() for s in standards_filter)
            before = len(self.db)
            self.db = self.db[self.db["standard"].str.upper().isin(allowed)].reset_index(drop=True)
            self.standards_loaded = sorted(allowed)
            if before != len(self.db):
                log.info(f"AISC validator partition filter: {before} → {len(self.db)} shapes "
                         f"(standards={self.standards_loaded})")
        else:
            self.standards_loaded = ["AISC"]  # legacy default

        self.shape_list = self.db["shape"].str.upper().unique().tolist()
        self.has_engineering = "ry_in" in self.db.columns
        log.info(f"AISC validator loaded {len(self.shape_list)} shapes "
                 f"(engineering={'YES' if self.has_engineering else 'NO'}, "
                 f"standards={self.standards_loaded})")

    def get_loaded_standards(self) -> list[str]:
        """Return the list of standards currently loaded (e.g., ['AISC'])."""
        return list(self.standards_loaded)

    def validate_shape(self, extracted_shape: str) -> dict:
        """Validate a single shape against AISC database."""
        clean = _normalize_shape(extracted_shape)

        # Non-AISC passthrough: SJI K/LH/DLH joists and plate designations.
        # These are standard on every Your Company bid but live outside the AISC
        # v16.0 database. Return valid=True with source flag so downstream
        # code can skip weight checks (no lb/ft data available).
        _NON_AISC = [
            # SJI K-series (e.g. 18K5, 22K9, 24K10)
            (re.compile(r'^\d+K\d+$'), 'SJI K-Series'),
            # SJI LH-series (e.g. LH08, LH10, LH14)
            (re.compile(r'^LH\d+$'), 'SJI LH-Series'),
            # SJI DLH-series (e.g. DLH10, DLH14)
            (re.compile(r'^DLH\d+$'), 'SJI DLH-Series'),
            # Plates: PL<thickness>X<width> variants (e.g. PL1/2X6, PL3/4X12, PL1X8)
            (re.compile(r'^PL[\d/]+X[\d.]+$'), 'Plate (non-AISC)'),
        ]
        for pattern, source in _NON_AISC:
            if pattern.match(clean):
                return {
                    "valid": True,
                    "normalized": clean,
                    "original": extracted_shape,
                    "weight_per_ft": None,
                    "source": source,
                    "confidence": "non-aisc-passthrough",
                    "message": f"'{clean}' recognized as {source}; no weight data in AISC v16.0.",
                }

        if clean in self.shape_list:
            row = self.db[self.db["shape"].str.upper() == clean].iloc[0]
            data = row.to_dict()
            return {
                "valid": True,
                "normalized": clean,
                "original": extracted_shape,
                "weight_per_ft": float(data.get("lb_per_ft", 0)),
                "data": {k: _safe_float(v) for k, v in data.items()},
                "confidence": "exact" if clean == extracted_shape.upper().strip() else "normalized",
            }

        # Suggestion logic for typos
        suggestions = self._find_closest(clean)
        return {
            "valid": False,
            "normalized": clean,
            "original": extracted_shape,
            "confidence": "unknown",
            "suggestions": suggestions[:5],
            "message": (
                f"'{extracted_shape}' does not exist in AISC v16.0. "
                + (f"Did you mean: {', '.join(suggestions[:3])}?"
                   if suggestions else "No close matches found.")
            ),
        }

    def check_engineering_viability(self, shape: str, length_ft: float,
                                    member_type: str = "column") -> dict:
        """Check slenderness ratio (L/r) for compression members.
        L/r should typically be < 200 for columns, < 300 for tension.
        """
        # vj: parity-ok (pass 10g classified: mixed J=0.54; needs manual audit)
        if not self.has_engineering:
            return {"checked": False, "reason": "No engineering data in CSV"}

        clean = _normalize_shape(shape)
        match = self.db[self.db["shape"].str.upper() == clean]
        if match.empty:
            return {"checked": False, "reason": f"Shape {clean} not found"}

        row = match.iloc[0]
        ry = float(row.get("ry_in", 0))
        rx = float(row.get("rx_in", 0))

        if ry <= 0:
            return {"checked": False, "reason": "No ry data for this shape"}

        L_inches = length_ft * 12
        slenderness_minor = L_inches / ry
        slenderness_major = L_inches / rx if rx > 0 else 0

        # K-factor per Gemini research: accounts for effective length
        K_FACTORS = {
            "column": 1.0,       # pinned-pinned (conservative default)
            "col": 1.0,
            "brace": 1.0,        # typically pinned both ends
            "bracing": 1.0,
            "cantilever": 2.1,   # fixed-free (worst case)
            "post": 2.1,         # cantilevered post
            "beam": 1.0,         # lateral-torsional, different limit
        }
        K = K_FACTORS.get(member_type.lower(), 1.0)
        limit = 200 if member_type.lower() in ("column", "col", "brace", "bracing", "cantilever", "post") else 300

        # KL/r instead of L/r
        slenderness_minor = (K * L_inches) / ry
        slenderness_major = (K * L_inches) / rx if rx > 0 else 0
        viable = slenderness_minor < limit

        warning = None
        if not viable:
            warning = (f"KL/ry = {slenderness_minor:.0f} (K={K}) exceeds {limit} limit. "
                      f"{clean} at {length_ft}' is likely too slender for {member_type}.")

        return {
            "checked": True,
            "shape": clean,
            "length_ft": length_ft,
            "member_type": member_type,
            "K_factor": K,
            "ry": ry,
            "rx": rx,
            "slenderness_minor": round(slenderness_minor, 1),
            "slenderness_major": round(slenderness_major, 1),
            "limit": limit,
            "viable": viable,
            "warning": warning,
        }

    def calculate_tonnage(self, members: list[dict]) -> float:
        """Local Python calculator for ground-truth tonnage.
        NEVER let the LLM do this math.
        """
        total_weight_lbs = 0
        for m in members:
            shape = _normalize_shape(m.get("shape", ""))
            qty = m.get("qty", 1)
            length = m.get("length_ft", 25)

            match = self.db[self.db["shape"].str.upper() == shape]
            if not match.empty:
                wt = float(match.iloc[0]["lb_per_ft"])
            else:
                # Try to extract weight from shape name
                wm = re.match(r'W\d+X(\d+)', shape)
                wt = float(wm.group(1)) if wm else 0

            total_weight_lbs += qty * length * wt

        return total_weight_lbs / 2000

    def lookup(self, shape: str) -> dict:
        """Thin alias for validate_shape. Preferred call site."""
        return self.validate_shape(shape)

    def _find_closest(self, shape: str) -> list[str]:
        """Find closest AISC shapes by family and weight."""
        wm = re.match(r'^W(\d+)X(\d+)', shape)
        if wm:
            depth = int(wm.group(1))
            weight = int(wm.group(2))
            same_depth = []
            for s in self.shape_list:
                dm = re.match(r'^W(\d+)X(\d+)', s)
                if dm and int(dm.group(1)) == depth:
                    same_depth.append((s, abs(int(dm.group(2)) - weight)))
            same_depth.sort(key=lambda x: x[1])
            return [s[0] for s in same_depth[:5]]

        prefix = re.match(r'^([A-Z]+)', shape)
        if prefix:
            return [s for s in self.shape_list if s.startswith(prefix.group(1))][:5]
        return []


def _get_validator() -> AISCValidator:
    """Get or create the singleton validator."""
    global _VALIDATOR
    if _VALIDATOR is None:
        _VALIDATOR = AISCValidator()
    return _VALIDATOR


# ── Public API (matches existing bridge method signatures) ───────────

def validate_shape(raw_shape: str) -> dict:
    return _get_validator().validate_shape(raw_shape)


def validate_takeoff(members: list[dict]) -> dict:
    """Validate an entire takeoff member list."""
    v = _get_validator()
    validated = []
    issues = []
    total_weight_lbs = 0

    for m in members:
        raw = m.get("shape", "")
        qty = m.get("qty", 1)
        length = m.get("length_ft", 25)
        member_type = m.get("type", "beam")

        result = v.validate_shape(raw)
        entry = {
            "shape": result.get("normalized", raw),
            "original": raw,
            "qty": qty,
            "length_ft": length,
            "valid": result["valid"],
        }

        if result["valid"]:
            wt = result["weight_per_ft"]
            member_weight = wt * length * qty
            entry["weight_per_ft"] = wt
            entry["member_weight_lbs"] = round(member_weight, 1)
            total_weight_lbs += member_weight

            # Engineering viability check
            eng = v.check_engineering_viability(raw, length, member_type)
            if eng.get("checked") and not eng.get("viable"):
                issues.append({
                    "shape": result["normalized"],
                    "type": "slenderness_fail",
                    "message": eng["warning"],
                    "slenderness": eng["slenderness_minor"],
                })
                entry["engineering_warning"] = eng["warning"]

        else:
            entry["suggestions"] = result.get("suggestions", [])
            issues.append({
                "shape": raw,
                "type": "invalid_shape",
                "message": result.get("message", ""),
                "suggestions": result.get("suggestions", []),
            })

        validated.append(entry)

    tonnage = total_weight_lbs / 2000
    return {
        "valid_count": sum(1 for v in validated if v["valid"]),
        "invalid_count": sum(1 for v in validated if not v["valid"]),
        "total_tonnage": round(tonnage, 2),
        "total_weight_lbs": round(total_weight_lbs, 1),
        "issues": issues,
        "members": validated,
        "mass_balance_check": True if tonnage > 0 else False,
    }


def mass_balance_check(extracted_tonnage: float, members: list[dict],
                       tolerance_pct: float = 5.0) -> dict:
    """Compare AI-extracted tonnage against calculated tonnage."""
    v = _get_validator()
    calculated = v.calculate_tonnage(members)
    delta = abs(extracted_tonnage - calculated)
    delta_pct = (delta / max(extracted_tonnage, 0.1)) * 100

    return {
        "extracted_tonnage": extracted_tonnage,
        "calculated_tonnage": round(calculated, 2),
        "delta_tons": round(delta, 2),
        "delta_pct": round(delta_pct, 1),
        "within_tolerance": delta_pct <= tolerance_pct,
        "message": (
            f"Mass balance OK. Delta: {delta:.1f}T ({delta_pct:.1f}%)"
            if delta_pct <= tolerance_pct
            else f"WARNING: {delta:.1f}T gap ({delta_pct:.1f}%). "
                 f"Members may be missing from takeoff."
        ),
    }


def _normalize_shape(raw: str) -> str:
    """Normalize shape designation to AISC format."""
    s = raw.strip().upper()
    m = re.match(r'^(\d+)[- ]*(W\d+)$', s)
    if m:
        return f"{m.group(2)}X{m.group(1)}"
    s = re.sub(r'\s+', '', s)
    s = s.replace('\u00d7', 'X')   # Unicode × → X (PDF copy-paste)
    s = s.replace('x', 'X')
    s = re.sub(r'HSS\s*', 'HSS', s)
    # HSS decimal wall thickness → fraction (AISC stores fractions only)
    # Decimal wall/thickness → fraction (AISC stores fractions for HSS, L, WT, etc.)
    _DEC_FRAC = {
        '.125': '1/8', '.1875': '3/16', '.250': '1/4', '.2500': '1/4',
        '.3125': '5/16', '.375': '3/8', '.3750': '3/8',
        '.500': '1/2', '.5000': '1/2', '.625': '5/8', '.6250': '5/8',
        '.750': '3/4', '.7500': '3/4', '.875': '7/8', '.8750': '7/8',
        '1.000': '1', '1.0000': '1',
    }
    # Apply to any shape family that uses fractional thickness (HSS, L, WT, 2L, etc.)
    if any(s.startswith(prefix) for prefix in ('HSS', 'L', 'WT', '2L', 'C', 'MC')):
        for dec, frac in _DEC_FRAC.items():
            if s.endswith(dec):
                s = s[:-len(dec)] + frac
                break
    return s


def _safe_float(v):
    """Convert value to float, return as-is if not numeric."""
    try:
        return float(v)
    except (ValueError, TypeError):
        return v


# ── v3.5.11: Shape audit on free-form text ────────────────────────────
# Code-side hard-flag for hallucinated AISC shapes in LLM responses.
# Per-Gemini-review (May 9, 2026) and Joseph's structural-safety pattern:
# move shape verification from prompt instruction to deterministic
# code-side check. Runs after every LLM response on structural task
# categories. Hallucinations get flagged in a banner at the top of the
# response so Joseph and Owner see them before the response leaves
# the chat. Not a hard-block (the LLM may legitimately mention shapes
# from older AISC editions or foreign standards we don't carry).

def extract_shape_designations(text: str) -> list[str]:
    """Find AISC-pattern shape designations in free-form text.

    Pattern matches W/HSS/L/C/WT/HP/MC/M/S followed by digits and one
    or two X-separated dimension groups, optionally with fraction or
    decimal. Examples that match:

        W14X82, W14x82, W14×82
        HSS6X6X1/2, HSS6X6X.500
        L4X4X3/8, L12X12X1-3/8 (mixed fraction)
        C8X18.75, WT4X12, HP12X84
        MC10X33.6, S12X35

    Word-boundary anchored so license-plate-like text (MA1234) is not
    matched. Plate (PL) shapes are intentionally excluded; they don't
    have a deterministic shape-name to validate against.
    """
    import re
    pattern = (
        r'\b(?:HSS|WT|HP|MC|W|L|C|M|S)'        # leading family
        r'\d+(?:\.\d+)?'                        # first numeric part
        r'(?:[Xx\u00d7](?:\d+(?:[\.\-/]\d+){0,2}|\.\d+)){1,2}'  # one or two X-suffixes
        r'\b'
    )
    return re.findall(pattern, text)


def audit_shapes_in_text(text: str) -> dict:
    """Validate every AISC shape designation found in text.

    Returns a dict with three keys:
        valid    (list[str]): unique shape names that exist in v16.0
        invalid  (list[str]): unique shape names that do NOT exist
        total    (int)      : raw count of shape-pattern hits

    De-duplicates the valid/invalid lists. The total reflects raw hits
    (so "W14X82 mentioned three times" counts as 3 in total but 1 in
    valid). No exception path. Empty text returns empty audit.
    """
    if not text:
        return {"valid": [], "invalid": [], "total": 0}

    raw = extract_shape_designations(text)
    seen_valid: set[str] = set()
    seen_invalid: set[str] = set()

    for shape in raw:
        # validate_shape is idempotent and memoization-friendly
        result = validate_shape(shape)
        norm = result.get("normalized", shape)
        if result.get("valid"):
            seen_valid.add(norm)
        else:
            seen_invalid.add(norm)

    return {
        "valid":   sorted(seen_valid),
        "invalid": sorted(seen_invalid),
        "total":   len(raw),
    }


def build_shape_audit_warning(audit: dict) -> str:
    """Format an audit result into a banner string for chat output.

    Returns empty string when there are no invalid shapes (no banner).
    Otherwise returns a short, voice-clean banner that lists the
    flagged shapes and tells the user what to do.
    """
    invalid = audit.get("invalid", [])
    if not invalid:
        return ""
    if len(invalid) == 1:
        head = (
            f"⚠️ **AISC shape audit**. The shape `{invalid[0]}` is not in "
            f"the AISC v16.0 database (2,299 shapes). Verify the "
            f"designation before using it in any bid."
        )
    else:
        listed = ", ".join(f"`{s}`" for s in invalid)
        head = (
            f"⚠️ **AISC shape audit**. {len(invalid)} shapes are not "
            f"in the AISC v16.0 database: {listed}. Verify each "
            f"designation before using it in any bid."
        )
    return head + "\n\n"
