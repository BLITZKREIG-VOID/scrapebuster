"""Unit tests for dataset ingestion, validation, and storage."""

import hashlib
from pathlib import Path

import pytest
from sb.provenance import dataset
from sb.provenance import reset as provenance_reset
from sb.provenance.dataset import DatasetValidationError


def test_ingest_sample(sample_path: Path):
    """Ingest sample as target: verify record count, sha256, copied file, and DB queries."""
    file_bytes = sample_path.read_bytes()
    expected_sha256 = hashlib.sha256(file_bytes).hexdigest()

    ds = dataset.ingest(sample_path, role="target")

    assert ds.records == 8
    assert ds.sha256 == expected_sha256
    assert ds.role == "target"

    copy_path = dataset.INGEST_DIR / f"{ds.dataset_id}.jsonl"
    assert copy_path.is_file()
    assert copy_path.read_bytes() == file_bytes
    assert ds.path == str(copy_path)

    # Check database retrieval
    retrieved = dataset.get_dataset(ds.dataset_id)
    assert retrieved is not None
    assert retrieved == ds

    all_datasets = dataset.list_datasets()
    assert len(all_datasets) == 1
    assert all_datasets[0] == ds


def test_latest(sample_path: Path):
    """latest('target') returns newest ingest; latest('control') returns None when none."""
    assert dataset.latest("control") is None

    dataset.ingest(sample_path, role="target", now="2026-09-29T10:00:00Z")
    ds2 = dataset.ingest(sample_path, role="target", now="2026-09-29T11:00:00Z")

    latest_target = dataset.latest("target")
    assert latest_target is not None
    assert latest_target.dataset_id == ds2.dataset_id
    assert latest_target.ingested_at == "2026-09-29T11:00:00Z"


def test_invalid_role(sample_path: Path):
    """Invalid role raises ValueError in ingest and latest."""
    with pytest.raises(ValueError):
        dataset.ingest(sample_path, role="invalid_role")

    with pytest.raises(ValueError):
        dataset.latest("invalid_role")


@pytest.mark.parametrize(
    ("bad_content", "expected_line"),
    [
        (
            (
                '{"url": "http://1", "fetched_at": "2026-09-29T10:00:00Z", "title": "t", "text": "ok"}\n'
                "not a valid json string\n"
            ),
            "line 2",
        ),
        (
            (
                '{"url": "http://1", "fetched_at": "2026-09-29T10:00:00Z", "title": "t", "text": "ok"}\n'
                '{"url": "http://2", "fetched_at": "2026-09-29T10:00:00Z", "title": "t"}\n'
            ),
            "line 2",
        ),
        (
            '{"url": "http://1", "fetched_at": "2026-09-29T10:00:00Z", "title": 12345, "text": "ok"}\n',
            "line 1",
        ),
        (
            (
                '{"url": "http://1", "fetched_at": "2026-09-29T10:00:00Z", "title": "t1", "text": "ok"}\n'
                '{"url": "http://2", "fetched_at": "not-iso-timestamp", "title": "t2", "text": "ok"}\n'
            ),
            "line 2",
        ),
        (
            "",
            "line 1",
        ),
    ],
    ids=["non-JSON", "missing-text", "non-str-title", "bad-fetched-at", "empty-file"],
)
def test_validation_errors(tmp_path: Path, bad_content: str, expected_line: str):
    """Validation errors raise DatasetValidationError mentioning line number, with no DB row or file copy."""
    file_path = tmp_path / "test_dataset.jsonl"
    file_path.write_text(bad_content, encoding="utf-8")

    with pytest.raises(DatasetValidationError) as exc_info:
        dataset.ingest(file_path, role="target")

    assert expected_line in str(exc_info.value)
    # Ensure no DB row or copied file exists
    assert len(dataset.list_datasets()) == 0
    assert not any(dataset.INGEST_DIR.glob("*.jsonl"))


def test_load_records_reload_after_reset(sample_path: Path):
    """load_records after sb.provenance.reset() reloads from the copied file."""
    ds = dataset.ingest(sample_path, role="target")

    recs1 = dataset.load_records(ds.dataset_id)
    assert len(recs1) == 8

    # Reset caches
    provenance_reset()
    assert ds.dataset_id not in dataset._RECORDS_CACHE

    recs2 = dataset.load_records(ds.dataset_id)
    assert recs2 == recs1
    assert ds.dataset_id in dataset._RECORDS_CACHE
