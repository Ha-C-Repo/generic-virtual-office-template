"""Screen 3: Fabrication (Gate 2 - In-Process).

Locked sequence: only the lowest unsigned floor field can be signed. The floor
range is per variant and comes from db.spec_meta (structural 5..14, joist 5..16),
never assumed here. See _floor().
Field 8 (pre-weld CWI) is the hard block - it sits in the sequence, so the
weld steps after it are physically unreachable until a CWI name is recorded.
Open NCRs put the piece on NCR_HOLD and freeze the whole traveler.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog

from .. import db, reports, labels, piece_ids, standards
from . import widgets as W


class FabricationScreen(tk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.piece = None
        W.header(self, "FABRICATION - GATE 2 (In-Process)")
        self.scan = W.ScanEntry(self, self.load_piece)
        self.scan.pack(fill="x", padx=10, pady=8)

        self.info = tk.Label(self, text="Scan a piece to open its traveler.",
                             font=("Helvetica", 11))
        self.info.pack(anchor="w", padx=10)
        self.progress = ttk.Progressbar(self, length=420)
        self.progress.pack(anchor="w", padx=10, pady=4)

        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=10)
        cols = [("num", "#"), ("name", "Field"), ("value", "Value"),
                ("by", "Signed By"), ("ts", "Date")]
        self.tree, vsb = W.make_tree(body, cols, [35, 230, 230, 130, 120], height=18)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        self.tree.tag_configure("active", background="#fff2cc")
        self.tree.tag_configure("done", background="#e8f5e9")
        self.tree.tag_configure("hold", background="#ffcdd2")

        bot = tk.Frame(self, pady=8)
        bot.pack(fill="x", padx=10)
        ttk.Button(bot, text="Sign Active Step",
                   command=self.sign_active).pack(side="left")
        ttk.Button(bot, text="Open NCR on Active Step",
                   command=self.open_ncr).pack(side="left", padx=8)
        ttk.Button(bot, text="Reprint Label",
                   command=self.reprint).pack(side="left", padx=8)
        ttk.Button(bot, text="Print Traveler PDF",
                   command=self.traveler_pdf).pack(side="left")

    def on_show(self):
        self.scan.focus_scan()
        if self.piece:
            self.load_piece(self.piece["piece_id"])

    # ----- loading -----
    def load_piece(self, scan):
        row = db.piece_by_scan(self.ctx.conn, scan)
        if not row:
            return W.err(self, f"No piece found for scan '{scan}'.")
        self.piece = row
        self.redraw()

    def _floor(self):
        """Floor-step range for the current piece's traveler variant."""
        m = db.spec_meta(self.piece["traveler_type"])
        return m["floor_first"], m["floor_last"]

    def _active_field(self, rows):
        # Locked sequence (hard block 2): the lowest unsigned floor field only.
        return db.lowest_unsigned_floor(rows, self.piece["traveler_type"])

    def redraw(self):
        conn = self.ctx.conn
        self.piece = conn.execute("SELECT * FROM pieces WHERE id=?",
                                  (self.piece["id"],)).fetchone()
        rows = db.traveler_rows(conn, self.piece["id"])
        hold = db.open_ncr_count(conn, self.piece["id"]) > 0
        active = self._active_field(rows)
        first, last = self._floor()
        self.tree.delete(*self.tree.get_children())
        done = 0
        for r in rows:
            n = r["field_number"]
            tag = ()
            if hold and first <= n <= last and not r["signed_by"]:
                tag = ("hold",)
            elif n == active:
                tag = ("active",)
            elif r["signed_by"]:
                tag = ("done",)
            if first <= n <= last and r["signed_by"]:
                done += 1
            self.tree.insert("", "end", tags=tag, values=(
                n, r["field_name"], r["value"] or "", r["signed_by"] or "",
                (r["timestamp"] or "")[:16]))
        total = last - first + 1
        self.progress["maximum"] = total
        self.progress["value"] = done
        state = "NCR HOLD - traveler frozen" if hold else (
            f"Active step: field {active}" if active else "Floor steps complete - ready for Gate 3")
        variant = "JOIST (SJI)" if self.piece["traveler_type"] == "JOIST" else "STRUCTURAL"
        self.info.config(
            text=f"{self.piece['piece_id']}  |  {self.piece['section']}  |  "
                 f"{variant}  |  Heat {self.piece['heat_number'] or 'N/A'}  |  "
                 f"Status {self.piece['status']}  |  {done}/{total} steps  |  {state}",
            fg=W.RED if hold else "black")

    # ----- signing -----
    def sign_active(self):
        if not self.piece:
            return W.err(self, "Scan a piece first.")
        conn = self.ctx.conn
        if db.open_ncr_count(conn, self.piece["id"]) > 0:
            return W.err(self, "This piece is on NCR HOLD. Close the NCR on the "
                               "NCR Log tab before continuing fabrication.")
        if self.piece["status"] in ("RELEASED", "SHIPPED"):
            return W.err(self, "Piece is already released.")
        rows = db.traveler_rows(conn, self.piece["id"])
        num = self._active_field(rows)
        if num is None:
            return W.info(self, "All floor steps are signed. Take the piece to Gate 3.")
        kind = db.field_kind(num, self.piece["traveler_type"])
        handler = {"cwi": self._sign_cwi, "weld": self._sign_weld,
                   "optional": self._sign_optional, "measure": self._sign_measure,
                   "seat": self._sign_seat, "bridging": self._sign_bridging,
                   "camber": self._sign_camber, "dft": self._sign_dft,
                   }.get(kind, self._sign_op)
        if handler(num):
            if self.piece["status"] == "RECEIVED":
                db.execute_write(conn, "UPDATE pieces SET status='IN_FAB' WHERE id=?",
                                 (self.piece["id"],))
            self.redraw()

    def _save_field(self, num, value, signed_by, notes=""):
        db.execute_write(self.ctx.conn,
            "UPDATE traveler_fields SET value=?, signed_by=?, timestamp=?, notes=? "
            "WHERE piece_pk=? AND field_number=?",
            (value, signed_by, db.now(), notes, self.piece["id"], num))
        return True

    def _sign_op(self, num):
        # The num==14 (DFT) and num==12 (dimensional) capture below is specific to
        # the STRUCTURAL field set, where those numbers mean DFT and dimensional.
        # In the joist set those numbers mean camber and bridging and are routed
        # to dedicated handlers, so the guard keeps this from misfiring there.
        structural = self.piece["traveler_type"] == "STRUCTURAL"
        fields = [("name", "Operator name", "entry", None)]
        if structural and num == 14:
            fields.insert(0, ("dft", "DFT reading (mils)", "entry", None))
        if structural and num == 12:
            fields.insert(0, ("result", "Dimensional result (e.g. within AISC 303-22)",
                              "entry", None))
            # Surface the AISC 303-22 length tolerance while the inspector measures.
            fields.insert(1, ("_tol", standards.AISC_303_LENGTH_TOL, "note", None))
        fields.append(("notes", "Notes", "entry", None))
        d = W.FormDialog(self, f"Sign field {num}", fields)
        r = d.result
        if not r or not r["name"]:
            return False
        value = db.today()
        if structural and num == 14:
            try:
                value = f"{float(r['dft'])} mils"
            except (ValueError, TypeError):
                W.err(self, "DFT must be a number in mils.")
                return False
        if structural and num == 12:
            value = r.get("result") or db.today()
        return self._save_field(num, value, r["name"], r.get("notes", ""))

    def _sign_measure(self, num):
        # Generic measured/observed capture for a joist QC step (span/depth, end
        # anchorage). The field name from the traveler drives the prompt so this
        # one handler serves several joist steps without number coupling.
        label = self._field_name(num)
        d = W.FormDialog(self, f"Sign field {num}", [
            ("value", f"{label} (measured / observed)", "entry", None),
            ("name", "Inspector name", "entry", None),
            ("notes", "Notes", "entry", None)])
        r = d.result
        if not r or not r["name"] or not r["value"]:
            if r:
                W.err(self, "A measured/observed value and inspector name "
                            "are required.")
            return False
        return self._save_field(num, r["value"], r["name"], r.get("notes", ""))

    def _sign_seat(self, num):
        # SJI bearing seat: depth plus type. K-series seats are shallower than
        # LH/DLH; the value the inspector enters is checked against the SJI
        # designation by the inspector, not invented by the app.
        d = W.FormDialog(self, f"Sign field {num} - Bearing seat (SJI)", [
            ("depth", "Seat depth (in)", "entry", None),
            ("stype", "Seat type", "combo",
             ["Underslung", "Square end", "Bottom chord bearing", "Other"]),
            ("name", "Inspector name", "entry", None),
            ("notes", "Notes", "entry", None)])
        r = d.result
        if not r or not r["name"] or not r["depth"] or not r["stype"]:
            if r:
                W.err(self, "Seat depth, type and inspector name are required.")
            return False
        try:
            depth = float(r["depth"])
        except (ValueError, TypeError):
            W.err(self, "Seat depth must be a number in inches.")
            return False
        return self._save_field(num, f"{depth} in / {r['stype']}", r["name"],
                                r.get("notes", ""))

    def _sign_bridging(self, num):
        # SJI bridging: rows installed and type. Bridging is the lateral-stability
        # load path; rows-required comes from the SJI bridging tables for the
        # joist and span and is verified by the inspector against the erection
        # drawings, recorded here for traceability.
        d = W.FormDialog(self, f"Sign field {num} - Bridging (SJI)", [
            ("rows", "Bridging rows installed", "entry", None),
            ("btype", "Bridging type", "combo",
             ["Horizontal", "Diagonal", "Bolted diagonal", "Mixed"]),
            ("name", "Inspector name", "entry", None),
            ("notes", "Rows required per SJI (note source)", "entry", None)])
        r = d.result
        if not r or not r["name"] or not r["rows"] or not r["btype"]:
            if r:
                W.err(self, "Bridging rows, type and inspector name are required.")
            return False
        return self._save_field(num, f"{r['rows']} rows / {r['btype']}", r["name"],
                                r.get("notes", ""))

    def _sign_camber(self, num):
        # The deflection-catch instrument. Captures measured camber against the
        # SJI-specified camber and flags an out-of-tolerance result toward an NCR,
        # which is exactly the check that should have caught the Elite Crossing
        # deflection failure. Camber is mandatory for joists, never N/A.
        d = W.FormDialog(self, f"Sign field {num} - Camber vs SJI", [
            ("measured", "Camber measured (in)", "entry", None),
            ("specified", "SJI-specified camber (in)", "entry", None),
            ("name", "Inspector name", "entry", None),
            ("notes", "Notes", "entry", None)])
        r = d.result
        if not r or not r["name"]:
            return False
        try:
            meas, spec = float(r["measured"]), float(r["specified"])
        except (ValueError, TypeError):
            W.err(self, "Camber measured and SJI-specified must both be numbers "
                        "(inches).")
            return False
        value = f"{meas} in vs SJI {spec} in"
        # PROVISIONAL tolerance: SJI camber is span-dependent and the program PDF
        # was not available, so 0.25 in is a placeholder flagged for Owner. A
        # measured camber short of the specified value beyond tolerance is a
        # deflection nonconformance: route it to an NCR. If the disposition is a
        # field modification, the NCR category is Unauthorized field modification,
        # which cannot close without an EOR sealed reference (hard block 6).
        if spec - meas > 0.25:
            W.err(self, "Camber is below the SJI-specified value beyond tolerance. "
                        "Open an NCR on this step (deflection / SJI "
                        "nonconformance). If a field modification is involved, "
                        "use category 'Unauthorized field modification' (an EOR "
                        "sealed reference is required to close it).")
        return self._save_field(num, value, r["name"], r.get("notes", ""))

    def _sign_dft(self, num):
        # Joist surface prep / DFT. Mirrors the structural DFT capture but as a
        # dedicated handler so it works at the joist field number without a
        # number-coupled branch in _sign_op.
        d = W.FormDialog(self, f"Sign field {num} - Surface prep / DFT", [
            ("dft", "DFT reading (mils)", "entry", None),
            ("name", "Operator name", "entry", None),
            ("notes", "Notes", "entry", None)])
        r = d.result
        if not r or not r["name"]:
            return False
        try:
            value = f"{float(r['dft'])} mils"
        except (ValueError, TypeError):
            W.err(self, "DFT must be a number in mils.")
            return False
        return self._save_field(num, value, r["name"], r.get("notes", ""))

    def _field_name(self, num):
        for fnum, name, _kind in db.traveler_spec(self.piece["traveler_type"]):
            if fnum == num:
                return name
        return f"field {num}"

    def _sign_cwi(self, num):
        # HARD BLOCK: no CWI name, no signature, no advancing. Non-negotiable.
        label = "Pre-weld inspection" if num == 8 else "Post-weld VT"
        fields = [("cwi", f"CWI name ({label}) - REQUIRED", "entry", None)]
        if num == 10:
            fields.append(("vt", "VT result", "combo", ["ACCEPT", "REJECT", "N/A - no welds"]))
        fields.append(("notes", "Notes", "entry", None))
        d = W.FormDialog(self, f"CWI sign - field {num}", fields)
        r = d.result
        if not r:
            return False
        if not db.cwi_signature_ok(r["cwi"]):
            W.err(self, f"HARD BLOCK: field {num} requires a CWI name. "
                        "The traveler cannot advance without it (NC-QC-FAB-001).")
            return False
        value = "PRE-WELD OK" if num == 8 else r.get("vt", "")
        if num == 10:
            if r.get("vt") == "REJECT":
                W.err(self, "VT REJECT recorded. Open an NCR on this step now.")
            db.execute_write(self.ctx.conn,
                "UPDATE weld_records SET vt_result=?, vt_by=?, vt_date=? "
                "WHERE piece_pk=?", (r.get("vt"), r["cwi"], db.now(),
                                     self.piece["id"]))
        else:
            db.execute_write(self.ctx.conn,
                "INSERT INTO weld_records (piece_pk, pre_weld_by, pre_weld_date) "
                "VALUES (?,?,?)", (self.piece["id"], r["cwi"], db.now()))
        return self._save_field(num, value, f"CWI: {r['cwi']}", r.get("notes", ""))

    def _sign_weld(self, num):
        d = W.FormDialog(self, "Weld step - field 9", [
            ("welder", "Welder ID (qualified welder no.)", "entry", None),
            ("wps", "WPS file", "combo", list(db.WPS_FILES) + ["N/A - no welds"]),
            ("notes", "Notes", "entry", None)])
        r = d.result
        if not r or not r["welder"] or not r["wps"]:
            if r:
                W.err(self, "Welder ID and WPS are required.")
            return False
        db.execute_write(self.ctx.conn,
            "UPDATE weld_records SET welder_id=?, wps_file=? WHERE piece_pk=?",
            (r["welder"], r["wps"], self.piece["id"]))
        return self._save_field(num, r["wps"], r["welder"], r.get("notes", ""))

    def _sign_optional(self, num):
        # Prompt from the actual field name so it reads correctly for both variants
        # (structural field 11 UT/MT and 13 camber; joist field 15 UT/MT).
        prompt = self._field_name(num)
        d = W.FormDialog(self, f"Sign field {num}", [
            ("value", f"{prompt} (or N/A)", "entry", None),
            ("name", "Inspector name", "entry", None),
            ("notes", "Notes", "entry", None)])
        r = d.result
        if not r or not r["name"]:
            return False
        return self._save_field(num, r["value"] or "N/A", r["name"],
                                r.get("notes", ""))

    # ----- NCR / outputs -----
    def open_ncr(self):
        if not self.piece:
            return W.err(self, "Scan a piece first.")
        d = W.FormDialog(self, "Open NCR (Gate 2)", [
            ("category", "Category", "combo", list(db.NCR_CATEGORIES)),
            ("description", "Description", "text", None),
            ("name", "Opened by", "entry", None)])
        r = d.result
        if not r or not r["category"] or not r["description"] or not r["name"]:
            if r:
                W.err(self, "Category, description and name are required.")
            return
        db.execute_write(self.ctx.conn,
            "INSERT INTO ncrs (project_id, piece_pk, gate, category, description, "
            "opened_by, opened_date) VALUES (?,?,?,?,?,?,?)",
            (self.piece["project_id"], self.piece["id"], 2, r["category"],
             r["description"], r["name"], db.now()))
        db.execute_write(self.ctx.conn,
            "UPDATE pieces SET status='NCR_HOLD' WHERE id=?", (self.piece["id"],))
        ncr_id = self.ctx.conn.execute("SELECT MAX(id) FROM ncrs").fetchone()[0]
        auto = db.spec_meta(self.piece["traveler_type"])["ncr_auto"]
        self._save_field(auto, f"NCR-{ncr_id}", "SYSTEM")
        self.redraw()
        self.ctx.refresh_all()
        W.info(self, f"NCR-{ncr_id} opened. Piece is on NCR HOLD.")

    def reprint(self):
        if not self.piece:
            return W.err(self, "Scan a piece first.")
        p = self.ctx.conn.execute("SELECT * FROM projects WHERE id=?",
                                  (self.piece["project_id"],)).fetchone()
        zpl = labels.build_zpl(
            self.piece["piece_id"], self.piece["section"], p["name"], db.today(),
            piece_ids.qr_payload(self.piece["piece_id"], p["job_number"],
                                 self.piece["heat_number"] or "", db.today()))
        try:
            W.info(self, labels.send_zpl(zpl, self.ctx.cfg))
        except Exception as e:
            W.err(self, f"Print failed: {e}")

    def traveler_pdf(self):
        if not self.piece:
            return W.err(self, "Scan a piece first.")
        conn = self.ctx.conn
        p = conn.execute("SELECT * FROM projects WHERE id=?",
                         (self.piece["project_id"],)).fetchone()
        rows = db.traveler_rows(conn, self.piece["id"])
        ncrs = [r["id"] for r in conn.execute(
            "SELECT id FROM ncrs WHERE piece_pk=?", (self.piece["id"],))]
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"{self.piece['piece_id']}_Traveler.pdf")
        if path:
            reports.traveler_pdf(path, p, self.piece, rows, ncrs)
            W.info(self, f"Saved {os.path.basename(path)}")
