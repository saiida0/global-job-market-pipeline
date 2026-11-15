"""Database access and pure data-shaping helpers for the Streamlit dashboard."""

from __future__ import annotations

from collections import Counter

import pandas as pd
import psycopg2


JOB_COLUMNS = (
    "id",
    "title",
    "company_name",
    "candidate_required_location",
    "salary_min",
    "salary_max",
    "salary_type",
    "currency",
    "publication_date",
    "fetched_at",
    "category",
    "job_type",
    "tags",
    "url",
    "updated_at",
)

FILTER_COLUMNS = {
    "category": "category",
    "job_type": "job_type",
    "location": "candidate_required_location",
}


def fetch_jobs() -> pd.DataFrame:
    """Fetch Remotive listings in a read-only PostgreSQL transaction."""
    # Import lazily so a missing local .env can be rendered as a dashboard error.
    from src.config import config

    connection = psycopg2.connect(
        host=config.db_host,
        port=config.db_port,
        dbname=config.db_name,
        user=config.db_user,
        password=config.db_password,
        connect_timeout=5,
    )
    try:
        connection.set_session(readonly=True)
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        title,
                        company_name,
                        candidate_required_location,
                        salary_min,
                        salary_max,
                        salary_type,
                        currency,
                        publication_date,
                        fetched_at,
                        category,
                        job_type,
                        tags,
                        url,
                        updated_at
                    FROM jobs
                    WHERE source = %s
                    ORDER BY publication_date DESC NULLS LAST, id
                    """,
                    ("remotive",),
                )
                rows = cursor.fetchall()
                columns = [description.name for description in cursor.description]
        return pd.DataFrame(rows, columns=columns)
    finally:
        connection.close()


def prepare_jobs(jobs: pd.DataFrame | None) -> pd.DataFrame:
    """Return a copy with the dashboard's expected columns and aliases."""
    frame = jobs.copy() if isinstance(jobs, pd.DataFrame) else pd.DataFrame(jobs or [])

    if "company_name" not in frame.columns and "company" in frame.columns:
        frame["company_name"] = frame["company"]
    if (
        "candidate_required_location" not in frame.columns
        and "location" in frame.columns
    ):
        frame["candidate_required_location"] = frame["location"]

    for column in JOB_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.Series(index=frame.index, dtype="object")
    return frame


def _text_values(values: pd.Series) -> pd.Series:
    return values.fillna("").astype(str).str.strip()


def filter_options(jobs: pd.DataFrame, field: str) -> list[str]:
    """Return sorted non-empty values for one sidebar filter."""
    if field not in FILTER_COLUMNS:
        raise ValueError(f"Unsupported filter field: {field}")

    frame = prepare_jobs(jobs)
    values = _text_values(frame[FILTER_COLUMNS[field]])
    unique_values = {value for value in values if value}
    return sorted(unique_values, key=str.casefold)


def filter_jobs(
    jobs: pd.DataFrame,
    category: str | None = None,
    job_type: str | None = None,
    location: str | None = None,
) -> pd.DataFrame:
    """Apply optional category, job type, and location filters."""
    frame = prepare_jobs(jobs)
    selections = {
        "category": category,
        "job_type": job_type,
        "location": location,
    }
    for field, selected in selections.items():
        if selected is None:
            continue
        column = FILTER_COLUMNS[field]
        matches = _text_values(frame[column]).str.casefold() == selected.strip().casefold()
        frame = frame.loc[matches]
    return frame.copy()


def summary_metrics(jobs: pd.DataFrame) -> dict[str, object]:
    """Calculate total jobs, salary coverage, category count, and latest update."""
    frame = prepare_jobs(jobs)
    salary_min = pd.to_numeric(frame["salary_min"], errors="coerce")
    salary_max = pd.to_numeric(frame["salary_max"], errors="coerce")
    has_salary = salary_min.notna() | salary_max.notna()
    categories = _text_values(frame["category"])
    categories = categories[categories.ne("")]

    updated_at = pd.to_datetime(frame["updated_at"], errors="coerce", utc=True)
    latest_update = updated_at.max() if updated_at.notna().any() else None

    return {
        "total_jobs": len(frame),
        "jobs_with_salary": int(has_salary.sum()),
        "category_count": int(categories.nunique()),
        "most_recent_update": latest_update,
    }


