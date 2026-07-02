"""Database layer. SQLite on a network share, multi-station safe.

Design notes (corrections to the original handoff):
- WAL mode is NOT used. WAL requires shared memory on one host and corrupts
  over SMB/OneDrive. We use journal_mode=DELETE with a long busy_timeout and
  retry, which is the only safe mode for a shared-folder SQLite file.
- Every write goes through execute_write() which retries on lock errors.
"""

import datetime
import sqlite3
import time

BUSY_TIMEOUT_MS = 15000
WRITE_RETRIES = 5

PIECE_STATUSES = ("RECEIVED", "IN_FAB", "NCR_HOLD", "RELEASED", "SHIPPED")
NCR_STATUSES = ("OPEN", "IN DISPOSITION", "CLOSED")

# Section 9 categories, NC-QC-FAB-001
NCR_CATEGORIES = (
    "Material nonconformance",
    "Dimensional",
    "Welding",
    "Coating / surface prep",
    "Documentation",
    "Damage / handling",
    "Unauthorized field modification",
)

NCR_DISPOSITIONS = ("USE AS IS", "REWORK", "REPAIR", "REJECT / SCRAP")

WPS_FILES = ("pWPS00003", "pWPS00004")

# The 18 traveler fields, NC-QC-FAB-001 Section 8. Order is the locked sequence.
# (number, name, kind) kind: info = filled at receiving, op = shop floor step,
# cwi = requires CWI sign, release = filled at Gate 3, optional = may be N/A.
TRAVELER_FIELDS = (
    (1,  "Project Name / Job No.",            "info"),
    (2,  "Piece Mark",                        "info"),
    (3,  "Material Section + Heat No.",       "info"),
    (4,  "MTR on file (lot no.)",             "info"),
    (5,  "Cut to length",                     "op"),
    (6,  "Hole punch / drill",                "op"),
    (7,  "Coping / fitting",                  "op"),
    (8,  "Pre-weld inspection (CWI)",         "cwi"),      # HARD BLOCK
    (9,  "Welder ID / WPS",                   "weld"),
    (10, "Post-weld VT (CWI)",                "cwi"),
    (11, "UT / MT result reference",          "optional"),
    (12, "Dimensional check",                 "op"),
    (13, "Camber check",                      "optional"),
    (14, "Surface prep / DFT reading",        "op"),
    (15, "Final Release - Shop Director",     "release"),
    (16, "Final Release - CWI",               "release"),
    (17, "Shipped - date + truck/load",       "release"),
    (18, "NCR number (if any)",               "auto"),
)

# SJI joist traveler field set (additive variant, SJI Spec 100-2020). This is a
# PARALLEL locked sequence; it does NOT replace or reorder the 18 structural
# fields above. It is selected per piece by traveler_type. It mirrors the
# structural gate structure on purpose so every hard block transfers unchanged:
#   info 1-4 (filled at receiving), floor steps 5-16 (Gate 2), pre-weld CWI at 8
#   and post-weld VT at 10 (same positions as structural -> _sign_cwi/_sign_weld
#   need no change), release 17-18, ship 19, NCR auto 20.
# Field-8 pre-weld CWI is the hard block: it sits in the sequence so the weld and
# downstream steps are unreachable until a CWI name is recorded.
# Camber (field 14) is the deflection-catch instrument for the Elite Crossing
# failure mode: it captures measured vs SJI-specified camber and is MANDATORY
# (not optional) for joists.
# PROVISIONAL: the NC-QC-FAB-001 program PDF did not enumerate joist fields, so
# this set is proposed from SJI Spec 100-2020 and the Joseph brief and is flagged
# for Owner. See JOIST-TRAVELER-MIGRATION-2026-06-18.md.
JOIST_TRAVELER_FIELDS = (
    (1,  "Project Name / Job No.",                   "info"),
    (2,  "Joist Mark (SJI designation)",             "info"),
    (3,  "Joist Designation + Heat/Lot",             "info"),
    (4,  "MTR / SJI mill cert on file (lot no.)",    "info"),
    (5,  "Span and depth verified vs SJI spec",      "measure"),
    (6,  "Top and bottom chord check",               "op"),
    (7,  "Web member check",                         "op"),
    (8,  "Pre-weld inspection (CWI)",                "cwi"),      # HARD BLOCK
    (9,  "Welder ID / WPS (chord, web, seat welds)", "weld"),
    (10, "Post-weld VT (CWI)",                       "cwi"),
    (11, "Bearing seat depth and type",              "seat"),
    (12, "Bridging rows installed and type",         "bridging"),
    (13, "End anchorage / support attachment",       "measure"),
    (14, "Camber measured vs SJI-specified",         "camber"),   # deflection catch
    (15, "UT / MT result reference",                 "optional"),
    (16, "Surface prep / paint / DFT reading",       "dft"),
    (17, "Final Release - Shop Director",            "release"),
    (18, "Final Release - CWI",                      "release"),
    (19, "Shipped - date + truck/load",              "release"),
    (20, "NCR number (if any)",                      "auto"),
)

