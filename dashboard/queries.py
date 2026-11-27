"""Database access and pure data-shaping helpers for the Streamlit dashboard."""

from __future__ import annotations

from collections import Counter

import pandas as pd
import psycopg2

from src.categories import CATEGORY_MAP, normalize_category


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
ROLE_FOCUS_OPTIONS = ("All roles", "Tech and data roles")
TECH_DATA_CATEGORIES = frozenset(
    {"Software Development", "Data and Analytics", "AI and Machine Learning"}
)
_TECH_DATA_CATEGORY_ALIASES = tuple(
    sorted(
        alias
        for alias, shared_name in CATEGORY_MAP.items()
        if shared_name in TECH_DATA_CATEGORIES
    )
)
MIN_SALARY_JOBS_PER_CATEGORY = 10

EMPTY_SALARIES = pd.DataFrame(
    columns=["category", "category_label", "median_salary_usd", "salary_job_count"],
)
EMPTY_POSTINGS = pd.DataFrame(columns=["publication_day", "source", "job_count"])
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


def filter_role_focus(jobs: pd.DataFrame, role_focus: str) -> pd.DataFrame:
    """Keep all jobs or limit results to software, data, and AI categories."""
    frame = prepare_jobs(jobs)
    if role_focus == "All roles":
        return frame.copy()
    if role_focus == "Tech and data roles":
        return frame.loc[frame["category"].isin(TECH_DATA_CATEGORIES)].copy()
    raise ValueError(f"Unsupported role focus: {role_focus}")

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


def category_chart_label(category: str, count: int) -> str:
    """Put each category's sample count first so it remains easy to see."""
    return f"n={count:,} · {category}"


def jobs_by_category(jobs: pd.DataFrame) -> pd.DataFrame:
    """Count listings by their shared category label."""
    categories = prepare_jobs(jobs)["category"]
    result = categories.value_counts().rename_axis("category").reset_index(name="job_count")
    result = result.sort_values(
        ["job_count", "category"], ascending=[False, True], ignore_index=True
    )
    result["category_label"] = [
        category_chart_label(category, count)
        for category, count in zip(result["category"], result["job_count"])
    ]
    return result[["category", "category_label", "job_count"]]


def salary_by_category(jobs: pd.DataFrame) -> pd.DataFrame:
    """Return median yearly USD salaries, hiding categories with small samples."""
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
        result = EMPTY_SALARIES.copy()
        result.attrs.update(
            jobs_used=0, eligible_jobs=0, hidden_categories=0
        )
        return result

    grouped = (
        eligible.groupby("category", as_index=False)
        .agg(
            median_salary_usd=("salary_estimate_usd", "median"),
            salary_job_count=("salary_estimate_usd", "size"),
        )
    )
    hidden = grouped["salary_job_count"] < MIN_SALARY_JOBS_PER_CATEGORY
    result = grouped.loc[~hidden].copy()
    result["category_label"] = [
        category_chart_label(category, count)
        for category, count in zip(result["category"], result["salary_job_count"])
    ]
    result = result[
        ["category", "category_label", "median_salary_usd", "salary_job_count"]
    ].sort_values("median_salary_usd", ascending=False, ignore_index=True)
    result.attrs.update(
        jobs_used=int(result["salary_job_count"].sum()),
        eligible_jobs=len(eligible),
        hidden_categories=int(hidden.sum()),
    )
    return result

def postings_per_day(jobs: pd.DataFrame) -> pd.DataFrame:
    """Count postings by continuous UTC date and source."""
    frame = prepare_jobs(jobs)
    dates = pd.to_datetime(frame["publication_date"], errors="coerce", utc=True)
    valid = dates.notna()
    if not valid.any():
        return EMPTY_POSTINGS.copy()

    dated = frame.loc[valid, ["source"]].copy()
    dated["publication_day"] = dates.loc[valid].dt.floor("D")
    dated["source"] = dated["source"].map(source_display_name).replace("", "Unknown")
    result = (
        dated.groupby(["publication_day", "source"], as_index=False)
        .size()
        .rename(columns={"size": "job_count"})
    )
    return result.sort_values(
        ["publication_day", "source"], ignore_index=True
    )

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


