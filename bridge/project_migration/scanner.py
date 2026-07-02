"""Two-pass project file migration scanner.

Pass 1: read-only inventory of an existing directory tree.
Pass 2: copy-only transfer to project schema folders, on explicit approval only.

Hard constraints (do not relax):
- Pass 1 never writes. No exceptions.
- Pass 2 never runs automatically. Explicit per-project instruction required.
- Copy only. Originals remain in place.
- API Keys/ directory is never scanned or touched.
- Supplier names are never written to project documents.
- Fuzzy match threshold 0.70. Below threshold -> unknown list, not auto-categorized.
"""

import difflib
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Verified Your Company project names (CLAUDE.md confirmed portfolio + active bids)
KNOWN_PROJECTS = [
    "ICD Church",
    "ICD Church Spring",
    "Elite Crossing",
    "Elite Crossing Lake Jackson",
    "Elite Crossing Ph2",
    "Topgolf New Braunfels",
    "Carvana Mobile",
    "Carvana Mobile AL",
    "Marathon Galveston Bay",
    "Marathon Galveston Bay Q3",
    "Kinder Morgan Pasadena",
    "Marathon Petroleum",
    "Your Company",
]

# Vendor-related keywords - these docs are flagged, not copied to project folders
KNOWN_VENDORS = [
    "vulcraft", "canam", "nucor", "ayamsa",
    "texas mutual", "disa", "isnetworld",
    "invoice", "vendor", "supplier", "purchase order", "po",
]

# Directory names to skip entirely during scan
SKIP_DIRS = {
    "API Keys",
    "api keys",
    "API_Keys",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    ".claude",
}

# Extensions treated as client-facing documents (require Owner approval to copy)
CLIENT_DOC_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"}

# Fuzzy match threshold - below this, folder goes to unknown list
MATCH_THRESHOLD = 0.70

# Scan limits
MAX_DEPTH = 5
MAX_FILES = 10_000


def _normalize(name: str) -> str:
    """Lowercase, strip common suffixes for better fuzzy matching."""
    name = name.lower().strip()
    for suffix in [" - ", "_", "-", "  "]:
        name = name.replace(suffix, " ")
    return name.strip()


def _best_match(folder_name: str) -> tuple[str, float]:
    """Return the best-matching known project name and its score."""
    normalized = _normalize(folder_name)
    best_name = ""
    best_score = 0.0
    for known in KNOWN_PROJECTS:
        score = difflib.SequenceMatcher(
            None, normalized, _normalize(known)
        ).ratio()
        if score > best_score:
            best_score = score
            best_name = known
    return best_name, best_score


def _is_vendor_doc(path: Path) -> bool:
    """Return True if file name or parent path contains vendor keywords."""
    text = (path.name + " " + str(path)).lower()
    return any(vendor in text for vendor in KNOWN_VENDORS)


def _classify_file(path: Path) -> str:
    """Return 'client', 'vendor', or 'internal'."""
    if _is_vendor_doc(path):
        return "vendor"
    if path.suffix.lower() in CLIENT_DOC_EXTENSIONS:
        return "client"
    return "internal"


