import pytest

from src.skill_extractor import EXTRACTOR_VERSION, extract_skills


def test_extracts_initial_canonical_skill_names():
    text = (
        "Python SQL Java JavaScript TypeScript Bash React Node.js Django FastAPI "
        "PostgreSQL MySQL pandas Apache Spark AWS Azure Google Cloud Platform "
        "Docker Kubernetes Terraform Git Excel Power BI"
    )

    assert extract_skills(description=text) == [
        "Python",
        "SQL",
        "Java",
        "JavaScript",
        "TypeScript",
        "Bash",
        "React",
        "Node.js",
        "Django",
        "FastAPI",
        "PostgreSQL",
        "MySQL",
        "pandas",
        "Apache Spark",
        "AWS",
        "Azure",
        "Google Cloud Platform",
        "Docker",
        "Kubernetes",
        "Terraform",
        "Git",
        "Excel",
        "Power BI",
    ]


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "JS Postgres Amazon Web Services GCP K8s",
            [
                "JavaScript",
                "PostgreSQL",
                "AWS",
                "Google Cloud Platform",
                "Kubernetes",
            ],
        ),
        (
            "jAvAsCrIpT JAVA python",
            ["Python", "Java", "JavaScript"],
        ),
        (
            "We use PowerBI and Microsoft Excel with Google Cloud.",
            ["Google Cloud Platform", "Excel", "Power BI"],
        ),
    ],
)
def test_aliases_and_case_insensitive_matching(text, expected):
    assert extract_skills(description=text) == expected


def test_java_does_not_match_inside_javascript():
    assert extract_skills(description="JavaScript engineer") == ["JavaScript"]
    assert extract_skills(description="Java and JavaScript") == ["Java", "JavaScript"]


def test_duplicate_mentions_across_description_and_title_are_deduplicated():
    assert extract_skills(
        description="Python, Python, and AWS. Python is required.",
        title="Senior Python Engineer",
    ) == ["Python", "AWS"]


def test_matches_multiword_aliases_with_variable_whitespace_and_html():
    description = "<p>Amazon&nbsp;&nbsp;Web Services and Apache <strong>Spark</strong></p>"

    assert extract_skills(description=description) == ["Apache Spark", "AWS"]


def test_missing_or_empty_description_does_not_raise():
    assert extract_skills() == []
    assert extract_skills(description=None) == []
    assert extract_skills(description="  ") == []


def test_ambiguous_short_terms_are_not_in_the_initial_dictionary():
    assert extract_skills(description="R, C, and Go are mentioned.") == []


def test_extractor_version_is_explicit():
    assert EXTRACTOR_VERSION == "1.0.0"