def _utc_timestamp_label(value) -> str:
    timestamp = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(timestamp):
        return ""
    return timestamp.strftime("%Y-%m-%d %H:%M UTC")

def compact_utc_timestamp(value) -> str:
    """Format a valid UTC timestamp compactly for a dashboard metric."""
    timestamp = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(timestamp):
        return ""
    return timestamp.strftime("%d %b %H:%M UTC")


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
            "Started at": frame["started_at"].map(_utc_timestamp_label),
            "Finished at": frame["finished_at"].map(_utc_timestamp_label),
            "Status": frame["status"].fillna(""),
            "Jobs fetched": frame["jobs_fetched"].fillna(0).astype(int),
            "Jobs cleaned": frame["jobs_cleaned"].fillna(0).astype(int),
            "Jobs skipped": frame["jobs_skipped"].fillna(0).astype(int),
            "Jobs upserted": frame["jobs_upserted"].fillna(0).astype(int),
            "Reused snapshot": frame["reused_snapshot"].fillna(False).astype(bool),
        }
    ).reset_index(drop=True)

def open_read_only_connection():
    """Open a read-only PostgreSQL connection using the project settings."""
    from src.config import config

    connection = psycopg2.connect(
        host=config.db_host,
        port=config.db_port,
        dbname=config.db_name,
        user=config.db_user,
        password=config.db_password,
        connect_timeout=5,
    )
    connection.set_session(readonly=True)
    return connection


def _query_dataframe(connection, query: str, parameters=()) -> pd.DataFrame:
    """Execute a parameterized query on a caller-owned connection."""
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        rows = cursor.fetchall()
        columns = [
            column.name if hasattr(column, "name") else column[0]
            for column in (cursor.description or ())
        ]
    return pd.DataFrame(rows, columns=columns)


def skill_display_name(skill_name: object) -> str:
    """Return a display-friendly name for an extracted skill."""
    if skill_name is None or pd.isna(skill_name):
        return ""
    label = str(skill_name).strip()
    return SKILL_DISPLAY_NAMES.get(label.casefold(), label)


def _selected_skill_names(selected_skills) -> list[str]:
    return list(
        dict.fromkeys(
            name
            for value in (selected_skills or ())
            if value is not None and (name := str(value).strip())
        )
    )


def _role_focus_parameters(role_focus: str) -> tuple[bool, list[str]]:
    if role_focus not in ROLE_FOCUS_OPTIONS:
        raise ValueError(f"Unsupported role focus: {role_focus}")
    return role_focus == ROLE_FOCUS_OPTIONS[0], list(_TECH_DATA_CATEGORY_ALIASES)


def fetch_skill_options(connection) -> pd.DataFrame:
    """Return all distinct tracked skills ordered by job demand."""
    result = _query_dataframe(
        connection,
        """
        SELECT
            skill_name,
            COUNT(DISTINCT (source, source_id)) AS job_count
        FROM extracted_job_skills
        GROUP BY skill_name
        ORDER BY job_count DESC, LOWER(skill_name), skill_name
        """,
    )
    result["display_name"] = result["skill_name"].map(skill_display_name)
    return result[["skill_name", "display_name", "job_count"]]


