"""Session Context Store - persists data between commands within a session.

Root cause fix for three problems:
  1. "create a 3D model" fires the guard even though the auto-pipeline
     just extracted 22 members from the PDF the user dropped.
  2. Buttons (GENERATE PROPOSAL, EXPORT TO TEKLA, etc.) inject text
     instead of calling Bridge methods with project context.
  3. PDF drop -> extract -> AISC -> STL has no chain; each step is
     standalone.

This module stores the current session's working data so every command
can see what the previous command produced.

Usage:
    from bridge.session_context import ctx

    # After auto-pipeline extracts members:
    ctx.set_takeoff(project_id="PRJ-2026-ASI-007", members=[...], tonnage=19.01)

    # When 3D model is requested:
    takeoff = ctx.get_takeoff()
    if takeoff:
        # Use takeoff["members"] to generate STL - no guard needed
        ...

    # When proposal is requested:
    project = ctx.get_project()
    # Has everything: members, tonnage, estimate, project_id
"""

import json
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("session_context")

_DATA_DIR = Path(__file__).parent.parent / "data" / "session"


@dataclass
class TakeoffData:
    """Extracted takeoff from a PDF or manual entry."""
    project_id: str = ""
    project_name: str = ""
    members: list[dict] = field(default_factory=list)
    member_count: int = 0
    tonnage: float = 0.0
    method: str = ""          # "pdfplumber", "gemini_vision", "manual"
    source_pdf: str = ""
    extracted_at: str = ""
    aisc_verified: bool = False


@dataclass
class EstimateData:
    """Cost estimate from the calculator."""
    fabrication: float = 0.0
    erection: float = 0.0
    gna: float = 0.0
    total: float = 0.0
    range_low: float = 0.0
    range_high: float = 0.0
    rates_source: str = "bid_rates.json"


@dataclass
class SessionContext:
    """Current session state. Persists across commands within one session."""
    # Project identity
    project_id: str = ""
    project_name: str = ""
    gc_name: str = ""
    gc_email: str = ""
    bid_due: str = ""
    site_address: str = ""

    # Extracted data
    takeoff: Optional[TakeoffData] = None
    estimate: Optional[EstimateData] = None

    # File paths
    source_pdf: str = ""
    output_folder: str = ""
    proposal_pdf: str = ""
    gp_report_pdf: str = ""
    stl_path: str = ""
    tekla_xml_path: str = ""

    # Session tracking
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = ""
    command_count: int = 0


