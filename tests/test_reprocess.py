import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from src import reprocess


def add_snapshot(raw_dir, name, modified_at):
    raw_dir.mkdir(parents=True, exist_ok=True)
    snapshot = raw_dir / name
    snapshot.write_text("{}", encoding="utf-8")
    timestamp = modified_at.timestamp()
    os.utime(snapshot, (timestamp, timestamp))
    return snapshot


def test_reprocess_uses_newest_snapshot_and_loads_cleaned_file(
    monkeypatch, tmp_path
):
    raw_dir = tmp_path / "data" / "raw"
    earlier = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)
    newest = datetime(2026, 10, 21, 8, tzinfo=timezone.utc)
    add_snapshot(raw_dir, "remotive_jobs_20261020_080000.json", earlier)
    newest_snapshot = add_snapshot(raw_dir, "remotive_jobs_20261021_080000.json", newest)
    monkeypatch.setattr(reprocess, "RAW_OUTPUT_DIR", raw_dir)

    cleaned_path = tmp_path / "jobs_cleaned.json"
    clean_mock = Mock(return_value={"file_path": str(cleaned_path), "total": 3})
    load_mock = Mock(return_value={"upserted": 3, "skipped": 0})
    monkeypatch.setattr(reprocess, "clean_jobs", clean_mock)
    monkeypatch.setattr(reprocess, "load_jobs", load_mock)

    result = reprocess.main()

    assert result == 0
    clean_mock.assert_called_once_with(str(newest_snapshot))
    load_mock.assert_called_once_with(str(cleaned_path))


def test_reprocess_without_snapshot_returns_nonzero_and_clear_message(
    monkeypatch, tmp_path, capsys
):
    raw_dir = tmp_path / "data" / "raw"
    monkeypatch.setattr(reprocess, "RAW_OUTPUT_DIR", raw_dir)
    clean_mock = Mock()
    load_mock = Mock()
    monkeypatch.setattr(reprocess, "clean_jobs", clean_mock)
    monkeypatch.setattr(reprocess, "load_jobs", load_mock)

    result = reprocess.main()

    captured = capsys.readouterr()
    assert result == 1
    assert "No Remotive snapshots found" in captured.err
    assert "python -m src.main" in captured.err
    clean_mock.assert_not_called()
    load_mock.assert_not_called()