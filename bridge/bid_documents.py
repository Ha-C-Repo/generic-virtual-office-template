"""
Bid Document Filing
====================
Auto-routes generated bid artifacts (proposals, internal estimates,
3D models, takeoff schedules, chat logs) to a structured folder under
the user's Documents directory.

Folder layout - mirrors how Owner already files projects by month:

    %USERPROFILE%\\Documents\\Your Company Bids\\
    └── 2026-05\\                                       # Year-month
        └── PRJ-2026-NTH-001 - Northlake Public Works\\  # Bid number + name
            ├── proposal.pdf                            # Client-facing (Owner signs)
            ├── internal_estimate.pdf                   # Internal cost detail
            ├── takeoff.json                            # Verified member schedule
            ├── 3d_model.stl                            # Tagged STL from drawings
            ├── source_drawings/                        # Original uploaded PDFs
            └── chat_log.md                             # Decision trail

Cross-platform: Windows uses %USERPROFILE%\\Documents, macOS/Linux use
~/Documents. Both honor pywebview's filesystem assumptions.

Public API:
    bids_root()                                    → Path to bids folder
    bid_folder(bid_number, project_name=None)      → Path to bid subfolder
    save_artifact(bid_number, filename, content)   → Path saved
    list_artifacts(bid_number)                     → List of artifact dicts
    open_in_explorer(path)                         → Opens path in OS file browser
    bid_number_from_project(project_name)          → Suggests NC-YYYY-XXX-NNN
"""

import base64
import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Folder name under Documents/ - matches what Owner expects to see
_BIDS_DIR_NAME = "Your Company Bids"


