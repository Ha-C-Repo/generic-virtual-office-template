"""Screen 5: NCR Log."""

import datetime
import os
import tkinter as tk
from tkinter import ttk, filedialog

from .. import db, reports
from . import widgets as W

# Single source of truth for hard block 6 lives in db; alias kept for the label.
EOR_CATEGORY = db.EOR_CATEGORY
STALE_DAYS = 30


class NCRScreen(tk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        W.header(self, "NCR LOG")
        top = tk.Frame(self, pady=6)
        top.pack(fill="x", padx=10)
        tk.Label(top, text="Project:").pack(side="left")
        self.proj_var = tk.StringVar(value="ALL")
        self.proj_combo = ttk.Combobox(top, textvariable=self.proj_var,
                                       state="readonly", width=28)
        self.proj_combo.pack(side="left", padx=4)
        tk.Label(top, text="Status:").pack(side="left", padx=(10, 0))
        self.status_var = tk.StringVar(value="ALL")
        ttk.Combobox(top, textvariable=self.status_var, state="readonly", width=16,
                     values=["ALL"] + list(db.NCR_STATUSES)).pack(side="left", padx=4)
        ttk.Button(top, text="Apply", command=self.refresh).pack(side="left", padx=6)
        ttk.Button(top, text="New NCR", command=self.new_ncr).pack(side="left", padx=6)
        ttk.Button(top, text="Disposition / Close",
                   command=self.disposition).pack(side="left", padx=6)
        ttk.Button(top, text="Export PDF", command=self.export_pdf).pack(side="left")

        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=6)
        cols = [("id", "NCR"), ("piece", "Piece"), ("gate", "Gate"),
                ("cat", "Category"), ("desc", "Description"), ("opened", "Opened"),
                ("status", "Status"), ("disp", "Disposition")]
        self.tree, vsb = W.make_tree(body, cols,
                                     [50, 150, 45, 170, 280, 90, 100, 100], height=16)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        # CEO review flag: open > 30 days with no disposition = red
        self.tree.tag_configure("stale", background="#ffcdd2")
        self.refresh()

    def refresh(self):
        conn = self.ctx.conn
        rows = conn.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
        self._projects = {f"{r['code']} - {r['name']}": r for r in rows}
        self.proj_combo["values"] = ["ALL"] + list(self._projects)
        sql = ("SELECT n.*, pc.piece_id FROM ncrs n "
               "LEFT JOIN pieces pc ON pc.id = n.piece_pk WHERE 1=1")
        params = []
        p = self._projects.get(self.proj_var.get())
        if p:
            sql += " AND n.project_id=?"
            params.append(p["id"])
        if self.status_var.get() != "ALL":
            sql += " AND n.status=?"
            params.append(self.status_var.get())
        sql += " ORDER BY n.id DESC"
        self.tree.delete(*self.tree.get_children())
        cutoff = (datetime.date.today()
                  - datetime.timedelta(days=STALE_DAYS)).isoformat()
        for r in conn.execute(sql, params):
            stale = (r["status"] != "CLOSED" and not r["disposition"]
                     and (r["opened_date"] or "")[:10] <= cutoff)
            self.tree.insert("", "end", iid=str(r["id"]),
                             tags=("stale",) if stale else (), values=(
                f"NCR-{r['id']}", r["piece_id"] or "(lot)", r["gate"],
                r["category"], (r["description"] or "")[:60],
                (r["opened_date"] or "")[:10], r["status"], r["disposition"] or ""))

    def new_ncr(self):
        d = W.FormDialog(self, "New NCR", [
            ("project", "Project", "combo", list(self._projects)),
            ("piece", "Piece ID (optional)", "entry", None),
            ("gate", "Gate detected", "combo", ["1", "2", "3"]),
            ("category", "Category", "combo", list(db.NCR_CATEGORIES)),
            ("description", "Description", "text", None),
            ("name", "Opened by", "entry", None)])
        r = d.result
        if not r:
            return
        p = self._projects.get(r.get("project"))
        if not p or not r["category"] or not r["description"] or not r["name"] or not r["gate"]:
            return W.err(self, "Project, gate, category, description and name "
                               "are all required.")
        piece_pk = None
        if r["piece"]:
            pr = db.piece_by_scan(self.ctx.conn, r["piece"])
            if not pr:
                return W.err(self, f"Piece '{r['piece']}' not found.")
            piece_pk = pr["id"]
        db.execute_write(self.ctx.conn,
            "INSERT INTO ncrs (project_id, piece_pk, gate, category, description, "
            "opened_by, opened_date) VALUES (?,?,?,?,?,?,?)",
            (p["id"], piece_pk, int(r["gate"]), r["category"], r["description"],
             r["name"], db.now()))
        if piece_pk:
            db.execute_write(self.ctx.conn,
                "UPDATE pieces SET status='NCR_HOLD' WHERE id=? "
                "AND status NOT IN ('RELEASED','SHIPPED')", (piece_pk,))
        self.refresh()
        self.ctx.refresh_all()

    def disposition(self):
        sel = self.tree.selection()
        if not sel:
            return W.err(self, "Select an NCR.")
        conn = self.ctx.conn
        n = conn.execute("SELECT * FROM ncrs WHERE id=?", (int(sel[0]),)).fetchone()
        if n["status"] == "CLOSED":
            return W.info(self, "This NCR is already closed.")
        needs_eor = n["category"] == EOR_CATEGORY
        fields = [
            ("disposition", "Disposition", "combo", list(db.NCR_DISPOSITIONS)),
            ("authority", "Disposition authority", "entry", None),
            ("eor", "EOR sealed analysis reference"
                    + (" - REQUIRED for this category" if needs_eor else " (if any)"),
             "entry", None),
            ("close", "Close this NCR now", "check", None),
            ("name", "Closed by / updated by", "entry", None)]
        d = W.FormDialog(self, f"NCR-{n['id']} disposition", fields,
                         initial={"disposition": n["disposition"] or "",
                                  "authority": n["disposition_authority"] or "",
                                  "eor": n["eor_reference"] or ""})
        r = d.result
        if not r or not r["name"]:
            return
        if not r["disposition"] or not r["authority"]:
            return W.err(self, "Disposition and authority are required.")
        closing = bool(r["close"])
        if closing:
            # Hard block 6, enforced from the one place db.ncr_close_blocked_reason
            # so the UI and the tests check identical logic (NC-QC-FAB-001 Sec 9).
            blocked = db.ncr_close_blocked_reason(n["category"], r["eor"])
            if blocked:
                return W.err(self, blocked)
        status = "CLOSED" if closing else "IN DISPOSITION"
        db.execute_write(conn,
            "UPDATE ncrs SET disposition=?, disposition_authority=?, "
            "eor_reference=?, status=?, closed_by=?, closed_date=? WHERE id=?",
            (r["disposition"], r["authority"], r["eor"].strip() or None, status,
             r["name"] if closing else None, db.now() if closing else None,
             n["id"]))
        # closing the last open NCR releases the hold
        if closing and n["piece_pk"]:
            if db.open_ncr_count(conn, n["piece_pk"]) == 0:
                db.execute_write(conn,
                    "UPDATE pieces SET status='IN_FAB' WHERE id=? "
                    "AND status='NCR_HOLD'", (n["piece_pk"],))
        self.refresh()
        self.ctx.refresh_all()

    def export_pdf(self):
        conn = self.ctx.conn
        rows = conn.execute(
            "SELECT n.*, pc.piece_id FROM ncrs n "
            "LEFT JOIN pieces pc ON pc.id=n.piece_pk ORDER BY n.id").fetchall()
        if not rows:
            return W.info(self, "No NCRs to export.")
        path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                            initialfile="NCR_Log.pdf")
        if path:
            reports.ncr_pdf(path, rows)
            W.info(self, f"Saved {os.path.basename(path)}")
