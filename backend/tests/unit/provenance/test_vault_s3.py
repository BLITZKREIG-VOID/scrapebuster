"""PRV-08: S3 Object Lock vault (boto3 replaced by an in-process fake; no AWS calls)."""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import sys
import threading
import types
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sb.provenance import evidence, vault_s3
from sb.store import db

from .test_evidence import _create_test_case_payload, _insert_case_row

RUN_ID = "RUN-20260929-120000"
CASE_ID = "SB-001"


class _FakeS3:
    def __init__(self, fail: Exception | None):
        self.fail = fail
        self.calls: list[dict] = []

    def put_object(self, **kwargs):
        if self.fail:
            raise self.fail
        self.calls.append(kwargs)
        return {"VersionId": f"v-{len(self.calls)}"}


@pytest.fixture
def fake_boto3(monkeypatch):
    """Install fake ``boto3``/``botocore.config`` modules; returns a setter for failure."""
    state = {"client": _FakeS3(None), "client_kwargs": None}

    def client(service, **kwargs):
        assert service == "s3"
        state["client_kwargs"] = kwargs
        return state["client"]

    boto3 = types.ModuleType("boto3")
    boto3.client = client
    botocore = types.ModuleType("botocore")
    config_mod = types.ModuleType("botocore.config")
    config_mod.Config = lambda **kw: kw
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    monkeypatch.setitem(sys.modules, "botocore", botocore)
    monkeypatch.setitem(sys.modules, "botocore.config", config_mod)
    return state


@pytest.fixture
def bundle(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(evidence, "EVIDENCE_ROOT", tmp_path / "evidence")
    vault_s3.reset()
    case = _create_test_case_payload(CASE_ID, RUN_ID)
    _insert_case_row(case)
    summary = evidence.build_bundle(case)
    return Path(summary["local_path"])


def _case_evidence() -> dict:
    with closing(db.get_connection()) as conn:
        row = conn.execute("SELECT evidence FROM cases WHERE case_id = ?", (CASE_ID,)).fetchone()
    return json.loads(row["evidence"])


def test_unset_bucket_is_disabled_and_stays_local(bundle, monkeypatch):
    monkeypatch.delenv("SB_S3_BUCKET", raising=False)

    assert vault_s3.s3_status() == "disabled"
    assert vault_s3.preserve_async(CASE_ID, RUN_ID, bundle) is None
    assert _case_evidence()["status"] == "PRESERVED_LOCAL"
    assert not (bundle / vault_s3.RECEIPT_NAME).exists()


def test_bucket_without_boto3_is_down_and_recorded(bundle, monkeypatch):
    monkeypatch.setenv("SB_S3_BUCKET", "sb-evidence-test")
    monkeypatch.setitem(sys.modules, "boto3", None)  # import raises ImportError

    assert vault_s3.s3_status() == "down"
    assert vault_s3.upload_bundle(CASE_ID, RUN_ID, bundle) is None
    ev = _case_evidence()
    assert ev["status"] == "PRESERVED_LOCAL"
    assert ev["vault"] == {"status": "down", "error": "boto3 not importable"}


def test_upload_locks_every_file_and_writes_receipt(bundle, monkeypatch, fake_boto3):
    monkeypatch.setenv("SB_S3_BUCKET", "sb-evidence-test")
    before = datetime.now(UTC)

    thread = vault_s3.preserve_async(CASE_ID, RUN_ID, bundle)
    thread.join(timeout=5)

    calls = fake_boto3["client"].calls
    assert [c["Key"] for c in calls] == [f"cases/{RUN_ID}/{CASE_ID}/{n}" for n in evidence.FILE_NAMES]
    for call in calls:
        body = (bundle / call["Key"].rsplit("/", 1)[1]).read_bytes()
        assert call["Bucket"] == "sb-evidence-test"
        assert call["Body"] == body
        assert call["ObjectLockMode"] == "GOVERNANCE"
        assert call["ChecksumAlgorithm"] == "SHA256"
        assert call["ChecksumSHA256"] == base64.b64encode(hashlib.sha256(body).digest()).decode()
        retain = call["ObjectLockRetainUntilDate"]
        assert before + timedelta(hours=24) - timedelta(seconds=2) <= retain <= datetime.now(UTC) + timedelta(hours=24)
    cfg = fake_boto3["client_kwargs"]["config"]
    assert cfg["connect_timeout"] == 5 and cfg["read_timeout"] == 5
    assert cfg["retries"] == {"total_max_attempts": 1}

    receipt = json.loads((bundle / vault_s3.RECEIPT_NAME).read_text())
    assert receipt["bucket"] == "sb-evidence-test"
    assert receipt["mode"] == "GOVERNANCE"
    assert len(receipt["keys"]) == 10
    assert [o["version_id"] for o in receipt["objects"]] == [f"v-{i}" for i in range(1, 11)]

    ev = _case_evidence()
    assert ev["status"] == "PRESERVED_S3_LOCKED"
    assert ev["vault"]["status"] == "ok"
    with closing(db.get_connection()) as conn:
        rows = conn.execute(
            "SELECT name, s3_key, s3_version_id, retain_until FROM evidence_objects WHERE case_id = ?",
            (CASE_ID,),
        ).fetchall()
    assert len(rows) == 10
    assert all(r["s3_key"] and r["s3_version_id"] and r["retain_until"] == receipt["retain_until"] for r in rows)
    assert vault_s3.s3_status() == "ok"

    # Receipt lives outside the manifest: the bundle still verifies.
    assert evidence.verify_case(CASE_ID)["result"] == "VALID"


def test_upload_error_is_down_and_case_stays_local(bundle, monkeypatch, fake_boto3):
    monkeypatch.setenv("SB_S3_BUCKET", "sb-evidence-test")
    fake_boto3["client"] = _FakeS3(RuntimeError("AccessDenied"))

    assert vault_s3.upload_bundle(CASE_ID, RUN_ID, bundle) is None

    ev = _case_evidence()
    assert ev["status"] == "PRESERVED_LOCAL"
    assert ev["vault"] == {"status": "down", "error": "RuntimeError: AccessDenied"}
    assert not (bundle / vault_s3.RECEIPT_NAME).exists()
    assert vault_s3.s3_status() == "down"

    vault_s3.reset()
    assert vault_s3.s3_status() == "ok"


class _LockedConnection:
    """Wraps a real sqlite connection; statements starting with ``fail_prefix`` raise "locked"."""

    def __init__(self, conn, fail_prefix: str):
        self._conn = conn
        self._fail_prefix = fail_prefix

    def _check(self, sql: str) -> None:
        if sql.lstrip().startswith(self._fail_prefix):
            raise sqlite3.OperationalError("database is locked")

    def execute(self, sql, *args):
        self._check(sql)
        return self._conn.execute(sql, *args)

    def executemany(self, sql, *args):
        self._check(sql)
        return self._conn.executemany(sql, *args)

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, *exc):
        return self._conn.__exit__(*exc)

    def close(self):
        self._conn.close()


