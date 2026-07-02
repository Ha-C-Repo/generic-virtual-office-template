#!/usr/bin/env python3
"""Split a drawing-set PDF into one file per sheet, render a high-resolution
image per sheet, and extract the vector-data text layer. Optionally count a tag.

This keeps the language model off the pixels. The model writes and triggers this;
the script does the deterministic work. Runs in Claude Code or any Python 3.9+ env.
No Google Antigravity required.

Requires: pip install pymupdf
Usage:
    python split_and_extract.py INPUT.pdf OUTDIR [--dpi 300] [--count CU5]
"""
import argparse
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("Install PyMuPDF first: pip install pymupdf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("outdir")
    ap.add_argument("--dpi", type=int, default=300, help="raster resolution per sheet")
    ap.add_argument("--count", default=None, help="tag string to count in the text layer, e.g. CU5")
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(args.pdf)
    total = 0
    for i, page in enumerate(doc):
        stem = f"sheet_{i + 1:03d}"
        one = fitz.open()
        one.insert_pdf(doc, from_page=i, to_page=i)
        one.save(out / f"{stem}.pdf")
        one.close()
        page.get_pixmap(dpi=args.dpi).save(out / f"{stem}.png")
        text = page.get_text("text")
        (out / f"{stem}.txt").write_text(text, encoding="utf-8")
        if args.count:
            n = text.count(args.count)
            total += n
            print(f"{stem}: {args.count} x {n}")
    if args.count:
        print(f"TOTAL {args.count}: {total}. Confidence high only if tagged in the vector layer. Verify before pricing.")
    print(f"Wrote {len(doc)} sheets to {out}")


if __name__ == "__main__":
    main()
