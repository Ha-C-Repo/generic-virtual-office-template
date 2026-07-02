#!/usr/bin/env python3
"""Atomic, watcher-safe overwrite of a protected file.

Background
----------
Cowork's project-instructions watcher monitors files named CLAUDE.md in the
project folder. Failure history:

1. 2026-05-24, REAL WATCHER RACE: the watcher races chunked Edit/Write tool
   writes and silently truncates the file to ~4 KB. Evidence:
   _handoff/diag/test_A_cowork_project.txt and NOT_CLAUDE_control.md. The
   atomic os.replace here closes that window; the settle-and-reverify pass
   below is the defense in depth for any future watcher interference.
2. 2026-06-12, ROOT CAUSE CORRECTED 2026-06-12 residuals session: the
   "CRLF-doubling" (CRLF in, CR CR LF on disk, +1 byte per line) attributed
   to the watcher was this script's own write step. os.open without
   os.O_BINARY opens in CRT text mode on Windows, so os.write translated
   every LF to CRLF. Proven by controlled A/B with O_BINARY; the watcher
   was not involved. Evidence appended to
   _handoff/diag/watcher-crlf-doubling-2026-06-12.md. Fixed in
   atomic_write below.

What this script does
---------------------
Take new content, back up the existing file, write atomically via a same-dir
temp file plus os.replace, then poll until the file is stable (two identical
reads 250 ms apart, 5 s timeout) and verify content-equal under newline
normalization: the watcher's line-ending re-emit of the intended content is a
PASS, any other divergence is a FAIL. On FAIL: restore the backup and retry,
up to 3 attempts, then fail loud. The target is never left half-written.

Note on the normalization: strict universal-newlines would read the watcher's
CR CR LF as two line breaks and reject it, so equality here strips CR bytes
before comparing. Only line-ending form is forgiven; every other byte must
match exactly.

Writes are byte-faithful (O_BINARY): the bytes you feed are the bytes that
land, regardless of line-ending style.

Usage
-----
    python safe_write.py TARGET --from SOURCE_PATH
    cat NEW.md | python safe_write.py TARGET --stdin
    python safe_write.py TARGET --content "string content"

Backups land in <project>/_handoff/backups/<UTC-ISO-timestamp>/ next to the
patch-era backups. Pass --no-backup to skip (not recommended).
"""
import argparse
import datetime
import os
import shutil
import sys
import time
from pathlib import Path

ATTEMPTS = 3
SETTLE_TIMEOUT = 5.0
SETTLE_INTERVAL = 0.25


def project_root_from(target: Path) -> Path:
    """Walk up from target looking for _handoff/ or the project root marker."""
    p = target.resolve().parent
    for _ in range(8):
        if (p / "_handoff").is_dir() or (p / "CLAUDE.md").is_file():
            return p
        if p.parent == p:
            break
        p = p.parent
    return target.resolve().parent


def normalize_newlines(data: bytes) -> bytes:
    """Newline-normalized form for watcher-tolerant comparison.

    Strips CR bytes so LF, CRLF, and the watcher's CR CR LF emit of the same
    text all compare equal. Strict universal-newlines would read CR CR LF as
    two line breaks and reject the watcher's re-emit; CR-stripping forgives
    line-ending form only. All non-CR bytes must match exactly.
    """
    return data.replace(b"\r", b"")


def settle_read(target: Path, timeout: float = SETTLE_TIMEOUT,
                interval: float = SETTLE_INTERVAL) -> tuple:
    """Poll target until two consecutive reads `interval` apart are identical.

    Returns (content_bytes, settled_bool). On timeout the last read is
    returned with settled=False; callers treat that as a verify failure.
    """
    deadline = time.monotonic() + timeout
    previous = target.read_bytes()
    while True:
        time.sleep(interval)
        current = target.read_bytes()
        if current == previous:
            return current, True
        previous = current
        if time.monotonic() >= deadline:
            return current, False


