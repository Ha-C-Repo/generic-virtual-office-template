"""Shared Tkinter helpers."""

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

RED = "#C8102E"
DARK = "#141414"


def header(parent, text):
    f = tk.Frame(parent, bg=DARK)
    f.pack(fill="x")
    tk.Label(f, text=text, bg=DARK, fg="white",
             font=("Helvetica", 13, "bold"), pady=8, padx=10).pack(side="left")
    tk.Frame(parent, bg=RED, height=3).pack(fill="x")
    return f


def ask_name(parent, title, prompt):
    v = simpledialog.askstring(title, prompt, parent=parent)
    return v.strip() if v else None


def err(parent, msg):
    messagebox.showerror("Shop QC", msg, parent=parent)


def info(parent, msg):
    messagebox.showinfo("Shop QC", msg, parent=parent)


def confirm(parent, msg):
    return messagebox.askyesno("Shop QC", msg, parent=parent)


class ScanEntry(tk.Frame):
    """Scanner wedge input. Zebra DS-series types the payload then Enter.
    Payload may be 'PIECEID|PROJECT|HEAT|DATE' or a bare piece ID."""

    def __init__(self, parent, on_scan, label="Scan piece QR:"):
        super().__init__(parent)
        self.on_scan = on_scan
        tk.Label(self, text=label, font=("Helvetica", 11, "bold")).pack(side="left")
        self.entry = tk.Entry(self, width=44, font=("Consolas", 12))
        self.entry.pack(side="left", padx=8)
        self.entry.bind("<Return>", self._fire)
        ttk.Button(self, text="Look up", command=self._fire).pack(side="left")

    def _fire(self, _evt=None):
        v = self.entry.get().strip()
        if v:
            self.entry.delete(0, "end")
            self.on_scan(v)

    def focus_scan(self):
        self.entry.focus_set()


def make_tree(parent, columns, widths, height=12):
    tree = ttk.Treeview(parent, columns=[c[0] for c in columns],
                        show="headings", height=height)
    for (key, label), w in zip(columns, widths):
        tree.heading(key, text=label)
        tree.column(key, width=w, anchor="w")
    vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    return tree, vsb


class FormDialog(tk.Toplevel):
    """Generic modal form. fields: list of (key, label, kind, options)
    kind: entry | combo | check | text | note. A 'note' is read-only wrapped
    helper text (its label is the text); it stores nothing and is not returned.
    Result in self.result dict or None."""

    def __init__(self, parent, title, fields, initial=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result = None
        self.vars = {}
        initial = initial or {}
        body = tk.Frame(self, padx=12, pady=10)
        body.pack(fill="both", expand=True)
        for i, (key, label, kind, options) in enumerate(fields):
            if kind == "note":
                tk.Label(body, text=label, anchor="w", wraplength=380,
                         justify="left", fg="#555555",
                         font=("Helvetica", 8, "italic")).grid(
                    row=i, column=0, columnspan=2, sticky="w", pady=3)
                continue
            tk.Label(body, text=label, anchor="w").grid(row=i, column=0,
                                                        sticky="w", pady=3)
            init = initial.get(key, "")
            if kind == "check":
                v = tk.IntVar(value=int(init or 0))
                tk.Checkbutton(body, variable=v).grid(row=i, column=1, sticky="w")
            elif kind == "combo":
                v = tk.StringVar(value=init)
                ttk.Combobox(body, textvariable=v, values=options,
                             state="readonly", width=30).grid(row=i, column=1)
            elif kind == "text":
                v = tk.Text(body, width=40, height=4)
                v.insert("1.0", init)
                v.grid(row=i, column=1, pady=3)
            else:
                v = tk.StringVar(value=str(init))
                tk.Entry(body, textvariable=v, width=33).grid(row=i, column=1, pady=3)
            self.vars[key] = (kind, v)
        btns = tk.Frame(self, pady=8)
        btns.pack()
        ttk.Button(btns, text="OK", command=self._ok).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left")
        self.grab_set()
        self.transient(parent)
        self.wait_window()

    def _ok(self):
        out = {}
        for key, (kind, v) in self.vars.items():
            if kind == "text":
                out[key] = v.get("1.0", "end").strip()
            elif kind == "check":
                out[key] = v.get()
            else:
                out[key] = v.get().strip()
        self.result = out
        self.destroy()
