"""
boq_sources.py

Registry of takeoff sources, fidelity-ranked.

The bid pipeline must not assume a single takeoff tool. Different bids
arrive with different artifacts:
  - Ivan-run PlanSwift export (highest fidelity, AISC weights verified)
  - Bluebeam markup (measured but not weight-verified)
  - Hand-keyed estimator Excel
  - Pattern-derived synthetic BOQ (placeholder only, must be flagged)

This module exposes a registry of source adapters. The resolver picks
the highest-fidelity source available for a given bid. Reconciliation
records which source was used via the boq_origin field.

Each adapter implements two methods:
  probe(ctx) -> bool       # can this source provide BOQ data for this bid?
  load(ctx)  -> dict       # normalized BOQ payload + metadata

The ctx dict carries (at minimum):
  bid_id, bid_name, bid_folder (Path), explicit_path (Path or None).

Adapters return a payload dict:
  {
    "rows": [estimate-line dicts conforming to estimate-line.schema.json],
    "boq_origin": str (planswift|bluebeam|manual_excel|synthetic),
    "source_file": str path,
    "row_count": int,
    "fidelity_rank": int (1 best),
  }

Hard rules respected
--------------------
- Does NOT replace existing bluebeam_import.py or takeoff_controller.py.
  This is a sibling layer that wraps them as adapters.
- Synthetic fallback always sets boq_origin="synthetic" so the
  reconciliation skill can flag the bid as "BOQ NOT FROM PLANSWIFT".
- AISC weights still come from bridge/aisc_validator.py. This module
  only sources quantities, not weights.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, List, Dict, Any


# -------- Fidelity ranks (lower = better) --------
FIDELITY_PLANSWIFT    = 1   # Ivan-approved real takeoff
FIDELITY_BLUEBEAM     = 2   # measured markup, no weight verification
FIDELITY_MANUAL_EXCEL = 3   # hand-keyed estimator workbook
FIDELITY_SYNTHETIC    = 4   # pattern-derived placeholder, always flagged


@dataclass
class BoqContext:
    """Input to a BOQ source's probe + load."""
    bid_id: Optional[int] = None
    bid_name: str = ""
    bid_folder: Optional[Path] = None        # the per-bid project folder
    explicit_path: Optional[Path] = None     # operator-supplied file path
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BoqPayload:
    """What every source returns."""
    rows: List[Dict[str, Any]]
    boq_origin: str
    source_file: str
    row_count: int
    fidelity_rank: int
    notes: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "rows": self.rows,
            "boq_origin": self.boq_origin,
            "source_file": self.source_file,
            "row_count": self.row_count,
            "fidelity_rank": self.fidelity_rank,
            "notes": self.notes,
        }


@dataclass
class BoqSourceAdapter:
    """One source. probe() answers can-you-handle-this, load() returns data."""
    name: str
    fidelity_rank: int
    probe: Callable[[BoqContext], bool]
    load: Callable[[BoqContext], BoqPayload]
    description: str = ""


# -------- Module-level registry --------
_REGISTRY: List[BoqSourceAdapter] = []


def register(adapter: BoqSourceAdapter) -> None:
    """Add an adapter. Idempotent on adapter.name."""
    global _REGISTRY
    _REGISTRY = [a for a in _REGISTRY if a.name != adapter.name]
    _REGISTRY.append(adapter)
    _REGISTRY.sort(key=lambda a: a.fidelity_rank)


def get_registry() -> List[BoqSourceAdapter]:
    """Return registered adapters in fidelity order (best first)."""
    return list(_REGISTRY)


def clear_registry() -> None:
    """Test helper - empty the registry."""
    global _REGISTRY
    _REGISTRY = []


# -------- Synthetic fallback (always last-resort) --------

def _synthetic_probe(ctx: BoqContext) -> bool:
    return True  # synthetic always available as the lowest fallback


def _synthetic_load(ctx: BoqContext) -> BoqPayload:
    """Return an empty placeholder marked synthetic. The estimating skills
    can still produce pattern-derived lines but they must use this origin
    string so reconciliation flags them."""
    return BoqPayload(
        rows=[],
        boq_origin="synthetic",
        source_file="",
        row_count=0,
        fidelity_rank=FIDELITY_SYNTHETIC,
        notes=(
            "No PlanSwift, Bluebeam, or manual workbook found for this bid. "
            "Pipeline will fall back to pattern-derived synthetic quantities. "
            "Reconciliation will flag this bid HIGH - BOQ_NOT_PLANSWIFT until "
            "Ivan provides a real takeoff."
        ),
    )


SYNTHETIC_ADAPTER = BoqSourceAdapter(
    name="synthetic",
    fidelity_rank=FIDELITY_SYNTHETIC,
    probe=_synthetic_probe,
    load=_synthetic_load,
    description="Pattern-derived placeholder. Last-resort fallback.",
)


def _bootstrap() -> None:
    """Register the built-in adapters. Called on import."""
    if not _REGISTRY:
        register(SYNTHETIC_ADAPTER)
    # PlanSwift and Bluebeam adapters self-register in their own modules
    # to keep dependencies one-way.


_bootstrap()
