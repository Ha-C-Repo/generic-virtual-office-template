import sqlite3, os, datetime, glob
SRC = r"C:\YourCoQC\yourco_qc.db"
DST_DIR = r"C:\Users\YourUser\OneDrive\YourCoQC_Backups"
if not os.path.isfile(SRC):
    raise SystemExit("backup skipped: live DB not found")
os.makedirs(DST_DIR, exist_ok=True)
stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
dst = os.path.join(DST_DIR, f"yourco_qc_{stamp}.db")
s = sqlite3.connect(SRC); d = sqlite3.connect(dst); s.backup(d); d.close(); s.close()
snaps = sorted(glob.glob(os.path.join(DST_DIR, "yourco_qc_*.db")))
for old in snaps[:-21]:
    try: os.remove(old)
    except OSError: pass
print("backup ok ->", dst)
