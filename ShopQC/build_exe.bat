@echo off
REM YOUR COMPANY Shop QC - one-shot EXE build. Run from this folder.
REM psycopg2-binary is required so the frozen EXE can reach Supabase in
REM storage_mode=supabase; without it the app falls back to local SQLite.
py -m pip install --quiet pyinstaller qrcode pdfplumber reportlab pillow pywin32 pytest psycopg2-binary

REM Ship gate: the full pytest suite must pass before the EXE is built.
echo Running ship gate...
py tests\run_all.py
if errorlevel 1 (
  echo.
  echo SHIP GATE FAILED - build aborted. Fix the tests, then rebuild.
  pause
  exit /b 1
)

py -m PyInstaller --noconfirm --onefile --windowed --name ShopQC ^
  --add-data "data\aisc_sections.csv;data" ^
  --add-data "brand\logos\Your Company LLC.png;brand\logos" ^
  --add-data "brand\logos\your company.png;brand\logos" ^
  --hidden-import psycopg2 ^
  --hidden-import shopqc.selftest ^
  main.py
echo.
echo Done. EXE is at dist\ShopQC.exe
echo Copy dist\ShopQC.exe to each shop machine. config.json is created on first run.
pause