def fetch_skill_match_summary(
    connection, selected_skills, role_focus: str = ROLE_FOCUS_OPTIONS[0]
) -> pd.DataFrame:
    """Count jobs matching any or all chosen skills and tracked job coverage."""
    skill_names = _selected_skill_names(selected_skills)
    all_roles, category_aliases = _role_focus_parameters(role_focus)
    return _query_dataframe(
        connection,
        """
        WITH selected_job_counts AS (
            SELECT
                e.source,
                e.source_id,
                COUNT(DISTINCT e.skill_name) AS selected_skill_count
            FROM extracted_job_skills AS e
            JOIN jobs AS j
              ON j.source = e.source AND j.source_id = e.source_id
            WHERE e.skill_name = ANY(%s)
              AND (
                  %s OR LOWER(TRIM(COALESCE(j.category, ''))) = ANY(%s)
              )
            GROUP BY e.source, e.source_id
        ),
        tracked_job_keys AS (
            SELECT DISTINCT e.source, e.source_id
            FROM extracted_job_skills AS e
            JOIN jobs AS j
              ON j.source = e.source AND j.source_id = e.source_id
            WHERE %s OR LOWER(TRIM(COALESCE(j.category, ''))) = ANY(%s)
        )
        SELECT
            (SELECT COUNT(*) FROM tracked_job_keys) AS tracked_jobs,
            (SELECT COUNT(*) FROM selected_job_counts) AS jobs_any,
            (
                SELECT COUNT(*)
                FROM selected_job_counts
                WHERE selected_skill_count = %s
            ) AS jobs_all
        """,
        (
            skill_names,
            all_roles,
            category_aliases,
            all_roles,
            category_aliases,
            len(skill_names),
        ),
    )


def fetch_selected_skill_counts(
    connection, selected_skills, role_focus: str = ROLE_FOCUS_OPTIONS[0]
) -> pd.DataFrame:
    """Count each chosen skill across jobs in the selected role focus."""
    columns = ["skill_name", "display_name", "job_count"]
    skill_names = _selected_skill_names(selected_skills)
    if not skill_names:
        return pd.DataFrame(columns=columns)
    all_roles, category_aliases = _role_focus_parameters(role_focus)
    result = _query_dataframe(
        connection,
        """
        WITH selected_skills AS (
            SELECT skill_name, skill_index
            FROM UNNEST(%s::TEXT[]) WITH ORDINALITY AS chosen(skill_name, skill_index)
        ),
        skill_counts AS (
            SELECT
                e.skill_name,
                COUNT(DISTINCT (e.source, e.source_id)) AS job_count
            FROM extracted_job_skills AS e
            JOIN jobs AS j
              ON j.source = e.source AND j.source_id = e.source_id
            WHERE e.skill_name = ANY(%s)
              AND (
                  %s OR LOWER(TRIM(COALESCE(j.category, ''))) = ANY(%s)
              )
            GROUP BY e.skill_name
        )
        SELECT
            selected.skill_name,
            COALESCE(skill_counts.job_count, 0) AS job_count
        FROM selected_skills AS selected
        LEFT JOIN skill_counts USING (skill_name)
        ORDER BY job_count DESC, selected.skill_index
        """,
        (skill_names, skill_names, all_roles, category_aliases),
    )
    result["display_name"] = result["skill_name"].map(skill_display_name)
    return result[["skill_name", "display_name", "job_count"]]


def fetch_skills_to_learn(
    connection, selected_skills, role_focus: str = ROLE_FOCUS_OPTIONS[0]
) -> pd.DataFrame:
    """Return up to ten unchosen skills common in any-skill matching jobs."""
    columns = ["skill_name", "display_name", "job_count", "percent_jobs"]
    skill_names = _selected_skill_names(selected_skills)
    if not skill_names:
        return pd.DataFrame(columns=columns)
    all_roles, category_aliases = _role_focus_parameters(role_focus)
    result = _query_dataframe(
        connection,
        """
        WITH matching_jobs AS (
            SELECT DISTINCT e.source, e.source_id
            FROM extracted_job_skills AS e
            JOIN jobs AS j
              ON j.source = e.source AND j.source_id = e.source_id
            WHERE e.skill_name = ANY(%s)
              AND (
                  %s OR LOWER(TRIM(COALESCE(j.category, ''))) = ANY(%s)
              )
        ),
        match_sample AS (
            SELECT COUNT(*) AS matched_jobs FROM matching_jobs
        ),
        related_skill_counts AS (
            SELECT
                e.skill_name,
                COUNT(DISTINCT (e.source, e.source_id)) AS job_count
            FROM matching_jobs AS matched
            JOIN extracted_job_skills AS e
              ON e.source = matched.source AND e.source_id = matched.source_id
            WHERE NOT (e.skill_name = ANY(%s))
            GROUP BY e.skill_name
        )
        SELECT
            related.skill_name,
            related.job_count,
            COALESCE(
                100.0 * related.job_count / NULLIF(sample.matched_jobs, 0),
                0
            ) AS percent_jobs
        FROM related_skill_counts AS related
        CROSS JOIN match_sample AS sample
        ORDER BY related.job_count DESC, related.skill_name
        LIMIT 10
        """,
        (skill_names, all_roles, category_aliases, skill_names),
    )
    result["display_name"] = result["skill_name"].map(skill_display_name)
    return result[["skill_name", "display_name", "job_count", "percent_jobs"]]


