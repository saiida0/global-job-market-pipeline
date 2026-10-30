import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from src import fetch_jobs


def make_response(payload=None, json_error=None):
    response = Mock()
    response.raise_for_status.return_value = None
    if json_error is not None:
        response.json.side_effect = json_error
    else:
        response.json.return_value = payload
    return response


def configure_output(monkeypatch, tmp_path):
    output_dir = tmp_path / "data" / "raw"
    monkeypatch.setattr(fetch_jobs, "RAW_OUTPUT_DIR", output_dir)
    fixed_time = datetime(2026, 10, 23, 12, 34, 56, tzinfo=timezone.utc)
    monkeypatch.setattr(fetch_jobs, "get_utc_now", lambda: fixed_time)
    monkeypatch.delenv("FORCE_FETCH", raising=False)
    return output_dir, fixed_time


def add_snapshot(output_dir, name, modified_at, data=None):
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = output_dir / name
    snapshot.write_text(json.dumps(data or {}), encoding="utf-8")
    timestamp = modified_at.timestamp()
    os.utime(snapshot, (timestamp, timestamp))
    return snapshot


def test_fetch_success_writes_timestamped_snapshot(monkeypatch, tmp_path, caplog):
    output_dir, fixed_time = configure_output(monkeypatch, tmp_path)
    response = make_response({"jobs": [{"id": 123, "title": "Engineer"}]})
    get_mock = Mock(return_value=response)
    monkeypatch.setattr(fetch_jobs.requests, "get", get_mock)

    with caplog.at_level(logging.INFO):
        result = fetch_jobs.fetch_remote_jobs()

    assert set(result) == {"file_path", "job_count", "fetched_at", "reused"}
    assert result["job_count"] == 1
    assert result["fetched_at"] == fixed_time.isoformat()
    assert result["reused"] is False
    assert "No raw snapshots found; fetching live" in caplog.text
    snapshot = Path(result["file_path"])
    assert snapshot.parent == output_dir
    assert re.fullmatch(r"remotive_jobs_\d{8}_\d{6}\.json", snapshot.name)
    assert snapshot.is_file()
    saved = json.loads(snapshot.read_text(encoding="utf-8"))
    assert saved["jobs"][0]["id"] == 123
    assert saved["jobs"][0]["fetched_at"] == fixed_time.isoformat()
    assert saved["_metadata"]["job_count"] == 1
    get_mock.assert_called_once_with(
        fetch_jobs.API_URL,
        timeout=fetch_jobs.REQUEST_TIMEOUT,
    )


def test_fetch_retries_then_succeeds(monkeypatch, tmp_path):
    configure_output(monkeypatch, tmp_path)
    response = make_response({"jobs": [{"id": 1}]})
    get_mock = Mock(side_effect=[requests.ConnectionError("temporary"), response])
    sleep_mock = Mock()
    monkeypatch.setattr(fetch_jobs.requests, "get", get_mock)
    monkeypatch.setattr(fetch_jobs.time, "sleep", sleep_mock)

    result = fetch_jobs.fetch_remote_jobs()

    assert result["job_count"] == 1
    assert result["reused"] is False
    assert get_mock.call_count == 2
    sleep_mock.assert_called_once_with(fetch_jobs.RETRY_DELAY)
    assert all(
        call.kwargs["timeout"] == fetch_jobs.REQUEST_TIMEOUT
        for call in get_mock.call_args_list
    )


def test_fetch_raises_runtime_error_after_all_retries(monkeypatch, tmp_path):
    configure_output(monkeypatch, tmp_path)
    get_mock = Mock(side_effect=requests.ConnectionError("offline"))
    sleep_mock = Mock()
    monkeypatch.setattr(fetch_jobs.requests, "get", get_mock)
    monkeypatch.setattr(fetch_jobs.time, "sleep", sleep_mock)

    with pytest.raises(RuntimeError, match="All 3 attempts"):
        fetch_jobs.fetch_remote_jobs()

    assert get_mock.call_count == fetch_jobs.MAX_RETRIES
    assert sleep_mock.call_count == fetch_jobs.MAX_RETRIES - 1


def test_fetch_rejects_zero_jobs(monkeypatch, tmp_path):
    output_dir, _ = configure_output(monkeypatch, tmp_path)
    monkeypatch.setattr(
        fetch_jobs.requests,
        "get",
        Mock(return_value=make_response({"jobs": []})),
    )

    with pytest.raises(ValueError, match="zero jobs"):
        fetch_jobs.fetch_remote_jobs()

    assert not list(output_dir.glob("*.json"))


def test_fetch_rejects_missing_or_invalid_jobs_list(monkeypatch, tmp_path):
    configure_output(monkeypatch, tmp_path)
    monkeypatch.setattr(
        fetch_jobs.requests,
        "get",
        Mock(return_value=make_response({"jobs": "not a list"})),
    )

    with pytest.raises(ValueError, match="'jobs' must be a list"):
        fetch_jobs.fetch_remote_jobs()


def test_fetch_rejects_invalid_json(monkeypatch, tmp_path):
    configure_output(monkeypatch, tmp_path)
    monkeypatch.setattr(
        fetch_jobs.requests,
        "get",
        Mock(return_value=make_response(json_error=ValueError("malformed"))),
    )

    with pytest.raises(ValueError, match="Invalid JSON"):
        fetch_jobs.fetch_remote_jobs()


def test_fetch_reuses_newest_snapshot_under_six_hours(monkeypatch, tmp_path, caplog):
    output_dir, fixed_time = configure_output(monkeypatch, tmp_path)
    add_snapshot(
        output_dir,
        "remotive_jobs_20261023_053456.json",
        fixed_time - timedelta(hours=7),
        {"jobs": [{"id": 1}]},
    )
    newest_snapshot = add_snapshot(
        output_dir,
        "remotive_jobs_20261023_063556.json",
        fixed_time - timedelta(hours=5, minutes=59),
        {
            "jobs": [{"id": 21}, {"id": 22}],
            "_metadata": {
                "fetched_at": "2026-10-23T06:35:56+00:00",
                "job_count": 2,
            },
        },
    )
    get_mock = Mock()
    monkeypatch.setattr(fetch_jobs.requests, "get", get_mock)

    with caplog.at_level(logging.INFO):
        result = fetch_jobs.fetch_remote_jobs()

    assert result == {
        "file_path": str(newest_snapshot),
        "job_count": 2,
        "fetched_at": "2026-10-23T06:35:56+00:00",
        "reused": True,
    }
    assert "Reusing recent raw snapshot" in caplog.text
    get_mock.assert_not_called()


def test_force_fetch_overrides_recent_snapshot_guard(monkeypatch, tmp_path, caplog):
    output_dir, fixed_time = configure_output(monkeypatch, tmp_path)
    add_snapshot(
        output_dir,
        "remotive_jobs_20261023_113456.json",
        fixed_time - timedelta(hours=1),
        {"jobs": [{"id": 5}]},
    )
    monkeypatch.setenv("FORCE_FETCH", "true")
    get_mock = Mock(return_value=make_response({"jobs": [{"id": 42}]}))
    monkeypatch.setattr(fetch_jobs.requests, "get", get_mock)

    with caplog.at_level(logging.INFO):
        result = fetch_jobs.fetch_remote_jobs()

    get_mock.assert_called_once_with(
        fetch_jobs.API_URL,
        timeout=fetch_jobs.REQUEST_TIMEOUT,
    )
    assert result["reused"] is False
    assert Path(result["file_path"]).name == "remotive_jobs_20261023_123456.json"
    assert "forcing a live remotive fetch" in caplog.text.lower()