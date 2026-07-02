"""Pytest fixtures and path setup for the Shop QC suite. Headless (no Tkinter)."""

import os
import sys

# Make `import shopqc` work whether pytest is run from ShopQC/ or tests/.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest  # noqa: E402
from shopqc import db  # noqa: E402

FIXTURE_PDF = os.path.join(ROOT, "data", "test_fixtures",
                           "PRJ-2026-HILLCREST-STR-001.pdf")
FIXTURE_TXT = os.path.join(ROOT, "data", "test_fixtures",
                           "PRJ-2026-HILLCREST-STR-001.txt")


@pytest.fixture
def conn(tmp_path):
    """A fresh initialized DB on a temp file (DELETE journal, like production)."""
    c = db.connect(str(tmp_path / "qc.db"))
    db.init_db(c)
    yield c
    c.close()
