"""
Structural Assembly Archetype Engine
======================================
Moves from "reading drawings" to "understanding structures."

When the system detects a structure type (pipe rack, moment frame, tilt-up,
etc.), it triggers a Component Checklist that flags missing elements the AI
may have skipped due to light lines, small text, or congested areas.

Houston Market Archetypes:
  - PIPE_RACK: 2-4 tier pipe support, longitudinal braces, base plates
  - MOMENT_FRAME: Rigid connections, heavy W-shapes, stiffener plates
  - BRACED_FRAME: X-brace or chevron, gusset plates, connection hardware
  - TILTUP_INTERIOR: Steel interior frame inside tilt-up concrete shell
  - CANOPY: Long-span beams, moment connections at columns, roof purlins
  - MEZZANINE: Intermediate floor, composite deck, shear studs
  - EQUIPMENT_SUPPORT: Isolated platform, vibration pads, anchor bolts

Usage:
    from bridge.archetypes import detect_archetype
    result = detect_archetype(member_list, project_type="industrial")
    if result['missing_components']:
        print(f"ANOMALY: {result['archetype']} missing {result['missing_components']}")
"""

from dataclasses import dataclass, field


@dataclass
class ComponentCheck:
    """A required component for a structural archetype."""
    name: str
    description: str
    search_patterns: list[str]      # Shapes/items to look for in takeoff
    required: bool = True           # False = optional but expected
    found: bool = False


@dataclass
class Archetype:
    """A structural assembly archetype with component checklist."""
    name: str
    code: str
    description: str
    trigger_keywords: list[str]     # Words in project description that trigger this
    trigger_shapes: list[str]       # Shapes that suggest this archetype
    components: list[ComponentCheck] = field(default_factory=list)
    confidence: float = 0.0


# ---- Archetype Definitions (Houston Market) ----

