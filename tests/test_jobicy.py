import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from src import jobicy


def fake_response(payload, *, status_code=200, headers=None):
    response = Mock()
    response.status_code = status_code
    response.headers = headers or {}
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def configure_output(monkeypatch, tmp_path):
    output_dir = tmp_path / "data" / "raw"
    monkeypatch.setattr(jobicy, "RAW_OUTPUT_DIR", output_dir)
    monkeypatch.setattr(
        jobicy,
        "PROCESSED_OUTPUT_FILE",
        tmp_path / "data" / "jobicy_jobs_latest.json",
    )
    fixed_time = datetime(2026, 11, 20, 12, 34, 56, tzinfo=timezone.utc)
    monkeypatch.setattr(jobicy, "get_utc_now", lambda: fixed_time)
    monkeypatch.delenv("FORCE_FETCH", raising=False)
    return output_dir, fixed_time


def raw_job(**changes):
    job = {
        "id": 123,
        "url": "https://jobicy.test/jobs/123",
        "jobTitle": "Python Engineer",
        "companyName": "Example Co",
        "jobIndustry": ["Engineering", "Data"],
        "jobType": ["Full-time", "Remote"],
        "jobGeo": "Remote",
        "jobLevel": "Senior",
        "jobDescription": "<p>Build with Python and <strong>SQL</strong>.</p>",
        "pubDate": "2026-11-19T10:30:00+00:00",
        "salaryMin": 6000,
        "salaryMax": 8000,
        "salaryCurrency": "EUR",
        "salaryPeriod": "monthly",
    }
    job.update(changes)
    return job


def test_fetch_paginates_until_next_cursor_is_null(monkeypatch, tmp_path):
    output_dir, fixed_time = configure_output(monkeypatch, tmp_path)
    get_mock = Mock(
        side_effect=[
            fake_response({"jobs": [{"id": 1}], "nextCursor": "cursor-2"}),
            fake_response({"jobs": [{"id": 2}], "nextCursor": None}),
        ]
    )
    sleep_mock = Mock()
    monkeypatch.setattr(jobicy.requests, "get", get_mock)
    monkeypatch.setattr(jobicy.time, "sleep", sleep_mock)

    result = jobicy.fetch_jobs()

    assert result["job_count"] == 2
    assert result["reused"] is False
    assert len(get_mock.call_args_list) == 2
    assert get_mock.call_args_list[0].kwargs["params"] == {"count": 100}
    assert get_mock.call_args_list[1].kwargs["params"] == {
        "count": 100,
        "cursor": "cursor-2",
    }
    assert all(
        call.kwargs["timeout"] == 30 for call in get_mock.call_args_list
    )
    sleep_mock.assert_called_once_with(1.5)

    snapshot = Path(result["file_path"])
    assert snapshot.parent == output_dir
    assert snapshot.name == "jobicy_jobs_20261120_123456.json"
    saved = json.loads(snapshot.read_text(encoding="utf-8"))
    assert saved["_metadata"]["source"] == "jobicy"
    assert saved["_metadata"]["fetched_at"] == fixed_time.isoformat()
    assert saved["jobs"][0]["fetched_at"] == fixed_time.isoformat()


def test_fetch_stops_at_twenty_page_cap_and_logs_warning(
    monkeypatch, tmp_path, caplog
):
    output_dir, _ = configure_output(monkeypatch, tmp_path)
    caplog.set_level(logging.INFO, logger=jobicy.__name__)
    responses = [
        fake_response(
            {"jobs": [{"id": page}], "nextCursor": f"cursor-{page + 1}"}
        )
        for page in range(1, jobicy.MAX_PAGES + 1)
    ]
    get_mock = Mock(side_effect=responses)
    sleep_mock = Mock()
    monkeypatch.setattr(jobicy.requests, "get", get_mock)
    monkeypatch.setattr(jobicy.time, "sleep", sleep_mock)

    result = jobicy.fetch_jobs()

    assert result["job_count"] == 20
    assert get_mock.call_count == 20
    assert sleep_mock.call_count == 19
    assert all(call.args == (1.5,) for call in sleep_mock.call_args_list)
    assert "Fetched 20 Jobicy pages." in caplog.text
    assert "page cap of 20 reached" in caplog.text

    saved = json.loads(Path(result["file_path"]).read_text(encoding="utf-8"))
    assert saved["_metadata"]["page_count"] == 20
    assert saved["_metadata"]["job_count"] == 20
    assert Path(result["file_path"]).parent == output_dir

