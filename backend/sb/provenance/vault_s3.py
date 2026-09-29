"""PRV-08: S3 Object Lock vault for evidence bundles (master plan §12, P1-high).

After ``evidence.build_bundle`` writes a local bundle, :func:`preserve_async` uploads each
bundle file to ``s3://$SB_S3_BUCKET/cases/<run_id>/<case_id>/<name>`` with
``ObjectLockMode=GOVERNANCE``, ``ObjectLockRetainUntilDate=now+24h`` and a SHA256 checksum,
in a background thread, single attempt, 5 s timeouts.

Outcomes are visible in data, never silent:
- ``SB_S3_BUCKET`` unset → no upload, :func:`s3_status` ``"disabled"``, case evidence stays
  ``PRESERVED_LOCAL``.
- boto3 missing or any error (upload, receipt write, DB update) → :func:`s3_status` ``"down"``,
  case evidence stays ``PRESERVED_LOCAL``, gains a ``vault`` entry
  ``{"status": "down", "error": ...}`` and no ``vault_receipt.json`` is left behind.
- success → ``vault_receipt.json`` next to the manifest (outside it: created after upload),
  ``evidence_objects`` rows get ``s3_key``/``s3_version_id``/``retain_until``, case evidence
  status ``PRESERVED_S3_LOCKED``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import threading
from contextlib import closing, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from sb.store import db

logger = logging.getLogger(__name__)

LOCK_MODE = "GOVERNANCE"
RETENTION = timedelta(hours=24)
TIMEOUT_S = 5
RECEIPT_NAME = "vault_receipt.json"

_state_lock = threading.Lock()
_last_error: str | None = None


def _bucket() -> str:
    return os.getenv("SB_S3_BUCKET", "").strip()


def _import_boto3() -> tuple[Any, Any]:
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        return None, None
    return boto3, Config


def _set_last_error(error: str | None) -> None:
    global _last_error
    with _state_lock:
        _last_error = error


def s3_status() -> Literal["ok", "disabled", "down"]:
    """``disabled`` without ``SB_S3_BUCKET``; ``down`` if boto3 is missing or the last upload
    failed; otherwise ``ok``."""
    if not _bucket():
        return "disabled"
    boto3, _ = _import_boto3()
    if boto3 is None:
        return "down"
    with _state_lock:
        return "down" if _last_error else "ok"


def reset() -> None:
    """Forget the last upload error (demo reset)."""
    _set_last_error(None)


def preserve_async(case_id: str, run_id: str, bundle_dir: str | Path) -> threading.Thread | None:
    """Start the upload in a background thread. ``None`` when the vault is disabled."""
    if not _bucket():
        return None
    thread = threading.Thread(
        target=upload_bundle,
        args=(case_id, run_id, Path(bundle_dir)),
        name=f"vault-s3-{case_id}",
        daemon=True,
    )
    thread.start()
    return thread


def upload_bundle(case_id: str, run_id: str, bundle_dir: Path) -> dict[str, Any] | None:
    """Upload every file listed in the bundle manifest (plus the manifest). Single attempt.

    Returns the receipt on success, ``None`` on failure (failure recorded in the case). Upload,
    receipt write and the DB state transition form one protected unit: any failure in it goes
    through :func:`_record_failure`, so the background thread never dies with vault state "ok"."""
    from sb.provenance.evidence import FILE_NAMES

    bucket = _bucket()
    boto3, config_cls = _import_boto3()
    if boto3 is None:
        _record_failure(case_id, "boto3 not importable")
        return None
    receipt_path = bundle_dir / RECEIPT_NAME
    try:
        client = boto3.client(
            "s3",
            region_name=os.getenv("AWS_REGION") or None,
            config=config_cls(
                connect_timeout=TIMEOUT_S,
                read_timeout=TIMEOUT_S,
                retries={"total_max_attempts": 1},
            ),
        )
        retain_until = datetime.now(UTC).replace(microsecond=0) + RETENTION
        objects = []
        for name in FILE_NAMES:
            body = (bundle_dir / name).read_bytes()
            digest = hashlib.sha256(body).digest()
            key = f"cases/{run_id}/{case_id}/{name}"
            resp = client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ObjectLockMode=LOCK_MODE,
                ObjectLockRetainUntilDate=retain_until,
                ChecksumAlgorithm="SHA256",
                ChecksumSHA256=base64.b64encode(digest).decode("ascii"),
            )
            objects.append({
                "name": name,
                "key": key,
                "version_id": resp.get("VersionId"),
                "sha256": digest.hex(),
            })

        receipt = {
            "bucket": bucket,
            "mode": LOCK_MODE,
            "retain_until": retain_until.isoformat().replace("+00:00", "Z"),
            "uploaded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "keys": [o["key"] for o in objects],
            "objects": objects,
        }
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with closing(db.get_connection()) as conn, conn:  # one transaction: all rows or none
            conn.executemany(
                "UPDATE evidence_objects SET s3_key = ?, s3_version_id = ?, retain_until = ? "
                "WHERE case_id = ? AND name = ?",
                [(o["key"], o["version_id"], receipt["retain_until"], case_id, o["name"]) for o in objects],
            )
            _update_case_evidence(conn, case_id, {
                "status": "PRESERVED_S3_LOCKED",
                "vault": {"status": "ok", "bucket": bucket, "receipt": str(receipt_path)},
            })
    except Exception as exc:  # any boto/IO/DB error = vault down, recorded visibly
        logger.exception("S3 vault preservation failed for case %s", case_id)
        # A receipt claims S3 lock; the DB transaction rolled back, so drop a half-written one.
        with suppress(OSError):
            receipt_path.unlink(missing_ok=True)
        _record_failure(case_id, f"{exc.__class__.__name__}: {exc}")
        return None
    _set_last_error(None)
    return receipt


def _record_failure(case_id: str, error: str) -> None:
    """Mark the vault down in memory first (so ``s3_status`` can never stay "ok"), then in the case.

    Must not raise: it runs in the background thread, and the DB may be the thing that failed."""
    _set_last_error(error)
    try:
        with closing(db.get_connection()) as conn, conn:
            _update_case_evidence(conn, case_id, {"vault": {"status": "down", "error": error}})
    except Exception:  # recording the failure must not kill the worker thread
        logger.exception("Could not record S3 vault failure for case %s", case_id)
        _set_last_error(f"{error}; failure not persisted to case")


def _update_case_evidence(conn: Any, case_id: str, changes: dict[str, Any]) -> None:
    row = conn.execute("SELECT evidence FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if row is None:
        return
    current = json.loads(row["evidence"]) if row["evidence"] else {}
    current.update(changes)
    conn.execute(
        "UPDATE cases SET evidence = ? WHERE case_id = ?",
        (json.dumps(current, sort_keys=True), case_id),
    )