ARCHETYPES: list[Archetype] = [
    Archetype(
        name="Pipe Rack",
        code="PIPE_RACK",
        description="Multi-tier pipe support structure. Common in petrochemical facilities.",
        trigger_keywords=["pipe rack", "pipe support", "pipe bridge", "utility rack",
                         "petrochemical", "refinery", "process piping"],
        trigger_shapes=["HP", "W6", "W8", "W10", "HSS4", "HSS5", "HSS6"],
        components=[
            ComponentCheck("Columns", "HP or W-shape columns at each bent",
                          ["HP", "W10", "W12", "W14"]),
            ComponentCheck("Transverse beams", "Beams spanning between column rows",
                          ["W8", "W10", "W12", "W14", "W16"]),
            ComponentCheck("Longitudinal struts", "Struts connecting bents along the rack",
                          ["W6", "W8", "HSS4", "HSS5", "HSS6"]),
            ComponentCheck("Longitudinal bracing", "X-brace or chevron between bents",
                          ["L", "HSS", "WT"]),
            ComponentCheck("Transverse bracing", "Vertical bracing in end bays",
                          ["L", "HSS", "WT"]),
            ComponentCheck("Base plates", "Column base plates with anchor bolts",
                          ["PL", "PLATE", "BASE"]),
            ComponentCheck("Pipe supports", "Individual pipe support clips or shoes",
                          ["CLIP", "SHOE", "SUPPORT", "GUIDE"], required=False),
            ComponentCheck("Stair/ladder", "Access stair or ladder to upper tiers",
                          ["STAIR", "LADDER", "CAGE"], required=False),
        ],
    ),
    Archetype(
        name="Moment Frame",
        code="MOMENT_FRAME",
        description="Rigid frame with moment connections. Resists lateral loads through beam-column rigidity.",
        trigger_keywords=["moment frame", "moment connection", "rigid frame",
                         "special moment", "SMF", "IMF", "OMF"],
        trigger_shapes=["W14", "W16", "W18", "W21", "W24", "W27", "W30"],
        components=[
            ComponentCheck("Columns", "Heavy W-shapes (W14+ typically)",
                          ["W14", "W16", "W18"]),
            ComponentCheck("Beams", "Deep beams with moment connections",
                          ["W18", "W21", "W24", "W27", "W30", "W33"]),
            ComponentCheck("Stiffener plates", "Column stiffeners at beam flanges",
                          ["PL", "STIFFENER", "CONT PL"]),
            ComponentCheck("Doubler plates", "Column web doublers for panel zone",
                          ["DOUBLER", "PL"]),
            ComponentCheck("Shear tab", "Beam-to-column shear connection",
                          ["SHEAR TAB", "PL"]),
            ComponentCheck("Base plates", "Column bases with anchor bolts",
                          ["PL", "BASE"]),
        ],
    ),
    Archetype(
        name="Braced Frame",
        code="BRACED_FRAME",
        description="Lateral system using diagonal bracing. X-brace, chevron, or single diagonal.",
        trigger_keywords=["braced frame", "x-brace", "chevron", "diagonal brace",
                         "SCBF", "OCBF", "CBF"],
        trigger_shapes=["HSS", "W", "L", "WT"],
        components=[
            ComponentCheck("Columns", "W-shape columns at brace frame bays",
                          ["W10", "W12", "W14"]),
            ComponentCheck("Beams", "Beams at brace intersections",
                          ["W12", "W14", "W16", "W18"]),
            ComponentCheck("Braces", "HSS or W-shape diagonal members",
                          ["HSS", "W", "PIPE"]),
            ComponentCheck("Gusset plates", "Connection plates at brace work points",
                          ["GUSSET", "PL"]),
            ComponentCheck("Splice plates", "Brace splice connections if needed",
                          ["SPLICE", "PL"], required=False),
        ],
    ),
    Archetype(
        name="Tilt-Up Interior Steel",
        code="TILTUP_INTERIOR",
        description="Steel framing inside tilt-up concrete shell. Columns, beams, joists, deck.",
        trigger_keywords=["tilt-up", "tiltup", "tilt up", "concrete shell",
                         "interior steel", "interior framing"],
        trigger_shapes=["W", "HSS", "JOIST", "DECK"],
        components=[
            ComponentCheck("Interior columns", "W-shape or HSS columns on interior grids",
                          ["W10", "W12", "W14", "HSS6", "HSS8"]),
            ComponentCheck("Roof beams/girders", "Primary roof framing",
                          ["W16", "W18", "W21", "W24"]),
            ComponentCheck("Open web joists", "SJI joists spanning between beams",
                          ["JOIST", "K-SERIES", "LH", "DLH"]),
            ComponentCheck("Metal deck", "Roof deck (1.5B22 or similar)",
                          ["DECK", "1.5B", "1.5N"]),
            ComponentCheck("Embed plates", "Connection to tilt-up panels",
                          ["EMBED", "PL"]),
            ComponentCheck("Bridging", "Joist bridging per SJI requirements",
                          ["BRIDGING", "X-BRIDGE"], required=False),
        ],
    ),
    Archetype(
        name="Equipment Support Platform",
        code="EQUIPMENT_SUPPORT",
        description="Isolated steel platform for mechanical equipment (HVAC, compressors, tanks).",
        trigger_keywords=["equipment support", "platform", "mechanical support",
                         "compressor platform", "tank support", "HVAC platform"],
        trigger_shapes=["W8", "W10", "W12", "HSS", "C"],
        components=[
            ComponentCheck("Support beams", "Primary beams under equipment",
                          ["W8", "W10", "W12", "W14"]),
            ComponentCheck("Platform framing", "Secondary framing or grating supports",
                          ["C", "MC", "L", "HSS"]),
            ComponentCheck("Grating or checkered plate", "Walking surface",
                          ["GRATING", "CHECKER", "PLATE"]),
            ComponentCheck("Handrail/guardrail", "Fall protection",
                          ["RAIL", "HANDRAIL", "GUARDRAIL", "PIPE"], required=False),
            ComponentCheck("Anchor bolts", "Equipment mounting hardware",
                          ["ANCHOR", "BOLT", "HILTI"], required=False),
        ],
    ),
]


