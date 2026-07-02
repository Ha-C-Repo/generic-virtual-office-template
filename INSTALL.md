# Installation — Your Company Virtual Office

## ALWAYS install to a FRESH folder

Do NOT unzip over an existing install. The zip contains database files
that carry state. Overwriting them merges old session data with the new
build, which causes fixture data, stale bids, and old compliance entries
to appear in the morning brief.

**Correct procedure:**

1. Create a new folder: `C:\Tools\virtualoffice-v3277\`
2. Unzip the new build into that folder
3. Confirm there is NO "Replace or Skip" dialog — if you see one, stop
   and pick a different destination folder
4. Copy your `data/API Keys/` folder from the old install to the new one
5. Launch `main.py` (or the EXE once built)

**Why you see the "Replace or Skip" dialog:**

Windows shows this when the destination already has files from a prior
session. The `output/` folder is the most common trigger — it holds
generated STLs, PDFs, and change orders from previous runs. These are
build artifacts. They do not belong in the install zip and will not
appear in builds v3.2.7.7 and later.

## What carries over between installs (manual copy)

These files hold YOUR data and should be copied from the old install:

| Path | What it contains |
|---|---|
| `data/API Keys/` | FRED, Gemini, OpenAI, SAM.gov API keys |
| `data/blockers.json` | Live blocker state (EMR, ISN, etc.) |
| `data/bid_pipeline.db` | Active bids |
| `data/engagement_records/` | Contact engagement history |
| `data/notifications_config.json` | SMS toggle settings |

Everything else rebuilds itself on first boot.

## Folder that ships EMPTY (by design)

`output/` — generated STLs, bid PDFs, change orders write here at runtime.
The folder ships with only a `.gitkeep` marker. Do not ship this folder's
contents to clients.
