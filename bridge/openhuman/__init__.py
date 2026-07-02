"""OpenHuman sidecar integration (Phase 29, v6.1.0).

OpenHuman is the "office manager brain." Our app is the "structural
steel engine." They communicate via JSON-RPC at localhost:7788.

OpenHuman provides: OAuth (118+ services), Memory Tree (auto-indexing),
auto-fetch (20-min loop), subconscious loop (event-driven triggers).

Our app provides: AISC validation, calculators, vision pipeline,
CNC output, connection design, Tekla/Strumis export.

Voice rules: zero em-dashes. Hyphens or periods only.
"""

from .rpc_client import OpenHumanClient
from .memory_bridge import search_memory, index_project
from .watchdog_bridge import get_recent_files, register_file_callback
from .skill_manifest import register_skill, get_skill_status, SKILL_MANIFEST

__all__ = [
    "OpenHumanClient",
    "search_memory",
    "index_project",
    "get_recent_files",
    "register_file_callback",
    "register_skill",
    "get_skill_status",
    "SKILL_MANIFEST",
]