def _user_documents() -> Path:
    """Return the user's Documents folder, cross-platform.

    Windows: %USERPROFILE%\\Documents (or OneDrive Documents if redirected)
    macOS:   ~/Documents
    Linux:   ~/Documents
    """
    home = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
    # Windows OneDrive Known Folder Move can redirect Documents - check both
    candidates = [
        home / "Documents",
        home / "OneDrive" / "Documents",
        home / "OneDrive - Your Company" / "Documents",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    # Fallback: create the standard Documents folder
    fallback = home / "Documents"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def bids_root() -> Path:
    """Path to %USERPROFILE%\\Documents\\Your Company Bids (creates if missing)."""
    root = _user_documents() / _BIDS_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_folder_name(name: str) -> str:
    """Sanitize a string for use as a folder name on Windows/macOS/Linux."""
    if not name:
        return ""
    # Strip Windows-illegal chars: < > : " / \ | ? *
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip().rstrip(".")
    # Collapse repeated whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Limit length so the full path stays under Windows MAX_PATH headroom
    return cleaned[:80]


def bid_folder(bid_number: str, project_name: str | None = None,
                created_at: datetime | None = None) -> Path:
    """Return the bid's subfolder, creating year-month + bid folders as needed.

    Args:
        bid_number: e.g. "PRJ-2026-NTH-001"
        project_name: e.g. "Northlake Public Works" - appended to folder name
                      for human navigability. Optional but recommended.
        created_at: defaults to today; used to pick the year-month folder.
    """
    if not bid_number:
        raise ValueError("bid_number required")
    bid_number = bid_number.strip()
    when = created_at or datetime.now()  # vj: local-time-ok
    year_month = when.strftime("%Y-%m")

    # Folder name: "PRJ-2026-NTH-001 - Northlake Public Works" (project name optional)
    folder_name = bid_number
    if project_name:
        clean_proj = _safe_folder_name(project_name)
        if clean_proj:
            folder_name = f"{bid_number} - {clean_proj}"

    folder = bids_root() / year_month / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_artifact(bid_number: str, filename: str, content: bytes | str,
                   project_name: str | None = None,
                   subfolder: str | None = None) -> Path:
    """Save a single artifact under the bid's folder. Returns the saved path.

    Args:
        bid_number: e.g. "PRJ-2026-NTH-001"
        filename: e.g. "proposal.pdf" - sanitized to remove path separators
        content: bytes or str - bytes written as binary, str written as UTF-8
        project_name: optional, used in folder name on first save
        subfolder: optional - e.g. "source_drawings" for the original PDFs.
                   Created under the bid folder as needed.
    """
    if not filename:
        raise ValueError("filename required")
    # Strip path separators from filename - must not escape the bid folder.
    # Replace illegal chars with _, then collapse leading dots/underscores
    # so filenames like "../../escape.pdf" don't yield ".._.._escape.pdf".
    safe_name = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", filename).strip()
    safe_name = re.sub(r"^[._]+", "", safe_name)
    # Also collapse "_._" sequences (artifacts of stripping ../)
    safe_name = re.sub(r"_+\.+_+", "_", safe_name)
    safe_name = re.sub(r"_+", "_", safe_name).strip("_")
    if not safe_name:
        raise ValueError(f"filename {filename!r} sanitizes to empty")

    folder = bid_folder(bid_number, project_name)
    if subfolder:
        folder = folder / _safe_folder_name(subfolder)
        folder.mkdir(parents=True, exist_ok=True)

    target = folder / safe_name
    if isinstance(content, str):
        target.write_text(content, encoding="utf-8")
    else:
        target.write_bytes(content)
    return target


def save_artifact_b64(bid_number: str, filename: str, content_b64: str,
                       project_name: str | None = None,
                       subfolder: str | None = None) -> Path:
    """Same as save_artifact but accepts base64-encoded bytes.

    Useful when called from the frontend - JSON can't carry raw binary, so
    PDFs/STLs from the chat layer arrive base64-encoded.
    """
    raw = base64.b64decode(content_b64)
    return save_artifact(bid_number, filename, raw, project_name, subfolder)


def list_artifacts(bid_number: str,
                    project_name: str | None = None) -> list[dict[str, Any]]:
    """List every file under a bid's folder. Used by the chat to show
    'already saved' badges and the MODEL tab to find STLs.
    """
    folder = bid_folder(bid_number, project_name)
    out = []
    for p in sorted(folder.rglob("*")):
        if p.is_file():
            try:
                stat = p.stat()
                out.append({
                    "name":      p.name,
                    "path":      str(p),
                    "size_kb":   round(stat.st_size / 1024, 1),
                    "modified":  datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "subfolder": str(p.parent.relative_to(folder)) if p.parent != folder else "",
                    "kind":      _classify_artifact(p.name),
                })
            except OSError:
                continue
    return out


def _classify_artifact(filename: str) -> str:
    """Tag a file as proposal | internal | takeoff | model | drawing | other.
    Used by the frontend for icon selection.
    """
    f = filename.lower()
    if "proposal" in f or f.endswith("_proposal.pdf"):
        return "proposal"
    if "internal" in f or "estimate" in f:
        return "internal"
    if "takeoff" in f or (f.endswith(".json") and "manifest" not in f and "_meta" not in f):
        return "takeoff"
    if f.endswith(".stl") or "3d" in f or "model" in f:
        return "model"
    if "drawing" in f or "rev_" in f or "sheet" in f:
        return "drawing"
    if f.endswith(".pdf"):
        return "pdf"
    return "other"


def open_in_explorer(path: str | Path) -> dict:
    """Open a path in the OS file browser. Returns ok/error dict.

    Windows: explorer.exe (selects the file if path is a file)
    macOS:   open
    Linux:   xdg-open

    Used by the chat's "Open Folder" button.
    """
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"Path does not exist: {p}"}
    try:
        system = platform.system()
        if system == "Windows":
            if p.is_file():
                # /select highlights the file in Explorer
                subprocess.Popen(["explorer.exe", "/select,", str(p)])
            else:
                os.startfile(str(p))   # type: ignore[attr-defined]
        elif system == "Darwin":
            if p.is_dir():
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["open", "-R", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p if p.is_dir() else p.parent)])
        return {"ok": True, "opened": str(p)}
    except Exception as e:
        return {"ok": False, "error": f"Could not open {p}: {e}"}