def detect_archetype(member_list: list[dict], 
                     project_type: str = "",
                     project_description: str = "") -> dict:
    """Detect structural archetype from takeoff member list.
    
    Args:
        member_list: List of dicts with 'shape', 'quantity', 'length' keys
        project_type: "industrial", "commercial", "tiltup", etc.
        project_description: Free text project description
    
    Returns:
        dict with archetype, confidence, found_components, missing_components, anomalies
    """
    # Normalize all shapes from the member list
    # vj: parity-ok (pass 10g classified: mixed J=0.50; needs manual audit)
    shapes_found = set()
    for member in member_list:
        shape = member.get("shape", "").upper()
        shapes_found.add(shape)
        # Also add the family prefix
        for prefix in ["W", "HSS", "HP", "MC", "C", "L", "S", "WT", "PIPE"]:
            if shape.startswith(prefix):
                shapes_found.add(prefix)
                # Add size prefix too (e.g., W14 from W14X82)
                parts = shape.split("X")
                if len(parts) >= 2:
                    shapes_found.add(parts[0])
                break
    
    combined_text = f"{project_type} {project_description}".lower()
    
    best_match = None
    best_score = 0
    
    for archetype in ARCHETYPES:
        score = 0
        
        # Keyword matching (weight: 2x)
        for kw in archetype.trigger_keywords:
            if kw.lower() in combined_text:
                score += 2
        
        # Shape matching (weight: 1x)
        for ts in archetype.trigger_shapes:
            for sf in shapes_found:
                if sf.startswith(ts):
                    score += 1
                    break
        
        if score > best_score:
            best_score = score
            best_match = archetype
    
    if best_match is None or best_score < 2:
        return {
            "archetype": "UNKNOWN",
            "confidence": 0.0,
            "found_components": [],
            "missing_components": [],
            "anomalies": [],
            "note": "No archetype detected. Manual review recommended.",
        }
    
    # Run component checklist
    confidence = min(1.0, best_score / (len(best_match.trigger_keywords) + 
                                        len(best_match.trigger_shapes)))
    
    found = []
    missing = []
    
    for component in best_match.components:
        component_found = False
        for pattern in component.search_patterns:
            for sf in shapes_found:
                if pattern.upper() in sf:
                    component_found = True
                    break
            if component_found:
                break
        
        if component_found:
            found.append(component.name)
        elif component.required:
            missing.append(component.name)
    
    # Generate anomaly messages
    anomalies = []
    for m in missing:
        anomalies.append(
            f"ANOMALY: {best_match.name} detected but '{m}' not found in takeoff. "
            f"Check for light lines, small text, or missing drawing sheet."
        )
    
    return {
        "archetype": best_match.code,
        "archetype_name": best_match.name,
        "confidence": round(confidence, 2),
        "found_components": found,
        "missing_components": missing,
        "anomalies": anomalies,
        "total_checks": len(best_match.components),
        "checks_passed": len(found),
        "description": best_match.description,
    }


class ArchetypeEngine:
    """Engine for managing and running archetype detection."""
    
    def __init__(self):
        self.archetypes = ARCHETYPES
    
    @property
    def count(self) -> int:
        return len(self.archetypes)
    
    def list_archetypes(self) -> list[dict]:
        return [{"code": a.code, "name": a.name, "components": len(a.components)}
                for a in self.archetypes]
    
    def detect(self, member_list: list[dict], **kwargs) -> dict:
        return detect_archetype(member_list, **kwargs)
    
    def get_checklist(self, archetype_code: str) -> list[dict]:
        for a in self.archetypes:
            if a.code == archetype_code:
                return [{"name": c.name, "description": c.description, 
                         "required": c.required, "patterns": c.search_patterns}
                        for c in a.components]
        return []
