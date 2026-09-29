"""Pytest fixtures for provenance unit tests."""

import atexit
import os
import shutil
import tempfile
from pathlib import Path

# Env SB_DB_PATH set at import time to a temp dir before anything imports sb.store.db
_BOOTSTRAP_DIR = tempfile.mkdtemp(prefix="sb_provenance_test_")
os.environ.setdefault("SB_DB_PATH", os.path.join(_BOOTSTRAP_DIR, "sb.db"))
atexit.register(lambda: shutil.rmtree(_BOOTSTRAP_DIR, ignore_errors=True))

import pytest
from sb.provenance import dataset
from sb.provenance import reset as provenance_reset
from sb.store import db


@pytest.fixture(autouse=True)
def isolate_env(tmp_path, monkeypatch):
    """Isolate DB and INGEST_DIR per test and reset caches before and after."""
    test_db = str(tmp_path / "sb.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()
    ingest_dir = tmp_path / "ingested"
    monkeypatch.setattr(dataset, "INGEST_DIR", ingest_dir)
    provenance_reset()
    try:
        yield
    finally:
        provenance_reset()


@pytest.fixture
def repo_root() -> Path:
    """Return repository root path."""
    return Path(__file__).resolve().parents[4]


@pytest.fixture
def sample_path(repo_root: Path) -> Path:
    """Return path to scraped dataset sample fixture."""
    return repo_root / "contracts" / "fixtures" / "scraped_dataset_sample.jsonl"
