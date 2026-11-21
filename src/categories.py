"""Shared category labels for jobs from all supported providers."""

from __future__ import annotations


SHARED_CATEGORIES = (
    "Software Development",
    "Data and Analytics",
    "AI and Machine Learning",
    "Design",
    "Marketing",
    "Sales",
    "Customer Support",
    "Product and Management",
    "Writing",
    "Finance and Legal",
    "Operations and HR",
    "Other",
)

_CATEGORY_GROUPS = {
    "Software Development": (
        "Cybersecurity",
        "DevOps & Infrastructure",
        "Information Technology",
        "QA & Testing",
        "Software Development",
        "Software Engineering",
        "Engineering",
        "Software",
    ),
    "Data and Analytics": (
        "Data and Analytics",
        "Data Science & Analytics",
        "Data",
    ),
    "AI and Machine Learning": (
        "Artificial Intelligence",
        "AI",
        "Machine Learning",
    ),
    "Design": (
        "Creative & Design",
        "Web, UI & UX Design",
        "Design",
    ),
    "Marketing": (
        "Marketing",
        "Marketing & Sales",
        "SEO",
    ),
    "Sales": (
        "Sales",
        "Business Development",
    ),
    "Customer Support": (
        "Customer Service",
        "Customer Support & Success",
        "Technical Support",
        "Customer Support",
    ),
    "Product and Management": (
        "Product & Operations",
        "Project & Program Management",
        "Product and Management",
    ),
    "Writing": (
        "Content & Editorial",
        "Writing",
    ),
    "Finance and Legal": (
        "Finance & Accounting",
        "Legal & Compliance",
        "Finance and Legal",
    ),
    "Operations and HR": (
        "HR & Recruiting",
        "Operations",
        "Operations and HR",
    ),
    "Other": (
        "All others",
        "Education & E-learning",
        "Healthcare & Medical",
        "Other",
    ),
}

CATEGORY_MAP = {
    alias.strip().casefold(): shared_name
    for shared_name, aliases in _CATEGORY_GROUPS.items()
    for alias in aliases
}


def normalize_category(value: object) -> str:
    """Map a provider category to a shared display label."""
    if value is None:
        return "Other"

    label = str(value).strip()
    if not label:
        return "Other"
    return CATEGORY_MAP.get(label.casefold(), "Other")
