import pandas as pd
import pytest

from dashboard import queries


@pytest.fixture
def sample_jobs():
    return pd.DataFrame(
        [
            {
                "id": 1,
                "title": "Data Engineer",
                "company_name": "Northwind",
                "candidate_required_location": "Remote",
                "salary_min": 80_000,
                "salary_max": 100_000,
                "salary_type": "yearly",
                "currency": "USD",
                "publication_date": "2026-11-12T10:00:00Z",
                "updated_at": "2026-11-13T09:00:00Z",
                "category": "Engineering",
                "job_type": "full_time",
                "tags": ["Python", "AWS", "python"],
                "url": "https://remotive.com/remote-jobs/data-engineer-1",
            },
            {
                "id": 2,
                "title": "Analyst",
                "company_name": "Contoso",
                "candidate_required_location": "Europe",
                "salary_min": 60_000,
                "salary_max": None,
                "salary_type": "yearly",
                "currency": "USD",
                "publication_date": "2026-11-12T15:00:00Z",
                "updated_at": "2026-11-14T09:00:00Z",
                "category": "Data",
                "job_type": "contract",
                "tags": ["Python", "SQL"],
                "url": "https://remotive.com/remote-jobs/analyst-2",
            },
            {
                "id": 3,
                "title": "Designer",
                "company_name": "Fabrikam",
                "candidate_required_location": "Remote",
                "salary_min": 40,
                "salary_max": 60,
                "salary_type": "hourly",
                "currency": "USD",
                "publication_date": "2026-11-13T08:00:00Z",
                "updated_at": None,
                "category": "Design",
                "job_type": "full_time",
                "tags": [],
                "url": "https://remotive.com/remote-jobs/designer-3",
            },
            {
                "id": 4,
                "title": "Researcher",
                "company_name": "Adventure Works",
                "candidate_required_location": None,
                "salary_min": 70_000,
                "salary_max": 90_000,
                "salary_type": "yearly",
                "currency": "GBP",
                "publication_date": None,
                "updated_at": None,
                "category": None,
                "job_type": "contract",
                "tags": None,
                "url": "",
            },
        ]
    )


def test_filter_options_and_jobs_support_case_insensitive_values(sample_jobs):
    assert queries.filter_options(sample_jobs, "category") == [
        "Data",
        "Design",
        "Engineering",
    ]
    filtered = queries.filter_jobs(
        sample_jobs,
        category="engineering",
        job_type="FULL_TIME",
        location="remote",
    )
    assert filtered["id"].tolist() == [1]
    assert len(sample_jobs) == 4


def test_filter_options_reject_unknown_fields(sample_jobs):
    with pytest.raises(ValueError, match="Unsupported filter field"):
        queries.filter_options(sample_jobs, "company")


def test_summary_metrics_counts_salary_categories_and_latest_update(sample_jobs):
    metrics = queries.summary_metrics(sample_jobs)

    assert metrics["total_jobs"] == 4
    assert metrics["jobs_with_salary"] == 4
    assert metrics["category_count"] == 3
    assert metrics["most_recent_update"] == pd.Timestamp("2026-11-14T09:00:00Z")


def test_skills_counts_deduplicates_tags_per_job_and_ignores_empty_values(sample_jobs):
    counts = queries.skills_counts(sample_jobs).set_index("skill")["job_count"]

    assert counts.to_dict() == {"Python": 2, "AWS": 1, "SQL": 1}


def test_jobs_by_category_counts_missing_category(sample_jobs):
    counts = queries.jobs_by_category(sample_jobs).set_index("category")["job_count"]

    assert counts.to_dict() == {
        "Engineering": 1,
        "Data": 1,
        "Design": 1,
        "Uncategorized": 1,
    }


def test_salary_by_category_includes_only_yearly_usd(sample_jobs):
    salary = queries.salary_by_category(sample_jobs).set_index("category")[
        "median_salary_usd"
    ]

    assert salary.to_dict() == {"Engineering": 90_000.0, "Data": 60_000.0}
    assert "Design" not in salary.index
    assert "Uncategorized" not in salary.index


def test_postings_per_day_ignores_missing_dates(sample_jobs):
    postings = queries.postings_per_day(sample_jobs)

    assert postings.to_dict("records") == [
        {"publication_day": pd.Timestamp("2026-11-12").date(), "job_count": 2},
        {"publication_day": pd.Timestamp("2026-11-13").date(), "job_count": 1},
    ]


def test_jobs_table_formats_salary_and_keeps_original_link(sample_jobs):
    table = queries.jobs_table(sample_jobs)

    assert table.loc[0, "Salary range"] == "USD 80,000–100,000 yearly"
    assert table.loc[2, "Salary range"] == "USD 40–60 hourly"
    assert table.loc[0, "Original posting"].startswith("https://remotive.com/")
    assert table.loc[3, "Salary range"] == "GBP 70,000–90,000 yearly"


def test_empty_inputs_return_empty_shapes_and_zero_metrics():
    empty = pd.DataFrame()

    assert queries.filter_options(empty, "category") == []
    assert queries.filter_jobs(empty).empty
    assert queries.skills_counts(empty).empty
    assert list(queries.skills_counts(empty).columns) == ["skill", "job_count"]
    assert queries.jobs_by_category(empty).empty
    assert list(queries.jobs_by_category(empty).columns) == ["category", "job_count"]
    assert queries.salary_by_category(empty).empty
    assert list(queries.salary_by_category(empty).columns) == [
        "category",
        "median_salary_usd",
    ]
    assert queries.postings_per_day(empty).empty
    assert queries.jobs_table(empty).empty
    assert queries.summary_metrics(empty) == {
        "total_jobs": 0,
        "jobs_with_salary": 0,
        "category_count": 0,
        "most_recent_update": None,
    }
