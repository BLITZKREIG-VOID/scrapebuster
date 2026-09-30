"""PRV-05: Hash-chained evidence bundles and verification (master plan §12)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path
from typing import Any

from sb.canary import hashing
from sb.store import db

_REPO = Path(__file__).resolve().parents[3]
_raw_runtime = Path(os.getenv("SB_RUNTIME_DIR", "data/runtime"))
_RUNTIME_DIR = _raw_runtime if _raw_runtime.is_absolute() else _REPO / _raw_runtime
EVIDENCE_ROOT: Path = _RUNTIME_DIR / "evidence"
GENESIS: str = "0" * 64
TOOL_VERSION: str = "scapebusters-0.1"

CONTENT_FILE_NAMES: tuple[str, ...] = (
    "01_canary.json",
    "02_publication_record.json",
    "03_exposure_events.json",
    "04_scraper_profile.json",
    "05_probe_request.json",
    "06_model_response.json",
    "07_control_response.json",
    "08_match_analysis.json",
    "09_finding.json",
)

FILE_NAMES: tuple[str, ...] = CONTENT_FILE_NAMES + ("manifest.json",)


def _json_default(obj: Any) -> Any:
    """Fallback serializer for Pydantic models or objects with model_dump/dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _serialize_json(obj: Any) -> str:
    """Format JSON with indent=2, sort_keys=True, ensure_ascii=False, and trailing newline."""
    return (
        json.dumps(
            obj,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            default=_json_default,
        )
        + "\n"
    )


