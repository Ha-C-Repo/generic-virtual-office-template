"""STL → PNG thumbnail renderer.

Generates a small isometric preview image of an STL file so Owner can
glance at a building in chat without opening Windows 3D Viewer.

No new dependencies beyond what's already in requirements.txt
(trimesh + numpy + matplotlib).

Usage:
    from bridge.stl_thumbnail import render_stl_thumbnail
    png_path = render_stl_thumbnail("output/NC_Beck_5x4.stl")
    # → "output/NC_Beck_5x4.png"

Returns None on any error (renderer is non-blocking; if it fails we
just skip the thumbnail rather than fail the whole build).
"""

import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Cache the import-check so we only emit the missing-deps warning ONCE
# per process (Owner pass 10e roadmap #2 - was firing on every call).
# None = not checked yet, True = deps present, False = deps missing.
_DEPS_AVAILABLE = None


def _check_thumbnail_deps():
    """Probe trimesh + numpy + matplotlib once. Cache the result.

    Returns True if all deps importable, False otherwise. Logs at WARNING
    on the FIRST missing-deps result, then DEBUG on subsequent calls so
    chat output stays clean.
    """
    global _DEPS_AVAILABLE
    if _DEPS_AVAILABLE is not None:
        return _DEPS_AVAILABLE
    try:
        import trimesh  # noqa: F401
        import numpy  # noqa: F401
        import matplotlib  # noqa: F401
        _DEPS_AVAILABLE = True
    except ImportError as e:
        # Owner roadmap #2: demote to debug. Missing thumbnail deps is a
        # degraded-mode state, not a warning. Bridge still returns valid STL.
        log.debug(
            "STL thumbnail dependencies missing: %s. "
            "Optional install: pip install trimesh matplotlib",
            e,
        )
        _DEPS_AVAILABLE = False
    return _DEPS_AVAILABLE


def render_stl_thumbnail(stl_path: str,
                        output_path: Optional[str] = None,
                        width_px: int = 480,
                        height_px: int = 320,
                        elev: float = 25.0,
                        azim: float = -45.0,
                        edge_color: str = "#1a2744",
                        face_color: str = "#9da9c4",
                        bg_color: str = "white") -> Optional[str]:
    """Render an STL file as a small isometric PNG thumbnail.

    Args:
        stl_path: Path to the .stl file to render.
        output_path: Where to save the PNG. Defaults to same name as STL
            with .png extension.
        width_px, height_px: Output image dimensions in pixels.
        elev, azim: Camera elevation and azimuth in degrees. Default is
            a standard isometric three-quarters view (Owner style).
        edge_color, face_color, bg_color: Hex colors. Defaults match the
            Your Company navy/silver palette.

    Returns:
        The path to the saved PNG, or None on any error.
        Non-blocking: any failure logs a warning and returns None instead
        of crashing the caller.
    """
    # Use cached dependency check (warns at most once per process)
    if not _check_thumbnail_deps():
        return None
    try:
        import trimesh
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")  # headless
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    except ImportError:
        # Deps present per _check_thumbnail_deps but a sub-import failed.
        # Cache to skip future attempts this session.
        global _DEPS_AVAILABLE
        _DEPS_AVAILABLE = False
        return None

    src = Path(stl_path)
    if not src.exists():
        log.warning("STL not found for thumbnail: %s", src)
        return None

    out = Path(output_path) if output_path else src.with_suffix(".png")

    try:
        mesh = trimesh.load(str(src), force="mesh")
        if not hasattr(mesh, "vertices") or len(mesh.vertices) == 0:
            log.warning("STL is empty: %s", src)
            return None

        verts = np.asarray(mesh.vertices)
        faces = np.asarray(mesh.faces)
        if len(faces) == 0:
            log.warning("STL has no faces: %s", src)
            return None

        # Compute aspect-aware figure size
        dpi = 100
        figsize = (width_px / dpi, height_px / dpi)
        fig = plt.figure(figsize=figsize, dpi=dpi, facecolor=bg_color)
        ax = fig.add_subplot(111, projection="3d")
        ax.set_facecolor(bg_color)

        # Build triangle collection
        triangles = verts[faces]
        collection = Poly3DCollection(
            triangles,
            facecolors=face_color,
            edgecolors=edge_color,
            linewidths=0.25,
            alpha=0.85,
        )
        ax.add_collection3d(collection)

        # Frame the model
        x_min, y_min, z_min = verts.min(axis=0)
        x_max, y_max, z_max = verts.max(axis=0)
        # Equal aspect across all axes
        max_range = max(x_max - x_min, y_max - y_min, z_max - z_min)
        cx, cy, cz = (x_max + x_min) / 2, (y_max + y_min) / 2, (z_max + z_min) / 2
        half = max_range / 2 * 1.05
        ax.set_xlim(cx - half, cx + half)
        ax.set_ylim(cy - half, cy + half)
        ax.set_zlim(cz - half, cz + half)
        ax.set_box_aspect((1, 1, 1))

        # Clean look
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.grid(False)

        plt.tight_layout(pad=0.1)
        fig.savefig(str(out), dpi=dpi, bbox_inches="tight",
                   facecolor=bg_color, edgecolor="none")
        plt.close(fig)

        log.info("STL thumbnail saved: %s", out)
        return str(out)
    except Exception as e:
        log.warning("STL thumbnail render failed for %s: %s", src, e)
        # Cleanup partial output
        try:
            if out.exists():
                out.unlink()
        except OSError:
            pass
        return None