def skills_counts(jobs: pd.DataFrame) -> pd.DataFrame:
    """Count how many listings include each tag, case-insensitively."""
    frame = prepare_jobs(jobs)
    counts: Counter[str] = Counter()
    display_names: dict[str, str] = {}

    for tags in frame["tags"]:
        if isinstance(tags, str):
            values = [tags]
        elif isinstance(tags, (list, tuple, set)):
            values = tags
        else:
            continue

        seen_for_job: set[str] = set()
        for value in values:
            if value is None or pd.isna(value):
                continue
            label = str(value).strip()
            key = label.casefold()
            if label and key not in seen_for_job:
                seen_for_job.add(key)
                display_names.setdefault(key, label)
                counts[key] += 1

    result = pd.DataFrame(
        [
            {"skill": display_names[key], "job_count": count}
            for key, count in counts.items()
        ],
        columns=["skill", "job_count"],
    )
    return result.sort_values(
        ["job_count", "skill"], ascending=[False, True], ignore_index=True
    )


def jobs_by_category(jobs: pd.DataFrame) -> pd.DataFrame:
    """Count listings by category, including rows without a category."""
    frame = prepare_jobs(jobs)
    categories = _text_values(frame["category"]).replace("", "Uncategorized")
    result = categories.value_counts().rename_axis("category").reset_index(name="job_count")
    return result.sort_values(
        ["job_count", "category"], ascending=[False, True], ignore_index=True
    )


def salary_by_category(jobs: pd.DataFrame) -> pd.DataFrame:
    """Return median salary midpoints for yearly USD listings only."""
    frame = prepare_jobs(jobs)
    salary_type = _text_values(frame["salary_type"]).str.casefold()
    currency = _text_values(frame["currency"]).str.upper()
    eligible = frame.loc[salary_type.eq("yearly") & currency.eq("USD")].copy()

    minimum = pd.to_numeric(eligible["salary_min"], errors="coerce")
    maximum = pd.to_numeric(eligible["salary_max"], errors="coerce")
    eligible["salary_estimate_usd"] = pd.concat(
        [minimum, maximum], axis=1
    ).mean(axis=1)
    eligible = eligible.loc[eligible["salary_estimate_usd"].notna()]
    if eligible.empty:
        return pd.DataFrame(columns=["category", "median_salary_usd"])

    eligible["category"] = _text_values(eligible["category"]).replace(
        "", "Uncategorized"
    )
    result = (
        eligible.groupby("category", as_index=False)["salary_estimate_usd"]
        .median()
        .rename(columns={"salary_estimate_usd": "median_salary_usd"})
    )
    return result.sort_values(
        "median_salary_usd", ascending=False, ignore_index=True
    )


def postings_per_day(jobs: pd.DataFrame) -> pd.DataFrame:
    """Count listings by their publication date."""
    frame = prepare_jobs(jobs)
    dates = pd.to_datetime(frame["publication_date"], errors="coerce", utc=True)
    valid = dates.notna()
    if not valid.any():
        return pd.DataFrame(columns=["publication_day", "job_count"])

    result = dates.loc[valid].dt.date.value_counts().sort_index()
    return result.rename_axis("publication_day").reset_index(name="job_count")


def format_salary_range(row: pd.Series) -> str:
    """Format the raw salary bounds and period for display in the jobs table."""
    minimum = pd.to_numeric(pd.Series([row.get("salary_min")]), errors="coerce").iloc[0]
    maximum = pd.to_numeric(pd.Series([row.get("salary_max")]), errors="coerce").iloc[0]
    bounds = [value for value in (minimum, maximum) if pd.notna(value)]
    if not bounds:
        return "Not listed"

    currency = str(row.get("currency") or "").strip().upper()
    salary_type = str(row.get("salary_type") or "").strip().lower()
    formatted = [f"{value:,.0f}" for value in bounds]
    amount = formatted[0] if len(formatted) == 1 or formatted[0] == formatted[1] else (
        f"{formatted[0]}–{formatted[1]}"
    )
    parts = [part for part in (currency, amount, salary_type) if part]
    return " ".join(parts)


def jobs_table(jobs: pd.DataFrame) -> pd.DataFrame:
    """Build the user-facing job table with a formatted salary range."""
    frame = prepare_jobs(jobs)
    return pd.DataFrame(
        {
            "Title": frame["title"].fillna(""),
            "Company": frame["company_name"].fillna(""),
            "Category": frame["category"].fillna(""),
            "Salary range": frame.apply(format_salary_range, axis=1),
            "Original posting": frame["url"].fillna(""),
        }
    )