class SessionStore:
    """Thread-safe session context that persists between commands."""

    def __init__(self):
        self._ctx = SessionContext()
        self._lock = threading.Lock()
        _DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Takeoff ----

    def set_takeoff(
        self,
        project_id: str = "",
        project_name: str = "",
        members: list = None,
        tonnage: float = 0.0,
        method: str = "",
        source_pdf: str = "",
    ) -> TakeoffData:
        """Store takeoff results from auto-pipeline or manual entry."""
        with self._lock:
            takeoff = TakeoffData(
                project_id=project_id or self._ctx.project_id,
                project_name=project_name or self._ctx.project_name,
                members=members or [],
                member_count=len(members or []),
                tonnage=tonnage,
                method=method,
                source_pdf=source_pdf,
                extracted_at=datetime.now(timezone.utc).isoformat(),
                aisc_verified=True,
            )
            self._ctx.takeoff = takeoff
            self._ctx.project_id = takeoff.project_id
            self._ctx.project_name = takeoff.project_name
            self._ctx.source_pdf = source_pdf
            self._ctx.last_updated = datetime.now(timezone.utc).isoformat()
            self._ctx.command_count += 1
            self._save()
            log.info(
                "Takeoff stored: %s, %d members, %.2f tons",
                project_id, takeoff.member_count, tonnage,
            )
            return takeoff

    def get_takeoff(self) -> Optional[TakeoffData]:
        """Get the current session's takeoff data, if any."""
        with self._lock:
            return self._ctx.takeoff

    def has_takeoff(self) -> bool:
        """Check if there's an active takeoff in session."""
        with self._lock:
            return self._ctx.takeoff is not None and self._ctx.takeoff.member_count > 0

    # ---- Estimate ----

    def set_estimate(
        self,
        fabrication: float = 0.0,
        erection: float = 0.0,
        gna: float = 0.0,
        total: float = 0.0,
        range_low: float = 0.0,
        range_high: float = 0.0,
    ) -> EstimateData:
        """Store cost estimate."""
        with self._lock:
            est = EstimateData(
                fabrication=fabrication,
                erection=erection,
                gna=gna,
                total=total,
                range_low=range_low,
                range_high=range_high,
            )
            self._ctx.estimate = est
            self._ctx.last_updated = datetime.now(timezone.utc).isoformat()
            self._ctx.command_count += 1
            self._save()
            return est

    def get_estimate(self) -> Optional[EstimateData]:
        """Get the current session's estimate."""
        with self._lock:
            return self._ctx.estimate

    # ---- Project details ----

    def set_project_details(self, **kwargs):
        """Update project details (gc_name, gc_email, bid_due, site_address, etc.)."""
        with self._lock:
            for key, val in kwargs.items():
                if hasattr(self._ctx, key) and val:
                    setattr(self._ctx, key, val)
            self._ctx.last_updated = datetime.now(timezone.utc).isoformat()
            self._ctx.command_count += 1
            self._save()

    def set_output_path(self, key: str, path: str):
        """Store an output file path (stl_path, proposal_pdf, etc.)."""
        with self._lock:
            if hasattr(self._ctx, key):
                setattr(self._ctx, key, path)
                self._ctx.last_updated = datetime.now(timezone.utc).isoformat()
                self._save()

    # ---- Full context ----

    def get_project(self) -> dict:
        """Get full project context as a dict for passing to Bridge methods."""
        with self._lock:
            result = {
                "project_id": self._ctx.project_id,
                "project_name": self._ctx.project_name,
                "gc_name": self._ctx.gc_name,
                "gc_email": self._ctx.gc_email,
                "bid_due": self._ctx.bid_due,
                "site_address": self._ctx.site_address,
                "source_pdf": self._ctx.source_pdf,
                "output_folder": self._ctx.output_folder,
                "command_count": self._ctx.command_count,
            }
            if self._ctx.takeoff:
                result["takeoff"] = {
                    "members": self._ctx.takeoff.members,
                    "member_count": self._ctx.takeoff.member_count,
                    "tonnage": self._ctx.takeoff.tonnage,
                    "method": self._ctx.takeoff.method,
                    "aisc_verified": self._ctx.takeoff.aisc_verified,
                }
            if self._ctx.estimate:
                result["estimate"] = {
                    "total": self._ctx.estimate.total,
                    "fabrication": self._ctx.estimate.fabrication,
                    "erection": self._ctx.estimate.erection,
                    "range_low": self._ctx.estimate.range_low,
                    "range_high": self._ctx.estimate.range_high,
                }
            return result

    def get_members_for_3d(self) -> list[dict]:
        """Get member list formatted for 3D model generation.

        Returns list of dicts with shape, length, count for each member.
        Returns empty list if no takeoff in session.
        """
        with self._lock:
            if not self._ctx.takeoff or not self._ctx.takeoff.members:
                return []
            return self._ctx.takeoff.members

    def get_shapes_list(self) -> list[str]:
        """Get unique AISC shape designations from the current takeoff."""
        with self._lock:
            if not self._ctx.takeoff or not self._ctx.takeoff.members:
                return []
            shapes = set()
            for m in self._ctx.takeoff.members:
                shape = m.get("shape", m.get("designation", m.get("name", "")))
                if shape:
                    shapes.add(shape)
            return sorted(shapes)

    # ---- Reset ----

    def clear(self):
        """Clear session context for a new project."""
        with self._lock:
            self._ctx = SessionContext()
            self._save()

    # ---- Persistence ----

    def _save(self):
        """Save session to disk so it survives across messages."""
        try:
            path = _DATA_DIR / "current_session.json"
            data = {
                "project_id": self._ctx.project_id,
                "project_name": self._ctx.project_name,
                "gc_name": self._ctx.gc_name,
                "gc_email": self._ctx.gc_email,
                "source_pdf": self._ctx.source_pdf,
                "output_folder": self._ctx.output_folder,
                "command_count": self._ctx.command_count,
                "started_at": self._ctx.started_at,
                "last_updated": self._ctx.last_updated,
            }
            if self._ctx.takeoff:
                data["takeoff"] = asdict(self._ctx.takeoff)
            if self._ctx.estimate:
                data["estimate"] = asdict(self._ctx.estimate)
            path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            log.warning("Session save failed: %s", e)

    def _load(self):
        """Load session from disk if it exists."""
        try:
            path = _DATA_DIR / "current_session.json"
            if path.exists():
                data = json.loads(path.read_text())
                for key in ("project_id", "project_name", "gc_name",
                            "gc_email", "source_pdf", "output_folder"):
                    if key in data:
                        setattr(self._ctx, key, data[key])
                if "takeoff" in data and data["takeoff"]:
                    self._ctx.takeoff = TakeoffData(**data["takeoff"])
                if "estimate" in data and data["estimate"]:
                    self._ctx.estimate = EstimateData(**data["estimate"])
        except Exception as e:
            log.warning("Session load failed: %s", e)


# ---- Singleton ----

_store: Optional[SessionStore] = None


def get_session() -> SessionStore:
    """Get the singleton SessionStore."""
    global _store
    if _store is None:
        _store = SessionStore()
        _store._load()
    return _store


# Convenience alias
ctx = get_session
