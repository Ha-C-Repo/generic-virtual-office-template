"""Value engineering package (Phase 19, build slot 19, v5.1.0).

Fabricators who submit VE proposals alongside their base bid win more
work. The GC sees: "Base bid: $485,000. Alternate with VE: $452,000."

Modules:
    section_optimizer       - Lighter AISC shapes from aisc_master.csv
    connection_standardizer - Reduce bolt pattern variety
    ve_report_gen           - Combined VE proposal summary

Voice rules: zero em-dashes. Hyphens or periods only.
"""

from .section_optimizer import find_lighter_section, optimize_project
from .connection_standardizer import analyze_bolt_patterns
from .ve_report_gen import generate_ve_report

__all__ = [
    "find_lighter_section",
    "optimize_project",
    "analyze_bolt_patterns",
    "generate_ve_report",
]
