import logging
import time
from datetime import datetime, timezone

from .clean_jobs import main as clean_jobs
from .config import config
from .fetch_jobs import fetch_remote_jobs
from .jobicy import clean_jobs as clean_jobicy_jobs
from .jobicy import fetch_jobs as fetch_jobicy_jobs
from .load_jobs import main as load_jobs
from .logging_config import setup_logging
from .run_log import record_daily_stats, record_pipeline_run


def _record_run_safely(logger, run_fields: dict) -> None:
    try:
        record_pipeline_run(**run_fields)
    except Exception:
        # Instrumentation failure must not replace the pipeline result/error.
        logger.error("Could not write the pipeline run record.")


def main() -> None:
    logger = logging.getLogger(__name__)
    started_at = datetime.now(timezone.utc)
    run_fields = {
        "started_at": started_at,
        "finished_at": started_at,
        "status": "failed",
        "jobs_fetched": 0,
        "jobs_cleaned": 0,
        "jobs_skipped": 0,
        "jobs_upserted": 0,
        "reused_snapshot": False,
        "error": None,
    }
    start = time.perf_counter()
    source_errors = []
    loaded_any_source = False

    try:
        setup_logging(log_level="INFO")
        logger.info("Pipeline started")
        logger.info(
            "Configuration loaded for database %s at %s:%s as user %s",
            config.db_name,
            config.db_host,
            config.db_port,
            config.db_user,
        )

        source_pipelines = (
            ("Remotive", fetch_remote_jobs, clean_jobs),
            ("Jobicy", fetch_jobicy_jobs, clean_jobicy_jobs),
        )
        for source_name, fetch_source, clean_source in source_pipelines:
            try:
                if source_name == "Remotive":
                    logger.info("Step 1/3: fetching jobs")
                else:
                    logger.info("Step 1/3: fetching %s jobs", source_name)
                ingestion_result = fetch_source()
                run_fields["jobs_fetched"] += ingestion_result.get("job_count", 0)
                run_fields["reused_snapshot"] = (
                    run_fields["reused_snapshot"]
                    or ingestion_result.get("reused", False)
                )
                logger.info(
                    "Fetching complete: %s jobs fetched at %s",
                    ingestion_result["job_count"],
                    ingestion_result["fetched_at"],
                )

                if source_name == "Remotive":
                    logger.info("Step 2/3: cleaning jobs")
                else:
                    logger.info("Step 2/3: cleaning %s jobs", source_name)
                processing_result = clean_source(ingestion_result["file_path"])
                run_fields["jobs_cleaned"] += processing_result.get("total", 0)
                run_fields["jobs_skipped"] += processing_result.get("skipped", 0)
                logger.info(
                    "Cleaning complete: %s jobs cleaned (%s with salary, "
                    "%s without, %s skipped)",
                    processing_result["total"],
                    processing_result.get("with_salary", 0),
                    processing_result.get("without_salary", 0),
                    processing_result.get("skipped", 0),
                )

                if source_name == "Remotive":
                    logger.info("Step 3/3: loading jobs")
                else:
                    logger.info("Step 3/3: loading %s jobs", source_name)
                loading_result = load_jobs(processing_result["file_path"])
                run_fields["jobs_upserted"] += loading_result.get("upserted", 0)
                run_fields["jobs_skipped"] += loading_result.get("skipped", 0)
                logger.info(
                    "Loading complete: %s rows upserted (%s skipped)",
                    loading_result.get("upserted", 0),
                    loading_result.get("skipped", 0),
                )
                loaded_any_source = True
            except Exception as error:
                source_errors.append(error)
                logger.error(
                    "%s source failed (%s).", source_name, type(error).__name__
                )

        if loaded_any_source:
            record_daily_stats(datetime.now(timezone.utc).date())
        if source_errors:
            raise source_errors[0]

        elapsed = time.perf_counter() - start
        logger.info("Pipeline completed successfully in %.2fs", elapsed)
    except Exception as error:
        logger.error("Pipeline failed (%s)", type(error).__name__)
        run_fields.update(
            finished_at=datetime.now(timezone.utc),
            status="failed",
            error=error,
        )
        _record_run_safely(logger, run_fields)
        raise
    else:
        run_fields.update(
            finished_at=datetime.now(timezone.utc),
            status="success",
            error=None,
        )
        _record_run_safely(logger, run_fields)


if __name__ == "__main__":
    main()
