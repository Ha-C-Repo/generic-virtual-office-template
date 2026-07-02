# ShopQC Deployment - Remaining Steps for Joseph

Date: 2026-06-18
Status of the build: COMPLETE and running on the host PC (YOUR-COMPANY-USA-H).

The software is built, tested, merged, and live on the host. The first
project (ICD Church, job 2931) is created and visible. The steps below are
the ones that need elevated rights or physical access to the other shop PCs,
so they could not be done from the single non-elevated session.

## What is already done (no action needed)

- ShopQC.exe built: `ShopQC\dist\ShopQC.exe` (71.8 MB, PyInstaller onefile).
  Passed the 44/44 ship gate before packaging.
- Live database created: `C:\YourCoQC\yourco_qc.db` (8 tables, WAL OFF -
  journal_mode=DELETE, required for SMB/OneDrive safety).
- Host config: `ShopQC\dist\config.json` -> db_path `C:\YourCoQC\yourco_qc.db`,
  station GATE1, printer_mode file.
- NTFS permissions on `C:\YourCoQC` already set to Modify for Everyone.
- Nightly backup task registered: "YourCo QC Nightly DB Backup", daily 23:00,
  consistent SQLite .backup to `C:\Users\YourUser\OneDrive\YourCoQC_Backups`,
  keeps 21 snapshots. First snapshot verified.
- Code merged to main (commit 86bfc1f). Pre-merge tar in `_handoff\backups\`.

## Step 1 - Create the network share (elevated, on the host)

Open PowerShell as Administrator on YOUR-COMPANY-USA-H and run:

    New-SmbShare -Name YourCoQC -Path C:\YourCoQC -ChangeAccess Everyone

The folder NTFS permission is already Modify/Everyone, so only the share
itself is missing. The non-elevated session could not create it
(New-SmbShare returned Access is denied without the elevated token).

Verify:

    Get-SmbShare -Name YourCoQC

## Step 2 - Set up the other two shop PCs (per PC)

1. Copy `ShopQC.exe` to each PC (any local folder, e.g. `C:\ShopQC\`).
2. Map the host share as drive Z: (persistent):

       net use Z: \\YOUR-COMPANY-USA-H\YourCoQC /persistent:yes

3. Put a `config.json` next to the EXE on that PC with:

       {
         "db_path": "Z:\\yourco_qc.db",
         "printer_mode": "file",
         "station_name": "GATE2"
       }

   Use a distinct station_name per PC (GATE2, GATE3, etc.).

All three PCs then read and write the same database on the host.

## Step 3 - Hardware

- Zebra ZD421 label printer: install the Windows driver, then set
  `"printer_mode": "win32"` in config.json on the PC that drives it.
  Until the driver is in, leave printer_mode at "file" (labels write to disk).
- DS2208 / DS9308 scanners: plug in via USB. They are keyboard-wedge, no
  driver needed. Test by scanning into Notepad first.

## Notes

- Do NOT move the live DB into OneDrive. OneDrive sync corrupts a live SQLite
  file. OneDrive holds the nightly backups only (the Owner's locked 2026-06-10
  decision).
- If the host PC name differs from YOUR-COMPANY-USA-H, substitute it in Step 2.
- To rebuild the EXE after future code changes: run `ShopQC\build_exe.bat`
  from a checkout of main. It runs the 44/44 ship gate first and aborts if
  anything is red.
