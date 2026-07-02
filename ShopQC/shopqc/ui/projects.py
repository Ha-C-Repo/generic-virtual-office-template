"""Screen 1: Projects."""

import os
import tkinter as tk
from tkinter import ttk, filedialog

from .. import db, reports
from . import widgets as W


class ProjectsScreen(tk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        W.header(self, "PROJECTS")
        top = tk.Frame(self, pady=6)
        top.pack(fill="x", padx=10)
        ttk.Button(top, text="New Project", command=self.new_project).pack(side="left")
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=6)
        ttk.Button(top, text="Project Summary PDF",
                   command=self.summary_pdf).pack(side="left")
        cols = [("code", "Code"), ("job", "Job No."), ("name", "Name"),
                ("gc", "GC"), ("tons", "Tons"), ("ias", "IAS"),
                ("recv", "Received"), ("fab", "In Fab"), ("rel", "Released"),
                ("ncr", "Open NCRs")]
        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=6)
        self.tree, vsb = W.make_tree(body, cols,
                                     [70, 90, 220, 140, 60, 50, 80, 70, 80, 90])
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        self.refresh()

    def refresh(self):
        conn = self.ctx.conn
        self.tree.delete(*self.tree.get_children())
        for p in conn.execute("SELECT * FROM projects ORDER BY id DESC"):
            c = {r["status"]: r["n"] for r in conn.execute(
                "SELECT status, COUNT(*) n FROM pieces WHERE project_id=? "
                "GROUP BY status", (p["id"],))}
            ncr = conn.execute(
                "SELECT COUNT(*) FROM ncrs WHERE project_id=? AND status!='CLOSED'",
                (p["id"],)).fetchone()[0]
            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p["code"], p["job_number"], p["name"], p["gc_name"] or "",
                p["tonnage"] or 0, "YES" if p["ias_required"] else "",
                c.get("RECEIVED", 0), c.get("IN_FAB", 0),
                c.get("RELEASED", 0) + c.get("SHIPPED", 0), ncr))

    def new_project(self):
        d = W.FormDialog(self, "New Project", [
            ("code", "Project code (e.g. ICD)", "entry", None),
            ("job_number", "Job number", "entry", None),
            ("name", "Project name", "entry", None),
            ("gc_name", "GC name", "entry", None),
            ("contract_number", "Contract number", "entry", None),
            ("tonnage", "Estimated tonnage", "entry", None),
            ("ias_required", "IAS inspection required", "check", None)])
        r = d.result
        if not r:
            return
        if not r["code"] or not r["job_number"] or not r["name"]:
            return W.err(self, "Code, job number and name are required.")
        try:
            tons = float(r["tonnage"] or 0)
        except ValueError:
            return W.err(self, "Tonnage must be a number.")
        try:
            db.execute_write(self.ctx.conn,
                "INSERT INTO projects (code, job_number, name, gc_name, "
                "contract_number, tonnage, ias_required, created_date) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (r["code"].upper(), r["job_number"], r["name"], r["gc_name"],
                 r["contract_number"], tons, r["ias_required"], db.now()))
        except Exception as e:
            return W.err(self, f"Could not create project: {e}")
        self.ctx.refresh_all()

    def _selected_project(self):
        sel = self.tree.selection()
        if not sel:
            W.err(self, "Select a project first.")
            return None
        return self.ctx.conn.execute("SELECT * FROM projects WHERE id=?",
                                     (int(sel[0]),)).fetchone()

    def summary_pdf(self):
        p = self._selected_project()
        if not p:
            return
        conn = self.ctx.conn
        counts = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) n FROM pieces WHERE project_id=? GROUP BY status",
            (p["id"],))}
        ncr = conn.execute(
            "SELECT COUNT(*) FROM ncrs WHERE project_id=? AND status!='CLOSED'",
            (p["id"],)).fetchone()[0]
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", initialfile=f"{p['code']}_QC_Summary.pdf")
        if path:
            reports.project_summary_pdf(path, p, counts, ncr)
            W.info(self, f"Saved {os.path.basename(path)}")
