"""Application shell: five tabs, shared context, status bar."""

import tkinter as tk
from tkinter import ttk, messagebox

from .. import VERSION, APP_NAME, config, storage
from .projects import ProjectsScreen
from .receiving import ReceivingScreen
from .fabrication import FabricationScreen
from .release import ReleaseScreen
from .ncr import NCRScreen


class AppContext:
    def __init__(self, conn, cfg, backend=None):
        self.conn = conn
        self.cfg = cfg
        self.backend = backend
        self._screens = []

    def refresh_all(self):
        for s in self._screens:
            if hasattr(s, "refresh"):
                try:
                    s.refresh()
                except Exception:
                    pass


def run():
    cfg = config.load()
    backend = storage.make_backend(cfg)
    try:
        conn = backend.open()
    except storage.StorageError as e:
        messagebox.showerror(APP_NAME, str(e))
        return
    backend.start_background_sync()

    root = tk.Tk()
    root.title(f"{APP_NAME} v{VERSION} - NC-QC-FAB-001 Rev 0")
    root.geometry("1180x780")
    ctx = AppContext(conn, cfg, backend)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)
    screens = [("Projects", ProjectsScreen), ("Receiving (Gate 1)", ReceivingScreen),
               ("Fabrication (Gate 2)", FabricationScreen),
               ("Release (Gate 3)", ReleaseScreen), ("NCR Log", NCRScreen)]
    frames = []
    for label, cls in screens:
        f = cls(nb, ctx)
        nb.add(f, text=label)
        frames.append(f)
    ctx._screens = frames

    def on_tab(_evt):
        f = frames[nb.index(nb.select())]
        if hasattr(f, "on_show"):
            f.on_show()
    nb.bind("<<NotebookTabChanged>>", on_tab)

    st = backend.status()
    bar = tk.Label(root, anchor="w", bg="#141414", fg="#cccccc",
                   text=f"  DB: {cfg['db_path']}   |   Storage: {st['mode']}"
                        f"   |   Station: {cfg.get('station_name')}"
                        f"   |   Printer mode: {cfg.get('printer_mode')}")
    bar.pack(fill="x", side="bottom")
    root.mainloop()
    backend.stop_background_sync()
    backend.close()
