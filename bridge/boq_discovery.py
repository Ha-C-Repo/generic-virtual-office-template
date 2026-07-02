"""F23: Auto-discover existing BOQ / Bluebeam markups in a project folder.

Scans a project workspace for any pre-existing human-verified takeoff:
- Assemblies BOQ.xlsx (ConstructIQ standard)
- *_BOQ.xlsx, *boq*.xlsx (any naming variant)
- *_markups.csv (Bluebeam Markups Summary export)
- *markups*.csv

Returns the highest-priority match. Priority order:
    1. Explicit "Assemblies BOQ.xlsx" in 3. Estimate/
    2. Any *_BOQ.xlsx in 3. Estimate/
    3. Any *markups*.csv in 3. Estimate/ or 4. Correspondence/
    4. Any *.xlsx with "boq" in name anywhere under the project
    5. None
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional


def discover_boq(project_folder) -> Optional[dict]:
    """Walk project_folder looking for a usable BOQ source.

    Returns dict {kind, path, priority} or None.
    kind ∈ {"assemblies_xlsx", "boq_xlsx", "markups_csv", "boq_xlsx_loose"}
    """
    if not project_folder:
        return None
    root = Path(project_folder)
    if not root.exists():
        return None

    # Priority 1: 3. Estimate/Assemblies BOQ.xlsx
    p1 = root / "3. Estimate" / "Assemblies BOQ.xlsx"
    if p1.exists():
        return {"kind": "assemblies_xlsx", "path": str(p1), "priority": 1}

    # Priority 2: 3. Estimate/*_BOQ.xlsx
    estimate = root / "3. Estimate"
    if estimate.exists():
        for p in estimate.glob("*BOQ*.xlsx"):
            return {"kind": "boq_xlsx", "path": str(p), "priority": 2}
        for p in estimate.glob("*boq*.xlsx"):
            return {"kind": "boq_xlsx", "path": str(p), "priority": 2}

    # Priority 3: any markups CSV under project
    for sub in ("3. Estimate", "4. Correspondence"):
        d = root / sub
        if d.exists():
            for p in d.glob("*markups*.csv"):
                return {"kind": "markups_csv", "path": str(p), "priority": 3}
            for p in d.glob("*Markups*.csv"):
                return {"kind": "markups_csv", "path": str(p), "priority": 3}

    # Priority 4: anywhere under project, loose match
    for p in root.rglob("*BOQ*.xlsx"):
        return {"kind": "boq_xlsx_loose", "path": str(p), "priority": 4}
    for p in root.rglob("*boq*.xlsx"):
        return {"kind": "boq_xlsx_loose", "path": str(p), "priority": 4}
    for p in root.rglob("*markups*.csv"):
        return {"kind": "markups_csv", "path": str(p), "priority": 4}

    return None


def discover_pdf(project_folder) -> Optional[str]:
    """Find the structural drawing PDF in a project folder.

    Looks under '1. Project Docs' and '7. Site' first.
    """
    if not project_folder:
        return None
    root = Path(project_folder)
    if not root.exists():
        return None

    for sub in ("1. Project Docs", "7. Site"):
        d = root / sub
        if d.exists():
            for p in d.glob("*structural*.pdf"):
                return str(p)
            for p in d.glob("*Structural*.pdf"):
                return str(p)
            for p in d.glob("*.pdf"):
                # Skip already-generated tagged/client/GP PDFs
                low = p.name.lower()
                if any(x in low for x in ("_tagged", "_client", "_gp",
                                          "client.pdf", "gp.pdf")):
                    continue
                return str(p)
    return None
