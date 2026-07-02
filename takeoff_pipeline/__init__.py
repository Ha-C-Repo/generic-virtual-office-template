"""Takeoff pipeline package - standalone, no bridge/ imports.

Member census spike (Prompt 4): sheet_router (T1), census (T2),
scale_check (T3), score_spike (scoring harness). Conforms to
takeoff_pipeline/docs/TAKEOFF_SCHEMA_V2.md; where code and that
document disagree, the document wins.

Counts only. No pricing anywhere (P25). No AISC weight math here;
weights are derived downstream per schema section 4.

Paths are package-relative on purpose. If a module is later promoted
into bridge/, its paths switch to vo_app._resources.resource_path()
at that time (per the prompt that built this spike).
"""

__all__ = ["sheet_router", "census", "scale_check", "score_spike"]
