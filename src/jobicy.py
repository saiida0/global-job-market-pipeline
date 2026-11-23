"""Jobicy fetching and cleaning helpers."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

import requests

from .clean_jobs import parse_datetime
from .schemas import CleanedJob, SalaryRange
from .skill_extractor import extract_skills
from .time_utils import get_utc_now
from .validators import ValidationError, validate_int, validate_string


logger = logging.getLogger(__name__)

API_URL = "https://jobicy.com/api/jobs"
SOURCE = "jobicy"
PAGE_SIZE = 100
MAX_PAGES = 20
PAGE_DELAY_SECONDS = 1.5
MAX_RETRIES = 3
RETRY_DELAY = 5
REQUEST_TIMEOUT = 30
RAW_OUTPUT_DIR = Path("data/raw")
PROCESSED_OUTPUT_FILE = Path("data/jobicy_jobs_latest.json")
MIN_FETCH_INTERVAL = timedelta(hours=6)

SALARY_PERIODS = {
    "hour": "hourly",
    "hourly": "hourly",
    "per hour": "hourly",
    "month": "monthly",
    "monthly": "monthly",
    "per month": "monthly",
    "year": "yearly",
    "yearly": "yearly",
    "annual": "yearly",
    "annually": "yearly",
    "per year": "yearly",
}


def _validate_page(data) -> tuple[list, str | int | None]:
    if not isinstance(data, dict):
        raise ValueError("Invalid Jobicy API response: expected a JSON object.")
    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("Invalid Jobicy API response: 'jobs' must be a list.")
    next_cursor = data.get("nextCursor")
    if next_cursor is not None and not isinstance(next_cursor, (str, int)):
        raise ValueError("Invalid Jobicy API response: 'nextCursor' must be text or null.")
    return jobs, next_cursor


def _retry_after_delay(value) -> float:
    if value is not None:
        try:
            return max(1.0, float(value))
        except (TypeError, ValueError):
            try:
                retry_at = parsedate_to_datetime(str(value))
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(1.0, (retry_at - get_utc_now()).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    return max(1.0, float(RETRY_DELAY))


def _fetch_page(params: dict) -> dict:
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                logger.warning(
                    "Jobicy request failed (%s); retrying page in %ss.",
                    type(exc).__name__,
                    RETRY_DELAY,
                )
                time.sleep(RETRY_DELAY)
                continue
            break

        status_code = response.status_code
        if status_code in {429, 503}:
            last_error = RuntimeError(f"Jobicy returned HTTP {status_code}.")
            if attempt < MAX_RETRIES:
                headers = getattr(response, "headers", {}) or {}
                delay = _retry_after_delay(headers.get("Retry-After"))
                logger.warning(
                    "Jobicy returned HTTP %s; retrying the same page in %ss.",
                    status_code,
                    delay,
                )
                time.sleep(delay)
                continue
            break

        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Jobicy request failed with HTTP {status_code}."
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ValueError("Invalid JSON response from Jobicy API.") from exc
        if not isinstance(data, dict):
            raise ValueError("Invalid Jobicy API response: expected a JSON object.")
        return data

    raise RuntimeError(
        f"All {MAX_RETRIES} attempts to fetch a Jobicy page failed."
    ) from last_error


def _reuse_recent_snapshot(now: datetime) -> dict | None:
    if os.getenv("FORCE_FETCH", "").strip().lower() == "true":
        logger.info("FORCE_FETCH=true; forcing a live %s fetch.", SOURCE)
        return None

    snapshots = [
        path
        for path in RAW_OUTPUT_DIR.glob("jobicy_jobs_*.json")
        if path.is_file()
    ]
    if not snapshots:
        logger.info("No raw snapshots found; fetching live from %s.", SOURCE)
        return None

    newest_snapshot = max(snapshots, key=lambda path: path.stat().st_mtime)
    saved_at = datetime.fromtimestamp(newest_snapshot.stat().st_mtime, timezone.utc)
    age = now - saved_at
    if age >= MIN_FETCH_INTERVAL:
        logger.info("Newest Jobicy snapshot is at least 6 hours old; fetching live.")
        return None

    try:
        with newest_snapshot.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"Cannot reuse recent Jobicy snapshot {newest_snapshot}: "
            "the file could not be read as JSON."
        ) from exc

    jobs, _ = _validate_page(data)
    metadata = data.get("_metadata")
    fetched_at = metadata.get("fetched_at") if isinstance(metadata, dict) else None
    if not isinstance(fetched_at, str) or not fetched_at:
        fetched_at = next(
            (
                job.get("fetched_at")
                for job in jobs
                if isinstance(job, dict)
                and isinstance(job.get("fetched_at"), str)
                and job["fetched_at"]
            ),
            saved_at.isoformat(),
        )

    logger.info(
        "Reusing recent Jobicy snapshot %s (%s jobs; age %s).",
        newest_snapshot,
        len(jobs),
        age,
    )
    return {
        "file_path": str(newest_snapshot),
        "job_count": len(jobs),
        "fetched_at": fetched_at,
        "reused": True,
    }


def fetch_jobs() -> dict:
    """Fetch up to twenty Jobicy pages or reuse a recent snapshot."""
    reused_result = _reuse_recent_snapshot(get_utc_now())
    if reused_result is not None:
        return reused_result

    jobs = []
    cursor = None
    page_count = 0
    cap_reached = False

    for page_number in range(1, MAX_PAGES + 1):
        params = {"count": PAGE_SIZE}
        if cursor is not None:
            params["cursor"] = cursor

        logger.info("Fetching Jobicy page %s/%s.", page_number, MAX_PAGES)
        data = _fetch_page(params)
        page_jobs, next_cursor = _validate_page(data)
        jobs.extend(job for job in page_jobs if isinstance(job, dict))
        malformed_count = len(page_jobs) - sum(
            isinstance(job, dict) for job in page_jobs
        )
        if malformed_count:
            logger.warning("Skipped %s malformed Jobicy jobs.", malformed_count)
        page_count += 1

        if next_cursor is None:
            break
        if page_number == MAX_PAGES:
            cap_reached = True
            break
        cursor = next_cursor
        time.sleep(PAGE_DELAY_SECONDS)

    logger.info("Fetched %s Jobicy pages.", page_count)
    if cap_reached:
        logger.warning(
            "Jobicy page cap of %s reached; more pages may remain.", MAX_PAGES
        )

    fetched_at = get_utc_now()
    fetched_at_iso = fetched_at.isoformat()
    for job in jobs:
        job["fetched_at"] = fetched_at_iso

    snapshot = {
        "jobs": jobs,
        "_metadata": {
            "source": SOURCE,
            "source_url": API_URL,
            "fetched_at": fetched_at_iso,
            "job_count": len(jobs),
            "page_count": page_count,
        },
    }
    filename = f"jobicy_jobs_{fetched_at.strftime('%Y%m%d_%H%M%S')}.json"
    output_path = RAW_OUTPUT_DIR / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(snapshot, file, indent=2, ensure_ascii=False)

    logger.info("Fetched %s jobs from Jobicy and saved %s.", len(jobs), output_path)
    return {
        "file_path": str(output_path),
        "job_count": len(jobs),
        "fetched_at": fetched_at_iso,
        "reused": False,
    }


def _first_label(value) -> str | None:
    values = value if isinstance(value, list) else [value]
    for item in values:
        if isinstance(item, dict):
            item = item.get("label") or item.get("name")
        if isinstance(item, str) and item.strip():
            return unescape(item.strip())
    return None


def _salary_amount(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return amount if amount > 0 else None


def _salary_frequency(value) -> str | None:
    if value is None:
        return "yearly"
    if not isinstance(value, str):
        return None
    return SALARY_PERIODS.get(value.strip().lower())


def _salary_range(raw_job: dict) -> SalaryRange | None:
    minimum = _salary_amount(raw_job.get("salaryMin"))
    maximum = _salary_amount(raw_job.get("salaryMax"))
    if minimum is None and maximum is None:
        return None
    if minimum is None:
        minimum = maximum
    if maximum is None:
        maximum = minimum
    if minimum > maximum:
        minimum, maximum = maximum, minimum

    frequency = _salary_frequency(raw_job.get("salaryPeriod"))
    if frequency is None:
        logger.info("Ignoring unsupported Jobicy salary period.")
        return None

    currency = raw_job.get("salaryCurrency") or "USD"
    try:
        return SalaryRange(minimum, maximum, currency, frequency)
    except (TypeError, ValueError):
        logger.info("Ignoring Jobicy salary outside supported currency or bounds.")
        return None


def _strip_html(value) -> str:
    if not isinstance(value, str):
        return ""
    return unescape(re.sub(r"<[^>]*>", " ", value))


def _unescape_text(value):
    return unescape(value) if isinstance(value, str) else value


def clean_job(raw_job: dict) -> CleanedJob | None:
    """Convert one raw Jobicy listing to the shared cleaned job structure."""
    raw_job_id = raw_job.get("id") if isinstance(raw_job, dict) else None
    try:
        if not isinstance(raw_job, dict):
            raise ValidationError("raw_job must be a dictionary")

        job_id = validate_int(raw_job.get("id"), "id", min_val=1)
        title = _unescape_text(validate_string(raw_job.get("jobTitle"), "jobTitle"))
        company = _unescape_text(validate_string(raw_job.get("companyName"), "companyName"))
        description = _strip_html(raw_job.get("jobDescription"))

        return CleanedJob(
            id=job_id,
            source=SOURCE,
            source_id=str(job_id),
            title=title,
            company=company,
            category=_first_label(raw_job.get("jobIndustry")),
            job_type=_first_label(raw_job.get("jobType")),
            location=_unescape_text(
                validate_string(raw_job.get("jobGeo"), "jobGeo", allow_empty=True)
            ),
            salary=_salary_range(raw_job),
            publication_date=parse_datetime(raw_job.get("pubDate"), "pubDate"),
            url=validate_string(raw_job.get("url"), "url", allow_empty=True),
            tags=[],
            fetched_at=parse_datetime(raw_job.get("fetched_at"), "fetched_at"),
            extracted_skills=extract_skills(description=description, title=title),
        )
    except (ValidationError, ValueError) as exc:
        logger.warning("Skipping Jobicy job %r (%s).", raw_job_id, type(exc).__name__)
        return None


def _extract_raw_jobs(data) -> list:
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return data["jobs"]
    if isinstance(data, list):
        return data
    raise ValueError("Unsupported Jobicy data format; expected an object with jobs list.")


def clean_jobs(raw_file_path: str | Path) -> dict:
    """Clean a Jobicy raw snapshot into a separate description-free JSON file."""
    raw_file_path = Path(raw_file_path)
    with raw_file_path.open("r", encoding="utf-8") as file:
        raw_data = json.load(file)

    cleaned_jobs = []
    skipped = 0
    with_salary = 0
    without_salary = 0

    for raw_job in _extract_raw_jobs(raw_data):
        cleaned_job = clean_job(raw_job)
        if cleaned_job is None:
            skipped += 1
            continue
        cleaned_jobs.append(cleaned_job.to_dict())
        if cleaned_job.salary is None:
            without_salary += 1
        else:
            with_salary += 1

    PROCESSED_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PROCESSED_OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(cleaned_jobs, file, indent=2, ensure_ascii=False)

    return {
        "file_path": str(PROCESSED_OUTPUT_FILE),
        "total": len(cleaned_jobs),
        "with_salary": with_salary,
        "without_salary": without_salary,
        "skipped": skipped,
    }
