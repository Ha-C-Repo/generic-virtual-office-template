"""
Tekla viewport export - member-accurate frame image for proposals/gallery.
====================================================================
Policy (2026-06-09, Owner): member-accurate structural frame images used on
client proposals and the public gallery are ALWAYS Tekla viewport exports from
the project's Tekla Structures detailing model. AI image generation interprets
geometry and is never used for the structural frame (it swaps member systems
and invents framing). A Tekla viewport export is performed on every bid that
has a detailing model.

This module does not drive Tekla (Tekla Structures is operated by Joseph). It
defines the required artifact, locates it in the bid folder, and reports a
clear EXPORT-REQUIRED action when it is missing so the pipeline surfaces it as
a gate rather than silently substituting another image.

Convention: save the export into the bid's ``renders/`` subfolder named with
``tekla`` or ``viewport`` (e.g. ``<bid>_TEKLA.png``). find_render and the
proposal generator prefer that file for the structural-frame slot.

How to perform the export in Tekla Structures:
  1. Open the project model. Set a clean rendered 3D view (View > Rendering >
     Shaded wireframe or Rendered), isometric three-quarter.
  2. File > Export > to image (or print the view to PNG) at 1920px+ wide.
  3. Save to the bid's renders/ folder as <bid>_TEKLA.png.
"""

from pathlib import Path

_EXTS = (".png", ".jpg", ".jpeg", ".webp")
_TOKENS = ("tekla", "viewport")


def _renders_dir(bid_number: str | None, project_name: str | None) -> Path | None:
    """Resolve the bid's renders/ folder in the production bids tree, else the
    working 'Bids To Estimate' tree. Returns None if neither is found."""
    try:
        from bridge.bid_documents import bid_folder, bids_root, _safe_folder_name
    except Exception:
        return None
    # 1) production bid folder
    try:
        if bid_number:
            d = bid_folder(bid_number, project_name) / "renders"
            if d.parent.is_dir():
                return d
    except Exception:
        pass
    # 2) working 'Bids To Estimate' job folder matched by project name
    try:
        if project_name:
            target = _safe_folder_name(project_name).lower()
            work = Path(__file__).resolve().parent.parent / "Bids To Estimate"
            if work.is_dir() and target:
                for job in work.iterdir():
                    if job.is_dir() and target in job.name.lower():
                        return job / "renders"
    except Exception:
        pass
    return None


def find_tekla_viewport(bid_number: str | None = None,
                        project_name: str | None = None) -> str:
    """Return the path to the bid's Tekla viewport export, or "" if absent."""
    d = _renders_dir(bid_number, project_name)
    if not d or not d.is_dir():
        return ""
    hits = [f for f in d.iterdir()
            if f.is_file() and f.suffix.lower() in _EXTS
            and any(t in f.name.lower() for t in _TOKENS)]
    if not hits:
        return ""
    hits.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return str(hits[0])


def require_tekla_viewport(bid_number: str | None = None,
                           project_name: str | None = None) -> dict:
    """Pipeline gate. Returns the Tekla viewport path or a clear required-action.

    {"ok": True, "path": "<...>_TEKLA.png", "source": "tekla_viewport"}
    {"ok": False, "required": True, "action": "...", "save_to": "<renders dir>"}

    ok=False is not a failure - it means the member-accurate frame image has
    not been exported from Tekla yet. The proposal can still ship (text-only or
    with a finished/atmospheric illustrative cover); it simply must not use an
    AI-generated structural-frame image in place of the Tekla export.
    """
    path = find_tekla_viewport(bid_number, project_name)
    if path:
        return {"ok": True, "path": path, "source": "tekla_viewport"}
    d = _renders_dir(bid_number, project_name)
    save_to = str(d) if d else "<bid>/renders/"
    return {
        "ok": False,
        "required": True,
        "source": "tekla_viewport",
        "action": ("Export a member-accurate viewport from the project's Tekla "
                   "Structures model (rendered isometric 3D view, File > Export "
                   "to image, 1920px+) and save to the bid renders/ folder named "
                   "<bid>_TEKLA.png. AI renders must not fill the structural-frame "
                   "slot on a proposal or the gallery."),
        "save_to": save_to,
    }
