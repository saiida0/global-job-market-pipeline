"""Deterministic, sample-aware findings for the dashboard."""

from __future__ import annotations

from collections import Counter
from itertools import combinations

import pandas as pd


MIN_INSIGHT_SAMPLE = 10
CLOUD_SKILLS = frozenset(
    {"aws", "amazon web services", "azure", "gcp", "google cloud platform"}
)
SOURCE_DISPLAY_NAMES = {"remotive": "Remotive", "jobicy": "Jobicy"}


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
    source_names = {
        SOURCE_DISPLAY_NAMES.get(str(source).strip().casefold(), str(source).strip())
        for source in tracked.get("source", pd.Series(dtype="object")).dropna()
        if str(source).strip()
    }
    ordered_sources = [
        name for name in ("Remotive", "Jobicy") if name in source_names
    ] + sorted(source_names - {"Remotive", "Jobicy"}, key=str.casefold)
    sources = " and ".join(ordered_sources) or "the available sources"
    share = 100 * cloud_jobs / sample_size
    return (
        f"Cloud skills appeared in {share:.1f}% of jobs with a tracked skill "
        f"(n={sample_size}; sources: {sources})."
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

    source_names = {
        SOURCE_DISPLAY_NAMES.get(str(source).strip().casefold(), str(source).strip())
        for source in eligible.get("source", pd.Series(dtype="object")).dropna()
        if str(source).strip()
    }
    ordered_sources = [
        name for name in ("Remotive", "Jobicy") if name in source_names
    ] + sorted(source_names - {"Remotive", "Jobicy"}, key=str.casefold)
    sources = " and ".join(ordered_sources) or "the available sources"
    python_median = float(python_group["salary_estimate"].median())
    other_median = float(other_group["salary_estimate"].median())
    salary_difference = abs(python_median - other_median)
    direction = "higher" if python_median >= other_median else "lower"
    return (
        f"Across {sources}, Python jobs had a median yearly USD salary of "
        f"${python_median:,.0f} (n={python_count}), ${salary_difference:,.0f} "
        f"{direction} than tracked-skill jobs without Python "
        f"(median ${other_median:,.0f}; n={other_count})."
    )


def source_difference_insight(jobs: pd.DataFrame) -> str:
    """Describe the largest category-share difference between the two sources."""
    if not isinstance(jobs, pd.DataFrame) or "source" not in jobs.columns:
        return "Not enough data for a reliable finding (n=0)."
    source_keys = jobs["source"].fillna("").astype(str).str.strip().str.casefold()
    remotive = jobs.loc[source_keys.eq("remotive")].copy()
    jobicy = jobs.loc[source_keys.eq("jobicy")].copy()
    remotive_count = len(remotive)
    jobicy_count = len(jobicy)
    if min(remotive_count, jobicy_count) < MIN_INSIGHT_SAMPLE:
        return (
            "Not enough data for a reliable finding "
            f"(n={min(remotive_count, jobicy_count)})."
        )
    if "category" not in jobs.columns:
        return (
            "Not enough data for a reliable finding "
            f"(n={min(remotive_count, jobicy_count)})."
        )

    remotive_categories = remotive["category"].fillna("Other").astype(str)
    jobicy_categories = jobicy["category"].fillna("Other").astype(str)
    categories = sorted(
        set(remotive_categories) | set(jobicy_categories), key=str.casefold
    )
    shares = [
        (
            abs(
                100 * remotive_categories.eq(category).sum() / remotive_count
                - 100 * jobicy_categories.eq(category).sum() / jobicy_count
            ),
            category,
            100 * remotive_categories.eq(category).sum() / remotive_count,
            100 * jobicy_categories.eq(category).sum() / jobicy_count,
        )
        for category in categories
    ]
    if not shares:
        return (
            "Not enough data for a reliable finding "
            f"(n={min(remotive_count, jobicy_count)})."
        )
    difference, category, remotive_share, jobicy_share = sorted(
        shares, key=lambda value: (-value[0], value[1].casefold())
    )[0]
    return (
        f"The largest category-share gap was {category}: {remotive_share:.1f}% "
        f"of Remotive jobs (n={remotive_count}) and {jobicy_share:.1f}% of "
        f"Jobicy jobs (n={jobicy_count}), a {difference:.1f}-percentage-point gap."
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

    source_names = {
        SOURCE_DISPLAY_NAMES.get(str(source).strip().casefold(), str(source).strip())
        for source in tracked.get("source", pd.Series(dtype="object")).dropna()
        if str(source).strip()
    }
    ordered_sources = [
        name for name in ("Remotive", "Jobicy") if name in source_names
    ] + sorted(source_names - {"Remotive", "Jobicy"}, key=str.casefold)
    sources = " and ".join(ordered_sources) or "the available sources"
    if not pair_counts:
        return (
            f"No tracked-skill pair appeared together among {sample_size} jobs "
            f"(n={sample_size}; sources: {sources})."
        )

    pair, pair_count = sorted(
        pair_counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
    )[0]
    return (
        f"The most common tracked-skill pair was {display_names[pair[0]]} and "
        f"{display_names[pair[1]]}, found together in {pair_count} jobs "
        f"(n={sample_size}; sources: {sources})."
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

    raw_sources = first.get("sources", [])
    if isinstance(raw_sources, str):
        source_values = [value.strip() for value in raw_sources.split(",")]
    elif isinstance(raw_sources, (list, tuple, set, frozenset)):
        source_values = [str(value).strip() for value in raw_sources]
    else:
        source_values = []
    source_names = {
        SOURCE_DISPLAY_NAMES.get(value.casefold(), value)
        for value in source_values
        if value
    }
    ordered_sources = [
        name for name in ("Remotive", "Jobicy") if name in source_names
    ] + sorted(source_names - {"Remotive", "Jobicy"}, key=str.casefold)
    sources = " and ".join(ordered_sources) or "the available sources"

    if "job_count" not in matches.columns:
        return (
            f"No unchosen tracked skill appeared among {matching_jobs} matching "
            f"jobs (n={matching_jobs}; sources: {sources})."
        )
    numeric_counts = pd.to_numeric(matches["job_count"], errors="coerce")
    candidates = matches.loc[numeric_counts.fillna(0) > 0].copy()
    if candidates.empty:
        return (
            f"No unchosen tracked skill appeared among {matching_jobs} matching "
            f"jobs (n={matching_jobs}; sources: {sources})."
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
        f"matching jobs ({share:.1f}%; sources: {sources})."
    )