def bid_number_from_project(project_name: str,
                              location_code: str | None = None) -> str:
    """Suggest a bid number like 'PRJ-2026-NTH-001' from a project name.

    Reads existing bid folders under the current year to find the next
    sequence number. Doesn't claim/reserve - just suggests; caller can
    accept or override.

    Args:
        project_name: e.g. "Northlake Public Works"
        location_code: optional 2-4 letter prefix (e.g. "NTH", "BAY").
                       If omitted, derived from first letters of project_name.
    """
    year = datetime.now().year  # vj: local-time-ok
    if not location_code:
        # First 3 letters of first significant word
        words = re.findall(r"\b[A-Za-z]{3,}", project_name or "BID")
        location_code = (words[0][:3] if words else "GEN").upper()
    location_code = re.sub(r"[^A-Z]", "", location_code.upper())[:4] or "GEN"

    # Scan existing folders for the year to find next sequence
    root = bids_root()
    existing = []
    pattern = re.compile(rf"^NC-{year}-{location_code}-(\d{{3}})\b")
    for ym in root.glob(f"{year}-*"):
        if not ym.is_dir():
            continue
        for sub in ym.iterdir():
            m = pattern.match(sub.name)
            if m:
                existing.append(int(m.group(1)))
    next_seq = max(existing) + 1 if existing else 1
    return f"NC-{year}-{location_code}-{next_seq:03d}"


def manifest_path(bid_number: str, project_name: str | None = None) -> Path:
    """Path to the bid folder's `manifest.json` - central record of artifacts."""
    return bid_folder(bid_number, project_name) / "manifest.json"


def update_manifest(bid_number: str, key: str, value: Any,
                     project_name: str | None = None) -> Path:
    """Update the bid's manifest.json with a single key/value. Creates if missing.
    The manifest tracks: bid_number, project_name, status, created_at, last_updated,
    artifacts_saved (list), 3d_model_status, total_tonnage, total_price, etc.
    """
    p = manifest_path(bid_number, project_name)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {
            "bid_number":    bid_number,
            "project_name":  project_name or "",
            "created_at":    datetime.now(timezone.utc).isoformat(),
        }
    data[key] = value
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def get_manifest(bid_number: str, project_name: str | None = None) -> dict:
    """Read the bid's manifest.json. Returns {} if missing."""
    p = manifest_path(bid_number, project_name)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def find_render(project_name: str | None = None,
                bid_number: str | None = None) -> str:
    """Locate an illustrative project render for a bid, if one exists.

    The Cowork steel-render pipeline saves drawing-anchored renders into the
    bid's ``renders/`` subfolder. The client proposal embeds one as a cover
    image (see documents.generate_proposal render_path). Preference order:
    a member-accurate Tekla viewport export (name contains ``tekla`` or
    ``viewport``), then the in-house estimate-grade MODEL viewport (stem ends
    ``_MODEL``), then a fused ``MASTER``, then the newest image by mtime within
    whichever tier matches first. Returns a path string, or "" when no render is
    present (proposal stays text-only).
    """
    exts = (".jpg", ".jpeg", ".png", ".webp")
    candidates: list[Path] = []

    def _collect(renders_dir: Path):
        if renders_dir.is_dir():
            for f in renders_dir.iterdir():
                if f.is_file() and f.suffix.lower() in exts:
                    candidates.append(f)

    try:
        if bid_number:
            _collect(bid_folder(bid_number, project_name) / "renders")
        if not candidates and project_name:
            target = _safe_folder_name(project_name).lower()
            root = bids_root()
            if root.is_dir():
                for month in root.iterdir():
                    if not month.is_dir():
                        continue
                    for job in month.iterdir():
                        if job.is_dir() and target and target in job.name.lower():
                            _collect(job / "renders")
        if not candidates and project_name:
            target = _safe_folder_name(project_name).lower()
            work = Path(__file__).resolve().parent.parent / "Bids To Estimate"
            if work.is_dir():
                for job in work.iterdir():
                    if job.is_dir() and target and target in job.name.lower():
                        _collect(job / "renders")
    except Exception:
        return ""

    if not candidates:
        return ""
    def _pref(tokens):
        return [c for c in candidates if any(t in c.name.lower() for t in tokens)]
    # Member-accurate Tekla viewport export wins; then the in-house estimate-grade
    # MODEL viewport from the verified takeoff (the pipeline writes <name>_MODEL.png,
    # matched by stem suffix so a coincidental "model" in a filename does not
    # qualify); then a fused MASTER; then newest.
    model_tier = [c for c in candidates if c.stem.lower().endswith("_model")]
    pool = (_pref(["tekla", "viewport"]) or model_tier
            or _pref(["master"]) or candidates)
    pool.sort(key=lambda c: c.stat().st_mtime, reverse=True)
    return str(pool[0])
