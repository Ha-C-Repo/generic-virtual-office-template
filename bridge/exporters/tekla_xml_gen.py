"""
Tekla PowerFab (FabSuite) XML export module.
Converts internal takeoff JSON to industry-standard FabSuiteXMLRequest XML.

Integration points:
- bridge/api.py: add export_tekla_xml() method
- mcp_server.py: add "export_tekla" to drawing_intel dispatcher
- frontend/app.js: add "Export to Tekla" button on project card

Voice rules apply. Zero em-dashes. Hyphens or periods only.
"""


import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from datetime import datetime, timezone

# Import the existing validator. Do NOT recreate it. The validator owns the
# 2,299-shape AISC v16.0 set and has already been hardened across 5 sim
# rounds (HSS decimal-to-fraction map, Unicode times normalization, etc.).
import sys
_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from aisc_validator import validate_shape  # noqa: E402

NAMESPACE = "http://www.fabsuite.com/xml/fabsuite-xml-request-v0108.xsd"


def generate_tekla_xml(
    job_number: str,
    project_name: str,
    takeoff_data: list[dict],
    output_path: str | Path | None = None,
    validate_shapes: bool = True,
) -> dict:
    """Generate Tekla PowerFab XML from takeoff data.

    Args:
        job_number: Your Company bid number (e.g., "PRJ-2026-HOU-0042").
        project_name: Project name for the XML header.
        takeoff_data: List of member dicts from the takeoff pipeline.
            Required keys per item:
                mark (str): Piece mark (e.g., "B101")
                qty (int): Assembly quantity
                shape (str): AISC family (e.g., "W")
                size (str): Dimensions (e.g., "14X22")
                length_in (float): Length in decimal inches
            Optional keys:
                grade (str): Material grade (default "A992")
                sequence (str): Erection sequence
                lot (str): Zone/lot identifier
                camber (str): Camber value (e.g., "3/4")
        output_path: If provided, write .xml file here.
        validate_shapes: If True, reject items not in AISC 2,299 set.

    Returns:
        {
            "success": bool,
            "xml_string": str,         # The full XML
            "output_path": str,        # If file was written
            "items_exported": int,
            "items_rejected": int,
            "rejected_shapes": list,   # Shapes that failed AISC validation
            "warnings": list[str],
        }
    """
    warnings: list[str] = []
    rejected: list[str] = []
    valid_items: list[dict] = []

    # AISC validation gate. Every shape that reaches the XML must exist in
    # the v16.0 set. The handoff is explicit: rejection is the safe default.
    for item in takeoff_data:
        full_shape = f"{item.get('shape', '')}{item.get('size', '')}"
        if validate_shapes:
            result = validate_shape(full_shape)
            if not result.get("valid", False):
                rejected.append(full_shape)
                warnings.append(f"Rejected: {full_shape} not in AISC v16.0")
                continue
        valid_items.append(item)

    if not valid_items:
        return {
            "success": False,
            "xml_string": "",
            "output_path": "",
            "items_exported": 0,
            "items_rejected": len(rejected),
            "rejected_shapes": rejected,
            "warnings": warnings + ["No valid items to export"],
        }

    # Build the XML tree.
    root = ET.Element("FabSuiteXMLRequest", xmlns=NAMESPACE)
    project = ET.SubElement(root, "Project")
    ET.SubElement(project, "ProjectNumber").text = str(job_number)
    ET.SubElement(project, "ProjectName").text = project_name
    ET.SubElement(project, "DateCreated").text = datetime.now(timezone.utc).isoformat()

    bom = ET.SubElement(project, "BillOfMaterials")
    for item in valid_items:
        assembly = ET.SubElement(bom, "Assembly")
        ET.SubElement(assembly, "AssemblyMark").text = item.get("mark", "UNMARKED")
        ET.SubElement(assembly, "Quantity").text = str(item.get("qty", 1))

        part = ET.SubElement(assembly, "Part")
        ET.SubElement(part, "PartMark").text = item.get("mark", "UNMARKED")
        ET.SubElement(part, "MainMember").text = "true"
        ET.SubElement(part, "PartQuantity").text = "1"
        ET.SubElement(part, "Shape").text = item.get("shape", "W")
        ET.SubElement(part, "Dimensions").text = item.get("size", "")
        ET.SubElement(part, "Grade").text = item.get("grade", "A992")
        length_el = ET.SubElement(part, "Length")
        length_el.set("UOM", "in")
        length_el.text = str(item.get("length_in", 0.0))

        # Optional fabrication attributes
        if item.get("camber"):
            ET.SubElement(part, "Camber").text = str(item["camber"])
        if item.get("sequence"):
            ET.SubElement(part, "Sequence").text = str(item["sequence"])
        if item.get("lot"):
            ET.SubElement(part, "LotNumber").text = str(item["lot"])

    # Pretty-print so the XML is readable when opened in a text editor.
    rough = ET.tostring(root, "utf-8")
    reparsed = minidom.parseString(rough)
    xml_str = reparsed.toprettyxml(indent="  ")

    # Write file if a path was supplied.
    out_path = ""
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(xml_str, encoding="utf-8")
        out_path = str(p)

    return {
        "success": True,
        "xml_string": xml_str,
        "output_path": out_path,
        "items_exported": len(valid_items),
        "items_rejected": len(rejected),
        "rejected_shapes": rejected,
        "warnings": warnings,
    }