def _compute_manifest_self_hash(manifest_dict: Mapping[str, Any]) -> str:
    """Compute sha256 of canonical compact JSON with manifest_sha256 field set to empty string."""
    copy_manifest = dict(manifest_dict)
    copy_manifest["manifest_sha256"] = ""
    raw = json.dumps(
        copy_manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_bundle(case: dict[str, Any]) -> dict[str, Any]:
    """Build a tamper-evident evidence bundle for a case.

    Writes files 01..09 and manifest.json into EVIDENCE_ROOT/<run_id>/<case_id>/,
    appends to EVIDENCE_ROOT/chain.json, sets file modes to 0o444, inserts
    evidence_objects rows, and updates cases.evidence.
    """
    root = EVIDENCE_ROOT
    case_id = str(case["case_id"])
    run_id = str(case["run_id"])
    created_at = str(case["created_at"])

    bundle_dir = root / run_id / case_id
    if bundle_dir.exists():
        raise FileExistsError(f"Evidence directory {bundle_dir} already exists")

    # Ensure bundle directory can be created
    bundle_dir.mkdir(parents=True, exist_ok=False)

    bundle_data = case.get("bundle") or {}
    finding_data = {k: v for k, v in case.items() if k != "bundle"}

    bundle_map: list[tuple[str, Any]] = [
        ("01_canary.json", bundle_data.get("canaries")),
        ("02_publication_record.json", bundle_data.get("publications")),
        ("03_exposure_events.json", bundle_data.get("exposures")),
        ("04_scraper_profile.json", bundle_data.get("sessions")),
        ("05_probe_request.json", bundle_data.get("probe_request")),
        ("06_model_response.json", bundle_data.get("target_responses")),
        ("07_control_response.json", bundle_data.get("control_responses")),
        ("08_match_analysis.json", bundle_data.get("match_analysis")),
        ("09_finding.json", finding_data),
    ]

    files_meta: list[dict[str, Any]] = []
    for filename, payload in bundle_map:
        file_path = bundle_dir / filename
        content_str = _serialize_json(payload)
        content_bytes = content_str.encode("utf-8")
        file_path.write_bytes(content_bytes)
        file_sha256 = hashlib.sha256(content_bytes).hexdigest()
        file_size = len(content_bytes)
        files_meta.append({
            "name": filename,
            "sha256": file_sha256,
            "bytes": file_size,
        })

    # Read current chain head
    chain_path = root / "chain.json"
    if chain_path.exists():
        # A corrupt chain file must fail loudly; silently restarting at GENESIS would hide tampering.
        chain_obj = json.loads(chain_path.read_text(encoding="utf-8"))
        prev_manifest_sha256 = chain_obj["head"]
        chain_entries = chain_obj["entries"]
    else:
        prev_manifest_sha256 = GENESIS
        chain_entries = []

    # Prepare manifest with empty manifest_sha256
    manifest: dict[str, Any] = {
        "case_id": case_id,
        "run_id": run_id,
        "created_at": created_at,
        "files": files_meta,
        "prev_manifest_sha256": prev_manifest_sha256,
        "tool_version": TOOL_VERSION,
        "manifest_sha256": "",
    }

    manifest_sha256 = _compute_manifest_self_hash(manifest)
    manifest["manifest_sha256"] = manifest_sha256

    manifest_path = bundle_dir / "manifest.json"
    manifest_str = _serialize_json(manifest)
    manifest_bytes = manifest_str.encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)
    manifest_file_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    manifest_file_size = len(manifest_bytes)

    # Append to chain atomically; chain.json stays writable
    new_entry = {
        "case_id": case_id,
        "run_id": run_id,
        "manifest_sha256": manifest_sha256,
        "prev_manifest_sha256": prev_manifest_sha256,
        "path": str(bundle_dir),
    }
    chain_data = {
        "head": manifest_sha256,
        "entries": chain_entries + [new_entry],
    }
    chain_json_str = _serialize_json(chain_data)

    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(root),
        delete=False,
    ) as tf:
        tf.write(chain_json_str)
        tf.flush()
        os.fsync(tf.fileno())
        temp_name = tf.name

    os.replace(temp_name, chain_path)

    # chmod 0o444 all 10 bundle files
    for filename in FILE_NAMES:
        (bundle_dir / filename).chmod(0o444)

    # Prepare evidence_objects rows for all 10 files
    evidence_rows = [
        (case_id, fm["name"], fm["sha256"], fm["bytes"], str(bundle_dir / fm["name"]))
        for fm in files_meta
    ]
    evidence_rows.append(
        (case_id, "manifest.json", manifest_file_sha256, manifest_file_size, str(manifest_path))
    )

    evidence_summary: dict[str, Any] = {
        "status": "PRESERVED_LOCAL",
        "local_path": str(bundle_dir),
        "manifest_sha256": manifest_sha256,
        "prev_manifest_sha256": prev_manifest_sha256,
        "files": 10,
    }

    with closing(db.get_connection()) as conn, conn:
        conn.executemany(
            """
            INSERT INTO evidence_objects (case_id, name, sha256, bytes, local_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            evidence_rows,
        )
        conn.execute(
            "UPDATE cases SET evidence = ? WHERE case_id = ?",
            (json.dumps(evidence_summary, sort_keys=True), case_id),
        )

    return evidence_summary


def verify_bundle(bundle_dir: Path | str, chain_path: Path | str | None = None) -> dict[str, Any]:
    """Verify integrity of an evidence bundle on disk.

    Returns dict with 'result' ('VALID' or 'TAMPERED') and 'checks' list.
    """
    bundle_path = Path(bundle_dir)
    chain_file = Path(chain_path) if chain_path is not None else None
    checks: list[dict[str, Any]] = []

    manifest_file = bundle_path / "manifest.json"
    if not manifest_file.exists():
        for fname in CONTENT_FILE_NAMES:
            checks.append({"name": f"file:{fname}", "ok": False, "detail": "manifest.json missing"})
        checks.append({"name": "manifest_self_hash", "ok": False, "detail": "manifest.json missing"})
        if chain_file is not None:
            checks.append({"name": "chain_link", "ok": False, "detail": "manifest.json missing"})
        checks.append({"name": "canary_hashes", "ok": False, "detail": "manifest.json missing"})
        return {"result": "TAMPERED", "checks": checks}

    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError) as e:
        for fname in CONTENT_FILE_NAMES:
            checks.append({"name": f"file:{fname}", "ok": False, "detail": f"manifest.json unparseable: {e}"})
        checks.append({"name": "manifest_self_hash", "ok": False, "detail": f"manifest.json unparseable: {e}"})
        if chain_file is not None:
            checks.append({"name": "chain_link", "ok": False, "detail": f"manifest.json unparseable: {e}"})
        checks.append({"name": "canary_hashes", "ok": False, "detail": f"manifest.json unparseable: {e}"})
        return {"result": "TAMPERED", "checks": checks}

    # 1. file:<name> checks
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, list):
        checks.append({"name": "manifest_files", "ok": False, "detail": "manifest files key is not a list"})
    else:
        for f_info in manifest_files:
            fname = f_info.get("name", "unknown")
            check_name = f"file:{fname}"
            expected_sha = f_info.get("sha256")
            expected_bytes = f_info.get("bytes")

            disk_file = bundle_path / fname
            if not disk_file.exists():
                checks.append({"name": check_name, "ok": False, "detail": f"File {fname} not found on disk"})
                continue

            try:
                data = disk_file.read_bytes()
                actual_sha = hashlib.sha256(data).hexdigest()
                actual_bytes = len(data)
                if actual_sha == expected_sha and actual_bytes == expected_bytes:
                    checks.append({"name": check_name, "ok": True, "detail": "ok"})
                else:
                    checks.append({
                        "name": check_name,
                        "ok": False,
                        "detail": (
                            f"Mismatch in {fname}: expected sha256={expected_sha}, bytes={expected_bytes}; "
                            f"got sha256={actual_sha}, bytes={actual_bytes}"
                        ),
                    })
            except (OSError, ValueError, KeyError, TypeError) as e:
                checks.append({"name": check_name, "ok": False, "detail": f"Error reading {fname}: {e}"})

    # 2. manifest_self_hash
    try:
        expected_self_hash = _compute_manifest_self_hash(manifest)
        actual_self_hash = manifest.get("manifest_sha256")
        if actual_self_hash and actual_self_hash == expected_self_hash:
            checks.append({"name": "manifest_self_hash", "ok": True, "detail": "ok"})
        else:
            checks.append({
                "name": "manifest_self_hash",
                "ok": False,
                "detail": f"Self hash mismatch: expected {expected_self_hash}, got {actual_self_hash}",
            })
    except (OSError, ValueError, KeyError, TypeError) as e:
        checks.append({"name": "manifest_self_hash", "ok": False, "detail": f"Error verifying self hash: {e}"})

    # 3. chain_link (only when chain_path given)
    if chain_file is not None:
        if not chain_file.exists():
            checks.append({"name": "chain_link", "ok": False, "detail": f"Chain file {chain_file} does not exist"})
        else:
            try:
                chain_obj = json.loads(chain_file.read_text(encoding="utf-8"))
                entries = chain_obj.get("entries", [])
                case_id = manifest.get("case_id")
                matching = [(i, e) for i, e in enumerate(entries) if e.get("case_id") == case_id]
                if not matching:
                    checks.append({"name": "chain_link", "ok": False, "detail": f"Case {case_id} not found in chain"})
                else:
                    idx, entry = matching[-1]
                    m_sha = manifest.get("manifest_sha256")
                    m_prev = manifest.get("prev_manifest_sha256")
                    e_sha = entry.get("manifest_sha256")
                    e_prev = entry.get("prev_manifest_sha256")

                    expected_prev = GENESIS if idx == 0 else entries[idx - 1].get("manifest_sha256")

                    if (
                        e_sha == m_sha
                        and e_prev == m_prev
                        and m_prev == expected_prev
                    ):
                        checks.append({"name": "chain_link", "ok": True, "detail": "ok"})
                    else:
                        checks.append({
                            "name": "chain_link",
                            "ok": False,
                            "detail": (
                                f"Chain mismatch: entry(manifest={e_sha}, prev={e_prev}), "
                                f"manifest(manifest={m_sha}, prev={m_prev}), expected_prev={expected_prev}"
                            ),
                        })
            except (OSError, ValueError, KeyError, TypeError) as e:
                checks.append({"name": "chain_link", "ok": False, "detail": f"Error verifying chain: {e}"})

    # 4. canary_hashes
    canary_file = bundle_path / "01_canary.json"
    if not canary_file.exists():
        checks.append({"name": "canary_hashes", "ok": False, "detail": "01_canary.json not found"})
    else:
        try:
            canaries_raw = json.loads(canary_file.read_text(encoding="utf-8"))
            if isinstance(canaries_raw, list):
                records = canaries_raw
            elif isinstance(canaries_raw, dict):
                records = [canaries_raw]
            else:
                records = []

            mismatches: list[str] = []
            for rec in records:
                cid = rec.get("canary_id")
                ctype = rec.get("type")
                ccontent = rec.get("canonical_content")
                if ccontent is None:
                    ccontent = rec.get("content", "")
                cver = rec.get("content_version")
                expected_sha = rec.get("sha256")

                rec_payload = {
                    "canary_id": cid,
                    "type": ctype,
                    "content": ccontent,
                    "content_version": cver,
                }
                computed_sha = hashing.canary_hash(rec_payload)
                if computed_sha != expected_sha:
                    mismatches.append(f"{cid} (computed {computed_sha} != expected {expected_sha})")

            if mismatches:
                checks.append({
                    "name": "canary_hashes",
                    "ok": False,
                    "detail": "; ".join(mismatches),
                })
            else:
                checks.append({"name": "canary_hashes", "ok": True, "detail": "ok"})
        except (OSError, ValueError, KeyError, TypeError) as e:
            checks.append({"name": "canary_hashes", "ok": False, "detail": f"Error verifying canary hashes: {e}"})

    result = "VALID" if all(c["ok"] for c in checks) else "TAMPERED"
    return {"result": result, "checks": checks}


def verify_case(case_id: str) -> dict[str, Any]:
    """Verify evidence of a case from the database and disk.

    Raises KeyError if case_id or manifest.json row is unknown.
    Runs verify_bundle with EVIDENCE_ROOT/chain.json, plus db:<name> checks
    comparing evidence_objects sha256 to disk.
    """
    root = EVIDENCE_ROOT
    with closing(db.get_connection()) as conn, conn:
        rows = conn.execute(
            "SELECT name, sha256, bytes, local_path FROM evidence_objects WHERE case_id = ? ORDER BY name ASC",
            (case_id,),
        ).fetchall()

    if not rows:
        raise KeyError(f"Unknown case: {case_id}")

    manifest_row = next((r for r in rows if r["name"] == "manifest.json"), None)
    if manifest_row is None:
        raise KeyError(f"Manifest row missing for case {case_id}")

    bundle_dir = Path(manifest_row["local_path"]).parent
    chain_path = root / "chain.json"

    bundle_res = verify_bundle(bundle_dir, chain_path=chain_path)
    checks = list(bundle_res["checks"])

    for r in rows:
        name = r["name"]
        check_name = f"db:{name}"
        expected_sha = r["sha256"]
        file_path = bundle_dir / name

        if not file_path.exists():
            checks.append({"name": check_name, "ok": False, "detail": f"File {name} not found"})
            continue

        try:
            actual_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if actual_sha == expected_sha:
                checks.append({"name": check_name, "ok": True, "detail": "ok"})
            else:
                checks.append({
                    "name": check_name,
                    "ok": False,
                    "detail": f"DB hash {expected_sha} != disk hash {actual_sha}",
                })
        except (OSError, ValueError, KeyError, TypeError) as e:
            checks.append({"name": check_name, "ok": False, "detail": f"Error reading {name}: {e}"})

    result = "VALID" if all(c["ok"] for c in checks) else "TAMPERED"
    return {"result": result, "checks": checks}
