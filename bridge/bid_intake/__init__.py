"""Bid intake package (Phase 25, build slot 25, v5.7.0).

Automates bid invite intake from BuildingConnected (Autodesk).
Downloads drawings, triggers takeoff pipeline, presents Owner
with a pre-analyzed project card.

Voice rules: zero em-dashes. Hyphens or periods only.
"""

from .buildingconnected import (
    check_bc_status,
    poll_bid_invites,
    download_bid_package,
)

__all__ = ["check_bc_status", "poll_bid_invites", "download_bid_package"]
