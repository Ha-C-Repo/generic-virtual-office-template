# Shop QC Deployment - Joseph's One-Pager

The live database is now Supabase Postgres (the `shopqc` schema), not a shared
folder. Each shop PC keeps a local SQLite file that is only an offline cache and
write outbox: if the network drops, the floor keeps capturing scans locally and they
flush to Supabase on reconnect. The full connection and Supabase steps are in
`SUPABASE_SETUP.md`.

## 1. Build the EXE (once, on your machine)
1. Install Python 3.x from python.org if not present.
2. Open this folder (ShopQC) in a command prompt.
3. Run `build_exe.bat`. It installs what it needs and produces `dist\ShopQC.exe`.

## 2. The live database is Supabase (already provisioned)
The Supabase project `yourco-training` (Your Company org, us-east-1) holds the
`shopqc` schema, the limited app role `shopqc_app`, and row-level security. There is
no shared Windows folder and no OneDrive live file to set up any more. Backups are
Supabase's job (point-in-time recovery in the dashboard), not a nightly robocopy.
See `SUPABASE_SETUP.md` for the schema apply, the role, and password rotation.

## 3. Install on each machine
1. Copy `ShopQC.exe` anywhere (e.g. Desktop) on each PC.
2. Run it once. It creates `config.json` next to the EXE.
3. Edit `config.json` on each machine:
   - `storage_mode`: `supabase`
   - `supabase_db_host`: `aws-1-us-east-1.pooler.supabase.com`
   - `supabase_db_port`: `5432`
   - `supabase_db_name`, `supabase_db_user`, `supabase_db_password`: the
     `shopqc_app` values from the Supabase Connect dialog (session pooler / Session
     mode). SSL is on by default. See `SUPABASE_SETUP.md` for the exact values.
   - `station_name`: `GATE1`, `FAB`, or `GATE3`
   - `db_path`: leave the default; it is now just the local offline cache file.
   `config.json` is per machine and is never committed. Never paste the password
   into chat or email.
4. Restart the app. The status bar shows `Storage: supabase` when connected.

## 4. Zebra ZD421 printer
1. Install the ZDesigner driver (Zebra Setup Utilities), plug in USB.
2. Note the exact printer name in Windows (Settings > Printers).
3. In `config.json`: `printer_mode` = `win32`, `printer_name` = that exact name.
4. If raw printing misbehaves: share the printer as `ZEBRA`, set
   `printer_mode` = `share`, `printer_share` = `\\\\localhost\\ZEBRA`.
5. Test: receive one line on a test project and click Receive + Print Labels.

## 5. Scanner (DS2208 / DS9308)
Plug into USB. It types like a keyboard. No driver, no config. Make sure the
scanner adds an Enter suffix (factory default). Click into the Scan box first.

## 6. Daily use
- Gate 1 PC: Receiving tab. Gate 2 (fab floor): Fabrication tab.
  Gate 3 PC: Release tab. NCRs from anywhere. All stations read and write the same
  live Supabase data, so an NCR or status change at one station is seen at the
  others right away.
- If the network drops, the app keeps working from the local cache and queues every
  scan in the outbox; it flushes to Supabase automatically when the connection
  returns, last-write-wins, with an audit-log row per change. The floor never stops
  on a network blip.
- Keep the shop PCs on NTP (the Windows default time sync is fine). The reconnect
  merge uses the clock, so a badly wrong clock could pick the wrong winner.
