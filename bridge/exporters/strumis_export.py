"""
Strumis ERP XML export module.
Phase 6 of the post-parity roadmap (v3.9.1).

Strumis is the second major fabrication ERP in the Houston market. The
Tekla / Strumis split runs roughly 60/40, so adding this exporter alongside
Phase 1's Tekla exporter brings shop-floor coverage close to 100 percent
of Houston structural fabricators.

Schema differences from the Tekla FabSuiteXMLRequest format:
    Tekla                          Strumis
    ----------------------         -------------------------
    Root: FabSuiteXMLRequest       Root: StrumisExport
    Namespace: fabsuite.com/...    Namespace: strumis.com/export/...
    Grouping: Assembly > Part      Grouping: Item > Component
    Length: Length UOM="in"        Length + LengthUnit element
    Grade: Grade element           MaterialGrade element
    Mark: PartMark                 ItemMark

Same AISC validation gate as the Tekla exporter. Items not in the
2,299-shape AISC v16.0 set are rejected. Plates (PL prefix) are not in
the AISC set and will be rejected here too. The misc-steel exporter
bridge converts AISC-valid misc items (stair stringers, lintels, pipe
rails, posts) into the same item shape so they ride into Strumis the
same way they ride into Tekla.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from datetime import datetime, timezone

# Reuse the AISC validator. Do not recreate it. The validator owns the
# 2,299-shape v16.0 set and has been hardened across multiple sim rounds.
import sys
_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from aisc_validator import validate_shape  # noqa: E402

NAMESPACE = "http://www.strumis.com/export/strumis-export-v1.xsd"


def generate_strumis_xml(
    job_number: str,
    project_name: str,
    takeoff_data: list[dict],
    output_path: str | Path | None = None,
    validate_shapes: bool = True,
) -> dict:
    """Generate Strumis ERP XML from takeoff data.

    Args:
        job_number: Your Company bid number (e.g., "PRJ-2026-HOU-0042").
        project_name: Project name for the XML header.
        takeoff_data: List of member dicts. Same shape as the Tekla
            exporter expects so callers can hand the same data to either:
                mark (str): Piece mark (e.g., "B101")
                qty (int): Item quantity
                shape (str): AISC family (e.g., "W")
                size (str): Dimensions (e.g., "14X22")
                length_in (float): Length in decimal inches
            Optional keys:
                grade (str): Material grade (default "A992")
                sequence (str): Erection sequence
                lot (str): Zone or lot identifier
                camber (str): Camber value (e.g., "3/4")
                finish (str): Surface finish (e.g., "shop_paint", "galvanized")
        output_path: If provided, write .xml file here.
        validate_shapes: If True, reject items not in AISC 2,299 set.

    Returns:
        {
            "success": bool,
            "xml_string": str,
            "output_path": str,
            "items_exported": int,
            "items_rejected": int,
            "rejected_shapes": list,
            "warnings": list[str],
        }
    """
    warnings: list[str] = []
    rejected: list[str] = []
    valid_items: list[dict] = []

    # AISC validation gate. Same contract as the Tekla exporter so the
    # frontend handler can route the same takeoff data to either format.
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

    # Build the XML tree using the Strumis schema.
    root = ET.Element("StrumisExport", xmlns=NAMESPACE)

    # Project header
    project = ET.SubElement(root, "Project")
    ET.SubElement(project, "ProjectNumber").text = str(job_number)
    ET.SubElement(project, "ProjectName").text = project_name
    ET.SubElement(project, "DateCreated").text = datetime.now(timezone.utc).isoformat()
    ET.SubElement(project, "ExportFormat").text = "StrumisXML-v1"

    # Bill of Materials uses Item > Component grouping in Strumis
    bom = ET.SubElement(root, "BillOfMaterials")
    for item in valid_items:
        item_el = ET.SubElement(bom, "Item")
        ET.SubElement(item_el, "ItemMark").text = item.get("mark", "UNMARKED")
        ET.SubElement(item_el, "ItemQuantity").text = str(item.get("qty", 1))

        component = ET.SubElement(item_el, "Component")
        ET.SubElement(component, "ComponentMark").text = item.get("mark", "UNMARKED")
        ET.SubElement(component, "IsMain").text = "true"
        ET.SubElement(component, "ComponentQuantity").text = "1"
        ET.SubElement(component, "Shape").text = item.get("shape", "W")
        ET.SubElement(component, "Dimensions").text = item.get("size", "")
        ET.SubElement(component, "MaterialGrade").text = item.get("grade", "A992")

        # Length and unit are split into separate elements per Strumis schema
        ET.SubElement(component, "Length").text = str(item.get("length_in", 0.0))
        ET.SubElement(component, "LengthUnit").text = "in"

        # Optional fabrication attributes
        if item.get("camber"):
            ET.SubElement(component, "Camber").text = str(item["camber"])
        if item.get("sequence"):
            ET.SubElement(component, "ErectionSequence").text = str(item["sequence"])
        if item.get("lot"):
            ET.SubElement(component, "LotNumber").text = str(item["lot"])
        if item.get("finish"):
            ET.SubElement(component, "Finish").text = str(item["finish"])

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
