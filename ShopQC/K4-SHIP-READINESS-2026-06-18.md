# K4 Hard-Block Code Review and Ship-Readiness Note

**Date:** 2026-06-18
**Branch:** feature/joist-traveler (K1 joist variant + K2 logo + K3 test suite)
**Scope:** Final consolidated hard-block code review across K1+K2+K3. Hard-block
review only. The EXE build (`build_exe.bat`) is a Windows-host step and was NOT run
here; Cowork runs it via Windows MCP after this review.
**Verdict:** READY TO BUILD. All six hard blocks enforced. One hard-block defect was
found during this review (Gate 3 sign-time TOCTOU) and is fixed with a regression.
Two non-blocking coverage gaps and a few minor items are recorded as residual risk.

## 1. Test results

```
py tests\run_all.py   ->   SHIP GATE PASS: 43/43 tests passed
py tests\smoke_test.py ->  SMOKE TEST PASS + JOIST VARIANT PASS
```

43 pytest tests (was 42; one regression added for the fix in section 3). The legacy
end-to-end script still passes. No em-dashes; no supplier names in any output. The
structural 18-field `TRAVELER_FIELDS` sequence is byte-for-byte identical to its
pre-K1 backup.

## 2. The six hard blocks: where each is enforced now

Verified by reading the code and by an independent red-team that tried to defeat each
block through the UI, the scan path, and a late-edit race. Direct hand-editing of the
`.db` file is out of scope (the app exposes no raw-SQL console).

**1. Pre-weld CWI (field 8) cannot be signed without a CWI name. ENFORCED.**
Field 8 is kind `cwi` in BOTH specs (`db.py` TRAVELER_FIELDS / JOIST_TRAVELER_FIELDS),
so `FabricationScreen.sign_active` dispatch (`fabrication.py:128-133`) routes it only
to `_sign_cwi`, which blocks on `db.cwi_signature_ok` (`fabrication.py:305-308`) before
`_save_field` (`fabrication.py:321`). `db.cwi_signature_ok` (`db.py:400-403`) rejects
empty, whitespace, and None; `FormDialog` strips entries (`widgets.py:126`). The lock
sequence keeps field 9 (weld) unreachable until 8 is signed (`db.lowest_unsigned_floor`,
`db.py:388-397`). No app path writes `traveler_fields.signed_by` for field 8 except
`_save_field` from `_sign_cwi`. No bypass found.

**2. Locked sequence: only the lowest unsigned floor step is signable. ENFORCED.**
`sign_active` computes the active field from FRESH rows via
`_active_field -> db.lowest_unsigned_floor` (`fabrication.py:74-76`, `db.py:388-397`)
and signs exactly that number; every handler calls `self._save_field(num, ...)` with
the passed `num` (no handler writes an arbitrary field). Correct for structural (floor
5..14) and joist (5..16) from `db.spec_meta`. No skip or out-of-order path found.

**3. Open NCR freezes the traveler until closed. ENFORCED (traveler freeze).**
`sign_active` returns early when `db.open_ncr_count > 0` (`fabrication.py:119-121`);
`open_ncr_count` counts `status!='CLOSED'` (`db.py:382-385`), so OPEN and IN
DISPOSITION both freeze. Tkinter is single-threaded, so there is no check-then-write
race inside one station. Closing the last NCR reverts NCR_HOLD to IN_FAB
(`ncr.py:153-157`). Gate 3 also blocks on open NCRs (block 4). No bypass of the
traveler freeze. See residual risk R1 for shipping (not one of the six blocks).

**4. Gate 3: all completeness fields signed plus zero open NCRs, re-verified at sign
time. ENFORCED after the fix in section 3.**
`load_piece` disables the button on any blocker (`release.py:72-93`). `release()`
re-verifies via `db.release_blockers` (`db.py:406-417` = unsigned fields through
`gate3_last` plus open NCRs) both before the sign-off dialog and, after the fix, again
immediately before the commit (`release.py:107` and the new check before
`release.py` writes). The completeness window is variant-correct (`gate3_last` 14
structural, 16 joist). No app feature can null a `signed_by`, so a field cannot be
unsigned after load; a late NCR is now caught by the second re-verify.

**5. CEO co-sign (exact name) for projects >= 50 tons or IAS. ENFORCED.**
`db.needs_ceo_cosign` (`db.py:122-130`) returns `tons >= 50 or bool(ias_required)`:
exactly 50 is True, IAS at 0 tons is True, and bad or None tonnage falls to 0 (can
only weaken the tonnage arm, never the IAS arm). `db.ceo_name_matches` (`db.py:133-136`)
requires the exact CEO name, case and surrounding whitespace tolerant only.
`release.py:87` sets the flag from the project; `release.py:121-125` returns an error
before any write when the name does not match. No bypass found.

**6. Unauthorized-field-modification NCR cannot close without an EOR reference.
ENFORCED.**
`NCRScreen.disposition` calls `db.ncr_close_blocked_reason` in the closing branch and
returns the block before any write (`ncr.py:138-144`). The predicate (`db.py:154-163`)
blocks when the category is the EOR category and the reference is empty or whitespace.
`disposition()` is the ONLY code in the app that sets `ncrs.status='CLOSED'` (verified
by grep: the other ncrs writers are INSERTs that create OPEN records in
`fabrication.py`, `ncr.py`, and `receiving.py`). The dialog strips the EOR entry, and
the predicate also strips, so a whitespace-only reference is blocked. No bypass found.

## 3. Hard-block defect found and fixed (HB4 sign-time TOCTOU)

