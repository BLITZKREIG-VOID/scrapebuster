"""Dataset ingestion, validation, and metadata store for provenance."""

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
from typing import Any

from sb.contracts import Dataset
from sb.store import db

INGEST_DIR: Path = Path(__file__).resolve().parents[3] / "data" / "datasets" / "ingested"

_RECORDS_CACHE: dict[str, list[dict]] = {}


class DatasetValidationError(ValueError):
    """Raised when a dataset record fails validation."""


def reset() -> None:
    """Clear the in-memory records cache."""
    _RECORDS_CACHE.clear()


def validate_record(obj: Any, line_no: int) -> dict:
    """Validate a single dataset record from a JSON object.

    Requires string keys 'url', 'fetched_at' (parseable ISO8601), 'title', 'text'.
    Raises DatasetValidationError mentioning line_no on failure.
    """
    if not isinstance(obj, dict):
        raise DatasetValidationError(
            f"line {line_no}: record must be a JSON object, got {type(obj).__name__}"
        )

    for field in ("url", "fetched_at", "title", "text"):
        if field not in obj:
            raise DatasetValidationError(f"line {line_no}: missing required field '{field}'")
        if not isinstance(obj[field], str):
            raise DatasetValidationError(
                f"line {line_no}: field '{field}' must be a string, got {type(obj[field]).__name__}"
            )

    try:
        datetime.fromisoformat(obj["fetched_at"])
    except (ValueError, TypeError) as exc:
        raise DatasetValidationError(f"line {line_no}: invalid fetched_at: {exc}") from exc

    return obj


def ingest(
    path: str | Path,
    role: str,
    dataset_id: str | None = None,
    now: str | None = None,
) -> Dataset:
    """Ingest a JSONL dataset file with validation, copy to INGEST_DIR, and index creation.

    Validates every non-blank line (at least 1 record required).
    If validation fails, raises DatasetValidationError with line number and makes no changes.
    """
    if role not in ("target", "control"):
        raise ValueError(f"Invalid role: {role!r}. Role must be 'target' or 'control'.")

    src_path = Path(path)
    if not src_path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {src_path}")

    source_bytes = src_path.read_bytes()
    sha256 = hashlib.sha256(source_bytes).hexdigest()

    try:
        content_str = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DatasetValidationError(f"line 1: file is not valid UTF-8: {exc}") from exc

    lines = content_str.splitlines()
    if not lines or not content_str.strip():
        raise DatasetValidationError("line 1: empty file or no records found")

    records: list[dict] = []
    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetValidationError(f"line {line_no}: invalid JSON: {exc}") from exc
        records.append(validate_record(obj, line_no))

    if not records:
        raise DatasetValidationError("line 1: empty file or no records found")

    if dataset_id is None:
        dataset_id = f"DS-{secrets.token_hex(4)}"

    if now is None:
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

    # Only write file and insert into DB after full validation succeeds
    INGEST_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = INGEST_DIR / f"{dataset_id}.jsonl"
    dest_path.write_bytes(source_bytes)

    with closing(db.get_connection()) as conn, conn:
        conn.execute(
            "INSERT INTO datasets (dataset_id, role, path, sha256, records, ingested_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (dataset_id, role, str(dest_path), sha256, len(records), now),
        )

    _RECORDS_CACHE[dataset_id] = records

    from sb.provenance import rag
    rag.build_index(dataset_id, records)

    return Dataset(
        dataset_id=dataset_id,
        role=role,
        path=str(dest_path),
        sha256=sha256,
        records=len(records),
        ingested_at=now,
    )


def get_dataset(dataset_id: str) -> Dataset | None:
    """Retrieve dataset metadata by dataset_id."""
    with closing(db.get_connection()) as conn:
        cursor = conn.execute(
            "SELECT dataset_id, role, path, sha256, records, ingested_at FROM datasets WHERE dataset_id = ?",
            (dataset_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return Dataset(
            dataset_id=row["dataset_id"],
            role=row["role"],
            path=row["path"],
            sha256=row["sha256"],
            records=row["records"],
            ingested_at=row["ingested_at"],
        )


def list_datasets() -> list[Dataset]:
    """List all datasets ordered by ingested_at ascending."""
    with closing(db.get_connection()) as conn:
        cursor = conn.execute(
            "SELECT dataset_id, role, path, sha256, records, ingested_at FROM datasets ORDER BY ingested_at ASC"
        )
        rows = cursor.fetchall()
        return [
            Dataset(
                dataset_id=r["dataset_id"],
                role=r["role"],
                path=r["path"],
                sha256=r["sha256"],
                records=r["records"],
                ingested_at=r["ingested_at"],
            )
            for r in rows
        ]


def latest(role: str) -> Dataset | None:
    """Return the newest dataset for the given role, or None if none exist."""
    if role not in ("target", "control"):
        raise ValueError(f"Invalid role: {role!r}. Role must be 'target' or 'control'.")

    with closing(db.get_connection()) as conn:
        cursor = conn.execute(
            "SELECT dataset_id, role, path, sha256, records, ingested_at FROM datasets WHERE role = ?",
            (role,),
        )
        rows = cursor.fetchall()
        if not rows:
            return None
        datasets = [
            Dataset(
                dataset_id=r["dataset_id"],
                role=r["role"],
                path=r["path"],
                sha256=r["sha256"],
                records=r["records"],
                ingested_at=r["ingested_at"],
            )
            for r in rows
        ]
        datasets.sort(key=lambda d: datetime.fromisoformat(d.ingested_at), reverse=True)
        return datasets[0]


def load_records(dataset_id: str) -> list[dict]:
    """Load records for dataset_id from cache or the stored file."""
    if dataset_id in _RECORDS_CACHE:
        return _RECORDS_CACHE[dataset_id]

    ds = get_dataset(dataset_id)
    if ds is None:
        raise KeyError(f"Dataset {dataset_id!r} not found in database.")

    dest_path = Path(ds.path)
    if not dest_path.is_file():
        raise FileNotFoundError(f"Dataset file not found at {dest_path}")

    records: list[dict] = []
    with dest_path.open("r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetValidationError(f"line {line_no}: invalid JSON: {exc}") from exc
            records.append(validate_record(obj, line_no))

    _RECORDS_CACHE[dataset_id] = records
    return records
