"""Audit Excel skill matches in the newest local Jobicy snapshot.

The text report contains only each affected title and a short context window.
No full descriptions are printed or written.
"""

from __future__ import annotations

import json
import re
import sys
from html import unescape
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.skill_extractor import extract_skills


RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_FILE = PROJECT_ROOT / "analysis" / "excel_context_sample.txt"
HTML_TAG_PATTERN = re.compile(r"<[^>]*>")
LEGACY_EXCEL_PATTERN = re.compile(r"(?<!\w)excel(?!\w)", re.IGNORECASE)


def _plain_text(value: object) -> str:
    """Decode entities, strip HTML, and collapse whitespace without persisting it."""
    if not isinstance(value, str):
        return ""
    return " ".join(HTML_TAG_PATTERN.sub(" ", unescape(value)).split())


def _context_window(text: str, match: re.Match[str], radius: int = 60) -> str:
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return f"{text[start:match.start()]}[{match.group(0)}]{text[match.end():end]}"


def _newest_snapshot() -> Path:
    snapshots = [path for path in RAW_DIR.glob("jobicy_jobs_*.json") if path.is_file()]
    if not snapshots:
        raise FileNotFoundError("No Jobicy raw snapshots are available in data/raw.")
    return max(snapshots, key=lambda path: path.stat().st_mtime)


def audit_snapshot(snapshot_path: Path | None = None) -> tuple[int, int]:
    """Write baseline match contexts and return before/after matched-job counts."""
    snapshot_path = snapshot_path or _newest_snapshot()
    with snapshot_path.open("r", encoding="utf-8") as file:
        raw_data = json.load(file)

    jobs = raw_data.get("jobs") if isinstance(raw_data, dict) else None
    if not isinstance(jobs, list):
        raise ValueError("The selected Jobicy snapshot must contain a jobs list.")

    before_count = 0
    after_count = 0
    output_lines: list[str] = []

    for job in jobs:
        if not isinstance(job, dict):
            continue
        title = _plain_text(job.get("jobTitle"))
        description = _plain_text(job.get("jobDescription"))
        legacy_match = LEGACY_EXCEL_PATTERN.search(description)
        context_text = description
        if legacy_match is None:
            legacy_match = LEGACY_EXCEL_PATTERN.search(title)
            context_text = title
        if legacy_match is not None:
            before_count += 1
            output_lines.extend(
                (
                    f"Title: {title}",
                    f"Context: {_context_window(context_text, legacy_match)}",
                    "",
                )
            )

        if "Excel" in extract_skills(
            description=job.get("jobDescription"),
            title=job.get("jobTitle"),
        ):
            after_count += 1

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text("\n".join(output_lines), encoding="utf-8")
    return before_count, after_count


def main() -> None:
    before_count, after_count = audit_snapshot()
    print(f"Excel matched jobs before: {before_count}")
    print(f"Excel matched jobs after: {after_count}")


if __name__ == "__main__":
    main()
