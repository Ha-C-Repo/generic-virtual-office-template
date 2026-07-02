"""Per-bid cost tracker for the three-tier vision pipeline.

Tracks calls and estimated cost for each tier within a single bid run.
The tier router consults the tracker before escalating to Tier 3, so a
runaway bid cannot blow the per-bid cost cap.

Costs are estimates, not invoices. We track:
    - Tier 1 (DocTR): zero cost, but tracked for analytics.
    - Tier 2 (Gemini): per-call estimate based on token bands. Falls
      under the existing Gemini Premium subscription, so this is a
      quota check, not a dollar check.
    - Tier 3 (GPT-4o via OpenRouter): real per-call cost in USD. We
      cap this at $1.50 per bid by default. Configurable in
      data/governance.json under "vision_tiers.tier3_cap_usd".

Voice rules: zero em-dashes. Hyphens or periods only.
"""


from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import threading


# Per-call cost estimates in USD. These are conservative upper bounds.
# Joseph can adjust in governance.json without touching code.
TIER_COST_PER_CALL = {
    "doctr": 0.0,
    "gemini": 0.0,         # covered by Gemini Premium subscription
    "gpt4o": 0.05,         # via OpenRouter - approximate per-call
    "claude": 0.03,        # crosscheck model for table_extract and ocr_small_text
}


@dataclass
class TierCallRecord:
    """One vision tier call. Cheap to construct, JSON-serializable."""
    tier: str
    task: str
    timestamp: str
    duration_ms: float
    confidence: float
    success: bool
    cost_estimate_usd: float
    subtask: str = ""      # Phase 3 subtask type: ocr_small_text, table_extract, spatial_classify
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "task": self.task,
            "subtask": self.subtask,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "confidence": self.confidence,
            "success": self.success,
            "cost_estimate_usd": self.cost_estimate_usd,
            "notes": self.notes,
        }


@dataclass
class CostTracker:
    """Per-bid call/cost ledger.

    Thread-safe via a single lock. The takeoff controller may run pages
    in parallel in Phase 8 (LangGraph), so concurrent appends must not
    corrupt the call list.
    """
    bid_number: str = ""
    tier3_cap_usd: float = 1.50
    calls: list[TierCallRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock,
                                  repr=False, compare=False)

    def record(self, tier: str, task: str, duration_ms: float,
               confidence: float, success: bool,
               cost_estimate_usd: float | None = None,
               subtask: str = "",
               notes: str = "") -> TierCallRecord:
        """Append a new call record. Returns the record for inspection."""
        if cost_estimate_usd is None:
            cost_estimate_usd = TIER_COST_PER_CALL.get(tier, 0.0)
        rec = TierCallRecord(
            tier=tier,
            task=task,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=float(duration_ms),
            confidence=float(confidence),
            success=bool(success),
            cost_estimate_usd=float(cost_estimate_usd),
            subtask=subtask,
            notes=notes,
        )
        with self._lock:
            self.calls.append(rec)
        return rec

    def total_cost_usd(self) -> float:
        with self._lock:
            return round(sum(c.cost_estimate_usd for c in self.calls), 4)

    def tier3_cost_usd(self) -> float:
        with self._lock:
            return round(sum(c.cost_estimate_usd for c in self.calls
                             if c.tier == "gpt4o"), 4)

    def calls_by_tier(self) -> dict[str, int]:
        out = {"doctr": 0, "gemini": 0, "gpt4o": 0}
        with self._lock:
            for c in self.calls:
                out[c.tier] = out.get(c.tier, 0) + 1
        return out

    def can_escalate_to_tier3(self) -> bool:
        """Return False once Tier 3 cap is exceeded. Tier router uses this
        to decide whether to call GPT-4o or fall back to Tier 2 result."""
        return self.tier3_cost_usd() < self.tier3_cap_usd

    def summary(self) -> dict:
        by_tier = self.calls_by_tier()
        return {
            "bid_number": self.bid_number,
            "calls_total": sum(by_tier.values()),
            "calls_by_tier": by_tier,
            "total_cost_usd": self.total_cost_usd(),
            "tier3_cost_usd": self.tier3_cost_usd(),
            "tier3_cap_usd": self.tier3_cap_usd,
            "tier3_remaining_usd": round(
                max(self.tier3_cap_usd - self.tier3_cost_usd(), 0.0), 4),
        }

    def calls_by_subtask(self) -> dict[str, int]:
        """Count calls grouped by Phase 3 subtask type."""
        out: dict[str, int] = {}
        with self._lock:
            for c in self.calls:
                key = c.subtask or "unclassified"
                out[key] = out.get(key, 0) + 1
        return out

    def cost_by_subtask(self) -> dict[str, float]:
        """Total estimated USD cost grouped by Phase 3 subtask type."""
        out: dict[str, float] = {}
        with self._lock:
            for c in self.calls:
                key = c.subtask or "unclassified"
                out[key] = round(out.get(key, 0.0) + c.cost_estimate_usd, 5)
        return out

    def export_baseline_json(self, output_path: str | Path,
                              project_name: str = "",
                              bid_id: int = 0,
                              tonnage: float = 0.0,
                              pdf_page_count: int = 0,
                              data_source: str = "cost_tracker") -> str:
        """Write a Phase 6 gate baseline entry to a JSON file.

        Appends to the projects list in data/vision_cost_baseline.json if
        the file already exists, otherwise creates it fresh.

        Args:
            output_path:    Target JSON file path.
            project_name:   Human-readable project label.
            bid_id:         Numeric bid ID from bids.db.
            tonnage:        Total tonnage for this bid.
            pdf_page_count: Structural page count from the real PDF.
            data_source:    "real_pdf", "tonnage_scaled_estimate", or
                            "cost_tracker" (when driven by actual calls).

        Returns:
            Path written.
        """
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        existing: dict = {}
        if p.exists():
            try:
                existing = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                existing = {}

        subtask_breakdown = {}
        for st in ("ocr_small_text", "table_extract", "spatial_classify"):
            calls_st = [c for c in self.calls if c.subtask == st]
            cost_st = sum(c.cost_estimate_usd for c in calls_st)
            subtask_breakdown[st] = {
                "calls": len(calls_st),
                "estimated_cost_usd": round(cost_st, 4),
            }

        entry = {
            "bid_id": bid_id,
            "project_name": project_name,
            "tonnage": tonnage,
            "pdf_page_count": pdf_page_count,
            "subtask_breakdown": subtask_breakdown,
            "total_estimated_cost_usd": round(self.total_cost_usd(), 4),
            "data_source": data_source,
        }

        projects: list = existing.get("projects", [])
        # Replace existing entry with same bid_id, otherwise append
        replaced = False
        for i, proj in enumerate(projects):
            if proj.get("bid_id") == bid_id:
                projects[i] = entry
                replaced = True
                break
        if not replaced:
            projects.append(entry)

        baseline = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "methodology": "estimated_from_real_pdf_complexity",
            "tier_rates_usd": {k: v for k, v in TIER_COST_PER_CALL.items()},
            "projects": projects,
        }

        p.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        return str(p)

    def export_jsonl(self, output_path: str | Path) -> str:
        """Append all calls as JSONL to the given path. Returns the path."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with p.open("a", encoding="utf-8") as f:
                for c in self.calls:
                    f.write(json.dumps(c.to_dict()) + "\n")
        return str(p)
