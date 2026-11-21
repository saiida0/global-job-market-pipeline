from datetime import datetime, timezone

from src import load_jobs
from src.skill_extractor import EXTRACTOR_VERSION


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
        "extracted_skills": ["Python", "Apache Spark"],
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
    assert row[0:5] == ("remotive", "42", "Data Engineer", "Example Co", "Remote")
    assert row[5:9] == (100000, 120000, "yearly", "USD")
    assert row[9] == datetime(2026, 10, 20, 10, 30, tzinfo=timezone.utc)
    assert row[10] == datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    assert row[11:15] == (
        "Software",
        "full_time",
        ["Python", "SQL"],
        "https://example.test/jobs/42",
    )


def test_build_skill_rows_keeps_extracted_skills_separate_and_deduplicated():
    job = valid_job()
    job["extracted_skills"] = ["Python", "Python", " Apache Spark ", "python"]

    rows = load_jobs.build_skill_rows(
        [job, {"id": 3, "title": "Missing company", "extracted_skills": ["SQL"]}]
    )

    assert rows == [
        ("remotive", "42", "Python", EXTRACTOR_VERSION),
        ("remotive", "42", "Apache Spark", EXTRACTOR_VERSION),
    ]


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
    assert "ON CONFLICT (source, source_id) DO UPDATE" in captured["query"]


def test_upsert_jobs_replaces_extracted_skill_rows_idempotently(monkeypatch):
    operations = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params):
            operations.append(("execute", query, params))

    class FakeConnection:
        def __init__(self):
            self.commits = 0

        def cursor(self):
            return FakeCursor()

        def commit(self):
            self.commits += 1

    def fake_execute_values(cursor, query, rows):
        operations.append(("values", query, list(rows)))

    monkeypatch.setattr(load_jobs, "execute_values", fake_execute_values)
    job_rows, _ = load_jobs.build_rows([valid_job()])
    skill_rows = load_jobs.build_skill_rows([valid_job()])
    connection = FakeConnection()

    first_result = load_jobs.upsert_jobs(job_rows, connection, skill_rows)
    second_result = load_jobs.upsert_jobs(job_rows, connection, skill_rows)

    assert first_result == second_result == {"upserted": 1}
    assert connection.commits == 2
    deletes = [
        operation
        for operation in operations
        if operation[0] == "values"
        and "DELETE FROM extracted_job_skills" in operation[1]
    ]
    skill_inserts = [
        operation
        for operation in operations
        if operation[0] == "values"
        and "INSERT INTO extracted_job_skills" in operation[1]
    ]
    assert [operation[2] for operation in deletes] == [
        [("remotive", "42")],
        [("remotive", "42")],
    ]
    assert [operation[2] for operation in skill_inserts] == [skill_rows, skill_rows]
    assert all(
        "ON CONFLICT (source, source_id, skill_name) DO UPDATE" in operation[1]
        for operation in skill_inserts
    )
    for start in (0, 3):
        assert operations[start][0] == "values"
        assert operations[start + 1][0] == "values"
        assert operations[start + 2][0] == "values"


def test_same_id_from_different_sources_survives_upsert(monkeypatch):
    jobs = [
        valid_job(),
        {
            **valid_job(),
            "source": "greenhouse",
            "source_id": "42",
            "title": "Different Source Engineer",
        },
    ]
    rows, skipped = load_jobs.build_rows(jobs)
    stored_rows = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

    def fake_execute_values(cursor, query, values):
        if "INSERT INTO jobs" in query:
            for row in values:
                stored_rows[(row[0], row[1])] = row

    monkeypatch.setattr(load_jobs, "execute_values", fake_execute_values)

    result = load_jobs.upsert_jobs(rows, FakeConnection())

    assert skipped == 0
    assert result == {"upserted": 2}
    assert set(stored_rows) == {("remotive", "42"), ("greenhouse", "42")}


def test_parse_timestamp_returns_none_for_invalid_input():
    assert load_jobs.parse_timestamp("not-a-timestamp", "fetched_at") is None


def test_parse_timestamp_treats_naive_remotive_datetime_as_utc():
    timestamp = load_jobs.parse_timestamp(
        "2026-10-20T10:30:00", "publication_date"
    )

    assert timestamp == datetime(2026, 10, 20, 10, 30, tzinfo=timezone.utc)
