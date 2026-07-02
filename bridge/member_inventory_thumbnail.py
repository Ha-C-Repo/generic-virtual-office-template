"""Member-inventory thumbnail renderer.

When auto_process_drawing extracts unique member shapes from a drawing,
this builds a single PNG showing all of them side-by-side with shape
names and quantities labeled. Owner gets a visual takeoff inventory
in chat instead of just a tonnage number.

Layout: dynamic grid (1-9 panels), navy/silver palette, white background.
Falls back to None on any error (non-blocking).
"""

import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Cache the import-check so missing-deps warning fires ONCE per process
# (Owner pass 10f roadmap #2 - same pattern as stl_thumbnail.py).
_DEPS_AVAILABLE = None


def _check_inventory_thumbnail_deps():
    """Probe trimesh+numpy+matplotlib once. Cache result. Warns once."""
    global _DEPS_AVAILABLE
    if _DEPS_AVAILABLE is not None:
        return _DEPS_AVAILABLE
    try:
        import trimesh  # noqa: F401
        import numpy  # noqa: F401
        import matplotlib  # noqa: F401
        _DEPS_AVAILABLE = True
    except ImportError as e:
        log.warning(
            "Inventory thumbnail deps missing (suppressed on subsequent "
            "calls this session): %s. Install: pip install trimesh matplotlib",
            e,
        )
        _DEPS_AVAILABLE = False
    return _DEPS_AVAILABLE


def render_member_inventory_thumbnail(
    stl_paths: list,
    verified_members: list,
    output_path: str,
    width_px: int = 600,
    height_px: int = 400,
    edge_color: str = "#1a2744",
    face_color: str = "#9da9c4",
    bg_color: str = "white",
    text_color: str = "#1a2744",
) -> Optional[str]:
    """Render an inventory grid showing each unique shape extracted.

    Args:
        stl_paths: list of dicts from auto_process_drawing, each with
            'shape' and 'path' keys.
        verified_members: list of member dicts with 'shape' and optional
            'qty' or 'count'. Used to compute total qty per shape.
        output_path: where to save the PNG.
        width_px, height_px: dimensions.

    Returns:
        Output path on success, None on any error.
    """
    if not _check_inventory_thumbnail_deps():
        return None
    try:
        import trimesh
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    except ImportError as e:
        log.warning("Inventory thumbnail deps missing: %s", e)
        return None

    if not stl_paths:
        return None

    # Cap at 9 shapes (3x3 grid is the max we display)
    items = stl_paths[:9]
    n = len(items)
    if n == 0:
        return None

    # Compute quantity per shape from verified_members
    qty_by_shape = {}
    for m in (verified_members or []):
        shape = m.get("shape", "")
        if not shape:
            continue
        try:
            qty = int(m.get("qty") or m.get("count") or 1)
        except (ValueError, TypeError):
            qty = 1
        qty_by_shape[shape] = qty_by_shape.get(shape, 0) + qty

    # Pick grid shape
    if n <= 2:
        rows, cols = 1, n
    elif n <= 4:
        rows, cols = 2, 2
    elif n <= 6:
        rows, cols = 2, 3
    else:
        rows, cols = 3, 3

    try:
        dpi = 100
        fig = plt.figure(figsize=(width_px/dpi, height_px/dpi),
                        dpi=dpi, facecolor=bg_color)
        fig.suptitle(f"Member Inventory ({n} unique shapes)",
                    color=text_color, fontsize=11, fontweight="bold", y=0.97)

        for i, item in enumerate(items):
            shape = item.get("shape", "?")
            stl_path = item.get("path", "")
            qty = qty_by_shape.get(shape, 0)

            ax = fig.add_subplot(rows, cols, i + 1, projection="3d")
            ax.set_facecolor(bg_color)
            ax.set_axis_off()
            ax.grid(False)

            # Try to load + draw the mesh
            mesh_loaded = False
            if stl_path and Path(stl_path).exists():
                try:
                    mesh = trimesh.load(stl_path, force="mesh")
                    if hasattr(mesh, "vertices") and len(mesh.vertices) > 0:
                        verts = np.asarray(mesh.vertices)
                        faces = np.asarray(mesh.faces)
                        if len(faces) > 0:
                            tri = verts[faces]
                            coll = Poly3DCollection(
                                tri,
                                facecolors=face_color,
                                edgecolors=edge_color,
                                linewidths=0.15,
                                alpha=0.85,
                            )
                            ax.add_collection3d(coll)
                            x_min, y_min, z_min = verts.min(axis=0)
                            x_max, y_max, z_max = verts.max(axis=0)
                            rng = max(x_max-x_min, y_max-y_min, z_max-z_min)
                            cx, cy, cz = (x_max+x_min)/2, (y_max+y_min)/2, (z_max+z_min)/2
                            half = rng/2 * 1.05
                            ax.set_xlim(cx-half, cx+half)
                            ax.set_ylim(cy-half, cy+half)
                            ax.set_zlim(cz-half, cz+half)
                            ax.set_box_aspect((1, 1, 1))
                            ax.view_init(elev=20, azim=-50)
                            mesh_loaded = True
                except Exception as e:
                    log.debug("Couldn't load %s: %s", stl_path, e)

            # Caption regardless of whether mesh loaded
            label = f"{shape}"
            if qty:
                label += f" × {qty}"
            if not mesh_loaded:
                label = f"{label}\n(STL missing)"
            ax.set_title(label, color=text_color, fontsize=8, pad=2)

        plt.tight_layout(rect=[0, 0, 1, 0.94], pad=0.5)
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight",
                   facecolor=bg_color, edgecolor="none")
        plt.close(fig)
        return str(output_path)
    except Exception as e:
        log.warning("Inventory thumbnail render failed: %s", e)
        try:
            if Path(output_path).exists():
                Path(output_path).unlink()
        except OSError:
            pass
        return None
