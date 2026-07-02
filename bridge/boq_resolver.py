"""
boq_resolver.py

Picks the best available BOQ source for a bid.

Resolution order (configurable via boq_sources registry, sorted by fidelity_rank):
  1. PlanSwift export (CSV or XLSX)
  2. Bluebeam markup data
  3. Hand-keyed estimator Excel
  4. Synthetic pattern-derived fallback (always available)

The first adapter that successfully probes wins. If multiple sources are
present (e.g. Ivan ran PlanSwift but Joseph also marked up Bluebeam),
the higher-fidelity one is used and the others are logged.

Usage from the bid pipeline
---------------------------
    from bridge.boq_resolver import resolve_boq, BoqContext

    payload = resolve_boq(BoqContext(
        bid_id=42,
        bid_name="Northside Launchpad",
        bid_folder=Path("C:/Users/YourUser/Documents/Your Company Bids/2026-05/PRJ-2026-NSL-001"),
    ))
    # payload.boq_origin -> "planswift" | "bluebeam" | "manual_excel" | "synthetic"
    # payload.rows       -> estimate-line dicts
    # payload.notes      -> any source-specific notes

The pipeline writes payload.boq_origin to the bid row in bid_pipeline.db.
The reconciliation skill reads it back to satisfy Ivan-rule F.

Hard rules respected
--------------------
- Never trusts a synthetic BOQ as the final answer. Synthetic is allowed
  but always marked so reconciliation flags it.
- Does not call any adapter's load() until its probe() returns True.
- Logs which adapters were probed and which won via the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

# Import for side effect: registers built-in adapters
from bridge import boq_sources
from bridge.boq_sources import BoqContext, BoqPayload

# Side-effect imports so concrete adapters self-register.
try:
    from bridge import planswift_import  # noqa: F401
except Exception:
    pass
try:
    from bridge import bluebeam_boq_adapter  # noqa: F401
except Exception:
    pass


@dataclass
class ResolutionResult:
    payload: BoqPayload
    chosen_adapter: str
    probed_adapters: List[str]
    skipped_adapters: List[str]
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "payload": self.payload.as_dict(),
            "chosen_adapter": self.chosen_adapter,
            "probed_adapters": self.probed_adapters,
            "skipped_adapters": self.skipped_adapters,
            "notes": self.notes,
        }


def resolve_boq(ctx: BoqContext) -> ResolutionResult:
    """Walk the registry in fidelity order. First successful probe wins.

    Synthetic is always last and always wins if nothing else does. So
    this function never raises - it always returns a payload.
    """
    probed: List[str] = []
    skipped: List[str] = []
    notes: List[str] = []

    registry = boq_sources.get_registry()
    if not registry:
        # Defensive: registry should always have at least synthetic.
        boq_sources._bootstrap()  # type: ignore[attr-defined]
        registry = boq_sources.get_registry()

    for adapter in registry:
        probed.append(adapter.name)
        try:
            ok = adapter.probe(ctx)
        except Exception as e:
            notes.append(f"probe({adapter.name}) raised: {e}")
            ok = False
        if not ok:
            skipped.append(adapter.name)
            continue
        # Found a usable source - load and return.
        try:
            payload = adapter.load(ctx)
        except Exception as e:
            notes.append(f"load({adapter.name}) raised: {e} - skipping")
            skipped.append(adapter.name)
            continue
        return ResolutionResult(
            payload=payload,
            chosen_adapter=adapter.name,
            probed_adapters=probed,
            skipped_adapters=skipped,
            notes=notes,
        )

    # Should be unreachable because synthetic always probes True.
    # Defensive fallback.
    fallback = boq_sources.SYNTHETIC_ADAPTER.load(ctx)
    return ResolutionResult(
        payload=fallback,
        chosen_adapter="synthetic",
        probed_adapters=probed,
        skipped_adapters=skipped,
        notes=notes + ["No adapter resolved; forced synthetic fallback."],
    )


def list_available_sources(ctx: BoqContext) -> List[Dict[str, Any]]:
    """Inventory all sources that *could* serve this bid, in fidelity order.

    Useful for the operator UI: shows what is available, which one would
    be chosen, and which others would be skipped.
    """
    out = []
    for adapter in boq_sources.get_registry():
        try:
            can = adapter.probe(ctx)
        except Exception as e:
            can = False
            out.append({
                "name": adapter.name,
                "fidelity_rank": adapter.fidelity_rank,
                "available": False,
                "error": str(e),
            })
            continue
        out.append({
            "name": adapter.name,
            "fidelity_rank": adapter.fidelity_rank,
            "available": can,
            "description": adapter.description,
        })
    return out
