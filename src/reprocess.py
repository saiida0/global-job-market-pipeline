import logging
import sys
from pathlib import Path

from .clean_jobs import main as clean_jobs
from .load_jobs import main as load_jobs


logger = logging.getLogger(__name__)
RAW_OUTPUT_DIR = Path("data/raw")


def find_newest_snapshot(raw_output_dir: Path | None = None) -> Path:
    raw_dir = raw_output_dir if raw_output_dir is not None else RAW_OUTPUT_DIR
    snapshots = [
        path
        for path in raw_dir.glob("remotive_jobs_*.json")
        if path.is_file()
    ]
    if not snapshots:
        raise FileNotFoundError(
            f"No Remotive snapshots found in {raw_dir}. "
            "Run python -m src.main to fetch jobs first."
        )
    return max(snapshots, key=lambda path: path.stat().st_mtime)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        snapshot = find_newest_snapshot()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    logger.info("Reprocessing existing raw snapshot %s", snapshot)
    cleaning_result = clean_jobs(str(snapshot))
    loading_result = load_jobs(cleaning_result["file_path"])
    logger.info(
        "Reprocessing complete: %s jobs cleaned, %s rows upserted (%s skipped)",
        cleaning_result["total"],
        loading_result["upserted"],
        loading_result.get("skipped", 0),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())