TRAVELER_TYPES = ("STRUCTURAL", "JOIST")

# Per-variant metadata. The floor range is the locked-sequence enforcement window
# (only the lowest unsigned field in [floor_first, floor_last] is signable).
# gate3_last is the last field that must be signed for Gate 3 completeness.
TRAVELER_SPECS = {
    "STRUCTURAL": {
        "fields": TRAVELER_FIELDS,
        "floor_first": 5, "floor_last": 14, "gate3_last": 14,
        "release_director": 15, "release_cwi": 16, "ship": 17, "ncr_auto": 18,
    },
    "JOIST": {
        "fields": JOIST_TRAVELER_FIELDS,
        "floor_first": 5, "floor_last": 16, "gate3_last": 16,
        "release_director": 17, "release_cwi": 18, "ship": 19, "ncr_auto": 20,
    },
}

# Section 9 category that triggers hard block 6 (EOR sealed reference before close).
EOR_CATEGORY = "Unauthorized field modification"

# Hard block 5: CEO co-sign at Gate 3. The name must read exactly this.
CEO_NAME = "The Owner"


def needs_ceo_cosign(tonnage, ias_required) -> bool:
    """Hard block 5 trigger: a CEO co-sign is required to release a piece on a
    project of 50 tons or more, or any IAS-inspected project. Centralized so the
    Gate 3 UI and the tests evaluate the identical rule."""
    try:
        tons = float(tonnage or 0)
    except (ValueError, TypeError):
        tons = 0
    return tons >= 50 or bool(ias_required)


def ceo_name_matches(entered) -> bool:
    """Hard block 5 name check: the co-sign must read exactly the CEO name,
    case and surrounding whitespace insensitive."""
    return (entered or "").strip().lower() == CEO_NAME.lower()


def spec_meta(traveler_type: str) -> dict:
    """Variant metadata. Unknown or NULL type falls back to STRUCTURAL so legacy
    pieces (pre-migration) and bad data never crash a gate."""
    return TRAVELER_SPECS.get(traveler_type or "STRUCTURAL",
                              TRAVELER_SPECS["STRUCTURAL"])


def traveler_spec(traveler_type: str) -> tuple:
    return spec_meta(traveler_type)["fields"]


def gate3_last_field(traveler_type: str) -> int:
    return spec_meta(traveler_type)["gate3_last"]


def ncr_close_blocked_reason(category: str, eor_reference) -> str:
    """Hard block 6, centralized so it is enforced and testable identically from
    the UI and from tests. Returns a non-empty reason string when the close must
    be blocked, or '' when it may proceed. An unauthorized-field-modification NCR
    cannot close without an EOR sealed analysis reference (NC-QC-FAB-001 Sec 9).
    This is the path the joist camber/deflection failure mode flows into."""
    if category == EOR_CATEGORY and not (eor_reference or "").strip():
        return ("HARD BLOCK: unauthorized field modification NCRs cannot close "
                "without an EOR sealed analysis reference.")
    return ""


