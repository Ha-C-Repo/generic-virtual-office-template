"""One-line ship gate. Runs the pytest suite, prints a single PASS/COUNT line, and
exits non-zero on any failure so the EXE build can gate on it.

    py tests\run_all.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


class _Tally:
    """Collects pass/fail/error counts from the pytest run."""

    passed = failed = errors = 0

    def pytest_terminal_summary(self, terminalreporter):
        st = terminalreporter.stats
        _Tally.passed = len(st.get("passed", []))
        _Tally.failed = len(st.get("failed", []))
        _Tally.errors = len(st.get("error", []))


def main():
    code = pytest.main(["-q", HERE], plugins=[_Tally()])
    total = _Tally.passed + _Tally.failed + _Tally.errors
    verdict = "PASS" if code == 0 else "FAIL"
    print(f"SHIP GATE {verdict}: {_Tally.passed}/{total} tests passed"
          + (f", {_Tally.failed} failed, {_Tally.errors} errors"
             if code != 0 else ""))
    return int(code)


if __name__ == "__main__":
    sys.exit(main())
