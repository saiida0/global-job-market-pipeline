from datetime import date, datetime, timezone

from src import run_log


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.current_query = ""
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.closed = True
        return False

    def execute(self, query, params=None):
        self.current_query = query
        self.executed.append((query, params))

    def fetchone(self):
        if "COUNT(*) AS total_jobs" in self.current_query:
            return (12, 5)
        return None

    def fetchall(self):
        if "COUNT(DISTINCT (jobs.source, jobs.source_id))" in self.current_query:
            return [("Python", 7), ("SQL", 4)]
        return []


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()
        self.commits = 0

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.commits += 1


def test_write_pipeline_run_records_success_row():
    connection = FakeConnection()
    started_at = datetime(2026, 11, 15, 8, tzinfo=timezone.utc)
    finished_at = datetime(2026, 11, 15, 8, 2, tzinfo=timezone.utc)

    run_log.write_pipeline_run(
        connection,
        started_at=started_at,
        finished_at=finished_at,
        status="success",
        jobs_fetched=10,
        jobs_cleaned=9,
        jobs_skipped=1,
        jobs_upserted=9,
        reused_snapshot=True,
    )

    query, params = connection.fake_cursor.executed[0]
    assert "INSERT INTO pipeline_runs" in query
    assert params == (
        started_at,
        finished_at,
        "success",
        10,
        9,
        1,
        9,
        True,
        None,
    )
    assert connection.commits == 1


def test_write_pipeline_run_records_failed_row():
    connection = FakeConnection()

    run_log.write_pipeline_run(
        connection,
        started_at=datetime(2026, 11, 15, 8, tzinfo=timezone.utc),
        finished_at=datetime(2026, 11, 15, 8, 1, tzinfo=timezone.utc),
        status="failed",
        jobs_fetched=3,
        error=RuntimeError("pipeline stopped"),
    )

    query, params = connection.fake_cursor.executed[0]
    assert "INSERT INTO pipeline_runs" in query
    assert params[2] == "failed"
    assert params[-1] == "Pipeline failed; see application logs."
    assert connection.commits == 1


def test_failed_run_error_message_never_persists_password():
    connection = FakeConnection()
    password = "db-password-sentinel"

    run_log.write_pipeline_run(
        connection,
        started_at=datetime(2026, 11, 15, 8, tzinfo=timezone.utc),
        finished_at=datetime(2026, 11, 15, 8, 1, tzinfo=timezone.utc),
        status="failed",
        error=RuntimeError(f"connection failed with password {password}"),
    )

    error_message = connection.fake_cursor.executed[0][1][-1]
    assert password not in error_message
    assert "password" not in error_message.lower()


def test_upsert_daily_stats_uses_conflicts_for_daily_keys():
    connection = FakeConnection()
    day = date(2026, 11, 15)

    result = run_log.upsert_daily_stats(connection, day)

    statements = [
        (query, params)
        for query, params in connection.fake_cursor.executed
    ]
    normalized_sql = [" ".join(query.split()) for query, _ in statements]

    assert result == {
        "total_jobs": 12,
        "jobs_with_salary": 5,
        "skills": 2,
    }
    assert any("ON CONFLICT (day) DO UPDATE" in query for query in normalized_sql)
    assert any(
        "DELETE FROM daily_skill_counts WHERE day = %s" in query
        for query in normalized_sql
    )
    skill_upserts = [
        params
        for query, params in statements
        if "INSERT INTO daily_skill_counts" in query
    ]
    assert skill_upserts == [(day, "Python", 7), (day, "SQL", 4)]
    assert all(
        "ON CONFLICT (day, skill) DO UPDATE" in query
        for query in normalized_sql
        if "INSERT INTO daily_skill_counts" in query
    )
    assert connection.commits == 1
