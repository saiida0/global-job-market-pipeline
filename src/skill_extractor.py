"""Deterministic dictionary-based skill extraction from job text."""

from __future__ import annotations

import re
from html import unescape


EXTRACTOR_VERSION = "1.1.0"

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

# These words also have common non-technical meanings. Require a nearby cue that
# the mention refers to a tool, language, framework, or data library.
_AMBIGUOUS_CONTEXTS: dict[str, tuple[str, ...]] = {
    "Excel": (
        r"\bmicrosoft\s+excel\b",
        r"\bexcel\s*(?:/|&|and)\s*(?:google\s+)?sheets?\b",
        r"\bexcel\s+(?:spread\s*)?sheets?\b",
        r"\b(?:spread\s*)?sheets?\s+(?:in|with|using)\s+excel\b",
        r"\bexcel\s+(?:skills?|proficiency|experience|expertise|formulas?|functions?|pivot\s*tables?|macros?|vba|workbooks?)\b",
        r"\b(?:advanced|expert|proficient|intermediate|basic|strong)\s+(?:in|with|using)?\s*excel\b",
        r"\b(?:skills?|experience|expertise|proficiency|proficient|knowledge)\s+(?:in|with|using|of)\s+(?:microsoft\s+)?excel\b",
        r"\b(?:using|with)\s+excel\b",
    ),
    "Java": (
        r"\bjava\s*(?:/|and)\s*(?:kotlin|scala)\b",
        r"\bjava\s+(?:\d{1,2}|se|ee|fx)\b",
        r"\bjava\b.{0,35}\b(?:developer|engineer|programmer|programming|software|code|language|backend|back-end|spring|jvm|skills?|experience|applications?)\b",
        r"\b(?:developer|engineer|programmer|programming|software|code|language|backend|back-end|spring|jvm|skills?|experience|applications?)\b.{0,35}\bjava\b",
        r"\bjvm\b|\bspring\s+boot\b",
    ),
    "React": (
        r"\breact(?:\.js|js)\b",
        r"\breact\b.{0,30}\b(?:developer|engineer|framework|library|component|hooks?|redux|frontend|front-end|skills?|experience|application)\b",
        r"\b(?:developer|engineer|framework|library|component|hooks?|redux|frontend|front-end|skills?|experience|application)\b.{0,30}\breact\b",
    ),
    "Bash": (
        r"\bbash\b.{0,30}\b(?:shell|scripts?|scripting|terminal|command\s+line|linux|unix|skills?|experience)\b",
        r"\b(?:shell|scripts?|scripting|terminal|command\s+line|linux|unix|skills?|experience)\b.{0,30}\bbash\b",
    ),
    "Git": (
        r"\bgit\b.{0,35}\b(?:version\s+control|source\s+control|repositories|repository|branches|branching|branch|commits|commit|skills?|experience|commands?)\b",
        r"\b(?:version\s+control|source\s+control|repositories|repository|branches|branching|branch|commits|commit|skills?|experience|commands?)\b.{0,35}\bgit\b",
    ),
    "pandas": (
        r"\bpandas\b.{0,30}\b(?:library|dataframes?|python|data\s+analysis|skills?|experience)\b",
        r"\b(?:python|library|dataframes?|data\s+analysis|skills?|experience)\b.{0,30}\bpandas\b",
    ),
    "Apache Spark": (
        r"\bapache\s+spark\b",
        r"\bspark\b.{0,30}\b(?:sql|streaming|dataframes?|mllib|ml|cluster|jobs?|skills?|experience)\b",
        r"\b(?:pyspark|spark\s+sql|spark\s+streaming|spark\s+dataframes?|apache)\b",
    ),
    "Azure": (
        r"\bmicrosoft\s+azure\b",
        r"\bazure\b.{0,30}\b(?:cloud|platform|services|resources?|subscription|devops|skills?|experience)\b",
        r"\b(?:cloud|platform|services|resources?|subscription|devops|skills?|experience)\b.{0,30}\bazure\b",
    ),
}

# The short JavaScript alias is ambiguous without a development cue, while the
# full JavaScript and Java Script aliases remain explicit.
_AMBIGUOUS_ALIAS_CONTEXTS: dict[tuple[str, str], tuple[str, ...]] = {
    ("JavaScript", "js"): (
        r"\bjs\b.{0,25}\b(?:developer|engineer|frontend|front-end|browser|node|react|skills?|experience|framework|library)\b",
        r"\b(?:developer|engineer|frontend|front-end|browser|node|react|skills?|experience|framework|library)\b.{0,25}\bjs\b",
    )
}

_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_COMPILED_AMBIGUOUS_CONTEXTS = {
    name: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for name, patterns in _AMBIGUOUS_CONTEXTS.items()
}
_COMPILED_ALIAS_CONTEXTS = {
    key: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for key, patterns in _AMBIGUOUS_ALIAS_CONTEXTS.items()
}


def _text_without_html(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return _HTML_TAG_PATTERN.sub(" ", unescape(value))


def _compile_alias(alias: str) -> re.Pattern[str]:
    words = r"\s+".join(re.escape(word) for word in alias.split())
    if alias.casefold() == "js":
        return re.compile(rf"(?<![\w.]){words}(?!\w)", re.IGNORECASE)
    return re.compile(rf"(?<!\w){words}(?!\w)", re.IGNORECASE)


def _has_technical_context(
    canonical_name: str,
    alias: str,
    searchable_text: str,
    match: re.Match[str],
) -> bool:
    """Require nearby technical wording for ambiguous names and aliases."""
    context_patterns = _COMPILED_AMBIGUOUS_CONTEXTS.get(canonical_name, ())
    context_patterns += _COMPILED_ALIAS_CONTEXTS.get((canonical_name, alias), ())
    if not context_patterns:
        return True

    boundaries = ".!?;\n"
    preceding = [searchable_text.rfind(char, 0, match.start()) for char in boundaries]
    following = [searchable_text.find(char, match.end()) for char in boundaries]
    sentence_start = max(preceding, default=-1) + 1
    sentence_ends = [position for position in following if position >= 0]
    sentence_end = min(sentence_ends, default=len(searchable_text))
    window_start = max(sentence_start, match.start() - 80)
    window_end = min(sentence_end, match.end() + 80)
    nearby_text = searchable_text[window_start:window_end]
    return any(pattern.search(nearby_text) for pattern in context_patterns)

_SKILL_PATTERNS = tuple(
    (
        canonical_name,
        tuple((alias, _compile_alias(alias)) for alias in aliases),
    )
    for canonical_name, aliases in SKILL_ALIASES.items()
)


def extract_skills(
    description: str | None = None,
    title: str | None = None,
) -> list[str]:
    """Return unique canonical skills found in a job description or title.

    Matching is case-insensitive and uses word boundaries. Ambiguous names such
    as Excel, Java, React, Bash, Git, pandas, Spark, and Azure need nearby
    technical wording. HTML tags in the description are ignored, and output
    order follows ``SKILL_ALIASES``.
    """
    searchable_text = " ".join(
        text
        for text in (_text_without_html(description), _text_without_html(title))
        if text
    )
    if not searchable_text:
        return []

    matches = []
    for canonical_name, alias_patterns in _SKILL_PATTERNS:
        if any(
            _has_technical_context(canonical_name, alias, searchable_text, match)
            for alias, pattern in alias_patterns
            for match in pattern.finditer(searchable_text)
        ):
            matches.append(canonical_name)
    return matches