@pytest.mark.parametrize("status_code", [429, 503])
def test_fetch_retries_rate_limit_and_unavailable_responses(
    monkeypatch, tmp_path, status_code
):
    configure_output(monkeypatch, tmp_path)
    get_mock = Mock(
        side_effect=[
            fake_response(
                {}, status_code=status_code, headers={"Retry-After": "2"}
            ),
            fake_response({"jobs": [{"id": 10}], "nextCursor": None}),
        ]
    )
    sleep_mock = Mock()
    monkeypatch.setattr(jobicy.requests, "get", get_mock)
    monkeypatch.setattr(jobicy.time, "sleep", sleep_mock)

    result = jobicy.fetch_jobs()

    assert result["job_count"] == 1
    assert get_mock.call_count == 2
    assert get_mock.call_args_list[0].kwargs["params"] == (
        get_mock.call_args_list[1].kwargs["params"]
    )
    sleep_mock.assert_called_once_with(2.0)


def test_clean_job_maps_jobicy_fields_and_salary_period():
    cleaned = jobicy.clean_job(raw_job())

    assert cleaned is not None
    data = cleaned.to_dict()
    assert data["source"] == "jobicy"
    assert data["source_id"] == "123"
    assert data["category"] == "Engineering"
    assert data["job_type"] == "Full-time"
    assert data["location"] == "Remote"
    assert data["tags"] == []
    assert data["salary_min"] == 6000
    assert data["salary_max"] == 8000
    assert data["salary_type"] == "monthly"
    assert data["currency"] == "EUR"
    assert "Python" in data["extracted_skills"]
    assert "jobDescription" not in data


def test_clean_job_decodes_html_entities_in_display_fields():
    cleaned = jobicy.clean_job(
        raw_job(
            jobTitle="Python &#038; SQL Engineer",
            companyName="Zone &#038; Co",
            jobIndustry=["Data &#038; Analytics"],
            jobType=["Full&#45;time"],
            jobGeo="Europe &#038; Remote",
        )
    )

    assert cleaned is not None
    data = cleaned.to_dict()
    assert data["title"] == "Python & SQL Engineer"
    assert data["company"] == "Zone & Co"
    assert data["category"] == "Data & Analytics"
    assert data["job_type"] == "Full-time"
    assert data["location"] == "Europe & Remote"


def test_clean_job_without_salary_keeps_salary_null():
    cleaned = jobicy.clean_job(
        raw_job(
            salaryMin=None,
            salaryMax=None,
            salaryCurrency=None,
            salaryPeriod=None,
        )
    )

    assert cleaned is not None
    assert cleaned.salary is None
    assert cleaned.to_dict()["salary_min"] is None
    assert cleaned.to_dict()["salary_max"] is None


def test_description_is_stripped_before_skill_extraction_and_not_cleaned_to_disk(
    monkeypatch, tmp_path
):
    output_dir, _ = configure_output(monkeypatch, tmp_path)
    description = "<p>Build with Python and <strong>SQL</strong>.</p>"
    raw_path = output_dir / "fixture.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        json.dumps({"jobs": [raw_job(jobDescription=description)]}),
        encoding="utf-8",
    )

    original_extract = jobicy.extract_skills
    observed = {}

    def capture_description(*, description, title):
        observed["description"] = description
        return original_extract(description=description, title=title)

    monkeypatch.setattr(jobicy, "extract_skills", capture_description)
    result = jobicy.clean_jobs(raw_path)

    assert "<" not in observed["description"]
    assert ">" not in observed["description"]
    cleaned_json = Path(result["file_path"]).read_text(encoding="utf-8")
    assert "jobDescription" not in cleaned_json
    assert description not in cleaned_json
    assert "Python" in json.loads(cleaned_json)[0]["extracted_skills"]


def test_fetch_reuses_recent_jobicy_snapshot_unless_forced(monkeypatch, tmp_path):
    output_dir, fixed_time = configure_output(monkeypatch, tmp_path)
    output_dir.mkdir(parents=True)
    snapshot = output_dir / "jobicy_jobs_20261120_100000.json"
    snapshot.write_text(
        json.dumps(
            {
                "jobs": [{"id": 1}],
                "_metadata": {"fetched_at": "2026-11-20T10:00:00+00:00"},
            }
        ),
        encoding="utf-8",
    )
    timestamp = (fixed_time - timedelta(hours=2)).timestamp()
    os.utime(snapshot, (timestamp, timestamp))
    get_mock = Mock()
    monkeypatch.setattr(jobicy.requests, "get", get_mock)

    result = jobicy.fetch_jobs()

    assert result == {
        "file_path": str(snapshot),
        "job_count": 1,
        "fetched_at": "2026-11-20T10:00:00+00:00",
        "reused": True,
    }
    get_mock.assert_not_called()
