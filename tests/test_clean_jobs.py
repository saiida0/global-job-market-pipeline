import pytest

from src.clean_jobs import SalaryParser, clean_job
from src.schemas import CleanedJob, SalaryRange
from src.validators import (
    ValidationError,
    validate_int,
    validate_list,
    validate_string,
)


@pytest.mark.parametrize(
    "salary_text,min_value,max_value,currency,frequency",
    [
        ("$30-$35/hour", 30, 35, "USD", "hourly"),
        ("$40- $60k", 40_000, 60_000, "USD", "yearly"),
        ("\u00a350k-\u00a375k", 50_000, 75_000, "GBP", "yearly"),
        ("$31,2k- $52k", 31_200, 52_000, "USD", "yearly"),
        ("\u20ac4k-\u20ac6k/month", 4_000, 6_000, "EUR", "monthly"),
    ],
)
def test_salary_parser_valid_formats(
    salary_text,
    min_value,
    max_value,
    currency,
    frequency,
):
    salary = SalaryParser.parse(salary_text)

    assert salary == SalaryRange(min_value, max_value, currency, frequency)


@pytest.mark.parametrize("salary_text", [None, "", "-", "bonus only", "up to 20%"])
def test_salary_parser_invalid_input_returns_none(salary_text):
    assert SalaryParser.parse(salary_text) is None


def test_salary_range_normalizes_hourly_to_yearly_usd():
    salary = SalaryRange(30, 35, "USD", "hourly")

    assert salary.normalize_to_yearly_usd() == (62_400, 72_800)


def test_salary_range_normalizes_gbp_yearly_to_usd():
    salary = SalaryRange(50_000, 75_000, "GBP", "yearly")

    assert salary.normalize_to_yearly_usd() == (63_500, 95_250)


def test_salary_range_normalizes_eur_monthly_to_usd():
    salary = SalaryRange(4_000, 5_000, "EUR", "monthly")

    assert salary.normalize_to_yearly_usd() == (52_800, 66_000)


def test_salary_range_rejects_invalid_bounds():
    with pytest.raises(ValueError):
        SalaryRange(600, 700, "USD", "hourly")

    with pytest.raises(ValueError):
        SalaryRange(70_000, 60_000, "USD", "yearly")


def test_validate_string_handles_expected_values():
    assert validate_string("  engineer  ", "title") == "engineer"
    assert validate_string(123, "external_id") == "123"
    assert validate_string(None, "optional", allow_empty=True) is None


def test_validate_string_rejects_invalid_values():
    with pytest.raises(ValidationError):
        validate_string(None, "title")

    with pytest.raises(ValidationError):
        validate_string(["engineer"], "title")


def test_validate_list_handles_none_string_and_mixed_list():
    assert validate_list(None, "tags") == []
    assert validate_list("Python", "tags") == ["Python"]
    assert validate_list(["Python", 1, "  AWS  ", ""], "tags") == ["Python", "AWS"]


def test_validate_list_rejects_unexpected_type():
    with pytest.raises(ValidationError):
        validate_list({"tag": "python"}, "tags")


def test_validate_int_handles_valid_values():
    assert validate_int(None, "id") is None
    assert validate_int("123", "id", min_val=1) == 123
    assert validate_int(123.0, "id", min_val=1) == 123


def test_validate_int_rejects_invalid_values():
    with pytest.raises(ValidationError):
        validate_int("abc", "id")

    with pytest.raises(ValidationError):
        validate_int(0, "id", min_val=1)


def test_cleaned_job_valid_creation():
    job = CleanedJob(
        id=12345,
        title=" Software Engineer ",
        company="TechCorp",
        salary=SalaryRange(40_000, 60_000, "USD", "yearly"),
        tags=[" Python ", "AWS"],
    )

    assert job.id == 12345
    assert job.source == "remotive"
    assert job.source_id == "12345"
    assert job.title == "Software Engineer"
    assert job.company == "TechCorp"
    assert job.tags == ["python", "aws"]


def test_clean_job_extracts_skills_without_storing_description_or_changing_tags():
    raw_job = {
        "id": 12345,
        "title": "Excel and Python Engineer",
        "company_name": "TechCorp",
        "description": "<p>Build services with AWS and JavaScript.</p>",
        "tags": ["Python", "Custom Tag"],
    }

    job = clean_job(raw_job)

    assert job is not None
    assert job.extracted_skills == ["Python", "JavaScript", "AWS", "Excel"]
    assert job.tags == ["python", "custom tag"]
    assert "description" not in job.to_dict()
    assert job.to_dict()["extracted_skills"] == job.extracted_skills


def test_clean_job_decodes_html_entities_in_display_fields():
    job = clean_job(
        {
            "id": 12348,
            "title": "Python &#038; SQL Engineer",
            "company_name": "Zone &#038; Co",
            "category": "Data &#038; Analytics",
            "job_type": "Full&#45;time",
            "candidate_required_location": "Europe &#038; Remote",
            "description": "Build Python &#038; SQL services.",
        }
    )

    assert job is not None
    data = job.to_dict()
    assert data["title"] == "Python & SQL Engineer"
    assert data["company"] == "Zone & Co"
    assert data["category"] == "Data & Analytics"
    assert data["job_type"] == "Full-time"
    assert data["location"] == "Europe & Remote"
    assert "Python" in data["extracted_skills"]

def test_clean_job_handles_missing_description_and_extracts_from_title():
    job = clean_job(
        {
            "id": 12346,
            "title": "Kubernetes Engineer",
            "company_name": "TechCorp",
        }
    )

    assert job is not None
    assert job.extracted_skills == ["Kubernetes"]
    assert job.tags == []


def test_clean_job_with_no_matching_title_or_description_has_no_extracted_skills():
    job = clean_job(
        {
            "id": 12347,
            "title": "Generalist",
            "company_name": "TechCorp",
            "description": "",
        }
    )

    assert job is not None
    assert job.extracted_skills == []


def test_cleaned_job_rejects_missing_required_fields():
    with pytest.raises(ValueError):
        CleanedJob(id=12345, title="", company="TechCorp")

    with pytest.raises(ValueError):
        CleanedJob(id=12345, title="Engineer", company=None)

    with pytest.raises(ValueError):
        CleanedJob(id=None, title="Engineer", company="TechCorp")
