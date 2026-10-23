import json
import logging
import time
from pathlib import Path

import requests

from .time_utils import get_utc_now


logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"
SOURCE = "remotive"
MAX_RETRIES = 3
RETRY_DELAY = 5
REQUEST_TIMEOUT = 30
RAW_OUTPUT_DIR = Path("data/raw")


def validate_api_response(data) -> list:
    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid {SOURCE} API response: expected a JSON object, "
            f"got {type(data).__name__}."
        )

    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError(f"Invalid {SOURCE} API response: 'jobs' must be a list.")
    if not jobs:
        raise ValueError(f"{SOURCE} API returned zero jobs.")

    return jobs


def fetch_remote_jobs() -> dict:
    """Fetch jobs and save the response as a timestamped raw snapshot."""
    last_exception = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Fetching jobs from Remotive API (attempt %s/%s)...",
                attempt,
                MAX_RETRIES,
            )
            response = requests.get(API_URL, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            break
        except requests.RequestException as exc:
            last_exception = exc
            logger.warning("Attempt %s failed: %s", attempt, exc)
            if attempt < MAX_RETRIES:
                logger.info("Retrying in %ss...", RETRY_DELAY)
                time.sleep(RETRY_DELAY)
    else:
        raise RuntimeError(
            f"All {MAX_RETRIES} attempts to fetch Remotive API failed."
        ) from last_exception

    try:
        data = response.json()
    except ValueError as exc:
        raise ValueError(f"Invalid JSON response from {SOURCE} API.") from exc

    raw_jobs = validate_api_response(data)
    fetched_at = get_utc_now()
    fetched_at_iso = fetched_at.isoformat()

    jobs = []
    for index, job in enumerate(raw_jobs, start=1):
        if not isinstance(job, dict):
            logger.warning(
                "Skipping malformed job at API response index %s: "
                "expected dict, got %s",
                index,
                type(job).__name__,
            )
            continue
        job["fetched_at"] = fetched_at_iso
        jobs.append(job)

    if not jobs:
        raise ValueError(f"{SOURCE} API response contained no valid jobs.")

    data["jobs"] = jobs
    data["_metadata"] = {
        "source": SOURCE,
        "source_url": API_URL,
        "fetched_at": fetched_at_iso,
        "job_count": len(jobs),
    }

    filename = f"remotive_jobs_{fetched_at.strftime('%Y%m%d_%H%M%S')}.json"
    output_path = RAW_OUTPUT_DIR / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    logger.info("Fetched %s jobs from %s", len(jobs), SOURCE)
    logger.info("Saved %s raw jobs to %s", len(jobs), output_path)
    return {
        "file_path": str(output_path),
        "job_count": len(jobs),
        "fetched_at": fetched_at_iso,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    print(fetch_remote_jobs())