def fastener_receiving_blocked_reason(rocap_lot_no, markings_verified,
                                      mfr_cert_on_file, galvanized,
                                      lube_check_done) -> str:
    """Gate 1 receiving acceptance for high-strength bolt assemblies (RCSC
    Specification / ASTM F3125). Centralized so the receiving UI and the tests
    enforce the identical rule. Returns '' when the lot may be marked
    received-complete, or a reason string when it must be blocked.

    A lot is accepted only with the ROCAP (rotational-capacity) test lot number
    recorded AND the bolt, nut, and washer markings verified AND the manufacturer
    cert on file. A galvanized assembly also requires the lubrication check, because
    the ROCAP test is what exposes lubrication on galvanized assemblies. The recorded
    ROCAP lot number is the one the bolt, nut, and washer must share in the
    connection. This is receiving acceptance, not an NCR category."""
    missing = []
    if not (rocap_lot_no or "").strip():
        missing.append("ROCAP test lot number")
    if not markings_verified:
        missing.append("bolt, nut and washer markings verified")
    if not mfr_cert_on_file:
        missing.append("manufacturer cert on file")
    if galvanized and not lube_check_done:
        missing.append("lubrication check (required for galvanized)")
    if not missing:
        return ""
    return ("Fastener lot cannot be marked received-complete. Missing: "
            + ", ".join(missing) + ".")


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  job_number TEXT NOT NULL,
  name TEXT NOT NULL,
  gc_name TEXT,
  contract_number TEXT,
  tonnage REAL DEFAULT 0,
  ias_required INTEGER DEFAULT 0,
  created_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE'
);
CREATE TABLE IF NOT EXISTS bol_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  line_number INTEGER,
  section TEXT NOT NULL,
  quantity_ordered INTEGER NOT NULL DEFAULT 0,
  quantity_received INTEGER NOT NULL DEFAULT 0,
  heat_number TEXT,
  lot_number TEXT,
  astm_grade TEXT,
  fy REAL,
  fu REAL,
  ce REAL,
  mtr_verified INTEGER DEFAULT 0,
  received_date TEXT
);
CREATE TABLE IF NOT EXISTS pieces (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  piece_id TEXT NOT NULL UNIQUE,
  section TEXT NOT NULL,
  heat_number TEXT,
  lot_number TEXT,
  status TEXT NOT NULL DEFAULT 'RECEIVED',
  label_printed INTEGER DEFAULT 0,
  traveler_type TEXT NOT NULL DEFAULT 'STRUCTURAL',
  created_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS traveler_fields (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  piece_pk INTEGER NOT NULL REFERENCES pieces(id),
  field_number INTEGER NOT NULL,
  field_name TEXT NOT NULL,
  value TEXT,
  signed_by TEXT,
  timestamp TEXT,
  notes TEXT,
  UNIQUE(piece_pk, field_number)
);
CREATE TABLE IF NOT EXISTS ncrs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  piece_pk INTEGER REFERENCES pieces(id),
  gate INTEGER NOT NULL,
  category TEXT NOT NULL,
  description TEXT NOT NULL,
  opened_by TEXT NOT NULL,
  opened_date TEXT NOT NULL,
  disposition TEXT,
  disposition_authority TEXT,
  eor_reference TEXT,
  closed_by TEXT,
  closed_date TEXT,
  status TEXT NOT NULL DEFAULT 'OPEN'
);
CREATE TABLE IF NOT EXISTS rir_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  lot_number TEXT,
  signed_by TEXT NOT NULL,
  signed_date TEXT NOT NULL,
  all_checks_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS weld_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  piece_pk INTEGER NOT NULL REFERENCES pieces(id),
  weld_type TEXT,
  wps_file TEXT,
  welder_id TEXT,
  pre_weld_by TEXT,
  pre_weld_date TEXT,
  vt_result TEXT,
  vt_by TEXT,
  vt_date TEXT,
  ndt_type TEXT,
  ndt_result TEXT,
  ndt_report_ref TEXT
);
CREATE TABLE IF NOT EXISTS release_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  piece_pk INTEGER NOT NULL REFERENCES pieces(id),
  shop_director_sign TEXT NOT NULL,
  cwi_sign TEXT NOT NULL,
  ceo_sign TEXT,
  release_date TEXT NOT NULL,
  truck_load_ref TEXT,
  certificate_printed INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fastener_lots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  assembly_type TEXT NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 0,
  rocap_lot_no TEXT,
  markings_verified INTEGER DEFAULT 0,
  mfr_cert_on_file INTEGER DEFAULT 0,
  galvanized INTEGER DEFAULT 0,
  lube_check_done INTEGER DEFAULT 0,
  rocap_result_reference TEXT,
  received_complete INTEGER DEFAULT 0,
  received_date TEXT,
  created_date TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pieces_project ON pieces(project_id);
