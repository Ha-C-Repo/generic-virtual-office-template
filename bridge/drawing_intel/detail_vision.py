"""
Detail Vision - Connection Symbol Classifier for Structural Drawings
=====================================================================
Phase 2 of the Sketchdeck parity roadmap (v3.6.1).

Analyzes high-resolution crops of structural connection nodes to extract
fabrication-critical details: moments, copes, studs, camber, and framing
codes. Uses Gemini Vision API via the existing conductor pattern.

Sketchdeck parity target: capture the same connection attributes that
drive labor cost differences between simple shear tabs and full moment
connections. A moment frame costs 2-3x the fabrication hours of a
standard shear connection. Missing this distinction means underbidding.

Integration:
    - Input: ConnectionNode objects from node_cropper.py (with crop_bytes)
    - Output: detail dicts merged into member/takeoff data
    - Consumers: Tekla exporter (camber tag), connection_check.py,
      bid pipeline (labor code adjustment)

Tool stack: Gemini Vision (covered by Google Premium subscription).
No additional paid dependencies.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import base64
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("detail_vision")


# ---- Symbol classifier prompt ------------------------------------------------

SYMBOL_CLASSIFIER_PROMPT = (
    "You are a Senior Structural Steel Estimator analyzing a connection detail "
    "cropped from an engineering drawing.\n\n"
    "Identify the following:\n\n"
    "1. CONNECTION TYPE: Classify as one of:\n"
    "   - B2B (beam-to-beam): standard shear connection\n"
    "   - B2C (beam-to-column): possible moment or seated connection\n"
    "   - C2F (column-to-foundation): base plate analysis\n"
    "   - BR2C (brace-to-column): gusset plate connection\n"
    "   - BR2B (brace-to-beam): gusset plate connection\n"
    "   - SPLICE (column splice or beam splice)\n"
    "   - UNKNOWN if not determinable\n\n"
    "2. MOMENT INDICATORS: Look for triangles, heavy solid lines, rectangles, "
    "or the word 'MOMENT' at the beam-to-column interface. If present, set "
    "moment to true. Moment connections require significantly more welding.\n\n"
    "3. CAMBER: Extract any value following 'c=', 'CAMBER', or 'CAM' on beam "
    "labels. Format as a fraction (e.g., '3/4'). If no camber is shown, "
    "set to null.\n\n"
    "4. STUDS: Count numeric values preceding 'STUDS', 'S', or 'SHEAR STUDS'. "
    "Return the count per beam. If no studs are shown, set to 0.\n\n"
    "5. COPE: Analyze the relative top-of-steel (TOS) elevations and member "
    "depths. If an incoming beam is smaller than the primary member and the "
    "drawing shows a notch or cutout at the beam end, set cope_required to "
    "true. Copes are labor-intensive (plasma or manual cutting).\n\n"
    "6. BOLT PATTERN: If visible, count the number of bolts in the connection. "
    "Note the pattern (e.g., '2 rows of 3' or '4 bolts single line').\n\n"
    "7. WELD INDICATORS: If weld symbols are visible, note the weld type "
    "(fillet, CJP, PJP) and size if readable.\n\n"
    "Respond with ONLY a JSON object. No markdown, no explanation. Keys:\n"
    "connection_type, moment, camber, studs, cope_required, bolt_count, "
    "bolt_pattern, weld_type, weld_size, confidence, notes\n\n"
    "Example response:\n"
    '{"connection_type":"B2C","moment":true,"camber":"3/4","studs":24,'
    '"cope_required":false,"bolt_count":6,"bolt_pattern":"2 rows of 3",'
    '"weld_type":"CJP","weld_size":null,"confidence":0.85,'
    '"notes":"Full moment frame with stiffener plates"}'
)


# ---- Data structures ---------------------------------------------------------

@dataclass
class ConnectionDetail:
    """Extracted detail attributes for a single connection node."""
    connection_type: str = "UNKNOWN"  # B2B, B2C, C2F, BR2C, BR2B, SPLICE
    moment: bool = False
    camber: Optional[str] = None      # e.g., "3/4"
    studs: int = 0
    cope_required: bool = False
    bolt_count: int = 0
    bolt_pattern: str = ""
    weld_type: Optional[str] = None   # fillet, CJP, PJP
    weld_size: Optional[str] = None
    confidence: float = 0.0
    notes: str = ""
    source: str = "vision"            # "vision", "text", "inferred"

    def to_dict(self) -> dict:
        return {
            "connection_type": self.connection_type,
            "moment": self.moment,
            "camber": self.camber,
            "studs": self.studs,
            "cope_required": self.cope_required,
            "bolt_count": self.bolt_count,
            "bolt_pattern": self.bolt_pattern,
            "weld_type": self.weld_type,
            "weld_size": self.weld_size,
            "confidence": round(self.confidence, 3),
            "notes": self.notes,
            "source": self.source,
        }

    @property
    def labor_multiplier(self) -> float:
        """Estimate labor cost multiplier relative to a standard shear tab.

        Standard shear (B2B, no moment): 1.0x
        Moment frame: 2.5x (heavy welding, stiffeners, testing)
        Cope required: +0.3x
        Column splice: 1.5x
        Base plate (C2F): 1.8x
        """
        mult = 1.0
        if self.moment:
            mult = 2.5
        elif self.connection_type == "C2F":
            mult = 1.8
        elif self.connection_type in ("SPLICE",):
            mult = 1.5
        if self.cope_required:
            mult += 0.3
        return mult


# ---- Text-based extraction (offline fallback) --------------------------------

_CAMBER_RE = re.compile(
    r"(?:c\s*=\s*|camber\s*[:=]?\s*|cam\s*[:=]?\s*)"
    r"(\d+(?:/\d+)?(?:\s*\")?)",
    re.IGNORECASE,
)

_STUDS_RE = re.compile(
    r"(\d+)\s*(?:shear\s+)?studs?",
    re.IGNORECASE,
)

_MOMENT_RE = re.compile(
    r"\bmoment\b|full\s+pen(?:etration)?|CJP|complete\s+joint",
    re.IGNORECASE,
)

_COPE_RE = re.compile(
    r"\bcope[sd]?\b|top\s+flange\s+cope|bottom\s+flange\s+cope",
    re.IGNORECASE,
)

_BOLT_RE = re.compile(
    r"(\d+)\s*(?:[-]?\s*)?(?:bolts?|A325|A490|F1852|F2280)",
    re.IGNORECASE,
)


def extract_from_text(text: str) -> ConnectionDetail:
    """Extract connection details from OCR text (offline fallback).

    Used when Gemini vision is unavailable or for pre-screening.
    Lower confidence than vision analysis.
    """
    detail = ConnectionDetail(source="text", confidence=0.5)

    # Camber
    m = _CAMBER_RE.search(text)
    if m:
        detail.camber = m.group(1).strip().rstrip('"')

    # Studs
    m = _STUDS_RE.search(text)
    if m:
        try:
            detail.studs = int(m.group(1))
        except ValueError:
            pass

    # Moment
    if _MOMENT_RE.search(text):
        detail.moment = True
        detail.connection_type = "B2C"  # moments are typically B2C

    # Cope
    if _COPE_RE.search(text):
        detail.cope_required = True

    # Bolts
    m = _BOLT_RE.search(text)
    if m:
        try:
            detail.bolt_count = int(m.group(1))
        except ValueError:
            pass

    return detail


# ---- Vision-based analysis (Gemini) ------------------------------------------

def _parse_vision_response(raw_text: str) -> ConnectionDetail:
    """Parse the JSON response from Gemini vision into a ConnectionDetail."""
    detail = ConnectionDetail(source="vision")

    # Strip markdown fences if present
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.warning(f"Failed to parse vision response as JSON: {e}")
        detail.notes = f"JSON parse failed: {str(e)[:100]}"
        detail.confidence = 0.1
        return detail

    if not isinstance(data, dict):
        detail.notes = "Vision response was not a JSON object"
        detail.confidence = 0.1
        return detail

    detail.connection_type = str(data.get("connection_type", "UNKNOWN")).upper()
    detail.moment = bool(data.get("moment", False))
    detail.camber = data.get("camber") or None
    detail.cope_required = bool(data.get("cope_required", False))
    detail.confidence = float(data.get("confidence", 0.7))
    detail.notes = str(data.get("notes", ""))
    detail.bolt_pattern = str(data.get("bolt_pattern", ""))
    detail.weld_type = data.get("weld_type") or None
    detail.weld_size = data.get("weld_size") or None

    # Integer fields with safe parsing
    try:
        detail.studs = int(data.get("studs", 0))
    except (TypeError, ValueError):
        detail.studs = 0
    try:
        detail.bolt_count = int(data.get("bolt_count", 0))
    except (TypeError, ValueError):
        detail.bolt_count = 0

    return detail


def analyze_crop_with_vision(
    crop_bytes: bytes,
    framing_code_hint: str = "",
    call_provider=None,
) -> ConnectionDetail:
    """Send a connection crop to Gemini Vision for detail analysis.

    Args:
        crop_bytes: PNG image bytes of the connection crop
        framing_code_hint: B2B/B2C/C2F hint from node_cropper (helps prompt)
        call_provider: Callable (provider, model, envelope) -> dict.
            Injected by the caller (usually bridge/api.py). If None, returns
            a text-extraction-only result.

    Returns:
        ConnectionDetail with vision-extracted attributes.
    """
    if not crop_bytes:
        return ConnectionDetail(
            source="none",
            confidence=0.0,
            notes="No crop image provided",
        )

    if call_provider is None:
        log.info("No vision provider available. Returning empty detail.")
        return ConnectionDetail(
            source="none",
            confidence=0.0,
            notes="Vision provider not configured. Use text extraction as fallback.",
        )

    # Encode crop as base64 for the vision API
    b64_image = base64.b64encode(crop_bytes).decode("ascii")

    # Build the prompt with the framing code hint if available
    prompt = SYMBOL_CLASSIFIER_PROMPT
    if framing_code_hint:
        prompt += (
            f"\n\nHINT: The geometric analysis suggests this is a "
            f"{framing_code_hint} connection. Confirm or override based "
            f"on what you see in the image."
        )

    # Build the Gemini-compatible message envelope
    envelope = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            },
        ],
    }

    try:
        result = call_provider("gemini", "gemini-2.5-flash", envelope)
        raw_text = ""
        if isinstance(result, dict):
            raw_text = result.get("text", "") or result.get("content", "")
            if isinstance(raw_text, list):
                raw_text = " ".join(
                    c.get("text", "") for c in raw_text if isinstance(c, dict)
                )
        elif isinstance(result, str):
            raw_text = result

        if raw_text:
            return _parse_vision_response(raw_text)
        else:
            return ConnectionDetail(
                source="vision",
                confidence=0.1,
                notes="Vision API returned empty response",
            )
    except Exception as e:
        log.error(f"Vision analysis failed: {e}")
        return ConnectionDetail(
            source="vision",
            confidence=0.0,
            notes=f"Vision API error: {str(e)[:200]}",
        )


# ---- Batch analysis ----------------------------------------------------------

def analyze_nodes(
    nodes: list,
    call_provider=None,
    text_fallback: str = "",
) -> list[dict]:
    """Analyze a list of ConnectionNode objects and return detail dicts.

    For each node with crop_bytes, sends to Gemini Vision.
    For nodes without crops, falls back to text extraction if text is provided.

    Args:
        nodes: List of ConnectionNode objects from node_cropper
        call_provider: Vision API callable (injected from bridge/api.py)
        text_fallback: Full page OCR text for regex-based fallback

    Returns:
        List of dicts, each with node_id + all ConnectionDetail fields.
    """
    results = []

    for node in nodes:
        if node.crop_bytes:
            detail = analyze_crop_with_vision(
                node.crop_bytes,
                framing_code_hint=node.framing_code,
                call_provider=call_provider,
            )
        elif text_fallback:
            detail = extract_from_text(text_fallback)
        else:
            detail = ConnectionDetail(
                source="inferred",
                connection_type=node.framing_code or "UNKNOWN",
                confidence=0.3,
                notes="No crop or text available. Type inferred from geometry.",
            )

        # Override connection_type with geometry if vision was low-confidence
        if detail.confidence < 0.4 and node.framing_code != "UNKNOWN":
            detail.connection_type = node.framing_code

        # Store detail back on the node
        node.detail = detail.to_dict()

        result = {"node_id": node.node_id, **detail.to_dict()}
        results.append(result)

    log.info(
        f"analyze_nodes: {len(results)} nodes analyzed. "
        f"Vision: {sum(1 for r in results if r.get('source') == 'vision')}. "
        f"Text: {sum(1 for r in results if r.get('source') == 'text')}. "
        f"Inferred: {sum(1 for r in results if r.get('source') == 'inferred')}."
    )
    return results


# ---- Merge details into takeoff data -----------------------------------------

def merge_details_into_takeoff(
    takeoff_members: list[dict],
    node_details: list[dict],
    node_member_map: dict[str, list[str]],
) -> list[dict]:
    """Merge connection detail attributes into takeoff member data.

    This populates the camber, studs, and connection metadata fields that
    the Tekla exporter reads. The Tekla exporter already accepts a 'camber'
    field per item (Phase 1). This function fills it from vision results.

    Args:
        takeoff_members: List of member dicts from the takeoff pipeline.
            Must have 'id' or 'mark' field.
        node_details: List of detail dicts from analyze_nodes().
        node_member_map: Maps node_id -> [member_id1, member_id2] from
            the ConnectionNode.members field.

    Returns:
        The same takeoff_members list with detail fields added in-place.
    """
    # Build a lookup: member_id -> list of details that affect it
    member_details: dict[str, list[dict]] = {}
    for detail in node_details:
        nid = detail.get("node_id", "")
        member_ids = node_member_map.get(nid, [])
        for mid in member_ids:
            member_details.setdefault(mid, []).append(detail)

    for member in takeoff_members:
        mid = member.get("id") or member.get("mark") or ""
        details = member_details.get(str(mid), [])
        if not details:
            continue

        # Take the highest-confidence detail for each attribute
        best = max(details, key=lambda d: d.get("confidence", 0))

        # Camber: populate for Tekla export
        if best.get("camber") and not member.get("camber"):
            member["camber"] = best["camber"]

        # Studs
        if best.get("studs", 0) > 0:
            member["studs"] = best["studs"]

        # Connection metadata
        member["connection_type"] = best.get("connection_type", "UNKNOWN")
        member["moment"] = best.get("moment", False)
        member["cope_required"] = best.get("cope_required", False)
        member["labor_multiplier"] = ConnectionDetail(
            moment=best.get("moment", False),
            cope_required=best.get("cope_required", False),
            connection_type=best.get("connection_type", "UNKNOWN"),
        ).labor_multiplier

        # Bolt info
        if best.get("bolt_count", 0) > 0:
            member["bolt_count"] = best["bolt_count"]
            member["bolt_pattern"] = best.get("bolt_pattern", "")

        # Weld info
        if best.get("weld_type"):
            member["weld_type"] = best["weld_type"]
            member["weld_size"] = best.get("weld_size")

    return takeoff_members
