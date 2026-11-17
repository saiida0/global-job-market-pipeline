from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


CURRENCY_TO_USD = {
    "USD": 1.0,
    "GBP": 1.27,
    "EUR": 1.10,
}

FREQUENCY_MULTIPLIER = {
    "hourly": 2080,
    "monthly": 12,
    "yearly": 1,
}

SALARY_BOUNDS = {
    "hourly": (5, 500),
    "monthly": (500, 50_000),
    "yearly": (5_000, 500_000),
}


@dataclass(frozen=True)
class SalaryRange:
    min_value: int
    max_value: int
    currency: str = "USD"
    frequency: str = "yearly"

    def __post_init__(self) -> None:
        try:
            min_value = int(self.min_value)
            max_value = int(self.max_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Salary values must be integers.") from exc

        currency = str(self.currency or "USD").upper()
        frequency = str(self.frequency or "yearly").lower()

        object.__setattr__(self, "min_value", min_value)
        object.__setattr__(self, "max_value", max_value)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "frequency", frequency)

        if min_value <= 0 or max_value <= 0:
            raise ValueError("Salary values must be positive.")
        if min_value > max_value:
            raise ValueError(
                f"Salary min_value must be <= max_value, got {min_value}>{max_value}."
            )
        if currency not in CURRENCY_TO_USD:
            raise ValueError(f"Unsupported currency {currency!r}.")
        if frequency not in FREQUENCY_MULTIPLIER:
            raise ValueError(f"Unsupported salary frequency {frequency!r}.")

        lower_bound, upper_bound = SALARY_BOUNDS[frequency]
        if min_value < lower_bound or max_value > upper_bound:
            raise ValueError(
                f"{frequency} salary must be between {lower_bound} and {upper_bound}; "
                f"got {min_value}-{max_value}."
            )

    def normalize_to_yearly_usd(self) -> tuple[int, int]:
        multiplier = FREQUENCY_MULTIPLIER[self.frequency]
        currency_rate = CURRENCY_TO_USD[self.currency]

        yearly_min = round(self.min_value * multiplier * currency_rate)
        yearly_max = round(self.max_value * multiplier * currency_rate)
        return yearly_min, yearly_max


@dataclass
class CleanedJob:
    id: int
    title: str
    company: str
    category: str | None = None
    location: str | None = None
    salary: SalaryRange | None = None
    job_type: str | None = None
    publication_date: datetime | None = None
    url: str | None = None
    tags: list[str] = field(default_factory=list)
    fetched_at: datetime | None = None
    extracted_skills: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.id is None:
            raise ValueError("CleanedJob.id is required.")
        try:
            self.id = int(self.id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"CleanedJob.id must be an integer, got {self.id!r}.") from exc
        if self.id <= 0:
            raise ValueError(f"CleanedJob.id must be positive, got {self.id!r}.")

        for field_name in ("title", "company"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"CleanedJob.{field_name} is required.")
            setattr(self, field_name, value.strip())

        clean_tags = []
        for tag in self.tags or []:
            if isinstance(tag, str) and tag.strip():
                clean_tags.append(tag.strip().lower())
        self.tags = clean_tags

    def to_dict(self) -> dict:
        salary_min = salary_max = salary_type = currency = None
        yearly_min_usd = yearly_max_usd = None
        if self.salary:
            salary_min = self.salary.min_value
            salary_max = self.salary.max_value
            salary_type = self.salary.frequency
            currency = self.salary.currency
            yearly_min_usd, yearly_max_usd = self.salary.normalize_to_yearly_usd()

        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "category": self.category,
            "job_type": self.job_type,
            "location": self.location,
            "tags": self.tags,
            "extracted_skills": self.extracted_skills,
            "url": self.url,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_type": salary_type,
            "currency": currency,
            "salary_yearly_min_usd": yearly_min_usd,
            "salary_yearly_max_usd": yearly_max_usd,
            "publication_date": (
                self.publication_date.isoformat() if self.publication_date else None
            ),
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
        }
