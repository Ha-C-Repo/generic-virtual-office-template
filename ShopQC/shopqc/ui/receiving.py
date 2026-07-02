"""Screen 2: Receiving (Gate 1 - Incoming Material)."""

import json
import os
import tkinter as tk
from tkinter import ttk, filedialog

from .. import db, bol_import, piece_ids, labels, reports, standards
from . import widgets as W

# Mirrors NC-QC-FAB-001 Section 4.1 (MTR review). Rename here if the program
# text differs; labels are data, not logic.
MTR_CHECKS = [
    "Heat number on steel matches MTR",
    "ASTM spec and grade conform to PO (A992 / A500 / A36 / F1554)",
    "Fy meets specified minimum",
    "Fu meets specified minimum",
    "Carbon equivalent (CE) within limit",
    "MTR legible and on file",
    "Country of origin recorded",
]
# Mirrors NC-QC-FAB-001 Section 4.2 (physical receiving).
PHYS_CHECKS = [
    "Piece count matches BOL",
    "Section size verified by measurement",
    "No visible damage (bends, gouges, torch marks)",
    "Straightness / sweep within AISC 303-22 tolerance",
    "Surface condition acceptable (rust, pitting, mill scale)",
    "Lengths spot-checked against BOL",
]


class ReceivingScreen(tk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        W.header(self, "RECEIVING - GATE 1 (Incoming Material)")
        top = tk.Frame(self, pady=6)
        top.pack(fill="x", padx=10)
        tk.Label(top, text="Project:").pack(side="left")
        self.proj_var = tk.StringVar()
        self.proj_combo = ttk.Combobox(top, textvariable=self.proj_var,
                                       state="readonly", width=34)
        self.proj_combo.pack(side="left", padx=6)
        ttk.Button(top, text="Import BOL PDF", command=self.import_bol).pack(side="left", padx=4)
        ttk.Button(top, text="Add Line", command=self.add_line).pack(side="left", padx=4)
        ttk.Button(top, text="Edit Line", command=self.edit_line).pack(side="left", padx=4)
        ttk.Button(top, text="Delete Line", command=self.del_line).pack(side="left", padx=4)

        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=10)
        left = tk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        cols = [("line", "#"), ("section", "Section"), ("ordered", "Qty BOL"),
                ("received", "Qty Recv"), ("heat", "Heat No."), ("conf", "Confidence")]
        self.tree, vsb = W.make_tree(left, cols, [40, 160, 80, 80, 130, 90], height=10)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        self.tree.tag_configure("low", background="#ffe0e0")

        right = tk.Frame(body, padx=12)
        right.pack(side="left", fill="y")
        tk.Label(right, text="MTR checks (Sec 4.1)",
                 font=("Helvetica", 10, "bold")).pack(anchor="w")
        self.mtr_vars = self._checks(right, MTR_CHECKS)
        tk.Label(right, text="Physical checks (Sec 4.2)",
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(8, 0))
        self.phys_vars = self._checks(right, PHYS_CHECKS)
        # On-screen tolerance reference for the straightness check (AISC 303-22).
        tk.Label(right, text=standards.AISC_303_STRAIGHTNESS_REF, fg=W.DARK,
                 wraplength=300, justify="left",
                 font=("Helvetica", 8, "italic")).pack(anchor="w", pady=(2, 0))

        # High-strength bolt receiving (Gate 1, RCSC / ASTM F3125). A working list
        # like the BOL lines above. "Receive Fastener Lots" enforces the acceptance
        # rule (db.fastener_receiving_blocked_reason) before any lot is recorded.
        fast = tk.LabelFrame(self, text="High-strength bolt lots (RCSC / ASTM F3125)",
                             padx=8, pady=4)
        fast.pack(fill="x", padx=10, pady=(4, 0))
        fbtns = tk.Frame(fast)
        fbtns.pack(fill="x")
        ttk.Button(fbtns, text="Add Fastener Lot",
                   command=self.add_fastener).pack(side="left", padx=2)
        ttk.Button(fbtns, text="Edit Fastener Lot",
                   command=self.edit_fastener).pack(side="left", padx=2)
        ttk.Button(fbtns, text="Delete Fastener Lot",
                   command=self.del_fastener).pack(side="left", padx=2)
        ttk.Button(fbtns, text="Receive Fastener Lots",
                   command=self.receive_fasteners).pack(side="left", padx=8)
        ftreef = tk.Frame(fast)
        ftreef.pack(fill="x")
        fcols = [("type", "Assembly"), ("qty", "Qty"), ("rocap", "ROCAP lot"),
                 ("galv", "Galv"), ("state", "Acceptance")]
        self.ftree, fvsb = W.make_tree(ftreef, fcols, [90, 60, 140, 50, 300], height=4)
        self.ftree.pack(side="left", fill="x", expand=True)
        fvsb.pack(side="left", fill="y")
        self.ftree.tag_configure("low", background="#ffe0e0")
        tk.Label(fast, text=standards.RCSC_F3125_RECEIVING_REF, fg=W.DARK,
                 wraplength=640, justify="left",
                 font=("Helvetica", 8, "italic")).pack(anchor="w", pady=(2, 0))

        bot = tk.Frame(self, pady=8)
        bot.pack(fill="x", padx=10)
        ttk.Button(bot, text="Receive + Print Labels",
                   command=self.receive).pack(side="left")
        ttk.Button(bot, text="Sign RIR", command=self.sign_rir).pack(side="left", padx=8)
        self.status = tk.Label(bot, text="", fg=W.RED)
        self.status.pack(side="left", padx=10)
        self.lines = []  # working (uncommitted) BOL lines
        self.fastener_lots = []  # working (uncommitted) fastener lots
        self.refresh()

    def _checks(self, parent, items):
        out = []
        for t in items:
            v = tk.IntVar(value=0)
            tk.Checkbutton(parent, text=t, variable=v, anchor="w",
                           wraplength=300, justify="left").pack(anchor="w")
            out.append((t, v))
        return out

    def refresh(self):
        rows = self.ctx.conn.execute(
            "SELECT * FROM projects WHERE status='ACTIVE' ORDER BY id DESC").fetchall()
        self._projects = {f"{r['code']} - {r['name']}": r for r in rows}
        self.proj_combo["values"] = list(self._projects)
        if rows and not self.proj_var.get():
            self.proj_combo.current(0)

    def _project(self):
        p = self._projects.get(self.proj_var.get())
        if not p:
            W.err(self, "Select a project.")
        return p

    def _redraw_lines(self):
        self.tree.delete(*self.tree.get_children())
        for i, ln in enumerate(self.lines):
            tag = ("low",) if ln.get("confidence") == "low" else ()
            self.tree.insert("", "end", iid=str(i), tags=tag, values=(
                ln.get("line", i + 1), ln["section"], ln.get("qty", 0),
                ln.get("received", ln.get("qty", 0)), ln.get("heat", ""),
                ln.get("confidence", "manual")))

    def import_bol(self):
        if not self._project():
            return
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            items = bol_import.extract_lines(path)
        except Exception as e:
            W.err(self, f"{e}\n\nFalling back to manual entry. Use Add Line.")
            return
        if not items:
            W.info(self, "No steel line items found. Use Add Line.")
            return
        for it in items:
            it["received"] = it["qty"]
        self.lines = items
        self._redraw_lines()
        low = sum(1 for i in items if i["confidence"] == "low")
        self.status.config(text=f"{len(items)} lines parsed. "
                                f"{low} low-confidence (red) need review.")

    def _line_fields(self):
        # Gate 1 MTR capture: lot and the actual ASTM Fy / Fu / CE off the mill
        # cert, recorded as structured values (not just a checkbox). Lot also signs
        # traveler field 4 so the piece can clear Gate 3.
        return [
            ("section", "Section / SJI mark (e.g. W14x90, 30KCS4)", "entry", None),
            ("qty", "Qty per BOL", "entry", None),
            ("received", "Qty physically received", "entry", None),
            ("heat", "Heat number", "entry", None),
            ("lot", "MTR lot number", "entry", None),
            ("astm_grade", "ASTM grade (MTR)", "combo", ["", *standards.ASTM_GRADES]),
            ("fy", "Fy actual (ksi, MTR)", "entry", None),
            ("fu", "Fu actual (ksi, MTR)", "entry", None),
            ("ce", "Carbon equivalent CE (MTR)", "entry", None)]

    def add_line(self):
        d = W.FormDialog(self, "Add BOL Line", self._line_fields())
        if d.result:
            self._commit_line_dialog(d.result, None)

    def edit_line(self):
        sel = self.tree.selection()
        if not sel:
            return W.err(self, "Select a line.")
        i = int(sel[0])
        ln = self.lines[i]
        d = W.FormDialog(self, "Edit BOL Line", self._line_fields(), initial={
            "section": ln["section"], "qty": ln.get("qty", 0),
            "received": ln.get("received", 0), "heat": ln.get("heat", ""),
            "lot": ln.get("lot", ""), "astm_grade": ln.get("astm_grade", ""),
            "fy": ln.get("fy") or "", "fu": ln.get("fu") or "",
            "ce": ln.get("ce") or ""})
        if d.result:
            self._commit_line_dialog(d.result, i)

    @staticmethod
    def _num_or_none(v):
        v = (v or "").strip()
        if not v:
            return None
        return float(v)  # caller catches ValueError

    def _commit_line_dialog(self, r, idx):
        if not piece_ids.section_format_ok(r["section"]):
            return W.err(self, f"'{r['section']}' is not a recognized section format.")
        try:
            qty, recv = int(r["qty"] or 0), int(r["received"] or 0)
        except ValueError:
            return W.err(self, "Quantities must be whole numbers.")
        try:
            fy = self._num_or_none(r.get("fy"))
            fu = self._num_or_none(r.get("fu"))
            ce = self._num_or_none(r.get("ce"))
        except ValueError:
            return W.err(self, "Fy, Fu and CE must be numbers (ksi for Fy/Fu) "
                               "or left blank.")
        ln = {"section": piece_ids.normalize_section(r["section"]), "qty": qty,
              "received": recv, "heat": r["heat"], "lot": r.get("lot", ""),
              "astm_grade": (r.get("astm_grade") or "").strip(),
              "fy": fy, "fu": fu, "ce": ce, "confidence": "manual"}
        if idx is None:
            ln["line"] = len(self.lines) + 1
            self.lines.append(ln)
        else:
            ln["line"] = self.lines[idx].get("line", idx + 1)
            self.lines[idx] = ln
        self._redraw_lines()
        # Non-blocking flag if the recorded MTR value is below the ASTM minimum.
        warn = standards.astm_shortfall(ln["astm_grade"], fy, fu)
        if warn:
            W.info(self, warn)

    def del_line(self):
        sel = self.tree.selection()
        if sel:
            del self.lines[int(sel[0])]
            self._redraw_lines()

    def receive(self):
        p = self._project()
        if not p or not self.lines:
            if p:
                W.err(self, "No BOL lines to receive.")
            return
        unresolved = [l for l in self.lines if l.get("confidence") == "low"]
        if unresolved and not W.confirm(
                self, f"{len(unresolved)} low-confidence lines were not edited. "
                      "Receive anyway?"):
            return
        conn, cfg = self.ctx.conn, self.ctx.cfg
        zpls, made = [], 0
        for ln in self.lines:
            recv = ln.get("received", 0)
            # shortage or mismatch -> automatic NCR per the QC program
            if recv != ln.get("qty", 0):
                db.execute_write(conn,
                    "INSERT INTO ncrs (project_id, gate, category, description, "
                    "opened_by, opened_date) VALUES (?,?,?,?,?,?)",
                    (p["id"], 1, "Material nonconformance",
                     f"BOL qty {ln.get('qty')} vs received {recv} for "
                     f"{ln['section']} heat {ln.get('heat') or 'N/A'}",
                     cfg.get("station_name", "GATE1"), db.now()))
            lot = ln.get("lot") or ""
            cur = db.execute_write(conn,
                "INSERT INTO bol_items (project_id, line_number, section, "
                "quantity_ordered, quantity_received, heat_number, lot_number, "
                "astm_grade, fy, fu, ce, received_date) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["id"], ln.get("line"), ln["section"], ln.get("qty", 0),
                 recv, ln.get("heat"), lot or None, ln.get("astm_grade") or None,
                 ln.get("fy"), ln.get("fu"), ln.get("ce"), db.today()))
            # Variant is chosen from the section/mark: SJI joist marks (K, KCS,
            # LH, DLH, SLH, G) get the joist traveler, everything else structural.
            ttype = piece_ids.traveler_type_for_section(ln["section"])
            for _ in range(recv):
                pid = piece_ids.next_piece_id(conn, p["code"], ln["section"])
                cur = db.execute_write(conn,
                    "INSERT INTO pieces (project_id, piece_id, section, "
                    "heat_number, traveler_type, created_date) VALUES (?,?,?,?,?,?)",
                    (p["id"], pid, ln["section"], ln.get("heat"), ttype, db.now()))
                piece_pk = cur.lastrowid
                # Pass the MTR lot so traveler field 4 auto-signs at receiving; an
                # info field sits outside the floor range and cannot be signed later,
                # so without this the piece could never clear Gate 3.
                db.seed_traveler(conn, piece_pk,
                                 f"{p['name']} / {p['job_number']}", pid,
                                 ln["section"], ln.get("heat") or "", lot, ttype)
                zpls.append(labels.build_zpl(
                    pid, ln["section"], p["name"], db.today(),
                    piece_ids.qr_payload(pid, p["job_number"],
                                         ln.get("heat") or "", db.today())))
                made += 1
        try:
            labels.print_batch(zpls, cfg)
            db.execute_write(conn, "UPDATE pieces SET label_printed=1 "
                             "WHERE project_id=? AND label_printed=0", (p["id"],))
            msg = f"{made} pieces received, {len(zpls)} labels printed."
        except Exception as e:
            msg = (f"{made} pieces received. LABEL PRINT FAILED: {e}. "
                   "Fix printer in config.json, then reprint from Fabrication tab.")
        self.lines = []
        self._redraw_lines()
        self.status.config(text=msg)
        self.ctx.refresh_all()

    def sign_rir(self):
        p = self._project()
        if not p:
            return
        unchecked = [t for t, v in self.mtr_vars + self.phys_vars if not v.get()]
        if unchecked:
            return W.err(self, "All MTR and physical checks must be completed "
                               "before the RIR can be signed:\n- "
                               + "\n- ".join(unchecked))
        name = W.ask_name(self, "Sign RIR", "Receiving inspector name:")
        if not name:
            return
        checks = {t: bool(v.get()) for t, v in self.mtr_vars + self.phys_vars}
        db.execute_write(self.ctx.conn,
            "INSERT INTO rir_records (project_id, lot_number, signed_by, "
            "signed_date, all_checks_json) VALUES (?,?,?,?,?)",
            (p["id"], None, name, db.now(), json.dumps(checks)))
        for _, v in self.mtr_vars + self.phys_vars:
            v.set(0)
        if W.confirm(self, "RIR signed and locked. Print RIR PDF now?"):
            rir = self.ctx.conn.execute(
                "SELECT * FROM rir_records WHERE project_id=? "
                "ORDER BY id DESC LIMIT 1", (p["id"],)).fetchone()
            bol = self.ctx.conn.execute(
                "SELECT * FROM bol_items WHERE project_id=? ORDER BY id",
                (p["id"],)).fetchall()
            path = filedialog.asksaveasfilename(
                defaultextension=".pdf", initialfile=f"{p['code']}_RIR_{rir['id']}.pdf")
            if path:
                reports.rir_pdf(path, p, rir, bol)
                W.info(self, f"Saved {os.path.basename(path)}")

    # --- High-strength bolt lots (RCSC / ASTM F3125) ---------------------------

    def _fastener_fields(self):
        return [
            ("assembly_type", "Assembly type", "combo",
             list(standards.FASTENER_ASSEMBLY_TYPES)),
            ("quantity", "Quantity in lot", "entry", None),
            ("rocap_lot_no", "ROCAP test lot number", "entry", None),
            ("markings_verified", "Bolt, nut and washer markings verified",
             "check", None),
            ("mfr_cert_on_file", "Manufacturer cert on file", "check", None),
            ("galvanized", "Galvanized", "check", None),
            ("lube_check_done", "Lubrication check done (galvanized)", "check", None),
            ("rocap_result_reference", "ROCAP result reference", "entry", None),
            ("ref", standards.RCSC_F3125_RECEIVING_REF, "note", None)]

    def _fastener_initial(self, f):
        return {k: f.get(k, 0 if k in ("markings_verified", "mfr_cert_on_file",
                                       "galvanized", "lube_check_done", "quantity")
                         else "")
                for k in ("assembly_type", "quantity", "rocap_lot_no",
                          "markings_verified", "mfr_cert_on_file", "galvanized",
                          "lube_check_done", "rocap_result_reference")}

    def add_fastener(self):
        d = W.FormDialog(self, "Add Fastener Lot", self._fastener_fields())
        if d.result:
            self._commit_fastener(d.result, None)

    def edit_fastener(self):
        sel = self.ftree.selection()
        if not sel:
            return W.err(self, "Select a fastener lot.")
        i = int(sel[0])
        d = W.FormDialog(self, "Edit Fastener Lot", self._fastener_fields(),
                         initial=self._fastener_initial(self.fastener_lots[i]))
        if d.result:
            self._commit_fastener(d.result, i)

    def _commit_fastener(self, r, idx):
        at = (r.get("assembly_type") or "").strip()
        if at not in standards.FASTENER_ASSEMBLY_TYPES:
            return W.err(self, "Select an assembly type: "
                         + ", ".join(standards.FASTENER_ASSEMBLY_TYPES) + ".")
        try:
            qty = int(r.get("quantity") or 0)
        except ValueError:
            return W.err(self, "Quantity must be a whole number.")
        f = {"assembly_type": at, "quantity": qty,
             "rocap_lot_no": (r.get("rocap_lot_no") or "").strip(),
             "markings_verified": int(r.get("markings_verified") or 0),
             "mfr_cert_on_file": int(r.get("mfr_cert_on_file") or 0),
             "galvanized": int(r.get("galvanized") or 0),
             "lube_check_done": int(r.get("lube_check_done") or 0),
             "rocap_result_reference": (r.get("rocap_result_reference") or "").strip()}
        if idx is None:
            self.fastener_lots.append(f)
        else:
            self.fastener_lots[idx] = f
        self._redraw_fasteners()

    @staticmethod
    def _fastener_block_reason(f):
        return db.fastener_receiving_blocked_reason(
            f.get("rocap_lot_no"), f.get("markings_verified"),
            f.get("mfr_cert_on_file"), f.get("galvanized"), f.get("lube_check_done"))

    def _redraw_fasteners(self):
        self.ftree.delete(*self.ftree.get_children())
        for i, f in enumerate(self.fastener_lots):
            reason = self._fastener_block_reason(f)
            tag = ("low",) if reason else ()
            self.ftree.insert("", "end", iid=str(i), tags=tag, values=(
                f.get("assembly_type", ""), f.get("quantity", 0),
                f.get("rocap_lot_no", ""),
                "Yes" if f.get("galvanized") else "No",
                "received-complete" if not reason else reason))

    def del_fastener(self):
        sel = self.ftree.selection()
        if sel:
            del self.fastener_lots[int(sel[0])]
            self._redraw_fasteners()

    def receive_fasteners(self):
        p = self._project()
        if not p or not self.fastener_lots:
            if p:
                W.err(self, "No fastener lots to receive.")
            return
        blocked = []
        for f in self.fastener_lots:
            reason = self._fastener_block_reason(f)
            if reason:
                blocked.append(f"{f['assembly_type']} ROCAP "
                               f"{f.get('rocap_lot_no') or 'N/A'}: {reason}")
        if blocked:
            return W.err(self, "These lots cannot be received-complete:\n- "
                         + "\n- ".join(blocked))
        conn = self.ctx.conn
        for f in self.fastener_lots:
            db.execute_write(conn,
                "INSERT INTO fastener_lots (project_id, assembly_type, quantity, "
                "rocap_lot_no, markings_verified, mfr_cert_on_file, galvanized, "
                "lube_check_done, rocap_result_reference, received_complete, "
                "received_date, created_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["id"], f["assembly_type"], f["quantity"], f["rocap_lot_no"],
                 f["markings_verified"], f["mfr_cert_on_file"], f["galvanized"],
                 f["lube_check_done"], f["rocap_result_reference"] or None,
                 1, db.today(), db.now()))
        n = len(self.fastener_lots)
        self.fastener_lots = []
        self._redraw_fasteners()
        self.status.config(
            text=f"{n} fastener lot(s) received-complete and recorded.")
        self.ctx.refresh_all()
