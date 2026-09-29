"""Pytest fixtures for trap unit tests."""

import atexit
import os
import shutil
import tempfile

# Env SB_DB_PATH set at import time to a temp dir BEFORE importing sb.store.db
_BOOTSTRAP_DIR = tempfile.mkdtemp(prefix="sb_trap_test_")
os.environ.setdefault("SB_DB_PATH", os.path.join(_BOOTSTRAP_DIR, "sb.db"))
atexit.register(lambda: shutil.rmtree(_BOOTSTRAP_DIR, ignore_errors=True))

import pytest

from sb.canary.seed import seed_canaries
from sb.store import db


@pytest.fixture(autouse=True)
def isolate_db(tmp_path, monkeypatch):
    """Autouse fixture monkeypatching sb.store.db.DB_PATH to tmp_path/'sb.db' then db.reset_db() and seed_canaries()."""
    test_db = str(tmp_path / "sb.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()
    seed_canaries()
    yield
