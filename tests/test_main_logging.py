import logging
from types import SimpleNamespace

from src import main as main_module


def test_main_logs_database_settings_without_password(monkeypatch, caplog):
    sentinel = "db-password-sentinel-never-log"
    monkeypatch.setattr(main_module, "setup_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        main_module,
        "config",
        SimpleNamespace(
            db_name="jobs_test",
            db_host="db.example.test",
            db_port=5432,
            db_user="pipeline_test",
            **{"db_password": sentinel},
        ),
    )
    monkeypatch.setattr(
        main_module,
        "fetch_remote_jobs",
        lambda: {
            "file_path": "raw.json",
            "job_count": 1,
            "fetched_at": "2026-10-23T12:00:00+00:00",
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
    caplog.set_level(logging.INFO, logger="src.main")

    main_module.main()

    assert sentinel not in caplog.text
    assert "jobs_test" in caplog.text
    assert "db.example.test" in caplog.text
    assert "pipeline_test" in caplog.text
