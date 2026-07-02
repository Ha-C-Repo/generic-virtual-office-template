"""Tests for the safe_write settle-and-reverify upgrade (2026-06-12 sign-off).

Simulates a CRLF-doubling re-emit (CRLF becomes CR CR LF, +1 byte per line)
as the external-interference model. Historical note: the 2026-06-12 doubling
documented in _handoff/diag/watcher-crlf-doubling-2026-06-12.md turned out to
be safe_write's own text-mode os.open (fixed with O_BINARY); the simulation
here stands in for the real, separately documented watcher race (2026-05-24
truncation) and any future interference. Proves the signed-off contract:

- normalized-equal passes (a line-ending re-emit of intended content is a PASS)
- content-divergent interference restores the backup
- three failed attempts fail loud, naming the watcher race
- the target is never left half-written

The interference is injected deterministically: settle_read is wrapped so the
emit lands exactly between safe_write's atomic write and its settle poll
(the worst-case timing). A free-running thread was tried first and flaked on
Windows sharing violations between its handles and os.replace; the wrapper
exercises the identical perform_safe_write code path without the race.
Restores are left alone (content != fresh payload), matching the observed
real-watcher behavior that restores stick.
"""
import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / ".claude" / "skills" / \
    "governance" / "scripts" / "safe_write.py"
_spec = importlib.util.spec_from_file_location("safe_write_under_test", _SCRIPT)
sw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sw)

# Fast settle parameters so the 3-strike path stays under a second.
FAST = {"settle_timeout": 2.0, "settle_interval": 0.05}

ORIGINAL = b"# CLAUDE.md\r\n\r\nOriginal loader content.\r\nLine two.\r\n"
PAYLOAD = b"# CLAUDE.md\r\n\r\nNew loader content.\r\nLine two.\r\nLine three.\r\n"


def crlf_double(data: bytes) -> bytes:
    """The CR-doubling emit signature: every CRLF becomes CR CR LF."""
    return data.replace(b"\r\n", b"\r\r\n")


def _inject_interference(monkeypatch, transform, fired):
    """Wrap settle_read so `transform(PAYLOAD)` lands on the target whenever
    the file holds the freshly written payload, before settling begins."""
    original_settle = sw.settle_read

    def wrapper(target, timeout=sw.SETTLE_TIMEOUT, interval=sw.SETTLE_INTERVAL):
        if Path(target).read_bytes() == PAYLOAD:
            Path(target).write_bytes(transform(PAYLOAD))
            fired.append(1)
        return original_settle(target, timeout, interval)

    monkeypatch.setattr(sw, "settle_read", wrapper)


def test_normalized_equality_semantics():
    assert sw.normalize_newlines(crlf_double(PAYLOAD)) == sw.normalize_newlines(PAYLOAD)
    assert sw.normalize_newlines(b"a\r\nb\r\n") == sw.normalize_newlines(b"a\nb\n")
    assert sw.normalize_newlines(b"a\r\nb\r\n") != sw.normalize_newlines(b"a\nc\n")
    # +1 byte per line, as documented
    assert len(crlf_double(PAYLOAD)) == len(PAYLOAD) + PAYLOAD.count(b"\r\n")


def test_byte_exact_pass_without_interference(tmp_path):
    target = tmp_path / "CLAUDE.md"
    target.write_bytes(ORIGINAL)
    result = sw.perform_safe_write(target, PAYLOAD, **FAST)
    assert result["ok"] and result["status"] == "exact"
    assert target.read_bytes() == PAYLOAD
    assert result["backup_path"] is not None
    assert Path(result["backup_path"]).read_bytes() == ORIGINAL


def test_crlf_doubling_emit_passes_normalized(tmp_path, monkeypatch):
    target = tmp_path / "CLAUDE.md"
    target.write_bytes(ORIGINAL)
    fired = []
    _inject_interference(monkeypatch, crlf_double, fired)
    result = sw.perform_safe_write(target, PAYLOAD, **FAST)
    assert fired, "the simulated emit never fired"
    assert result["ok"] and result["status"] == "normalized"
    on_disk = target.read_bytes()
    assert on_disk == crlf_double(PAYLOAD)
    assert sw.normalize_newlines(on_disk) == sw.normalize_newlines(PAYLOAD)
    assert Path(result["backup_path"]).read_bytes() == ORIGINAL


def test_divergent_interference_restores_and_fails_loud(tmp_path, monkeypatch):
    target = tmp_path / "CLAUDE.md"
    target.write_bytes(ORIGINAL)
    fired = []
    _inject_interference(monkeypatch, lambda _: b"INTERFERENCE OWNS THIS\r\n", fired)
    result = sw.perform_safe_write(target, PAYLOAD, **FAST)
    assert len(fired) == 3, "every attempt must have been interfered with"
    assert not result["ok"] and result["status"] == "failed"
    assert result["attempts"] == 3
    assert target.read_bytes() == ORIGINAL  # restored, not half-written
    assert "watcher" in result["message"].lower()
    assert "3 attempts" in result["message"]


def test_new_target_divergence_never_leaves_half_written(tmp_path, monkeypatch):
    target = tmp_path / "CLAUDE.md"  # does not exist yet
    fired = []
    _inject_interference(monkeypatch, lambda _: b"INTERFERENCE OWNS THIS\r\n", fired)
    result = sw.perform_safe_write(target, PAYLOAD, **FAST)
    assert len(fired) == 3
    assert not result["ok"] and result["status"] == "failed"
    assert result["backup_path"] is None
    assert not target.exists()  # removed: it did not exist before the write
    assert "watcher" in result["message"].lower()
