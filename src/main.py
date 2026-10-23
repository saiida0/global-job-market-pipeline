import logging
import time

from .clean_jobs import main as clean_jobs
from .config import config
from .fetch_jobs import fetch_remote_jobs
from .load_jobs import main as load_jobs
from .logging_config import setup_logging


def main() -> None:
    setup_logging(log_level="INFO")
    logger = logging.getLogger(__name__)
    logger.info("Pipeline started")

    start = time.perf_counter()

    try:
        logger.info(
            "Configuration loaded for database %s at %s:%s as user %s",
            config.db_name,
            config.db_host,
            config.db_port,
            config.db_user,
        )

        logger.info("Step 1/3: fetching jobs")
        ingestion_result = fetch_remote_jobs()
        logger.info(
            "Fetching complete: %s jobs fetched at %s",
            ingestion_result["job_count"],
            ingestion_result["fetched_at"],
        )

        logger.info("Step 2/3: cleaning jobs")
        processing_result = clean_jobs(ingestion_result["file_path"])
        logger.info(
            "Cleaning complete: %s jobs cleaned (%s with salary, %s without, %s skipped)",
            processing_result["total"],
            processing_result["with_salary"],
            processing_result["without_salary"],
            processing_result.get("skipped", 0),
        )

        logger.info("Step 3/3: loading jobs")
        loading_result = load_jobs(processing_result["file_path"])
        logger.info(
            "Loading complete: %s rows upserted (%s skipped)",
            loading_result["upserted"],
            loading_result.get("skipped", 0),
        )

        elapsed = time.perf_counter() - start
        logger.info("Pipeline completed successfully in %.2fs", elapsed)
    except Exception:
        logger.error("Pipeline failed", exc_info=True)
        raise


if __name__ == "__main__":
    main()
