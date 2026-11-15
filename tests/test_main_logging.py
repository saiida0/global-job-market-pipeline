import logging
from types import SimpleNamespace

import pytest

from src import main as main_module


def set_safe_test_config(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "config",
        SimpleNamespace(
            db_name="jobs_test",
            db_host="db.example.test",
            db_port=5432,
            db_user="pipeline_test",
            db_password="db-password-sentinel-never-log",
        ),
    )


def test_main_logs_database_settings_without_password(monkeypatch, caplog):
    set_safe_test_config(monkeypatch)
    monkeypatch.setattr(main_module, "setup_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        main_module,
        "fetch_remote_jobs",
        lambda: {
            "file_path": "raw.json",
            "job_count": 1,
            "fetched_at": "2026-10-23T12:00:00+00:00",
            "reused": False,
        },
    )
    monkeypatch.setattr(
        main_module,
        "clean_jobs",
        lambda file_path: {
            "file_path": "processed.json",
            "total": 1,
            "with_salary": 0,
            "without_salary": 1,
            "skipped": 0,
        },
    )
    monkeypatch.setattr(
        main_module,
        "load_jobs",
        lambda file_path: {"upserted": 1, "skipped": 0},
    )
    monkeypatch.setattr(main_module, "record_daily_stats", lambda day: {})
    recorded_runs = []
    monkeypatch.setattr(
        main_module,
        "record_pipeline_run",
        lambda **fields: recorded_runs.append(fields),
    )
    caplog.set_level(logging.INFO, logger="src.main")

    main_module.main()

    assert "db-password-sentinel-never-log" not in caplog.text
    assert "jobs_test" in caplog.text
    assert "db.example.test" in caplog.text
    assert "pipeline_test" in caplog.text
    assert len(recorded_runs) == 1
    assert recorded_runs[0]["status"] == "success"
    assert recorded_runs[0]["jobs_fetched"] == 1
    assert recorded_runs[0]["jobs_cleaned"] == 1
    assert recorded_runs[0]["jobs_upserted"] == 1


def test_pipeline_error_survives_failure_to_write_run_record(monkeypatch):
    set_safe_test_config(monkeypatch)
    monkeypatch.setattr(main_module, "setup_logging", lambda **kwargs: None)
    pipeline_error = RuntimeError("original pipeline error")
    recorded_runs = []

    def fail_fetch():
        raise pipeline_error

    def fail_record(**fields):
        recorded_runs.append(fields)
        raise OSError("run log unavailable")

    monkeypatch.setattr(main_module, "fetch_remote_jobs", fail_fetch)
    monkeypatch.setattr(main_module, "record_pipeline_run", fail_record)
    monkeypatch.setattr(
        main_module,
        "record_daily_stats",
        lambda day: pytest.fail("daily stats should not run before a successful load"),
    )

    with pytest.raises(RuntimeError) as raised:
        main_module.main()

    assert raised.value is pipeline_error
    assert recorded_runs[0]["status"] == "failed"
    assert recorded_runs[0]["error"] is pipeline_error