def _run_in_thread(monkeypatch, bundle) -> list:
    """Run the real background worker; return any exceptions that escaped the thread."""
    escaped: list = []
    monkeypatch.setattr(threading, "excepthook", lambda args: escaped.append(args.exc_value))
    vault_s3.preserve_async(CASE_ID, RUN_ID, bundle).join(timeout=5)
    return escaped


def _assert_down_and_consistent(bundle, error: str) -> None:
    ev = _case_evidence()
    assert ev["status"] == "PRESERVED_LOCAL"
    assert ev["vault"] == {"status": "down", "error": error}
    assert vault_s3.s3_status() == "down"
    assert not (bundle / vault_s3.RECEIPT_NAME).exists()
    with closing(db.get_connection()) as conn:
        locked = conn.execute(
            "SELECT COUNT(*) FROM evidence_objects WHERE case_id = ? AND s3_key IS NOT NULL", (CASE_ID,)
        ).fetchone()[0]
    assert locked == 0


def test_receipt_write_failure_after_upload_is_recorded_down(bundle, monkeypatch, fake_boto3):
    monkeypatch.setenv("SB_S3_BUCKET", "sb-evidence-test")
    real_write_text = Path.write_text

    def write_text(self, *args, **kwargs):
        if self.name == vault_s3.RECEIPT_NAME:
            raise OSError("No space left on device")
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write_text)

    assert _run_in_thread(monkeypatch, bundle) == []
    assert len(fake_boto3["client"].calls) == 10  # S3 succeeded; the local step failed
    _assert_down_and_consistent(bundle, "OSError: No space left on device")


def test_db_update_failure_after_upload_is_recorded_down(bundle, monkeypatch, fake_boto3):
    monkeypatch.setenv("SB_S3_BUCKET", "sb-evidence-test")
    real_get_connection = db.get_connection
    calls = {"n": 0}

    def get_connection():
        calls["n"] += 1
        conn = real_get_connection()
        # First connection = success transition (locked); second = _record_failure (works).
        return _LockedConnection(conn, "UPDATE evidence_objects") if calls["n"] == 1 else conn

    monkeypatch.setattr(db, "get_connection", get_connection)

    assert _run_in_thread(monkeypatch, bundle) == []
    assert len(fake_boto3["client"].calls) == 10
    _assert_down_and_consistent(bundle, "OperationalError: database is locked")


def test_failure_recording_db_error_does_not_kill_thread_or_report_ok(bundle, monkeypatch, fake_boto3):
    monkeypatch.setenv("SB_S3_BUCKET", "sb-evidence-test")
    real_get_connection = db.get_connection
    monkeypatch.setattr(db, "get_connection", lambda: _LockedConnection(real_get_connection(), "UPDATE"))

    assert _run_in_thread(monkeypatch, bundle) == []
    assert vault_s3.s3_status() == "down"
    assert not (bundle / vault_s3.RECEIPT_NAME).exists()
