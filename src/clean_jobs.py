from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from html import unescape
from pathlib import Path

from .schemas import CleanedJob, SalaryRange
from .skill_extractor import extract_skills
from .time_utils import to_utc
from .validators import ValidationError, validate_int, validate_list, validate_string


logger = logging.getLogger(__name__)

PROCESSED_OUTPUT_FILE = Path("data/jobs_latest.json")


class SalaryParser:
    NUMBER_PATTERN = re.compile(r"(?<!\w)(\d+(?:[,.]\d+)?)(?:\s*)(k)?\b", re.IGNORECASE)

    @classmethod
    def parse(cls, salary_str: str | None) -> SalaryRange | None:
        try:
            text = validate_string(salary_str, "salary", allow_empty=True)
        except ValidationError:
            return None

        if not text or text.strip() in {"-", "n/a", "na"}:
            return None

        currency = cls._detect_currency(text)
        frequency = cls._detect_frequency(text)
        scrubbed_text = cls._remove_noise(text.lower())
        parsed_numbers = cls._extract_numbers(scrubbed_text, frequency)
        if not parsed_numbers:
            return None

        salary_min = parsed_numbers[0]
        salary_max = parsed_numbers[1] if len(parsed_numbers) >= 2 else parsed_numbers[0]
        if salary_min > salary_max:
            salary_min, salary_max = salary_max, salary_min

        try:
            return SalaryRange(
                min_value=salary_min,
                max_value=salary_max,
                currency=currency,
                frequency=frequency,
            )
        except ValueError as exc:
            logger.debug("Could not parse salary %r: %s", salary_str, exc)
            return None

    @staticmethod
    def _detect_currency(text: str) -> str:
        lowered = text.lower()
        if "\u00a3" in text or "gbp" in lowered:
            return "GBP"
        if "\u20ac" in text or "eur" in lowered:
            return "EUR"
        return "USD"

    @staticmethod
    def _detect_frequency(text: str) -> str:
        lowered = text.lower()
        if re.search(r"(/?\s*h(?:ou)?r|hourly|per hour)", lowered):
            return "hourly"
        if re.search(r"(/?\s*mo\b|month|monthly|per month)", lowered):
            return "monthly"
        if re.search(r"(/?\s*yr\b|year|yearly|annual|annum|per year)", lowered):
            return "yearly"
        return "yearly"

    @staticmethod
    def _remove_noise(text: str) -> str:
        noise_patterns = [
            r"\bote\b",
            r"\bon target earnings\b",
            r"\([^)]*\)",
            r"bonus.*",
            r"performance.*",
            r"equity.*",
            r"up to \d+%",
            r"\+\s*\d+%",
        ]
        cleaned = text
        for pattern in noise_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
        return cleaned

    @classmethod
    def _extract_numbers(cls, text: str, frequency: str) -> list[int]:
        matches = list(cls.NUMBER_PATTERN.finditer(text))
        if not matches:
            return []

        any_k_suffix = any(match.group(2) for match in matches)
        values = []
        for match in matches:
            raw_number = match.group(1)
            has_k_suffix = bool(match.group(2))
            value = cls._parse_number(raw_number, has_k_suffix)

            if frequency in {"yearly", "monthly"}:
                if has_k_suffix or (any_k_suffix and value < 1000):
                    value *= 1000
                elif frequency == "yearly" and value < 1000 and not any_k_suffix:
                    value *= 1000

            values.append(round(value))
        return values

    @staticmethod
    def _parse_number(raw_number: str, has_k_suffix: bool) -> float:
        if has_k_suffix:
            normalized = raw_number.replace(",", ".")
            return float(normalized)
        normalized = raw_number.replace(",", "")
        return float(normalized)


def parse_datetime(value, field_name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return to_utc(value)

    try:
        text = validate_string(value, field_name, allow_empty=True)
    except ValidationError as exc:
        logger.warning("Invalid %s value %r: %s", field_name, value, exc)
        return None

    if not text:
        return None

    try:
        return to_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        logger.warning("Could not parse %s value %r; setting to None", field_name, value)
        return None


def _unescape_entities(value):
    return unescape(value) if isinstance(value, str) else value


def clean_job(raw_job: dict) -> CleanedJob | None:
    raw_job_id = raw_job.get("id") if isinstance(raw_job, dict) else None

    try:
        if not isinstance(raw_job, dict):
            raise ValidationError(f"raw_job must be dict, got {type(raw_job).__name__}")

        raw_job = dict(raw_job)
        for field in (
            "title",
            "company_name",
            "candidate_required_location",
            "category",
            "job_type",
            "description",
        ):
            raw_job[field] = _unescape_entities(raw_job.get(field))

        salary = SalaryParser.parse(raw_job.get("salary"))
        job = CleanedJob(
            id=validate_int(raw_job.get("id"), "id", min_val=1),
            title=validate_string(raw_job.get("title"), "title"),
            company=validate_string(raw_job.get("company_name"), "company_name"),
            category=validate_string(raw_job.get("category"), "category", allow_empty=True),
            job_type=validate_string(raw_job.get("job_type"), "job_type", allow_empty=True),
            location=validate_string(
                raw_job.get("candidate_required_location"),
                "candidate_required_location",
                allow_empty=True,
            ),
            tags=validate_list(raw_job.get("tags"), "tags", item_type=str),
            extracted_skills=extract_skills(
                description=raw_job.get("description"),
                title=raw_job.get("title"),
            ),
            url=validate_string(raw_job.get("url"), "url", allow_empty=True),
            salary=salary,
            publication_date=parse_datetime(
                raw_job.get("publication_date"),
                "publication_date",
            ),
            fetched_at=parse_datetime(raw_job.get("fetched_at"), "fetched_at"),
        )
        return job
    except ValidationError as exc:
        logger.warning("Skipping job %r due to validation error: %s", raw_job_id, exc)
        return None
    except ValueError as exc:
        logger.warning("Skipping job %r due to invalid data: %s", raw_job_id, exc)
        return None
    except Exception:
        logger.exception("Unexpected error while cleaning job %r", raw_job_id)
        return None


def _extract_raw_jobs(data) -> list:
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return data["jobs"]
    if isinstance(data, list):
        return data
    logger.warning("Unsupported raw jobs format; expected dict with jobs list or list.")
    return []


def main(raw_file_path: str) -> dict:
    logger.info("Processing raw file: %s", raw_file_path)
    PROCESSED_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(raw_file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    cleaned_jobs = []
    skipped = 0
    with_salary = 0
    without_salary = 0

    for raw_job in _extract_raw_jobs(data):
        cleaned_job = clean_job(raw_job)
        if cleaned_job is None:
            skipped += 1
            continue

        cleaned_jobs.append(cleaned_job.to_dict())
        if cleaned_job.salary is None:
            without_salary += 1
        else:
            with_salary += 1

    with PROCESSED_OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(cleaned_jobs, file, indent=2, ensure_ascii=False)

    total = len(cleaned_jobs)
    logger.info("Processing complete: %s", PROCESSED_OUTPUT_FILE)
    logger.info("Total jobs processed: %s", total)
    logger.info("Jobs with salary data: %s", with_salary)
    logger.info("Jobs without salary data: %s", without_salary)
    logger.info("Jobs skipped: %s", skipped)

    return {
        "file_path": str(PROCESSED_OUTPUT_FILE),
        "total": total,
        "with_salary": with_salary,
        "without_salary": without_salary,
        "skipped": skipped,
    }


if __name__ == "__main__":
    raise SystemExit("Run with python -m src.main from the project root, or import main(raw_file_path) directly.")
