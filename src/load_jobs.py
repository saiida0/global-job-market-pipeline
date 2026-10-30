from __future__ import annotations

import json
import logging
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from .config import config
from .time_utils import get_utc_now, to_utc


logger = logging.getLogger(__name__)

PROCESSED_OUTPUT_FILE = Path("data/jobs_latest.json")


@contextmanager
def get_db_connection():
    """
    Yield a psycopg2 connection and guarantee cleanup.
    """
    conn = None
    try:
        logger.info(
            "Connecting to database %s at %s:%s as user %s",
            config.db_name,
            config.db_host,
            config.db_port,
            config.db_user,
        )
        conn = psycopg2.connect(
            host=config.db_host,
            port=config.db_port,
            dbname=config.db_name,
            user=config.db_user,
            password=config.db_password,
        )
        yield conn
    except psycopg2.OperationalError:
        logger.error(
            "Database connection failed for database %s at %s:%s as user %s.",
            config.db_name,
            config.db_host,
            config.db_port,
            config.db_user,
            exc_info=True,
        )
        raise
    finally:
        if conn and not conn.closed:
            conn.close()


def get_latest_processed_file() -> Path:
    if not PROCESSED_OUTPUT_FILE.exists():
        raise FileNotFoundError(f"No processed job file found at {PROCESSED_OUTPUT_FILE}")
    logger.warning("No file path provided; using latest file: %s", PROCESSED_OUTPUT_FILE)
    return PROCESSED_OUTPUT_FILE


def parse_timestamp(value, field_name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return to_utc(value)
    if not isinstance(value, str) or not value.strip():
        logger.warning("Could not parse %s: %r; setting to None", field_name, value)
        return None

    try:
        return to_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        logger.warning("Could not parse %s: %r; setting to None", field_name, value)
        return None


def load_processed_jobs(file_path: Path) -> list:
    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return data["jobs"]
    raise ValueError(f"Unsupported processed jobs format in {file_path}")


def _has_required_fields(job: dict) -> bool:
    return bool(job.get("id") and job.get("title") and job.get("company"))


def build_rows(jobs: list) -> tuple[list, int]:
    """
    Map cleaned job dicts to DB row tuples for the jobs table.
    """
    rows = []
    skipped = 0
    for job in jobs:
        if not isinstance(job, dict) or not _has_required_fields(job):
            logger.warning("Skipping job with missing required fields: %r", job)
            skipped += 1
            continue

        fetched_at = parse_timestamp(job.get("fetched_at"), "fetched_at") or get_utc_now()
        rows.append(
            (
                job.get("id"),
                job.get("title"),
                job.get("company"),
                job.get("location"),
                job.get("salary_min"),
                job.get("salary_max"),
                job.get("salary_type"),
                job.get("currency"),
                parse_timestamp(job.get("publication_date"), "publication_date"),
                fetched_at,
                "remotive",
                job.get("category"),
                job.get("job_type"),
                job.get("tags") or [],
                job.get("url"),
            )
        )
    return rows, skipped


def upsert_jobs(rows: list, connection) -> dict:
    """
    Bulk upsert job rows into PostgreSQL.
    """
    if not rows:
        logger.warning("No rows to upsert.")
        return {"upserted": 0}

    query = """
        INSERT INTO jobs (
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
            source,
            category,
            job_type,
            tags,
            url
        ) VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            title                        = EXCLUDED.title,
            company_name                 = EXCLUDED.company_name,
            candidate_required_location  = EXCLUDED.candidate_required_location,
            salary_min                   = EXCLUDED.salary_min,
            salary_max                   = EXCLUDED.salary_max,
            salary_type                  = EXCLUDED.salary_type,
            currency                     = EXCLUDED.currency,
            publication_date             = EXCLUDED.publication_date,
            fetched_at                   = EXCLUDED.fetched_at,
            source                       = EXCLUDED.source,
            category                     = EXCLUDED.category,
            job_type                     = EXCLUDED.job_type,
            tags                         = EXCLUDED.tags,
            url                          = EXCLUDED.url,
            updated_at                   = NOW()
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)
    connection.commit()

    count = len(rows)
    logger.info("Inserted/updated %s job records", count)
    return {"upserted": count}


def main(processed_file_path: str | None = None) -> dict:
    file_path = Path(processed_file_path) if processed_file_path else get_latest_processed_file()
    logger.info("Loading processed jobs from: %s", file_path)

    jobs = load_processed_jobs(file_path)
    rows, skipped = build_rows(jobs)

    with get_db_connection() as connection:
        result = upsert_jobs(rows, connection)

    result["skipped"] = skipped
    if result["upserted"] == 0:
        logger.warning("0 rows upserted; the processed file may be empty or malformed.")

    return result


if __name__ == "__main__":
    input_path = sys.argv[1] if len(sys.argv) > 1 else None
    main(input_path)
