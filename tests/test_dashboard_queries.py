import pandas as pd
import pytest

from dashboard import queries
from src.categories import normalize_category


@pytest.fixture
def sample_jobs():
    return pd.DataFrame(
        [
            {
                "source": "remotive",
                "source_id": "1",
                "title": "Data Engineer",
                "company_name": "Northwind",
                "candidate_required_location": "Remote",
                "salary_min": 80_000,
                "salary_max": 100_000,
                "salary_type": "yearly",
                "currency": "USD",
                "publication_date": "2026-11-12T10:00:00Z",
                "updated_at": "2026-11-13T09:00:00Z",
                "category": "Software Engineering",
                "job_type": "full_time",
                "tags": ["provider tag is not a skill"],
                "url": "https://remotive.com/remote-jobs/data-engineer-1",
            },
            {
                "source": "jobicy",
                "source_id": "1",
                "title": "Machine Learning Analyst",
                "company_name": "Contoso AI",
                "candidate_required_location": "Europe",
                "salary_min": None,
                "salary_max": None,
                "salary_type": None,
                "currency": None,
                "publication_date": "2026-11-13T10:00:00Z",
                "updated_at": "2026-11-14T09:00:00Z",
                "category": "Artificial Intelligence",
                "job_type": "contract",
                "tags": [],
                "url": "https://jobicy.com/jobs/1",
            },
            {
                "source": "remotive",
                "source_id": "2",
                "title": "Analyst",
                "company_name": "Fabrikam",
                "candidate_required_location": "Remote",
                "salary_min": 60_000,
                "salary_max": None,
                "salary_type": "yearly",
                "currency": "USD",
                "publication_date": "2026-11-14T15:00:00Z",
                "updated_at": "2026-11-15T09:00:00Z",
                "category": "Data Science & Analytics",
                "job_type": "full_time",
                "tags": ["provider tag is not a skill"],
                "url": "https://remotive.com/remote-jobs/analyst-2",
            },
            {
                "source": "jobicy",
                "source_id": "3",
                "title": "Designer",
                "company_name": "Adventure Works",
                "candidate_required_location": "Remote",
                "salary_min": 40,
                "salary_max": 60,
                "salary_type": "hourly",
                "currency": "USD",
                "publication_date": "2026-11-15T08:00:00Z",
                "updated_at": None,
                "category": "Web, UI & UX Design",
                "job_type": "full_time",
                "tags": [],
                "url": "https://jobicy.com/jobs/3",
            },
            {
                "source": "jobicy",
                "source_id": "4",
                "title": "Generalist",
                "company_name": "Tailspin",
                "candidate_required_location": None,
                "salary_min": None,
                "salary_max": None,
                "salary_type": None,
                "currency": None,
                "publication_date": None,
                "updated_at": None,
                "category": None,
                "job_type": "contract",
                "tags": None,
                "url": "https://jobicy.com/jobs/4",
            },
        ]
    )


@pytest.fixture
def extracted_skills():
    return pd.DataFrame(
        [
            {"source": "remotive", "source_id": "1", "skill_name": "Python"},
            {"source": "remotive", "source_id": "1", "skill_name": "AWS"},
            {"source": "remotive", "source_id": "1", "skill_name": "python"},
            {"source": "jobicy", "source_id": "1", "skill_name": "Python"},
            {"source": "jobicy", "source_id": "1", "skill_name": "SQL"},
            {"source": "jobicy", "source_id": "999", "skill_name": "Should not match"},
        ]
    )


def test_category_mapping_normalizes_both_sources_and_unknown_values():
    assert normalize_category("Software Engineering") == "Software Development"
    assert normalize_category("Data Science & Analytics") == "Data and Analytics"
    assert normalize_category("Artificial Intelligence") == "AI and Machine Learning"
    assert normalize_category("Marketing & Sales") == "Marketing"
    assert normalize_category(None) == "Other"
    assert normalize_category("unrecognized provider label") == "Other"


def test_filter_options_and_jobs_support_sources_and_case_insensitive_values(sample_jobs):
    assert queries.filter_options(sample_jobs, "source") == ["Jobicy", "Remotive"]
    assert queries.filter_options(sample_jobs, "category") == [
        "AI and Machine Learning",
        "Data and Analytics",
        "Design",
        "Other",
        "Software Development",
    ]
    filtered = queries.filter_jobs(
        sample_jobs,
        category="software development",
        job_type="FULL_TIME",
        location="remote",
        sources=["remotive"],
    )
    assert filtered["source_id"].tolist() == ["1"]
    assert len(sample_jobs) == 5


def test_same_source_id_from_two_sources_is_kept_as_two_jobs(sample_jobs):
    same_id = sample_jobs.loc[sample_jobs["source_id"] == "1"]

    assert len(same_id) == 2
    assert set(zip(same_id["source"], same_id["source_id"])) == {
        ("remotive", "1"),
        ("jobicy", "1"),
    }
    assert len(queries.filter_jobs(sample_jobs, sources=["Remotive", "Jobicy"])) == 5


def test_filter_options_reject_unknown_fields(sample_jobs):
    with pytest.raises(ValueError, match="Unsupported filter field"):
        queries.filter_options(sample_jobs, "company")


def test_search_matches_title_or_company_case_insensitively(sample_jobs):
    assert queries.search_jobs(sample_jobs, "MACHINE LEARNING")["source_id"].tolist() == [
        "1"
    ]
    assert queries.search_jobs(sample_jobs, "fabrikam")["title"].tolist() == ["Analyst"]
    assert len(queries.search_jobs(sample_jobs, "  ")) == 5


