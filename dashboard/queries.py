"""Database access and pure data-shaping helpers for the Streamlit dashboard."""

from __future__ import annotations

from collections import Counter

import pandas as pd
import psycopg2

from src.categories import normalize_category


JOB_COLUMNS = (
    "source",
    "source_id",
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

PIPELINE_COLUMNS = (
    "id",
    "started_at",
    "finished_at",
    "status",
    "jobs_fetched",
    "jobs_cleaned",
    "jobs_skipped",
    "jobs_upserted",
    "reused_snapshot",
)

FILTER_COLUMNS = {
    "source": "source",
    "category": "category",
    "job_type": "job_type",
    "location": "candidate_required_location",
}

EMPTY_SALARIES = pd.DataFrame(columns=["category", "median_salary_usd"])
EMPTY_POSTINGS = pd.DataFrame(columns=["publication_day", "job_count"])
EMPTY_PIPELINE_RUNS = pd.DataFrame(
    columns=[
        "Started at",
        "Finished at",
        "Status",
        "Jobs fetched",
        "Jobs cleaned",
        "Jobs skipped",
        "Jobs upserted",
        "Reused snapshot",
    ]
)

SKILL_DISPLAY_NAMES = {
    "ai": "AI",
    "aws": "AWS",
    "c#": "C#",
    "ci/cd": "CI/CD",
    "css": "CSS",
    "gcp": "Google Cloud Platform",
    "git": "Git",
    "go": "Go",
    "html": "HTML",
    "ios": "iOS",
    "java": "Java",
    "javascript": "JavaScript",
    "kubernetes": "Kubernetes",
    "machine learning": "Machine Learning",
    "mysql": "MySQL",
    "node.js": "Node.js",
    "postgresql": "PostgreSQL",
    "power bi": "Power BI",
    "python": "Python",
    "r": "R",
    "react": "React",
    "ruby": "Ruby",
    "rust": "Rust",
    "sql": "SQL",
    "typescript": "TypeScript",
}


def _fetch_read_only(query: str) -> pd.DataFrame:
    """Run one read-only query using the project's database settings."""
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
                cursor.execute(query)
                rows = cursor.fetchall()
                columns = [description.name for description in cursor.description]
        return pd.DataFrame(rows, columns=columns)
    finally:
        connection.close()


def fetch_jobs() -> pd.DataFrame:
    """Fetch listings from every source in a read-only transaction."""
    return _fetch_read_only(
        """
        SELECT
            source,
            source_id,
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
        ORDER BY publication_date DESC NULLS LAST, source, source_id
        """
    )


def fetch_extracted_job_skills() -> pd.DataFrame:
    """Fetch extracted skills keyed to jobs by source and source ID."""
    return _fetch_read_only(
        """
        SELECT source, source_id, skill_name
        FROM extracted_job_skills
        ORDER BY source, source_id, skill_name
        """
    )


def fetch_pipeline_runs() -> pd.DataFrame:
    """Fetch the latest five pipeline runs and their public run counts."""
    return _fetch_read_only(
        """
        SELECT
            id,
            started_at,
            finished_at,
            status,
            jobs_fetched,
            jobs_cleaned,
            jobs_skipped,
            jobs_upserted,
            reused_snapshot
        FROM pipeline_runs
        ORDER BY finished_at DESC, id DESC
        LIMIT 5
        """
    )


def prepare_jobs(jobs: pd.DataFrame | None) -> pd.DataFrame:
    """Return a copy with expected columns, aliases, and shared categories."""
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

    frame["category"] = frame["category"].map(normalize_category)
    return frame


def _text_values(values: pd.Series) -> pd.Series:
    return values.fillna("").astype(str).str.strip()


def source_display_name(value: object) -> str:
    """Return a readable source label while preserving unknown source names."""
    if value is None or pd.isna(value):
        return ""
    source = str(value).strip()
    known = {"remotive": "Remotive", "jobicy": "Jobicy"}
    return known.get(source.casefold(), source.replace("_", " ").title())


def filter_options(jobs: pd.DataFrame, field: str) -> list[str]:
    """Return sorted non-empty values for one sidebar filter."""
    if field not in FILTER_COLUMNS:
        raise ValueError(f"Unsupported filter field: {field}")

    frame = prepare_jobs(jobs)
    values = frame[FILTER_COLUMNS[field]]
    if field == "source":
        values = values.map(source_display_name)
    else:
        values = _text_values(values)
    unique_values = {str(value).strip() for value in values if str(value).strip()}
    return sorted(unique_values, key=str.casefold)


def filter_jobs(
    jobs: pd.DataFrame,
    category: str | None = None,
    job_type: str | None = None,
    location: str | None = None,
    sources: list[str] | None = None,
) -> pd.DataFrame:
    """Apply optional source, category, job type, and location filters."""
    frame = prepare_jobs(jobs)
    if sources is not None:
        selected_sources = {source.casefold() for source in sources}
        source_labels = frame["source"].map(source_display_name).str.casefold()
        frame = frame.loc[source_labels.isin(selected_sources)]

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


def search_jobs(jobs: pd.DataFrame, query: str | None) -> pd.DataFrame:
    """Match a title or company substring without regard to letter case."""
    frame = prepare_jobs(jobs)
    term = str(query or "").strip()
    if not term:
        return frame.copy()

    title_matches = _text_values(frame["title"]).str.contains(
        term, case=False, regex=False
    )
    company_matches = _text_values(frame["company_name"]).str.contains(
        term, case=False, regex=False
    )
    return frame.loc[title_matches | company_matches].copy()


def summary_metrics(jobs: pd.DataFrame) -> dict[str, object]:
    """Calculate total jobs, salary coverage, category count, and latest update."""
    frame = prepare_jobs(jobs)
    salary_min = pd.to_numeric(frame["salary_min"], errors="coerce")
    salary_max = pd.to_numeric(frame["salary_max"], errors="coerce")
    has_salary = salary_min.notna() | salary_max.notna()
    updated_at = pd.to_datetime(frame["updated_at"], errors="coerce", utc=True)
    latest_update = updated_at.max() if updated_at.notna().any() else None

    return {
        "total_jobs": len(frame),
        "jobs_with_salary": int(has_salary.sum()),
        "category_count": int(frame["category"].nunique()),
        "most_recent_update": latest_update,
    }


def _job_keys(jobs: pd.DataFrame) -> set[tuple[str, str]]:
    """Return valid composite job keys from a prepared jobs frame."""
    frame = prepare_jobs(jobs)
    keys: set[tuple[str, str]] = set()
    for source, source_id in zip(frame["source"], frame["source_id"]):
        if pd.isna(source) or pd.isna(source_id):
            continue
        source_value = str(source).strip().casefold()
        id_value = str(source_id).strip()
        if source_value and id_value:
            keys.add((source_value, id_value))
    return keys


def _skill_rows_for_jobs(
    jobs: pd.DataFrame, extracted_skills: pd.DataFrame | None
) -> list[tuple[tuple[str, str], str, str]]:
    """Return unique (job key, normalized skill key, display name) rows."""
    selected_keys = _job_keys(jobs)
    if not selected_keys or not isinstance(extracted_skills, pd.DataFrame):
        return []
    required = {"source", "source_id", "skill_name"}
    if not required.issubset(extracted_skills.columns):
        return []

    unique: dict[tuple[tuple[str, str], str], str] = {}
    for source, source_id, skill_name in extracted_skills[
        ["source", "source_id", "skill_name"]
    ].itertuples(index=False, name=None):
        if pd.isna(source) or pd.isna(source_id) or pd.isna(skill_name):
            continue
        key = (str(source).strip().casefold(), str(source_id).strip())
        label = str(skill_name).strip()
        normalized_skill = label.casefold()
        if key not in selected_keys or not normalized_skill:
            continue
        display = SKILL_DISPLAY_NAMES.get(normalized_skill, label)
        unique.setdefault((key, normalized_skill), display)
    return [
        (job_key, skill_key, display)
        for (job_key, skill_key), display in unique.items()
    ]


def skills_counts(
    jobs: pd.DataFrame, extracted_skills: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Count extracted skills by distinct selected jobs, not provider tags."""
    counts: Counter[str] = Counter()
    display_names: dict[str, str] = {}
    for _, skill_key, display in _skill_rows_for_jobs(jobs, extracted_skills):
        counts[skill_key] += 1
        display_names.setdefault(skill_key, display)

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


def tracked_skill_job_count(
    jobs: pd.DataFrame, extracted_skills: pd.DataFrame | None = None
) -> int:
    """Count selected jobs with at least one extracted skill."""
    return len({job_key for job_key, _, _ in _skill_rows_for_jobs(jobs, extracted_skills)})


def jobs_by_category(jobs: pd.DataFrame) -> pd.DataFrame:
    """Count listings by their shared category label."""
    categories = prepare_jobs(jobs)["category"]
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
    jobs_used = len(eligible)
    if eligible.empty:
        result = EMPTY_SALARIES.copy()
        result.attrs["jobs_used"] = 0
        return result

    result = (
        eligible.groupby("category", as_index=False)["salary_estimate_usd"]
        .median()
        .rename(columns={"salary_estimate_usd": "median_salary_usd"})
    )
    result = result.sort_values(
        "median_salary_usd", ascending=False, ignore_index=True
    )
    result.attrs["jobs_used"] = jobs_used
    return result


def postings_per_day(jobs: pd.DataFrame) -> pd.DataFrame:
    """Count listings by their publication date."""
    frame = prepare_jobs(jobs)
    dates = pd.to_datetime(frame["publication_date"], errors="coerce", utc=True)
    valid = dates.notna()
    if not valid.any():
        return EMPTY_POSTINGS.copy()

    result = dates.loc[valid].dt.date.value_counts().sort_index()
    return result.rename_axis("publication_day").reset_index(name="job_count")


def format_salary_range(row: pd.Series) -> str:
    """Format the raw salary bounds and period for display in the jobs table."""
    minimum = pd.to_numeric(pd.Series([row.get("salary_min")]), errors="coerce").iloc[0]
    maximum = pd.to_numeric(pd.Series([row.get("salary_max")]), errors="coerce").iloc[0]
    bounds = [value for value in (minimum, maximum) if pd.notna(value)]
    if not bounds:
        return "Not listed"

    currency_value = row.get("currency")
    currency = "" if pd.isna(currency_value) else str(currency_value).strip().upper()
    salary_type_value = row.get("salary_type")
    salary_type = (
        "" if pd.isna(salary_type_value) else str(salary_type_value).strip().lower()
    )
    formatted = [f"{value:,.0f}" for value in bounds]
    amount = formatted[0] if len(bounds) == 1 or formatted[0] == formatted[1] else (
        f"{formatted[0]}–{formatted[1]}"
    )
    parts = [part for part in (currency, amount, salary_type) if part]
    return " ".join(parts)


def jobs_table(jobs: pd.DataFrame) -> pd.DataFrame:
    """Build a newest-first user-facing table with readable source labels."""
    frame = prepare_jobs(jobs)
    dates = pd.to_datetime(frame["publication_date"], errors="coerce", utc=True)
    ordered = frame.assign(_publication_sort=dates).sort_values(
        "_publication_sort", ascending=False, na_position="last", kind="stable"
    )
    return pd.DataFrame(
        {
            "Title": ordered["title"].fillna(""),
            "Company": ordered["company_name"].fillna(""),
            "Source": ordered["source"].map(source_display_name),
            "Category": ordered["category"],
            "Salary range": ordered.apply(format_salary_range, axis=1),
            "Original posting": ordered["url"].fillna(""),
        }
    ).reset_index(drop=True)


def pipeline_runs_table(runs: pd.DataFrame | None) -> pd.DataFrame:
    """Format the latest pipeline runs for a compact dashboard history table."""
    frame = runs.copy() if isinstance(runs, pd.DataFrame) else pd.DataFrame(runs or [])
    for column in PIPELINE_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.Series(index=frame.index, dtype="object")
    if frame.empty:
        return EMPTY_PIPELINE_RUNS.copy()

    frame["finished_at"] = pd.to_datetime(frame["finished_at"], errors="coerce", utc=True)
    frame = frame.sort_values(
        ["finished_at", "id"], ascending=[False, False], na_position="last", kind="stable"
    )
    return pd.DataFrame(
        {
            "Started at": frame["started_at"],
            "Finished at": frame["finished_at"],
            "Status": frame["status"].fillna(""),
            "Jobs fetched": frame["jobs_fetched"].fillna(0).astype(int),
            "Jobs cleaned": frame["jobs_cleaned"].fillna(0).astype(int),
            "Jobs skipped": frame["jobs_skipped"].fillna(0).astype(int),
            "Jobs upserted": frame["jobs_upserted"].fillna(0).astype(int),
            "Reused snapshot": frame["reused_snapshot"].fillna(False).astype(bool),
        }
    ).reset_index(drop=True)