**Found:** `release()` re-verified `db.release_blockers` only at `release.py:107`,
which runs BEFORE the modal Final Release sign-off dialog. The dialog is open-ended;
on a multi-station shared database (the deployment the code comment cites), another
station can open an NCR on the piece while the dialog is open. When the operator then
completes the dialog, the original code committed `status='RELEASED'` with no second
check, releasing a piece that now had an open NCR. That defeats the "re-verified at
sign time" requirement of hard block 4, because the true sign time is the commit, not
the moment the dialog opens.

**Fix:** added a second `db.release_blockers` re-verify immediately before the commit
(after the sign-off dialog returns and the CEO check passes) in
`shopqc/ui/release.py`. If a blocker appeared during the dialog, the release aborts
and the screen reloads. Behavior is otherwise unchanged; a clean piece still releases
in one pass.

**Regression:** `tests/test_gates.py::test_release_reverify_runs_after_signoff_dialog`
models the sequence (clean at the first check, NCR opened during sign-off, blocked at
the second check). Note: this locks the data-layer predicate the fix depends on; the
control-flow placement (re-check after the modal) is verified by code review, since
the headless suite does not drive the Tkinter modal. Full modal-timing testing would
need a dialog-mock harness, recorded as a deferred test-infra item.

## 4. Multi-station concurrency review

Confirmed safe for the shared-folder, multi-station deployment:

- `db.connect` (`db.py:282-289`) sets `journal_mode=DELETE` (never WAL),
  `busy_timeout=15000`, `foreign_keys=ON`, `synchronous=FULL`, and a 15 s connect
  timeout. DELETE mode is the correct choice on an SMB or OneDrive share, where WAL
  corrupts because it needs shared memory on a single host (CLAUDE.md Hard Rule 11).
  No WAL anywhere in the shop app.
- `db.execute_write` (`db.py:332-346`) retries up to 5 times on a "locked" or "busy"
  OperationalError with increasing backoff (0.5 s to 2.5 s), on top of the 15 s
  busy_timeout. Two stations writing the same piece serialize on the SQLite file
  lock; the second waits, then retries.
- Last-writer-wins on a given field, but every gate re-reads live state before acting:
  `sign_active` recomputes the active field from fresh rows, and `release()` now
  re-verifies twice. So a stale UI cannot drive a piece past a gate. Example: if two
  stations both try to sign field 8, the second recomputes the active field, sees 8
  already signed, and advances to 9 rather than double-signing.

## 5. Residual risks and recommendations (not hard-block defects; not changed in K4)

K4 is scoped to the six hard blocks, so the items below are recorded for Owner and
Joseph to decide, not changed here.

- **R1 (recommend a fix before heavy production use): a piece can ship with an NCR
  opened AFTER release.** `ship_load` (`release.py:172-211`) does not check open NCRs,
  and `ncr.new_ncr` leaves a RELEASED piece RELEASED (`ncr.py:106-108`), so a
  nonconforming piece flagged after release can still be put on a truck. This is NOT
  one of the six named hard blocks (there is no ship-on-NCR block; the release gate
  correctly enforced zero NCRs at release), but it is a genuine coverage gap for a
  QC tool. Recommended: add an `open_ncr_count` check to `ship_load` and refuse to
  ship a piece with an open NCR.
- **R2: `fabrication.open_ncr` has no status guard.** It sets `status='NCR_HOLD'`
  unconditionally (`fabrication.py:369-370`), unlike `ncr.new_ncr` which skips
  RELEASED/SHIPPED. Opening an NCR via the Fabrication tab on a released or shipped
  piece would demote its status. Recommend aligning the two paths.
- **R3: NCR auto-number labeling race.** `fabrication.open_ncr` reads
  `SELECT MAX(id) FROM ncrs` after the insert to label the traveler field; under
  concurrent NCR creation this could read another station's id. The NCR record itself
  is correct (autoincrement). Recommend using the insert cursor's `lastrowid`.
- **R4: camber out-of-tolerance is advisory.** The joist camber step warns and guides
  to an NCR but does not itself block or auto-open one. This is by design (verify, do
  not generate) and was approved with the 0.25 in provisional tolerance. Auto-opening
  an NCR is a possible future hardening.
- **R5: provisional joist field set and camber tolerance.** Approved by Owner
  2026-06-18; flagged in `JOIST-TRAVELER-MIGRATION-2026-06-18.md` for word-for-word
  confirmation if the NC-QC-FAB-001 program PDF is later provided.
- **R6: EXE not yet built or signed.** This review did not run `build_exe.bat`. The
  bundled logo PNGs resolve in dev via `resource_path`; confirming they resolve in the
  frozen EXE is part of the build step (next section).

## 6. Build command (run on the Windows host; do NOT run from this review)

From the `ShopQC` folder:

```
build_exe.bat
```

It installs the dev dependencies (including pytest and pillow), runs the ship gate
first (`py tests\run_all.py`) and ABORTS the build if any test fails, then runs
PyInstaller to produce `dist\ShopQC.exe` with the AISC CSV and both logo PNGs bundled.
After it completes, smoke-check the EXE: launch it, confirm `config.json` is created
on first run, print one traveler and one Final Release Certificate, and confirm the
silver logo renders on the dark header band.

## 7. Bottom line

The six hard blocks are enforced and were red-teamed; the one defect found (the Gate 3
sign-time TOCTOU) is fixed and regression-tested. The suite is green at 43/43 plus the
smoke script. The branch is ready for the Windows EXE build. After the build smoke
check passes, the branch may merge per the Owner's approval. R1 (ship-on-NCR) is the one
item worth deciding on before relying on the app to physically gate nonconforming
steel, but it is outside the six hard blocks and the release gate already enforces
zero NCRs at release.
