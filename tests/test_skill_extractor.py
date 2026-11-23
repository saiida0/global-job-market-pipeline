import pytest

from src.skill_extractor import EXTRACTOR_VERSION, extract_skills


def test_extracts_canonical_names_with_context_for_ambiguous_skills():
    text = (
        "Python SQL Java developer JavaScript TypeScript Bash scripting React developer "
        "Node.js Django FastAPI PostgreSQL MySQL pandas DataFrame Apache Spark "
        "AWS Azure cloud Google Cloud Platform Docker Kubernetes Terraform "
        "Git version control Excel spreadsheets Power BI"
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
            "JS developer Postgres Amazon Web Services GCP K8s",
            [
                "JavaScript",
                "PostgreSQL",
                "AWS",
                "Google Cloud Platform",
                "Kubernetes",
            ],
        ),
        (
            "jAvAsCrIpT JAVA developer python",
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


@pytest.mark.parametrize(
    "text",
    [
        "Microsoft Excel is required.",
        "Excel spreadsheets and workbooks.",
        "Advanced Excel skills.",
        "Excel skills are preferred.",
        "Excel/Sheets reporting.",
        "Proficiency in Excel formulas.",
        "Experience with Excel VBA.",
    ],
)
def test_excel_requires_and_accepts_spreadsheet_context(text):
    assert extract_skills(description=text) == ["Excel"]


@pytest.mark.parametrize(
    "text",
    [
        "I will excel in a collaborative environment.",
        "We excel at solving client problems.",
        "The candidate wants to excel.",
        "Candidates excel in fast-moving teams.",
    ],
)
def test_excel_verbs_are_not_skills(text):
    assert "Excel" not in extract_skills(description=text)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Java developer using Spring Boot", ["Java"]),
        ("Java coffee from the island", []),
        ("React.js developer", ["React"]),
        ("React to customer feedback", []),
        ("Bash shell scripting", ["Bash"]),
        ("bash the button to continue", []),
        ("Git version control and branch management", ["Git"]),
        ("git through the report before sending it", []),
        ("Apache Spark cluster", ["Apache Spark"]),
        ("a spark of creativity", []),
        ("Python pandas DataFrame", ["Python", "pandas"]),
        ("pandas live in the forest", []),
        ("Microsoft Azure cloud services", ["Azure"]),
        ("the azure sky above the water", []),
        ("JS developer", ["JavaScript"]),
        ("JS report due Friday", []),
    ],
)
def test_ambiguous_skill_names_need_technical_context(text, expected):
    assert extract_skills(description=text) == expected


def test_java_does_not_match_inside_javascript_or_without_context():
    assert extract_skills(description="JavaScript engineer") == ["JavaScript"]
    assert extract_skills(description="Java and JavaScript") == ["JavaScript"]
    assert extract_skills(description="Java developer and JavaScript") == [
        "Java",
        "JavaScript",
    ]


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


def test_terms_not_in_the_dictionary_remain_unmatched():
    assert extract_skills(description="R, C, Go, Rust, Swift, and Dash") == []


def test_extractor_version_is_explicit():
    assert EXTRACTOR_VERSION == "1.1.0"