def atomic_write(target: Path, new_bytes: bytes) -> None:
    """Write new_bytes to target via same-dir temp + fsync + os.replace."""
    tmp = target.with_suffix(target.suffix + ".tmp.safewrite")
    try:
        # O_BINARY is load-bearing on Windows: without it the CRT opens in
        # text mode and os.write translates LF to CRLF, which is what
        # produced the 2026-06-12 "CRLF-doubling" (CRLF in, CR CR LF out).
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
        fd = os.open(str(tmp), flags, 0o644)
        try:
            written = os.write(fd, new_bytes)
            if written != len(new_bytes):
                raise IOError(f"short write: {written} of {len(new_bytes)} bytes")
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, target)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def perform_safe_write(target: Path, new_bytes: bytes, no_backup: bool = False,
                       attempts: int = ATTEMPTS,
                       settle_timeout: float = SETTLE_TIMEOUT,
                       settle_interval: float = SETTLE_INTERVAL,
                       log=print) -> dict:
    """Write-settle-verify loop with backup, restore on FAIL, 3-strike fail loud.

    Returns a dict: ok (bool), status ('exact' | 'normalized' | 'failed' |
    'write_error'), message (str), backup_path (Path or None), attempts (int).
    The target is never left half-written: every failed attempt restores the
    backup (or removes a target that did not exist before).
    """
    target = Path(target)
    existed_before = target.exists()

    backup_path = None
    if existed_before and not no_backup:
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        root = project_root_from(target)
        backup_dir = root / "_handoff" / "backups" / ts
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / (target.name + ".pre-safe-write")
        shutil.copy2(target, backup_path)
        log(f"BACKUP {backup_path}")

    def _restore():
        if backup_path is not None:
            shutil.copy2(backup_path, target)
        elif existed_before:
            pass  # no backup requested for an existing file; leave as-is
        elif target.exists():
            target.unlink()  # target did not exist before; never leave a half-written file

    last_divergence = ""
    for attempt in range(1, attempts + 1):
        try:
            atomic_write(target, new_bytes)
        except Exception as e:
            _restore()
            msg = f"FAIL   write step (attempt {attempt}/{attempts}): {e}"
            log(msg)
            return {"ok": False, "status": "write_error", "message": msg,
                    "backup_path": backup_path, "attempts": attempt}

        on_disk, settled = settle_read(target, settle_timeout, settle_interval)

        if settled and on_disk == new_bytes:
            msg = f"OK     {target} ({len(new_bytes)} bytes, byte-exact)"
            log(msg)
            return {"ok": True, "status": "exact", "message": msg,
                    "backup_path": backup_path, "attempts": attempt}

        if settled and normalize_newlines(on_disk) == normalize_newlines(new_bytes):
            msg = (f"OK     {target} ({len(on_disk)} bytes on disk; watcher "
                   f"line-ending re-emit of the intended content, accepted)")
            log(msg)
            return {"ok": True, "status": "normalized", "message": msg,
                    "backup_path": backup_path, "attempts": attempt}

        last_divergence = ("file never settled within timeout" if not settled
                           else f"content diverges beyond line endings "
                                f"({len(on_disk)} bytes on disk vs {len(new_bytes)} intended)")
        log(f"RETRY  attempt {attempt}/{attempts} failed verify: {last_divergence}")
        _restore()

    if backup_path is not None:
        restore_note = f"Target restored from {backup_path}."
    elif existed_before:
        restore_note = ("No backup was taken (--no-backup); the target holds "
                        "the last interfered state. Restore it manually.")
    else:
        restore_note = "Target removed (it did not exist before this write)."
    msg = (f"VERIFY FAILED after {attempts} attempts: {last_divergence}. "
           f"The Cowork CLAUDE.md watcher race is the known cause of "
           f"interference on this filename (see _handoff/diag/"
           f"watcher-crlf-doubling-2026-06-12.md). {restore_note}")
    log(msg)
    return {"ok": False, "status": "failed", "message": msg,
            "backup_path": backup_path, "attempts": attempts}


def main():
    ap = argparse.ArgumentParser(description="Atomic overwrite that survives Cowork's CLAUDE.md watcher race.")
    ap.add_argument("target", help="path to the file to (over)write")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from", dest="src_path", help="read new content from this file")
    src.add_argument("--stdin", action="store_true", help="read new content from stdin")
    src.add_argument("--content", help="literal string content")
    ap.add_argument("--no-backup", action="store_true", help="skip the backup step (not recommended)")
    args = ap.parse_args()

    target = Path(args.target).resolve()

    if args.src_path:
        new_bytes = Path(args.src_path).read_bytes()
    elif args.stdin:
        new_bytes = sys.stdin.buffer.read()
    else:
        new_bytes = args.content.encode("utf-8")

    result = perform_safe_write(target, new_bytes, no_backup=args.no_backup)
    if result["ok"]:
        sys.exit(0)
    sys.exit(2 if result["status"] == "write_error" else 1)


if __name__ == "__main__":
    main()
