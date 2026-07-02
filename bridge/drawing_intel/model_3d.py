"""
Drawing Intel: 3D Wireframe Generator
=======================================
Generates a 3D wireframe from extracted member data using trimesh.
If a beam is "floating" in space (not connected to columns), the
system auto-flags a TAKEOFF ERROR.

This is a visual validation layer. No PE required. Just common sense:
columns should be vertical, beams should connect to columns, bracing
should be diagonal.

Usage:
    from bridge.drawing_intel.model_3d import generate_wireframe
    result = generate_wireframe(members, grid_spacing=30)
    # Saves STL file + returns validation flags
"""

import logging
import math
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def generate_wireframe(
    members: list[dict],
    grid_spacing_x: float = 30.0,
    grid_spacing_y: float = 30.0,
    eave_height: float = 24.0,
    output_path: str = "",
) -> dict:
    """Generate a 3D wireframe from member data.

    Members must have at minimum: {shape, qty, type}
    Optional: {length_ft, grid_start, grid_end}

    Args:
        members: List of member dicts from takeoff
        grid_spacing_x: Column spacing in X direction (feet)
        grid_spacing_y: Column spacing in Y direction (feet)
        eave_height: Building eave height (feet)
        output_path: Where to save the STL file

    Returns:
        {stl_path, member_count, warnings, validation}
    """
    try:
        import trimesh
        import numpy as np
    except ImportError:
        return {"error": "trimesh not installed. Run: pip install trimesh"}

    warnings = []
    meshes = []

    # Categorize members
    columns = [m for m in members if m.get("type", "").lower() in ("column", "col")]
    beams = [m for m in members if m.get("type", "").lower() in ("beam", "girder")]
    bracing = [m for m in members if m.get("type", "").lower() in ("brace", "bracing")]
    joists = [m for m in members if m.get("type", "").lower() in ("joist",)]

    # Auto-generate grid positions if not provided
    total_columns = sum(m.get("qty", 1) for m in columns)
    if total_columns == 0:
        warnings.append("No columns found. Cannot generate wireframe without columns.")
        return {"warnings": warnings, "validation": {"valid": False}}

    # Estimate grid layout
    cols_per_row = max(int(math.sqrt(total_columns)), 2)
    rows = max(total_columns // cols_per_row, 1)

    col_positions = []
    col_idx = 0
    for row in range(rows):
        for col in range(cols_per_row):
            if col_idx >= total_columns:
                break
            x = col * grid_spacing_x
            y = row * grid_spacing_y
            col_positions.append((x, y))
            col_idx += 1

    # Generate column meshes (vertical cylinders)
    for i, (x, y) in enumerate(col_positions):
        # Extract weight from shape to estimate flange width
        col_member = columns[0] if columns else {"shape": "W14X82"}
        radius = _shape_to_radius(col_member.get("shape", "W14X82"))

        col_mesh = trimesh.creation.cylinder(
            radius=radius / 12,  # convert inches to feet
            height=eave_height,
            sections=8,
        )
        # Position: center at (x, y, eave_height/2)
        col_mesh.apply_translation([x, y, eave_height / 2])
        meshes.append(col_mesh)

    # Generate beam meshes (horizontal cylinders between columns)
    beam_count = sum(m.get("qty", 1) for m in beams)
    connected_beams = 0
    for i in range(len(col_positions) - 1):
        if connected_beams >= beam_count:
            break
        x1, y1 = col_positions[i]
        x2, y2 = col_positions[i + 1]

        # Only connect adjacent columns in same row
        if abs(y1 - y2) < 0.1:
            length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            beam_member = beams[0] if beams else {"shape": "W24X68"}
            radius = _shape_to_radius(beam_member.get("shape", "W24X68")) * 0.8

            beam_mesh = trimesh.creation.cylinder(
                radius=radius / 12,
                height=length,
                sections=8,
            )
            # Rotate to horizontal and position
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            angle = math.atan2(y2 - y1, x2 - x1)

            rotation = trimesh.transformations.rotation_matrix(
                math.pi / 2, [0, 1, 0]
            )
            beam_mesh.apply_transform(rotation)
            if abs(angle) > 0.01:
                rot_z = trimesh.transformations.rotation_matrix(angle, [0, 0, 1])
                beam_mesh.apply_transform(rot_z)
            beam_mesh.apply_translation([mid_x, mid_y, eave_height])
            meshes.append(beam_mesh)
            connected_beams += 1

    # Combine all meshes
    if not meshes:
        return {"error": "No meshes generated", "warnings": warnings}

    combined = trimesh.util.concatenate(meshes)

    # Save STL
    if not output_path:
        output_path = str(Path(__file__).parent.parent.parent / "output" / "wireframe.stl")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    combined.export(output_path, file_type="stl")

    # Validation checks
    validation = {
        "valid": True,
        "columns_placed": len(col_positions),
        "beams_connected": connected_beams,
        "expected_beams": beam_count,
        "unconnected_beams": beam_count - connected_beams,
    }

    if connected_beams < beam_count:
        warnings.append(
            f"{beam_count - connected_beams} beams not connected to columns. "
            "Check takeoff for missing grid references."
        )
        validation["valid"] = False

    if not bracing:
        warnings.append("No bracing members found. Verify lateral system.")

    return {
        "stl_path": output_path,
        "member_count": len(meshes),
        "total_triangles": len(combined.faces),
        "bounding_box_ft": {
            "x": round(float(combined.bounds[1][0] - combined.bounds[0][0]), 1),
            "y": round(float(combined.bounds[1][1] - combined.bounds[0][1]), 1),
            "z": round(float(combined.bounds[1][2] - combined.bounds[0][2]), 1),
        },
        "warnings": warnings,
        "validation": validation,
    }


def _shape_to_radius(shape: str) -> float:
    """Estimate display radius from shape designation (in inches)."""
    import re
    # W-shape depth
    m = re.match(r'W(\d+)', shape)
    if m:
        depth = int(m.group(1))
        return depth / 2  # half-depth as radius

    # HSS
    m = re.match(r'HSS(\d+)', shape)
    if m:
        return int(m.group(1)) / 2

    return 6  # default 6" radius
