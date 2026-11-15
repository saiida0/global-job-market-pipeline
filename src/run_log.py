"""Helpers for recording pipeline runs and daily database snapshots."""

from __future__ import annotations

from datetime import date

from .load_jobs import get_db_connection


INSERT_PIPELINE_RUN_SQL = """
    INSERT INTO pipeline_runs (
        started_at,
        finished_at,
        status,
        jobs_fetched,
        jobs_cleaned,
        jobs_skipped,
        jobs_upserted,
        reused_snapshot,
        error_message
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

DAILY_TOTALS_SQL = """
    SELECT
        COUNT(*) AS total_jobs,
        COUNT(*) FILTER (
            WHERE salary_min IS NOT NULL OR salary_max IS NOT NULL
        ) AS jobs_with_salary
    FROM jobs
"""

DAILY_SKILLS_SQL = """
    SELECT BTRIM(tag.skill) AS skill, COUNT(DISTINCT jobs.id) AS jobs
    FROM jobs
    CROSS JOIN LATERAL UNNEST(
        COALESCE(jobs.tags, ARRAY[]::TEXT[])
    ) AS tag(skill)
    WHERE tag.skill IS NOT NULL AND BTRIM(tag.skill) <> ''
    GROUP BY BTRIM(tag.skill)
    ORDER BY BTRIM(tag.skill)
"""

UPSERT_DAILY_STATS_SQL = """
    INSERT INTO daily_stats (day, total_jobs, jobs_with_salary, updated_at)
    VALUES (%s, %s, %s, NOW())
    ON CONFLICT (day) DO UPDATE SET
        total_jobs = EXCLUDED.total_jobs,
        jobs_with_salary = EXCLUDED.jobs_with_salary,
        updated_at = NOW()
"""

DELETE_DAILY_SKILLS_SQL = """
    DELETE FROM daily_skill_counts
    WHERE day = %s
"""

UPSERT_DAILY_SKILL_SQL = """
    INSERT INTO daily_skill_counts (day, skill, jobs)
    VALUES (%s, %s, %s)
    ON CONFLICT (day, skill) DO UPDATE SET
        jobs = EXCLUDED.jobs
"""


def _safe_error_message(error: BaseException | None) -> str | None:
    if error is None:
        return None
    # Do not persist exception text: database errors may contain credentials.
    return "Pipeline failed; see application logs."


def write_pipeline_run(
    connection,
    *,
    started_at,
    finished_at,
    status: str,
    jobs_fetched: int = 0,
    jobs_cleaned: int = 0,
    jobs_skipped: int = 0,
    jobs_upserted: int = 0,
    reused_snapshot: bool = False,
    error: BaseException | None = None,
) -> None:
    """Insert exactly one success or failure record using a supplied connection."""
    if status not in {"success", "failed"}:
        raise ValueError("Pipeline run status must be 'success' or 'failed'.")

    error_message = _safe_error_message(error) if status == "failed" else None
    with connection.cursor() as cursor:
        cursor.execute(
            INSERT_PIPELINE_RUN_SQL,
            (
                started_at,
                finished_at,
                status,
                int(jobs_fetched),
                int(jobs_cleaned),
                int(jobs_skipped),
                int(jobs_upserted),
                bool(reused_snapshot),
                error_message,
            ),
        )
    connection.commit()


def upsert_daily_stats(connection, day: date) -> dict[str, int]:
    """Snapshot current job and tag totals for one UTC date."""
    with connection.cursor() as cursor:
        cursor.execute(DAILY_TOTALS_SQL)
        totals = cursor.fetchone() or (0, 0)
        total_jobs, jobs_with_salary = (int(value or 0) for value in totals)

        cursor.execute(DAILY_SKILLS_SQL)
        skills = cursor.fetchall()

        cursor.execute(
            UPSERT_DAILY_STATS_SQL,
            (day, total_jobs, jobs_with_salary),
        )
        cursor.execute(DELETE_DAILY_SKILLS_SQL, (day,))
        for skill, jobs in skills:
            cursor.execute(
                UPSERT_DAILY_SKILL_SQL,
                (day, skill, int(jobs)),
            )

    connection.commit()
    return {
        "total_jobs": total_jobs,
        "jobs_with_salary": jobs_with_salary,
        "skills": len(skills),
    }


def record_pipeline_run(**run_fields) -> None:
    """Open a pipeline connection and insert the supplied run record."""
    with get_db_connection() as connection:
        write_pipeline_run(connection, **run_fields)


def record_daily_stats(day: date) -> dict[str, int]:
    """Open a pipeline connection and refresh the snapshot for one date."""
    with get_db_connection() as connection:
        return upsert_daily_stats(connection, day)
