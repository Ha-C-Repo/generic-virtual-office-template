"""CNC post-processor package (Phase 17, build slot 17, v4.8.0).

Connects takeoff data directly to Mario's ironworker equipment.
Eliminates manual layout and measurement on the shop floor.

Modules:
    stop_list_gen  - CSV for Geka/Sunrise back gauges (no deps)
    dxf_part_gen   - 1:1 DXF via ezdxf (guarded)
    gcode_gen      - G-code for Piranha plasma tables (no deps)
    dstv_writer    - NC1/DSTV for robotic beam lines (no deps)
    punch_map_gen  - PDF overlay via reportlab (guarded)

Voice rules: zero em-dashes. Hyphens or periods only.
"""

from .stop_list_gen import generate_stop_list
from .gcode_gen import generate_gcode
from .dstv_writer import generate_dstv
from .dxf_part_gen import generate_part_dxf, HAS_EZDXF
from .punch_map_gen import generate_punch_map, HAS_REPORTLAB

__all__ = [
    "generate_stop_list",
    "generate_part_dxf",
    "generate_gcode",
    "generate_dstv",
    "generate_punch_map",
    "HAS_EZDXF",
    "HAS_REPORTLAB",
]
