"""QR code generator for shop floor piece labels (Phase 26, v5.8.0).

Generates QR labels that Mario's crew scans with a phone to update
piece status. One tap, done. Prints on standard Avery labels.

QR format: yourco://status/{job_number}/{piece_mark}

Requires qrcode library (pip install qrcode). Guarded.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


def generate_piece_qr(
    job_number: str,
    piece_mark: str,
    output_path: str | Path | None = None,
) -> dict:
    """Generate a QR code PNG for a single piece mark.

    Args:
        job_number: Your Company job number.
        piece_mark: Piece mark (e.g., W14X22-B7).
        output_path: Write PNG here if provided.

    Returns:
        {"success": bool, "output_path": str, "url": str}
    """
    if not HAS_QRCODE:
        url = f"yourco://status/{job_number}/{piece_mark}"
        return {"success": False, "error": "qrcode_not_installed",
                "output_path": "", "url": url}

    url = f"yourco://status/{job_number}/{piece_mark}"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    out_path = ""
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(p))
        out_path = str(p)

    return {"success": True, "output_path": out_path, "url": url}


def generate_job_qr_sheet(
    job_number: str,
    piece_marks: list[str],
    output_dir: str | Path | None = None,
) -> dict:
    """Generate QR PNGs for all pieces in a job.

    Returns:
        {"success": bool, "count": int, "output_dir": str}
    """
    if not HAS_QRCODE:
        return {"success": False, "error": "qrcode_not_installed",
                "count": 0, "output_dir": ""}

    od = Path(output_dir or (Path(tempfile.gettempdir()) / f"qr_{job_number}"))
    od.mkdir(parents=True, exist_ok=True)

    count = 0
    for pm in piece_marks:
        safe = pm.replace("/", "_").replace(" ", "_")
        out = od / f"{safe}.png"
        r = generate_piece_qr(job_number, pm, output_path=out)
        if r.get("success"):
            count += 1

    return {"success": True, "count": count, "output_dir": str(od)}
