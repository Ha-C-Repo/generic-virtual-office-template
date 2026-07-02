# Scheduled Tasks - Bid Estimating

Registration spec for the Cowork Dispatch panel. Three tasks. All run
against the active bid project folder defined in the Cowork
configuration.

Forward roadmap: the next-tier autonomous routines (email manager, CRM
updater, cost tracker, project context refresh, payment claim
generator, weekly progress reporter, weather log, meeting minutes) are
specced in `../../../claude-routines-construction.md` at the project
root. Anything added here should reconcile against that roadmap.

## Task 1: Weekly rate-band recompute

- ID: bid.rates.recompute.weekly
- Schedule: cron `0 6 * * 1` (Monday 6:00 America/Chicago)
- Action: Read closed-project estimate.json files in `data/closed_bids/`.
  For each item_class in `library/production-rates.yaml`, recompute
  p25, p75, floor, ceiling from observed unit_rates. Write back to
  `library/production-rates.yaml` with `last_updated_iso` updated.
- Output: append entry to `handoff_backups/journal.log`.
- Owner: Joseph Hasse.

## Task 2: Daily reconcile (active bid only)

- ID: bid.reconcile.daily
- Schedule: cron `30 7 * * 1-5` (Mon-Fri 7:30 America/Chicago)
- Action: Detect changes to `requirement-register.json` or
  `estimate.json` in the active bid folder. If changed since last run,
  invoke the reconciliation skill. Push the resulting
  `recon-report.json` and refresh the dashboard artifact.
- Output: Toast in Cowork. Critical count > 0 fires a notification.
- Owner: Owner or Joseph (whoever owns the active bid).

## Task 3: On-drop tender ingest

- ID: bid.tender.ingest.on_drop
- Trigger: filesystem watcher on `inbox/` subdirectory of the active
  bid folder.
- Action: When a new PDF or Word document lands, run the tender-ingest
  skill. Append results to `tender-index.json`. If `tender-index.json`
  is missing, create it.
- Output: Toast in Cowork. Auto-run requirement-register skill if any
  new `scope` or `head_contract` classified document arrived.
- Owner: System (no human approval required for ingest; estimator
  reviews after).

## Failure handling

All three tasks log to `handoff_backups/journal.log` on success and
to `data/diag_logs/scheduled-failures.log` on error. A task that
errors twice in a row is auto-disabled and surfaces a critical
notification in the STATUS tab.

## Reversal

To disable: open Dispatch panel, toggle each task off. Files in this
spec remain in place for restart.
