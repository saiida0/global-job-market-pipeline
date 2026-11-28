"""Deterministic, sample-aware findings for the dashboard."""

from __future__ import annotations

from collections import Counter
from itertools import combinations

import pandas as pd


MIN_INSIGHT_SAMPLE = 10
CLOUD_SKILLS = frozenset(
    {"aws", "amazon web services", "azure", "gcp", "google cloud platform"}
)


def cloud_demand_insight(jobs: pd.DataFrame) -> str:
    """Describe cloud-skill share among jobs with at least one tracked skill."""
    if not isinstance(jobs, pd.DataFrame) or "skills" not in jobs.columns:
        return "Not enough data for a reliable finding (n=0)."
    tracked = jobs.loc[
        jobs["skills"].map(
            lambda value: isinstance(value, (list, tuple, set, frozenset))
            and bool(value)
        )
    ]
    sample_size = len(tracked)
    if sample_size < MIN_INSIGHT_SAMPLE:
        return f"Not enough data for a reliable finding (n={sample_size})."

    cloud_jobs = int(
        tracked["skills"]
        .map(
            lambda skills: any(
                str(skill).strip().casefold() in CLOUD_SKILLS for skill in skills
            )
        )
        .sum()
    )
    share = 100 * cloud_jobs / sample_size
    return (
        f"Cloud skills appeared in {share:.1f}% of jobs with a tracked skill "
        f"(n={sample_size})."
    )


def salary_gap_insight(jobs: pd.DataFrame) -> str:
    """Compare yearly USD medians for tracked-skill jobs with and without Python."""
    if not isinstance(jobs, pd.DataFrame) or "skills" not in jobs.columns:
        return "Not enough data for a reliable finding (n=0)."
    tracked = jobs.loc[
        jobs["skills"].map(
            lambda value: isinstance(value, (list, tuple, set, frozenset))
            and bool(value)
        )
    ].copy()
    if tracked.empty:
        return "Not enough data for a reliable finding (n=0)."

    salary_type = tracked.get(
        "salary_type", pd.Series(index=tracked.index, dtype="object")
    ).fillna("").astype(str).str.strip().str.casefold()
    currency = tracked.get(
        "currency", pd.Series(index=tracked.index, dtype="object")
    ).fillna("").astype(str).str.strip().str.upper()
    minimum = pd.to_numeric(
        tracked.get("salary_min", pd.Series(index=tracked.index, dtype="object")),
        errors="coerce",
    )
    maximum = pd.to_numeric(
        tracked.get("salary_max", pd.Series(index=tracked.index, dtype="object")),
        errors="coerce",
    )
    tracked["salary_estimate"] = pd.concat([minimum, maximum], axis=1).mean(axis=1)
    eligible = tracked.loc[
        salary_type.eq("yearly")
        & currency.eq("USD")
        & tracked["salary_estimate"].notna()
    ].copy()
    python_jobs = eligible["skills"].map(
        lambda skills: any(str(skill).strip().casefold() == "python" for skill in skills)
    )
    python_group = eligible.loc[python_jobs]
    other_group = eligible.loc[~python_jobs]
    python_count = len(python_group)
    other_count = len(other_group)
    if min(python_count, other_count) < MIN_INSIGHT_SAMPLE:
        return (
            "Not enough data for a reliable finding "
            f"(n={min(python_count, other_count)})."
        )

    python_median = float(python_group["salary_estimate"].median())
    other_median = float(other_group["salary_estimate"].median())
    if python_median == other_median:
        return (
            "Python and tracked-skill jobs without Python had the same median "
            f"yearly USD salary of ${python_median:,.0f} "
            f"(n={python_count} and n={other_count})."
        )
    salary_difference = abs(python_median - other_median)
    direction = "higher" if python_median > other_median else "lower"
    difference_display = (
        f"${salary_difference:,.0f}"
        if salary_difference.is_integer()
        else "$" + f"{salary_difference:,.2f}".rstrip("0").rstrip(".")
    )
    return (
        f"Python jobs had a median yearly USD salary of ${python_median:,.0f} "
        f"(n={python_count}), {difference_display} {direction} than "
        f"tracked-skill jobs without Python "
        f"(median ${other_median:,.0f}; n={other_count})."
    )


