"""YOUR COMPANY Shop QC entry point."""

import sys

from shopqc.ui.app import run


def _check_db() -> int:
    # ShopQC.exe --check-db: confirm config.json reaches Supabase. The app is built
    # windowed (no console), so show the result in a dialog; fall back to print.
    from shopqc.selftest import summary
    ok, text = summary()
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        show = messagebox.showinfo if ok else messagebox.showwarning
        show("Shop QC - database check", text)
        root.destroy()
    except Exception:
        print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    if "--check-db" in sys.argv:
        sys.exit(_check_db())
    run()
