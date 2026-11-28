import inspect
import re

import pandas as pd
import pytest

from dashboard import insights
from dashboard.insight_format import add_selected_source


@pytest.fixture
def cloud_jobs():
    return pd.DataFrame(
        [
            {
                "source": "remotive" if index < 10 else "jobicy",
                "skills": ["AWS", "Python"] if index < 8 else ["Python", "SQL"],
                "category": "Software Development",
            }
            for index in range(20)
        ]
    )


@pytest.fixture
def salary_jobs():
    rows = []
    for index in range(24):
        python_job = index < 12
        salary = 100_000 + index * 1_000 if python_job else 80_000 + index * 1_000
        rows.append(
            {
                "source": "remotive" if python_job else "jobicy",
                "skills": ["Python", "SQL"] if python_job else ["SQL", "AWS"],
                "salary_min": salary,
                "salary_max": salary,
                "salary_type": "yearly",
                "currency": "USD",
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture
def salary_coverage_jobs():
    rows = []
    for index in range(20):
        row = {
            "salary_min": None,
            "salary_max": None,
            "salary_type": None,
            "currency": None,
            "salary_chart_used": index < 10,
        }
        if index < 11:
            row.update(
                salary_min=100_000 + index * 1_000,
                salary_type="yearly",
                currency="USD",
            )
        elif index == 11:
            row.update(salary_min=40_000, salary_type="monthly", currency="EUR")
        rows.append(row)
    return pd.DataFrame(rows)


@pytest.fixture
def paired_jobs():
    return pd.DataFrame(
        [
            {
                "source": "remotive" if index < 6 else "jobicy",
                "skills": ["Python", "SQL", *( ["AWS"] if index < 5 else [] )],
            }
            for index in range(12)
        ]
    )


@pytest.fixture
def skill_match_rows():
    return pd.DataFrame(
        [
            {
                "skill_name": "sql",
                "display_name": "SQL",
                "job_count": 12,
                "matching_job_count": 20,
                "sources": ["jobicy", "remotive"],
            },
            {
                "skill_name": "aws",
                "display_name": "AWS",
                "job_count": 7,
                "matching_job_count": 20,
                "sources": ["jobicy", "remotive"],
            },
        ]
    )


def assert_plain_analyst_sentence(sentence):
    assert sentence.endswith(".")
    assert "!" not in sentence
    assert not re.search(r"\b(significant|impressive|robust|strong)\b", sentence, re.I)
    assert "(sources:" not in sentence.casefold()
    assert "remotive" not in sentence.casefold()
    assert "jobicy" not in sentence.casefold()
    assert not any(
        0x1F000 <= ord(character) <= 0x1FAFF
        or 0x2600 <= ord(character) <= 0x27BF
        for character in sentence
    )


def test_insights_module_exposes_exactly_five_findings():
    names = {
        name
        for name, function in inspect.getmembers(insights, inspect.isfunction)
        if function.__module__ == insights.__name__
    }
    assert names == {
        "cloud_demand_insight",
        "salary_gap_insight",
        "salary_coverage_insight",
        "skill_pair_insight",
        "skill_match_insight",
    }


def test_cloud_demand_insight_reports_share_and_sample(cloud_jobs):
    sentence = insights.cloud_demand_insight(cloud_jobs)

    assert sentence == (
        "Cloud skills appeared in 40.0% of jobs with a tracked skill (n=20)."
    )
    assert_plain_analyst_sentence(sentence)


def test_salary_gap_insight_uses_yearly_usd_and_both_group_counts(salary_jobs):
    sentence = insights.salary_gap_insight(salary_jobs)

    assert sentence == (
        "Python jobs had a median yearly USD salary of $105,500 (n=12), "
        "$8,000 higher than tracked-skill jobs without "
        "Python (median $97,500; n=12)."
    )
    assert_plain_analyst_sentence(sentence)


def test_salary_coverage_insight_counts_chart_eligible_salary_rows(
    salary_coverage_jobs,
):
    sentence = insights.salary_coverage_insight(salary_coverage_jobs)

    assert sentence == (
        "12 of 20 jobs (60.0%) list a salary; 10 of them are yearly USD and "
        "used in the salary chart."
    )
    assert_plain_analyst_sentence(sentence)


def test_salary_gap_equal_medians_says_they_are_the_same(salary_jobs):
    equal_salary_jobs = salary_jobs.copy()
    equal_salary_jobs["salary_min"] = 95_000
    equal_salary_jobs["salary_max"] = 95_000

    sentence = insights.salary_gap_insight(equal_salary_jobs)

    assert sentence == (
        "Python and tracked-skill jobs without Python had the same median yearly "
        "USD salary of $95,000 (n=12 and n=12)."
    )
    assert "$0 higher" not in sentence
    assert_plain_analyst_sentence(sentence)


def test_skill_pair_insight_counts_jobs_with_the_pair(paired_jobs):
    sentence = insights.skill_pair_insight(paired_jobs)

    assert sentence == (
        "The most common tracked-skill pair was Python and SQL, found "
        "together in 12 jobs (n=12)."
    )
    assert_plain_analyst_sentence(sentence)


def test_skill_match_insight_reports_missing_skill_share(skill_match_rows):
    sentence = insights.skill_match_insight(skill_match_rows)

    assert sentence == (
        "Among jobs matching at least one chosen skill, the most common missing "
        "tracked skill was SQL, found in 12 of n=20 matching jobs "
        "(60.0%)."
    )
    assert_plain_analyst_sentence(sentence)


def test_all_insights_use_the_small_sample_fallback():
    small_jobs = pd.DataFrame(
        [
            {
                "source": "remotive" if index < 5 else "jobicy",
                "category": "Software Development",
                "skills": ["Python"] if index < 5 else ["SQL"],
                "salary_min": 90_000,
                "salary_max": 90_000,
                "salary_type": "yearly",
                "currency": "USD",
            }
            for index in range(9)
        ]
    )
    small_matches = pd.DataFrame(
        [
            {
                "skill_name": "sql",
                "display_name": "SQL",
                "job_count": 4,
                "matching_job_count": 9,
                "sources": ["remotive", "jobicy"],
            }
        ]
    )

    sentences = [
        insights.cloud_demand_insight(small_jobs),
        insights.salary_gap_insight(small_jobs),
        insights.salary_coverage_insight(small_jobs),
        insights.skill_pair_insight(small_jobs),
        insights.skill_match_insight(small_matches),
    ]

    assert sentences == [
        "Not enough data for a reliable finding (n=9).",
        "Not enough data for a reliable finding (n=4).",
        "Not enough data for a reliable finding (n=9).",
        "Not enough data for a reliable finding (n=9).",
        "Not enough data for a reliable finding (n=9).",
    ]
    for sentence in sentences:
        assert_plain_analyst_sentence(sentence)


@pytest.mark.parametrize(
    "function",
    [
        insights.cloud_demand_insight,
        insights.salary_gap_insight,
        insights.salary_coverage_insight,
        insights.skill_pair_insight,
        insights.skill_match_insight,
    ],
)
def test_empty_input_returns_a_sentence_without_claims(function):
    sentence = function(pd.DataFrame())

    assert sentence == "Not enough data for a reliable finding (n=0)."
    assert_plain_analyst_sentence(sentence)


def test_single_selected_source_is_added_as_a_suffix():
    sentence = "Cloud skills appeared in 40.0% of jobs with a tracked skill (n=20)."

    assert add_selected_source(sentence, ["Remotive"]) == (
        "Cloud skills appeared in 40.0% of jobs with a tracked skill "
        "(n=20); Source: Remotive."
    )
    assert add_selected_source(sentence, ["Remotive", "Jobicy"]) == sentence
    assert add_selected_source(sentence, []) == sentence
