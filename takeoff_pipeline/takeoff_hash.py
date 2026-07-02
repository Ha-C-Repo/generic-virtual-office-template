"""Version hash for the TAKEOFF sheet, per TAKEOFF_SCHEMA_V2.md 13.2.

ONE shared implementation. export_xlsx.py stamps with it and
validate_takeoff.py re-verifies with it; the spec forbids a second
implementation, so neither tool rolls its own.

Recipe, verbatim from 13.2:
1. TAKEOFF sheet from the header row (row 2) down to the last data row
   (the last row with at least one non-empty cell in columns A to O).
2. Cells in columns A to O per row (O is formula_ref, the last header).
3. Stored content as text: formula cells contribute the formula string
   including the leading equals sign; integral numbers serialize
   without a decimal point; non-integral numbers as Python repr;
   booleans as TRUE or FALSE; dates as ISO 8601; empty cells as the
   empty string.
4. Escape, in order, each a two-character sequence: backslash, then
   newline, then pipe.
5. Join cells with the pipe character, rows with a single newline,
   encode UTF-8, SHA-256, lowercase hex digest.

The metadata row (row 1) is excluded so the stamp cannot change its
own hash. Load the workbook WITHOUT data_only so formula cells keep
their formula strings.
"""

import datetime as _dt
import hashlib

TAKEOFF_COLUMNS = 15  # A through O


def cell_text(value) -> str:
    """Stored cell content as text, per 13.2 step 3."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return repr(value)
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    # openpyxl returns ArrayFormula/DataTableFormula OBJECTS for legacy
    # CSE formulas; str() on those embeds a process-local memory
    # address and the digest stops being reproducible. 13.2: formula
    # cells contribute the formula string.
    text = getattr(value, "text", None)
    if type(value).__name__ in ("ArrayFormula", "DataTableFormula"):
        return str(text) if text is not None else ""
    return str(value)


def escape_cell(text: str) -> str:
    """13.2 step 4: backslash, newline, pipe, in that order."""
    return (text.replace("\\", "\\\\")
                .replace("\n", "\\n")
                .replace("|", "\\|"))


def compute_takeoff_hash(ws) -> str:
    """SHA-256 digest of a TAKEOFF worksheet (openpyxl, not data_only)."""
    last_row = 1
    for r_idx in range(2, ws.max_row + 1):
        for c_idx in range(1, TAKEOFF_COLUMNS + 1):
            if ws.cell(row=r_idx, column=c_idx).value is not None:
                last_row = r_idx
                break
    if last_row < 2:
        last_row = 2
    lines = []
    for r_idx in range(2, last_row + 1):
        cells = []
        for c_idx in range(1, TAKEOFF_COLUMNS + 1):
            cells.append(escape_cell(
                cell_text(ws.cell(row=r_idx, column=c_idx).value)))
        lines.append("|".join(cells))
    payload = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
