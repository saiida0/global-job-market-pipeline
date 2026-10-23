from datetime import datetime, timezone

from src import load_jobs


def valid_job():
    return {
        "id": 42,
        "title": "Data Engineer",
        "company": "Example Co",
        "location": "Remote",
        "salary_min": 100000,
        "salary_max": 120000,
        "salary_type": "yearly",
        "currency": "USD",
        "publication_date": "2026-10-20T10:30:00Z",
        "fetched_at": "2026-10-23T12:00:00+00:00",
        "category": "Software",
        "job_type": "full_time",
        "tags": ["Python", "SQL"],
        "url": "https://example.test/jobs/42",
    }


def test_build_rows_column_order_and_skipped_required_fields():
    rows, skipped = load_jobs.build_rows(
        [
            valid_job(),
            {"title": "Missing id", "company": "Example Co"},
            {"id": 2, "company": "Example Co"},
            {"id": 3, "title": "Missing company"},
        ]
    )

    assert skipped == 3
    assert len(rows) == 1
    row = rows[0]
    assert len(row) == 15
    assert row[0:4] == (42, "Data Engineer", "Example Co", "Remote")
    assert row[4:8] == (100000, 120000, "yearly", "USD")
    assert row[8] == datetime(2026, 10, 20, 10, 30, tzinfo=timezone.utc)
    assert row[9] == datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    assert row[10:15] == (
        "remotive",
        "Software",
        "full_time",
        ["Python", "SQL"],
        "https://example.test/jobs/42",
    )


def test_upsert_jobs_uses_fake_connection(monkeypatch):
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    class FakeConnection:
        def __init__(self):
            self.commits = 0
            self.cursor_calls = 0

        def cursor(self):
            self.cursor_calls += 1
            return FakeCursor()

        def commit(self):
            self.commits += 1

    captured = {}

    def fake_execute_values(cursor, query, rows):
        captured["cursor"] = cursor
        captured["query"] = query
        captured["rows"] = rows

    monkeypatch.setattr(load_jobs, "execute_values", fake_execute_values)
    connection = FakeConnection()
    rows = [tuple(range(15))]

    result = load_jobs.upsert_jobs(rows, connection)

    assert result == {"upserted": 1}
    assert connection.cursor_calls == 1
    assert connection.commits == 1
    assert captured["rows"] == rows
    assert "INSERT INTO jobs" in captured["query"]
    assert "ON CONFLICT (id) DO UPDATE" in captured["query"]


def test_parse_timestamp_returns_none_for_invalid_input():
    assert load_jobs.parse_timestamp("not-a-timestamp", "fetched_at") is None
