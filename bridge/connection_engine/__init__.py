"""Connection design engine (Phase 18, build slot 18, v5.0.0).

Automates delegated connection design per AISC 303-22 Section 4.4
Option 3. Simple connections (shear tabs, base plates) are auto-
designed with GREEN/YELLOW/RED status. Complex connections are flagged
for PE review with preliminary sizing.

Internalizes ~$20/ton of connection engineering cost.

Modules:
    shear_tab_designer   - AISC 360-16 J3/J4, 7 limit states
    base_plate_designer  - AISC DG1 + ACI 318
    pynite_bridge        - PyNite FEA for non-standard connections

Voice rules: zero em-dashes. Hyphens or periods only.
"""

from .shear_tab_designer import design_shear_tab
from .base_plate_designer import design_base_plate
from .pynite_bridge import verify_connection_fea, HAS_PYNITE

__all__ = [
    "design_shear_tab",
    "design_base_plate",
    "verify_connection_fea",
    "HAS_PYNITE",
]
