"""Screen 4: Release (Gate 3 - Final Release) plus shipping manifest."""

import os
import tkinter as tk
from tkinter import ttk, filedialog

from .. import db, reports
from . import widgets as W

# Hard block 5 rule and name live in db (single source); alias kept for messages.
CEO_NAME = db.CEO_NAME


class ReleaseScreen(tk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.piece = None
        W.header(self, "RELEASE - GATE 3 (Final Release)")
        self.scan = W.ScanEntry(self, self.load_piece)
        self.scan.pack(fill="x", padx=10, pady=8)
        self.info = tk.Label(self, text="Scan a piece to run release checks.",
                             font=("Helvetica", 11), justify="left", anchor="w")
        self.info.pack(fill="x", padx=10)

        btns = tk.Frame(self, pady=6)
        btns.pack(fill="x", padx=10)
        self.release_btn = ttk.Button(btns, text="Sign + Release Piece",
                                      command=self.release, state="disabled")
        self.release_btn.pack(side="left")

        # ----- manifest section -----
        tk.Frame(self, height=2, bg=W.RED).pack(fill="x", pady=6)
        mtop = tk.Frame(self)
        mtop.pack(fill="x", padx=10)
        tk.Label(mtop, text="Shipping manifest - project:",
                 font=("Helvetica", 10, "bold")).pack(side="left")
        self.proj_var = tk.StringVar()
        self.proj_combo = ttk.Combobox(mtop, textvariable=self.proj_var,
                                       state="readonly", width=32)
        self.proj_combo.pack(side="left", padx=6)
        self.proj_combo.bind("<<ComboboxSelected>>", lambda e: self.load_released())
        ttk.Button(mtop, text="Ship Selected Load",
                   command=self.ship_load).pack(side="left", padx=8)
        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=4)
        cols = [("pid", "Piece ID"), ("section", "Section"), ("heat", "Heat"),
                ("rel", "Released")]
        self.tree, vsb = W.make_tree(body, cols, [200, 150, 130, 150], height=9)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        self.refresh()

    def on_show(self):
        self.scan.focus_scan()
        self.refresh()

    def refresh(self):
        rows = self.ctx.conn.execute(
            "SELECT * FROM projects ORDER BY id DESC").fetchall()
        self._projects = {f"{r['code']} - {r['name']}": r for r in rows}
        self.proj_combo["values"] = list(self._projects)
        self.load_released()

    # ----- release -----
    def load_piece(self, scan):
        conn = self.ctx.conn
        row = db.piece_by_scan(conn, scan)
        if not row:
            return W.err(self, f"No piece found for scan '{scan}'.")
        self.piece = row
        problems = []
        if row["status"] in ("RELEASED", "SHIPPED"):
            problems.append(f"Piece already {row['status']}.")
        # Completeness window depends on the variant: structural fields 1..14,
        # joist fields 1..16. Both come from the spec, never assumed.
        last = db.gate3_last_field(row["traveler_type"])
        missing = db.traveler_complete_through(conn, row["id"], last)
        if missing:
            problems.append("Unsigned traveler fields: "
                            + ", ".join(str(m) for m in missing))
        ncrs = db.open_ncr_count(conn, row["id"])
        if ncrs:
            problems.append(f"{ncrs} open NCR(s) on this piece.")
        p = conn.execute("SELECT * FROM projects WHERE id=?",
                         (row["project_id"],)).fetchone()
        self._needs_ceo = db.needs_ceo_cosign(p["tonnage"], p["ias_required"])
        head = (f"{row['piece_id']}  |  {row['section']}  |  "
                f"Project {p['code']}  |  Status {row['status']}")
        if problems:
            self.release_btn.config(state="disabled")
            self.info.config(fg=W.RED, text=head + "\n\nCANNOT RELEASE:\n- "
                             + "\n- ".join(problems))
        else:
            self.release_btn.config(state="normal")
            extra = ("\nCEO co-sign REQUIRED (project >= 50 tons or IAS)."
                     if self._needs_ceo else "")
            self.info.config(fg="#1b5e20",
                             text=head + "\n\nAll checks pass. Ready to release." + extra)

    def release(self):
        if not self.piece:
            return
        conn = self.ctx.conn
        # First gate: re-verify before opening the sign-off dialog so the operator
        # is not asked to sign a piece that is already blocked (hard block 4).
        if db.release_blockers(conn, self.piece["id"], self.piece["traveler_type"]):
            self.load_piece(self.piece["piece_id"])
            return W.err(self, "Release checks failed on re-verify. See screen.")
        fields = [("director", "Shop Director name", "entry", None),
                  ("cwi", "CWI name", "entry", None)]
        if self._needs_ceo:
            fields.append(("ceo", f"CEO name (must be {CEO_NAME})", "entry", None))
        d = W.FormDialog(self, "Final Release sign-off", fields)
        r = d.result
        if not r or not r["director"] or not r["cwi"]:
            if r:
                W.err(self, "Shop Director and CWI names are both required.")
            return
        ceo = None
        if self._needs_ceo:
            if not db.ceo_name_matches(r.get("ceo")):
                return W.err(self, f"HARD BLOCK: CEO co-sign required. "
                                   f"Entry must read '{CEO_NAME}'.")
            ceo = CEO_NAME
        # Second gate, at the actual sign moment: the sign-off dialog above is modal
        # and may have stayed open while another station opened an NCR or changed the
        # piece. Hard block 4 says "re-verified at sign time", which is the commit,
        # not only before the dialog. Without this re-check the dialog is a TOCTOU
        # window through which a late NCR could release a nonconforming piece.
        if db.release_blockers(conn, self.piece["id"], self.piece["traveler_type"]):
            self.load_piece(self.piece["piece_id"])
            return W.err(self, "Release checks failed on re-verify at sign time. "
                               "See screen.")
        ts = db.now()
        db.execute_write(conn,
            "INSERT INTO release_records (piece_pk, shop_director_sign, cwi_sign, "
            "ceo_sign, release_date) VALUES (?,?,?,?,?)",
            (self.piece["id"], r["director"], r["cwi"], ceo, ts))
        meta = db.spec_meta(self.piece["traveler_type"])
        for num, by in ((meta["release_director"], r["director"]),
                        (meta["release_cwi"], f"CWI: {r['cwi']}")):
            db.execute_write(conn,
                "UPDATE traveler_fields SET value=?, signed_by=?, timestamp=? "
                "WHERE piece_pk=? AND field_number=?",
                (ts[:10], by, ts, self.piece["id"], num))
        db.execute_write(conn, "UPDATE pieces SET status='RELEASED' WHERE id=?",
                         (self.piece["id"],))
        self.ctx.refresh_all()
        if W.confirm(self, f"{self.piece['piece_id']} RELEASED. "
                           "Print Final Release Certificate?"):
            p = conn.execute("SELECT * FROM projects WHERE id=?",
                             (self.piece["project_id"],)).fetchone()
            rel = conn.execute("SELECT * FROM release_records WHERE piece_pk=? "
                               "ORDER BY id DESC LIMIT 1",
                               (self.piece["id"],)).fetchone()
            path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                initialfile=f"{self.piece['piece_id']}_Release_Cert.pdf")
            if path:
                reports.release_cert_pdf(path, p, self.piece, rel)
        self.load_piece(self.piece["piece_id"])
        self.load_released()

    # ----- manifest -----
    def load_released(self):
        self.tree.delete(*self.tree.get_children())
        p = self._projects.get(self.proj_var.get())
        if not p:
            return
        rows = self.ctx.conn.execute(
            "SELECT pc.*, rr.release_date FROM pieces pc "
            "LEFT JOIN release_records rr ON rr.piece_pk = pc.id "
            "WHERE pc.project_id=? AND pc.status='RELEASED' ORDER BY pc.piece_id",
            (p["id"],)).fetchall()
        for r in rows:
            self.tree.insert("", "end", iid=str(r["id"]), values=(
                r["piece_id"], r["section"], r["heat_number"] or "",
                (r["release_date"] or "")[:10]))

    @staticmethod
    def open_ncr_piece_ids(conn, ids):
        """Selected piece IDs that still carry an open NCR and so cannot ship.
        Uses the same db.open_ncr_count helper the release gate uses, so the ship
        gate mirrors the Gate 3 zero-open-NCR rule (R1)."""
        blocked = []
        for pk in ids:
            if db.open_ncr_count(conn, pk) > 0:
                row = conn.execute("SELECT piece_id FROM pieces WHERE id=?",
                                   (pk,)).fetchone()
                blocked.append(row["piece_id"] if row else str(pk))
        return blocked

    def ship_load(self):
        p = self._projects.get(self.proj_var.get())
        sel = self.tree.selection()
        if not p or not sel:
            return W.err(self, "Pick a project and select the released pieces "
                               "going on this truck (Ctrl-click for multiple).")
        conn = self.ctx.conn
        ids = [int(i) for i in sel]
        # Ship gate (R1): a piece with any open NCR cannot leave the shop, mirroring
        # the Gate 3 zero-open-NCR rule. An NCR opened after release would otherwise
        # let a nonconforming piece ship. Fast-fail before asking for truck details.
        blocked = self.open_ncr_piece_ids(conn, ids)
        if blocked:
            return W.err(self, "Cannot ship pieces with an open NCR. Close the NCR "
                               "on the NCR Log tab first:\n- " + "\n- ".join(blocked))
        d = W.FormDialog(self, "Ship load", [
            ("truck", "Truck / load number", "entry", None),
            ("name", "Shipped by", "entry", None)])
        r = d.result
        if not r or not r["truck"] or not r["name"]:
            return
        # Re-verify at the ship moment: the dialog above is modal and an NCR may have
        # been opened on a selected piece while it was open (same TOCTOU guard as the
        # release gate).
        blocked = self.open_ncr_piece_ids(conn, ids)
        if blocked:
            return W.err(self, "Cannot ship: an NCR was opened on:\n- "
                               + "\n- ".join(blocked)
                               + "\nClose it on the NCR Log tab first.")
        ts = db.now()
        for pk in ids:
            pc = conn.execute("SELECT traveler_type FROM pieces WHERE id=?",
                              (pk,)).fetchone()
            ship_num = db.spec_meta(pc["traveler_type"] if pc else None)["ship"]
            db.execute_write(conn,
                "UPDATE traveler_fields SET value=?, signed_by=?, timestamp=? "
                "WHERE piece_pk=? AND field_number=?",
                (f"{ts[:10]} / {r['truck']}", r["name"], ts, pk, ship_num))
            db.execute_write(conn,
                "UPDATE pieces SET status='SHIPPED' WHERE id=?", (pk,))
            db.execute_write(conn,
                "UPDATE release_records SET truck_load_ref=? WHERE piece_pk=?",
                (r["truck"], pk))
        pieces = conn.execute(
            "SELECT pc.*, rr.release_date FROM pieces pc "
            "LEFT JOIN release_records rr ON rr.piece_pk=pc.id "
            f"WHERE pc.id IN ({','.join('?'*len(ids))})", ids).fetchall()
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"{p['code']}_Manifest_{r['truck']}.pdf")
        if path:
            reports.manifest_pdf(path, p, r["truck"], pieces)
            W.info(self, f"Manifest saved: {os.path.basename(path)}")
        self.load_released()
        self.ctx.refresh_all()
