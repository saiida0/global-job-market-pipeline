"""Deterministic dictionary-based skill extraction from job text."""

from __future__ import annotations

import re
from html import unescape


EXTRACTOR_VERSION = "1.0.0"

# Keep canonical names in the desired output order. Add aliases here when the
# dictionary changes; EXTRACTOR_VERSION should change with material updates.
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "SQL": ("sql", "structured query language"),
    "Java": ("java",),
    "JavaScript": ("javascript", "java script", "js"),
    "TypeScript": ("typescript", "type script"),
    "Bash": ("bash",),
    "React": ("react", "react.js", "reactjs"),
    "Node.js": ("node.js", "nodejs"),
    "Django": ("django",),
    "FastAPI": ("fastapi", "fast api"),
    "PostgreSQL": ("postgresql", "postgres", "postgre sql"),
    "MySQL": ("mysql", "my sql"),
    "pandas": ("pandas",),
    "Apache Spark": ("apache spark", "spark"),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure", "microsoft azure"),
    "Google Cloud Platform": ("google cloud platform", "google cloud", "gcp"),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "Terraform": ("terraform",),
    "Git": ("git",),
    "Excel": ("excel", "microsoft excel"),
    "Power BI": ("power bi", "powerbi"),
}

_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


def _text_without_html(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return _HTML_TAG_PATTERN.sub(" ", unescape(value))


def _compile_alias(alias: str) -> re.Pattern[str]:
    words = r"\s+".join(re.escape(word) for word in alias.split())
    return re.compile(rf"(?<!\w){words}(?!\w)", re.IGNORECASE)


_SKILL_PATTERNS = tuple(
    (
        canonical_name,
        tuple(_compile_alias(alias) for alias in aliases),
    )
    for canonical_name, aliases in SKILL_ALIASES.items()
)


def extract_skills(
    description: str | None = None,
    title: str | None = None,
) -> list[str]:
    """Return unique canonical skills found in a job description or title.

    Matching is case-insensitive and uses word boundaries. HTML tags in the
    description are ignored, and output order follows ``SKILL_ALIASES``.
    """
    searchable_text = " ".join(
        text
        for text in (_text_without_html(description), _text_without_html(title))
        if text
    )
    if not searchable_text:
        return []

    return [
        canonical_name
        for canonical_name, patterns in _SKILL_PATTERNS
        if any(pattern.search(searchable_text) for pattern in patterns)
    ]