def test_summary_metrics_counts_salary_shared_categories_and_latest_update(sample_jobs):
    metrics = queries.summary_metrics(sample_jobs)

    assert metrics["total_jobs"] == 5
    assert metrics["jobs_with_salary"] == 3
    assert metrics["category_count"] == 5
    assert metrics["most_recent_update"] == pd.Timestamp("2026-11-15T09:00:00Z")


def test_skills_counts_uses_extracted_rows_and_composite_keys(sample_jobs, extracted_skills):
    counts = queries.skills_counts(sample_jobs, extracted_skills)

    assert counts.to_dict("records") == [
        {"skill": "Python", "job_count": 2},
        {"skill": "AWS", "job_count": 1},
        {"skill": "SQL", "job_count": 1},
    ]
    assert queries.tracked_skill_job_count(sample_jobs, extracted_skills) == 2
    assert queries.tracked_skill_job_count(
        queries.filter_jobs(sample_jobs, sources=["Remotive"]), extracted_skills
    ) == 1


def test_jobs_by_category_counts_shared_categories_including_missing(sample_jobs):
    counts = queries.jobs_by_category(sample_jobs).set_index("category")["job_count"]

    assert counts.to_dict() == {
        "AI and Machine Learning": 1,
        "Data and Analytics": 1,
        "Design": 1,
        "Other": 1,
        "Software Development": 1,
    }


def test_salary_by_category_includes_only_yearly_usd_and_reports_jobs_used(sample_jobs):
    salary = queries.salary_by_category(sample_jobs).set_index("category")[
        "median_salary_usd"
    ]

    assert salary.to_dict() == {
        "Software Development": 90_000.0,
        "Data and Analytics": 60_000.0,
    }
    assert "Design" not in salary.index
    assert "AI and Machine Learning" not in salary.index
    assert "Other" not in salary.index
    assert queries.salary_by_category(sample_jobs).attrs["jobs_used"] == 2


def test_postings_per_day_ignores_missing_dates(sample_jobs):
    postings = queries.postings_per_day(sample_jobs)

    assert postings.to_dict("records") == [
        {"publication_day": pd.Timestamp("2026-11-12").date(), "job_count": 1},
        {"publication_day": pd.Timestamp("2026-11-13").date(), "job_count": 1},
        {"publication_day": pd.Timestamp("2026-11-14").date(), "job_count": 1},
        {"publication_day": pd.Timestamp("2026-11-15").date(), "job_count": 1},
    ]


def test_jobs_table_has_source_link_and_sorts_newest_first(sample_jobs):
    table = queries.jobs_table(sample_jobs)

    assert table.columns.tolist() == [
        "Title",
        "Company",
        "Source",
        "Category",
        "Salary range",
        "Original posting",
    ]
    assert table["Title"].tolist() == [
        "Designer",
        "Analyst",
        "Machine Learning Analyst",
        "Data Engineer",
        "Generalist",
    ]
    assert table.loc[0, "Source"] == "Jobicy"
    assert table.loc[0, "Salary range"] == "USD 40–60 hourly"
    assert table.loc[1, "Salary range"] == "USD 60,000 yearly"
    assert table.loc[3, "Salary range"] == "USD 80,000–100,000 yearly"
    assert table.loc[0, "Original posting"] == "https://jobicy.com/jobs/3"


def test_pipeline_runs_table_shows_latest_first_and_handles_empty_table():
    runs = pd.DataFrame(
        [
            {
                "id": 1,
                "started_at": "2026-11-20T10:00:00Z",
                "finished_at": "2026-11-20T10:03:00Z",
                "status": "success",
                "jobs_fetched": 20,
                "jobs_cleaned": 18,
                "jobs_skipped": 2,
                "jobs_upserted": 18,
                "reused_snapshot": False,
            },
            {
                "id": 2,
                "started_at": "2026-11-21T10:00:00Z",
                "finished_at": "2026-11-21T10:02:00Z",
                "status": "failed",
                "jobs_fetched": 10,
                "jobs_cleaned": 9,
                "jobs_skipped": 1,
                "jobs_upserted": 0,
                "reused_snapshot": True,
            },
        ]
    )

    table = queries.pipeline_runs_table(runs)
    assert table.iloc[0]["Status"] == "failed"
    assert table.iloc[0]["Jobs fetched"] == 10
    assert table.iloc[0]["Jobs upserted"] == 0
    assert table.iloc[1]["Status"] == "success"
    assert queries.pipeline_runs_table(pd.DataFrame()).empty


def test_empty_inputs_return_empty_shapes_and_zero_metrics():
    empty = pd.DataFrame()

    assert queries.filter_options(empty, "category") == []
    assert queries.filter_options(empty, "source") == []
    assert queries.filter_jobs(empty).empty
    assert queries.search_jobs(empty, "anything").empty
    assert queries.skills_counts(empty, pd.DataFrame()).empty
    assert queries.tracked_skill_job_count(empty, pd.DataFrame()) == 0
    assert list(queries.skills_counts(empty).columns) == ["skill", "job_count"]
    assert queries.jobs_by_category(empty).empty
    assert list(queries.jobs_by_category(empty).columns) == ["category", "job_count"]
    assert queries.salary_by_category(empty).empty
    assert queries.salary_by_category(empty).attrs["jobs_used"] == 0
    assert list(queries.salary_by_category(empty).columns) == [
        "category",
        "median_salary_usd",
    ]
    assert queries.postings_per_day(empty).empty
    assert queries.jobs_table(empty).empty
    assert queries.pipeline_runs_table(empty).empty
    assert queries.summary_metrics(empty) == {
        "total_jobs": 0,
        "jobs_with_salary": 0,
        "category_count": 0,
        "most_recent_update": None,
    }