CREATE INDEX IF NOT EXISTS idx_traveler_piece ON traveler_fields(piece_pk);
CREATE INDEX IF NOT EXISTS idx_ncrs_project ON ncrs(project_id);
CREATE INDEX IF NOT EXISTS idx_ncrs_status ON ncrs(status);
CREATE INDEX IF NOT EXISTS idx_fastener_project ON fastener_lots(project_id);
"""


def now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today() -> str:
    return datetime.date.today().isoformat()


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT_MS / 1000.0)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode=DELETE")  # network-share safe; never WAL here
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    migrate(conn)


def _columns(conn, table: str) -> set:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _table_exists(conn, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,)).fetchone() is not None


def migrate(conn: sqlite3.Connection) -> None:
    """Additive, idempotent schema upgrades for databases created before a
    feature shipped. Safe on the shared network file: ADD COLUMN with a constant
    DEFAULT rewrites no existing rows and never drops data. Runs every startup.

    pieces.traveler_type: added for the SJI joist variant. Existing pieces get
    'STRUCTURAL', so every traveler already in the field keeps its 18-field set
    and every gate behaves exactly as before.

    bol_items.astm_grade/fy/fu/ce: added for structured MTR capture at Gate 1.
    Existing rows get NULL, which renders blank; nothing else changes."""
    if _table_exists(conn, "pieces") and "traveler_type" not in _columns(conn, "pieces"):
        conn.execute("ALTER TABLE pieces ADD COLUMN traveler_type TEXT "
                     "NOT NULL DEFAULT 'STRUCTURAL'")
        conn.commit()
    if _table_exists(conn, "bol_items"):
        bol_cols = _columns(conn, "bol_items")
        for col, decl in (("astm_grade", "TEXT"), ("fy", "REAL"),
                          ("fu", "REAL"), ("ce", "REAL")):
            if col not in bol_cols:
                conn.execute(f"ALTER TABLE bol_items ADD COLUMN {col} {decl}")
        conn.commit()


def execute_write(conn, sql, params=()):
    """Single write with retry on transient network-share lock errors."""
    last = None
    for attempt in range(WRITE_RETRIES):
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur
        except sqlite3.OperationalError as e:
            last = e
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
    raise last


def seed_traveler(conn, piece_pk: int, project_label: str, piece_id: str,
                  section: str, heat: str, lot: str,
                  traveler_type: str = "STRUCTURAL") -> None:
    """Create the traveler rows for a new piece from the variant's field set.
    Fields 1-4 (info) auto-fill at receiving and are identical across variants,
    so the auto map below works for both STRUCTURAL (18 fields) and JOIST (20)."""
    ts = now()
    auto = {1: project_label, 2: piece_id, 3: f"{section} / Heat {heat or 'N/A'}",
            4: lot or ""}
    for num, name, _kind in traveler_spec(traveler_type):
        val = auto.get(num)
        conn.execute(
            "INSERT OR IGNORE INTO traveler_fields "
            "(piece_pk, field_number, field_name, value, signed_by, timestamp) "
            "VALUES (?,?,?,?,?,?)",
            (piece_pk, num, name, val,
             "SYSTEM" if val else None, ts if val else None))
    conn.commit()


def traveler_rows(conn, piece_pk: int):
    return conn.execute(
        "SELECT * FROM traveler_fields WHERE piece_pk=? ORDER BY field_number",
        (piece_pk,)).fetchall()


def field_kind(num: int, traveler_type: str = "STRUCTURAL") -> str:
    for n, _name, kind in traveler_spec(traveler_type):
        if n == num:
            return kind
    return "op"


def open_ncr_count(conn, piece_pk: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM ncrs WHERE piece_pk=? AND status!='CLOSED'",
        (piece_pk,)).fetchone()[0]


def lowest_unsigned_floor(rows, traveler_type: str = "STRUCTURAL"):
    """Hard block 2 core: the only signable floor step is the lowest unsigned field
    in the variant floor range. Returns its field number or None when all floor
    steps are signed. The Fabrication screen signs exactly this field, so testing
    this function tests the locked-sequence rule the UI runs."""
    m = spec_meta(traveler_type)
    for r in rows:
        if m["floor_first"] <= r["field_number"] <= m["floor_last"] and not r["signed_by"]:
            return r["field_number"]
    return None


def cwi_signature_ok(name) -> bool:
    """Hard block 1 core: a CWI step (field 8 pre-weld, field 10 post-weld) cannot
    advance without a non-empty CWI name. The Fabrication CWI handler calls this."""
    return bool((name or "").strip())


def release_blockers(conn, piece_pk: int, traveler_type: str = "STRUCTURAL") -> list:
    """Hard block 4 core: the reasons a piece cannot pass Gate 3, re-evaluated at
    sign time. Empty list means releasable. Combines the two facts the Release
    screen re-verifies: unsigned completeness fields and open NCRs."""
    reasons = []
    missing = traveler_complete_through(conn, piece_pk, gate3_last_field(traveler_type))
    if missing:
        reasons.append("unsigned fields: " + ", ".join(str(m) for m in missing))
    open_count = open_ncr_count(conn, piece_pk)
    if open_count:
        reasons.append(f"{open_count} open NCR(s)")
    return reasons


def traveler_complete_through(conn, piece_pk: int, last_field: int = 14) -> list:
    """Return field numbers 1..last_field that are NOT signed (N/A counts as signed)."""
    rows = traveler_rows(conn, piece_pk)
    missing = []
    for r in rows:
        if r["field_number"] > last_field:
            continue
        if not r["signed_by"]:
            missing.append(r["field_number"])
    return missing


def piece_by_scan(conn, scan: str):
    """Resolve a scanner payload to a piece row.
    Scanner is a keyboard wedge: payload may be the full QR string
    'PIECEID|PROJECT|HEAT|DATE' or a bare piece ID."""
    pid = scan.strip().split("|")[0].strip().upper()
    return conn.execute("SELECT * FROM pieces WHERE piece_id=?", (pid,)).fetchone()