def fetch_skill_match_salary(
    connection, selected_skills, role_focus: str = ROLE_FOCUS_OPTIONS[0]
) -> pd.DataFrame:
    """Return median yearly USD salary and sample count for any-skill matches."""
    columns = ["salary_job_count", "median_salary_usd"]
    skill_names = _selected_skill_names(selected_skills)
    if not skill_names:
        return pd.DataFrame([[0, None]], columns=columns)
    all_roles, category_aliases = _role_focus_parameters(role_focus)
    return _query_dataframe(
        connection,
        """
        WITH matching_jobs AS (
            SELECT DISTINCT e.source, e.source_id
            FROM extracted_job_skills AS e
            JOIN jobs AS j
              ON j.source = e.source AND j.source_id = e.source_id
            WHERE e.skill_name = ANY(%s)
              AND (
                  %s OR LOWER(TRIM(COALESCE(j.category, ''))) = ANY(%s)
              )
        ),
        salary_values AS (
            SELECT
                CASE
                    WHEN j.salary_min IS NOT NULL AND j.salary_max IS NOT NULL
                        THEN (j.salary_min::NUMERIC + j.salary_max::NUMERIC) / 2
                    ELSE COALESCE(j.salary_min::NUMERIC, j.salary_max::NUMERIC)
                END AS salary_value
            FROM matching_jobs AS matched
            JOIN jobs AS j
              ON j.source = matched.source AND j.source_id = matched.source_id
            WHERE LOWER(TRIM(COALESCE(j.salary_type, ''))) = 'yearly'
              AND UPPER(TRIM(COALESCE(j.currency, ''))) = 'USD'
              AND (j.salary_min IS NOT NULL OR j.salary_max IS NOT NULL)
        )
        SELECT
            COUNT(*) AS salary_job_count,
            percentile_cont(0.5::DOUBLE PRECISION) WITHIN GROUP (ORDER BY salary_value::DOUBLE PRECISION)
                AS median_salary_usd
        FROM salary_values
        """,
        (skill_names, all_roles, category_aliases),
    )


def fetch_skill_match_jobs(
    connection, selected_skills, role_focus: str = ROLE_FOCUS_OPTIONS[0]
) -> pd.DataFrame:
    """Return up to 20 newest jobs matching any selected skill."""
    columns = [
        "source",
        "source_id",
        "title",
        "company_name",
        "url",
        "publication_date",
    ]
    skill_names = _selected_skill_names(selected_skills)
    if not skill_names:
        return pd.DataFrame(columns=columns)
    all_roles, category_aliases = _role_focus_parameters(role_focus)
    return _query_dataframe(
        connection,
        """
        WITH matching_jobs AS (
            SELECT DISTINCT e.source, e.source_id
            FROM extracted_job_skills AS e
            JOIN jobs AS j
              ON j.source = e.source AND j.source_id = e.source_id
            WHERE e.skill_name = ANY(%s)
              AND (
                  %s OR LOWER(TRIM(COALESCE(j.category, ''))) = ANY(%s)
              )
        )
        SELECT
            j.source,
            j.source_id,
            j.title,
            j.company_name,
            j.url,
            j.publication_date
        FROM matching_jobs AS matched
        JOIN jobs AS j
          ON j.source = matched.source AND j.source_id = matched.source_id
        ORDER BY j.publication_date DESC NULLS LAST, j.source, j.source_id
        LIMIT 20
        """,
        (skill_names, all_roles, category_aliases),
    )
