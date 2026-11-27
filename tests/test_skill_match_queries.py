import pandas as pd

from dashboard import queries


class FakeCursor:
    def __init__(self, columns, rows):
        self.description = [(column,) for column in columns]
        self.rows = rows
        self.query = None
        self.parameters = None
        self.execute_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, parameters=()):
        self.query = query
        self.parameters = parameters
        self.execute_calls += 1

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, columns=(), rows=()):
        self.fake_cursor = FakeCursor(columns, rows)
        self.cursor_calls = 0

    def cursor(self):
        self.cursor_calls += 1
        return self.fake_cursor


def test_fetch_skill_options_returns_display_names_sorted_by_fake_demand():
    connection = FakeConnection(
        ["skill_name", "job_count"],
        [("Python", 8), ("AWS", 4), ("gcp", 1)],
    )

    result = queries.fetch_skill_options(connection)

    assert result.to_dict("records") == [
        {"skill_name": "Python", "display_name": "Python", "job_count": 8},
        {"skill_name": "AWS", "display_name": "AWS", "job_count": 4},
        {
            "skill_name": "gcp",
            "display_name": "Google Cloud Platform",
            "job_count": 1,
        },
    ]
    assert "FROM extracted_job_skills" in connection.fake_cursor.query
    assert "ORDER BY job_count DESC" in connection.fake_cursor.query


def test_fetch_skill_match_summary_uses_parameters_and_role_focus_aliases():
    connection = FakeConnection(
        ["tracked_jobs", "jobs_any", "jobs_all"],
        [(12, 6, 2)],
    )

    result = queries.fetch_skill_match_summary(
        connection, ["Python", "SQL"], "Tech and data roles"
    )

    assert result.to_dict("records") == [
        {"tracked_jobs": 12, "jobs_any": 6, "jobs_all": 2}
    ]
    assert connection.fake_cursor.parameters[0] == ["Python", "SQL"]
    assert connection.fake_cursor.parameters[1] is False
    assert "software engineering" in connection.fake_cursor.parameters[2]
    assert "data science & analytics" in connection.fake_cursor.parameters[2]
    assert connection.fake_cursor.parameters[-1] == 2
    assert "Python" not in connection.fake_cursor.query
    assert "= ANY(%s)" in connection.fake_cursor.query


def test_fetch_selected_skill_counts_returns_each_chosen_skill():
    connection = FakeConnection(
        ["skill_name", "job_count"],
        [("Python", 6), ("SQL", 2)],
    )

    result = queries.fetch_selected_skill_counts(
        connection, ["Python", "SQL"], "All roles"
    )

    assert result.to_dict("records") == [
        {"skill_name": "Python", "display_name": "Python", "job_count": 6},
        {"skill_name": "SQL", "display_name": "SQL", "job_count": 2},
    ]
    assert connection.fake_cursor.parameters[0] == ["Python", "SQL"]
    assert "WITH ORDINALITY" in connection.fake_cursor.query


def test_fetch_skills_to_learn_returns_counts_and_percent_of_any_matches():
    connection = FakeConnection(
        ["skill_name", "job_count", "percent_jobs"],
        [("gcp", 4, 66.7), ("AWS", 3, 50.0)],
    )

    result = queries.fetch_skills_to_learn(
        connection, ["Python"], "All roles"
    )

    assert result.to_dict("records") == [
        {
            "skill_name": "gcp",
            "display_name": "Google Cloud Platform",
            "job_count": 4,
            "percent_jobs": 66.7,
        },
        {
            "skill_name": "AWS",
            "display_name": "AWS",
            "job_count": 3,
            "percent_jobs": 50.0,
        },
    ]
    assert "LIMIT 10" in connection.fake_cursor.query
    assert connection.fake_cursor.parameters[0] == ["Python"]
    assert connection.fake_cursor.parameters[-1] == ["Python"]


def test_fetch_skill_match_salary_returns_median_and_sample_size():
    connection = FakeConnection(
        ["salary_job_count", "median_salary_usd"],
        [(12, 95_000.0)],
    )

    result = queries.fetch_skill_match_salary(connection, ["Python"])

    assert result.to_dict("records") == [
        {"salary_job_count": 12, "median_salary_usd": 95_000.0}
    ]
    assert "percentile_cont(0.5::DOUBLE PRECISION)" in connection.fake_cursor.query
    assert connection.fake_cursor.parameters[0] == ["Python"]


def test_fetch_skill_match_jobs_returns_source_and_original_link():
    connection = FakeConnection(
        ["source", "source_id", "title", "company_name", "url", "publication_date"],
        [
            (
                "jobicy",
                "42",
                "Data Engineer",
                "Contoso",
                "https://jobicy.com/jobs/42",
                pd.Timestamp("2026-11-25T12:00:00Z"),
            )
        ],
    )

    result = queries.fetch_skill_match_jobs(connection, ["Python"])

    assert result.iloc[0]["source"] == "jobicy"
    assert result.iloc[0]["url"] == "https://jobicy.com/jobs/42"
    assert "LIMIT 20" in connection.fake_cursor.query
    assert connection.fake_cursor.parameters[0] == ["Python"]


def test_empty_skill_selection_and_zero_match_cases_are_shaped():
    summary_columns = ["tracked_jobs", "jobs_any", "jobs_all"]
    summary_connection = FakeConnection(summary_columns, [(25, 0, 0)])
    summary = queries.fetch_skill_match_summary(summary_connection, [])
    assert summary.to_dict("records") == [
        {"tracked_jobs": 25, "jobs_any": 0, "jobs_all": 0}
    ]
    assert summary_connection.fake_cursor.parameters[0] == []

    no_match_summary = queries.fetch_skill_match_summary(
        FakeConnection(summary_columns, [(25, 0, 0)]), ["Not a tracked skill"]
    )
    assert no_match_summary.iloc[0]["jobs_any"] == 0
    assert no_match_summary.iloc[0]["jobs_all"] == 0

    unused_connection = FakeConnection()
    assert queries.fetch_selected_skill_counts(unused_connection, []).empty
    assert queries.fetch_skills_to_learn(unused_connection, []).empty
    salary = queries.fetch_skill_match_salary(unused_connection, [])
    assert salary.to_dict("records") == [
        {"salary_job_count": 0, "median_salary_usd": None}
    ]
    assert queries.fetch_skill_match_jobs(unused_connection, []).empty
    assert unused_connection.cursor_calls == 0

    zero_counts = queries.fetch_selected_skill_counts(
        FakeConnection(["skill_name", "job_count"], [("Python", 0)]), ["Python"]
    )
    assert zero_counts.iloc[0]["job_count"] == 0

    no_related_skills = queries.fetch_skills_to_learn(
        FakeConnection(["skill_name", "job_count", "percent_jobs"], []), ["Python"]
    )
    assert no_related_skills.empty

    no_salary = queries.fetch_skill_match_salary(
        FakeConnection(
            ["salary_job_count", "median_salary_usd"],
            [(0, None)],
        ),
        ["Python"],
    )
    assert no_salary.iloc[0]["salary_job_count"] == 0
    assert pd.isna(no_salary.iloc[0]["median_salary_usd"])

    no_jobs = queries.fetch_skill_match_jobs(
        FakeConnection(
            ["source", "source_id", "title", "company_name", "url", "publication_date"],
            [],
        ),
        ["Python"],
    )
    assert no_jobs.empty

    no_options = queries.fetch_skill_options(
        FakeConnection(["skill_name", "job_count"], [])
    )
    assert no_options.empty
    assert no_options.columns.tolist() == ["skill_name", "display_name", "job_count"]