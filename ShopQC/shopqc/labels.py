r"""QR label generation and Zebra ZD421 printing.

Correction to the original handoff: writing raw bytes to \\.\USB001 is not
reliable on Windows 11 (the USB printing support driver claims the port).
The dependable no-middleware paths are:
  1. win32 mode  - send RAW ZPL through the Windows print spooler (pywin32).
     Install the ZD421 with the ZDesigner driver, name in config.json.
  2. share mode  - share the printer (e.g. as ZEBRA), copy raw bytes to the
     UNC path. Works even without pywin32.
  3. file mode   - write .zpl files to labels_out/ for testing or manual copy.

Label: 2 x 1 inch at 203 dpi = 406 x 203 dots.
"""

import os

LABEL_W = 406
LABEL_H = 203


def build_zpl(piece_id: str, section: str, project_name: str, date: str,
              payload: str) -> str:
    proj = (project_name or "")[:18]
    return (
        "^XA\n"
        "^CI28\n"
        f"^PW{LABEL_W}\n"
        f"^LL{LABEL_H}\n"
        "^LH0,0\n"
        # QR code, model 2, magnification 4, left side
        "^FO12,16^BQN,2,4\n"
        f"^FDQA,{payload}^FS\n"
        # Human-readable block, right side
        f"^FO150,22^A0N,28,28^FD{piece_id}^FS\n"
        f"^FO150,58^A0N,24,24^FD{section}^FS\n"
        f"^FO150,90^A0N,20,20^FD{proj}^FS\n"
        f"^FO150,118^A0N,20,20^FD{date}^FS\n"
        # Shop mark
        "^FO150,160^A0N,18,18^FDYOUR COMPANY^FS\n"
        "^XZ\n"
    )


def send_zpl(zpl: str, cfg: dict) -> str:
    """Send one label. Returns a human-readable result string. Raises on failure."""
    mode = cfg.get("printer_mode", "win32")
    data = zpl.encode("utf-8")
    if mode == "win32":
        return _send_win32(data, cfg["printer_name"])
    if mode == "share":
        return _send_share(data, cfg["printer_share"])
    return _send_file(zpl, cfg.get("label_output_dir", "labels_out"))


def _send_win32(data: bytes, printer_name: str) -> str:
    try:
        import win32print  # type: ignore
    except ImportError:
        raise RuntimeError(
            "pywin32 not installed. Set printer_mode to 'share' or 'file' "
            "in config.json, or rebuild the EXE with pywin32.")
    h = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(h, 1, ("ShopQC Label", None, "RAW"))
        win32print.StartPagePrinter(h)
        win32print.WritePrinter(h, data)
        win32print.EndPagePrinter(h)
        win32print.EndDocPrinter(h)
    finally:
        win32print.ClosePrinter(h)
    return f"Sent to spooler: {printer_name}"


def _send_share(data: bytes, share_path: str) -> str:
    # copy /b is the classic raw-to-shared-printer path; do it natively.
    with open(share_path, "wb") as f:
        f.write(data)
    return f"Sent to share: {share_path}"


_file_seq = 0


def _send_file(zpl: str, out_dir: str) -> str:
    global _file_seq
    os.makedirs(out_dir, exist_ok=True)
    import time
    _file_seq += 1
    name = os.path.join(out_dir,
                        f"label_{int(time.time()*1000)}_{_file_seq:04d}.zpl")
    with open(name, "w", encoding="utf-8") as f:
        f.write(zpl)
    return f"Wrote {name}"


def print_batch(labels: list, cfg: dict, progress_cb=None) -> list:
    """labels: list of ZPL strings. Returns list of result strings."""
    results = []
    for i, zpl in enumerate(labels):
        results.append(send_zpl(zpl, cfg))
        if progress_cb:
            progress_cb(i + 1, len(labels))
    return results