def scan_pass1(root_dir: str, max_depth: int = MAX_DEPTH, max_files: int = MAX_FILES) -> dict:
    """Read-only inventory scan of root_dir.

    Returns a dict with keys:
      confirmed  - list of dicts: {folder, matched_project, score, files, client_docs, vendor_docs, size_bytes}
      unknown    - list of dicts: {folder, best_guess, score, files, size_bytes}
      skipped    - list of folder names skipped (API Keys, .git, etc.)
      totals     - {folders_scanned, files_scanned, confirmed_count, unknown_count}
      error      - set only if an exception occurred (otherwise absent)

    NEVER writes or modifies any file.
    """
    root = Path(root_dir).resolve()
    if not root.exists():
        return {"error": f"Directory not found: {root_dir}", "confirmed": [], "unknown": [], "skipped": [], "totals": {}}

    confirmed = []
    unknown = []
    skipped_dirs = []
    files_scanned = 0
    folders_scanned = 0

    try:
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue

            # Hard block: API Keys directory is never touched
            if entry.name in SKIP_DIRS or entry.name.lower() == "api keys":
                skipped_dirs.append(entry.name)
                continue

            folders_scanned += 1
            matched_project, score = _best_match(entry.name)

            folder_files = []
            client_docs = []
            vendor_docs = []
            size_bytes = 0

            depth = 0
            queue = [(entry, depth)]
            while queue and files_scanned < max_files:
                current, current_depth = queue.pop(0)
                if current_depth > max_depth:
                    continue
                try:
                    for child in sorted(current.iterdir()):
                        if child.is_dir():
                            if child.name in SKIP_DIRS or child.name.lower() == "api keys":
                                skipped_dirs.append(child.name)
                                continue
                            if current_depth + 1 <= max_depth:
                                queue.append((child, current_depth + 1))
                        elif child.is_file():
                            files_scanned += 1
                            fclass = _classify_file(child)
                            try:
                                fsize = child.stat().st_size
                            except OSError:
                                fsize = 0
                            size_bytes += fsize
                            file_entry = {
                                "path": str(child),
                                "name": child.name,
                                "class": fclass,
                                "size_bytes": fsize,
                            }
                            folder_files.append(file_entry)
                            if fclass == "client":
                                client_docs.append(file_entry)
                            elif fclass == "vendor":
                                vendor_docs.append(file_entry)
                except PermissionError:
                    pass

            record = {
                "folder": str(entry),
                "folder_name": entry.name,
                "matched_project": matched_project,
                "score": round(score, 3),
                "file_count": len(folder_files),
                "client_doc_count": len(client_docs),
                "vendor_doc_count": len(vendor_docs),
                "size_bytes": size_bytes,
                "client_docs": [f["path"] for f in client_docs],
                "vendor_docs": [f["path"] for f in vendor_docs],
            }

            if score >= MATCH_THRESHOLD:
                confirmed.append(record)
            else:
                record["best_guess"] = matched_project
                unknown.append(record)

    except Exception as exc:
        logger.exception("scan_pass1 failed")
        return {
            "error": str(exc),
            "confirmed": confirmed,
            "unknown": unknown,
            "skipped": skipped_dirs,
            "totals": {
                "folders_scanned": folders_scanned,
                "files_scanned": files_scanned,
                "confirmed_count": len(confirmed),
                "unknown_count": len(unknown),
            },
        }

    return {
        "confirmed": confirmed,
        "unknown": unknown,
        "skipped": list(set(skipped_dirs)),
        "totals": {
            "folders_scanned": folders_scanned,
            "files_scanned": files_scanned,
            "confirmed_count": len(confirmed),
            "unknown_count": len(unknown),
        },
    }


def scan_pass2(inventory: dict, approved_projects: list[str], dest_root: str) -> dict:
    """Copy-only migration for explicitly approved projects.

    Parameters:
      inventory        - result dict from scan_pass1
      approved_projects - list of folder paths (from confirmed list) approved by Owner
      dest_root        - project schema root (e.g. config project_root)

    Returns:
      {copied, skipped_vendor, skipped_client_pending, errors}

    NEVER automatic. NEVER moves files. Originals stay in place.
    Client docs require per-project Owner approval (passed via approved_projects).
    Vendor docs are never copied.
    """
    approved_set = set(str(Path(p).resolve()) for p in approved_projects)
    dest = Path(dest_root).resolve()

    copied = []
    skipped_vendor = []
    skipped_client_pending = []
    errors = []

    for record in inventory.get("confirmed", []):
        folder_path = str(Path(record["folder"]).resolve())
        if folder_path not in approved_set:
            continue

        project_name = record["matched_project"]
        project_dest = dest / project_name
        project_dest.mkdir(parents=True, exist_ok=True)

        # Walk source and copy non-vendor files
        source = Path(record["folder"])
        for child in source.rglob("*"):
            if not child.is_file():
                continue
            if child.name in SKIP_DIRS or "api keys" in str(child).lower():
                continue

            fclass = _classify_file(child)

            if fclass == "vendor":
                skipped_vendor.append(str(child))
                continue

            # Compute relative path from source folder root
            rel = child.relative_to(source)
            target = project_dest / rel

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(child), str(target))
                copied.append({"source": str(child), "dest": str(target)})
            except Exception as exc:
                errors.append({"file": str(child), "error": str(exc)})

    return {
        "copied": copied,
        "skipped_vendor": skipped_vendor,
        "skipped_client_pending": skipped_client_pending,
        "errors": errors,
        "totals": {
            "copied_count": len(copied),
            "skipped_vendor_count": len(skipped_vendor),
            "error_count": len(errors),
        },
    }