def salary_coverage_insight(jobs: pd.DataFrame) -> str:
    """Describe salary listing coverage and the yearly USD chart sample."""
    if not isinstance(jobs, pd.DataFrame):
        return "Not enough data for a reliable finding (n=0)."
    sample_size = len(jobs)
    if sample_size < MIN_INSIGHT_SAMPLE:
        return f"Not enough data for a reliable finding (n={sample_size})."

    minimum = pd.to_numeric(
        jobs.get("salary_min", pd.Series(index=jobs.index, dtype="object")),
        errors="coerce",
    )
    maximum = pd.to_numeric(
        jobs.get("salary_max", pd.Series(index=jobs.index, dtype="object")),
        errors="coerce",
    )
    has_salary = minimum.notna() | maximum.notna()
    salary_count = int(has_salary.sum())
    salary_share = 100 * salary_count / sample_size

    salary_type = jobs.get(
        "salary_type", pd.Series(index=jobs.index, dtype="object")
    ).fillna("").astype(str).str.strip().str.casefold()
    currency = jobs.get(
        "currency", pd.Series(index=jobs.index, dtype="object")
    ).fillna("").astype(str).str.strip().str.upper()
    yearly_usd = salary_type.eq("yearly") & currency.eq("USD") & has_salary
    chart_used = jobs.get(
        "salary_chart_used", pd.Series(False, index=jobs.index)
    ).fillna(False).astype(bool)
    chart_salary_count = int((yearly_usd & chart_used).sum())
    return (
        f"{salary_count} of {sample_size} jobs ({salary_share:.1f}%) list a salary; "
        f"{chart_salary_count} of them are yearly USD and used in the salary chart."
    )


def skill_pair_insight(jobs: pd.DataFrame) -> str:
    """Name the most common tracked-skill pair and its co-occurrence count."""
    if not isinstance(jobs, pd.DataFrame) or "skills" not in jobs.columns:
        return "Not enough data for a reliable finding (n=0)."
    tracked = jobs.loc[
        jobs["skills"].map(
            lambda value: isinstance(value, (list, tuple, set, frozenset))
            and bool(value)
        )
    ]
    sample_size = len(tracked)
    if sample_size < MIN_INSIGHT_SAMPLE:
        return f"Not enough data for a reliable finding (n={sample_size})."

    pair_counts: Counter[tuple[str, str]] = Counter()
    display_names: dict[str, str] = {}
    for skills in tracked["skills"]:
        unique_skills: dict[str, str] = {}
        for raw_skill in skills:
            label = str(raw_skill).strip()
            key = label.casefold()
            if key:
                unique_skills.setdefault(key, label)
                display_names.setdefault(key, label)
        pair_counts.update(combinations(sorted(unique_skills), 2))

    if not pair_counts:
        return (
            f"No tracked-skill pair appeared together among n={sample_size} jobs."
        )

    pair, pair_count = sorted(
        pair_counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
    )[0]
    return (
        f"The most common tracked-skill pair was {display_names[pair[0]]} and "
        f"{display_names[pair[1]]}, found together in {pair_count} jobs "
        f"(n={sample_size})."
    )


def skill_match_insight(matches: pd.DataFrame) -> str:
    """Describe the most common unchosen skill among the visitor's matches."""
    if not isinstance(matches, pd.DataFrame) or matches.empty:
        return "Not enough data for a reliable finding (n=0)."
    first = matches.iloc[0]
    matching_value = pd.to_numeric(
        first.get("matching_job_count", 0), errors="coerce"
    )
    matching_jobs = int(matching_value) if pd.notna(matching_value) else 0
    if matching_jobs < MIN_INSIGHT_SAMPLE:
        return f"Not enough data for a reliable finding (n={matching_jobs})."

    if "job_count" not in matches.columns:
        return (
            f"No unchosen tracked skill appeared among {matching_jobs} matching "
            f"jobs (n={matching_jobs})."
        )
    numeric_counts = pd.to_numeric(matches["job_count"], errors="coerce")
    candidates = matches.loc[numeric_counts.fillna(0) > 0].copy()
    if candidates.empty:
        return (
            f"No unchosen tracked skill appeared among {matching_jobs} matching "
            f"jobs (n={matching_jobs})."
        )
    candidates["_job_count"] = numeric_counts.loc[candidates.index]
    candidates = candidates.assign(
        _sort_name=candidates.get(
            "skill_name", pd.Series(index=candidates.index, dtype="object")
        )
        .fillna("")
        .astype(str)
        .str.casefold()
    ).sort_values(["_job_count", "_sort_name"], ascending=[False, True])
    top = candidates.iloc[0]
    skill_label = top.get("display_name")
    if pd.isna(skill_label) or not str(skill_label).strip():
        skill_label = top.get("skill_name", "")
    skill = str(skill_label).strip()
    skill_jobs = int(top["_job_count"])
    share = 100 * skill_jobs / matching_jobs
    return (
        f"Among jobs matching at least one chosen skill, the most common missing "
        f"tracked skill was {skill}, found in {skill_jobs} of n={matching_jobs} "
        f"matching jobs ({share:.1f}%)."
    )
