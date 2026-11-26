# Project Status

## Current Scope

The project collects Remotive and Jobicy job listings, normalizes them, and
loads them into PostgreSQL. Pipeline run history and daily job and skill
snapshots are stored in PostgreSQL.

Remotive is fetched, cleaned, and loaded as before. Jobicy has a separate
fetch-and-clean path using its public cursor API. It requests up to twenty pages
of 100 jobs, pauses 1.5 seconds between pages, retries HTTP 429 and 503 using
Retry-After, and reuses its own raw snapshot for up to six hours. Jobicy's API
provides a rolling seven-day window with an approximately three-hour update
delay. Its cleaner decodes HTML entities in listing text. Cleaned records use
an empty tag list and save extracted skills
without copying description text into cleaned JSON or PostgreSQL.

The main pipeline attempts both sources even if one source fails. It records
combined run totals and exits unsuccessfully if either source fails.

## Dashboard

- Run from the project root with `streamlit run dashboard/app.py`.
- Reads jobs from all sources in a read-only PostgreSQL transaction and caches
  results for 300 seconds. The app adds the project root to `sys.path` so this
  command works when launched from the project root.
- The Role focus radio filters all charts and listings to software development,
  data and analytics, and AI and machine learning roles when selected.
- Daily posting counts use a continuous UTC date axis and one compact panel per
  source with independent y-scales. Counts reflect each source's fetch window,
  not total market volume.
- Category chart labels put sample counts first (for example, `n=45 · Sales`)
  and use expanded y-axis label limits so full category names remain visible.
  Salary category bars also show the salary job count in each tooltip, extend the
  x-axis past the longest bar, and use yearly USD only. A job's salary value is
  the midpoint of min and max, or its available bound when only one is listed.
  Categories with fewer than ten salary jobs are hidden.
- Filters by source, shared category, job type, and location. The sidebar search
  matches title or company without regard to case.
- Maps provider category labels to shared dashboard names in
  `src/categories.py`; stored database values are unchanged.
- Shows job and salary metrics, extracted skills from `extracted_job_skills`,
  horizontal category and yearly USD salary charts, publication dates, and
  newest-first links to original postings. Listings show their source.
- The skills chart counts distinct jobs with each extracted skill, keeps longer
  labels such as Google Cloud Platform visible, and reports coverage against the
  selected jobs. Salary captions report how many jobs contributed estimates.
- The Pipeline status section shows the latest run in a compact UTC format and
  keeps full timestamps in the last-five-runs table. It has an empty state for a
  database without run history.
- Query and shaping helpers live in `dashboard/queries.py`, with fake-data,
  pandas-only tests in `tests/test_dashboard_queries.py`.

## Run History and Daily Statistics

src/run_log.py records one pipeline_runs row for each completed or failed
pipeline attempt. Failure records contain a short generic error message so
exception text and credentials are not persisted.

After a successful load, the pipeline snapshots total jobs, jobs with salary,
and counts per source tag for the current UTC date. daily_stats is upserted
by day; daily_skill_counts is refreshed for that day using its (day, skill)
key, so a same-day rerun replaces the snapshot instead of adding duplicate
rows. These counts continue to represent provider tags, not extracted skills.

## Independent Skill Extraction

src/skill_extractor.py checks the job title and description against a
deterministic, case-insensitive dictionary and returns canonical skill names.
Cleaning stores the results in extracted_skills while keeping provider tags
separate. Full descriptions are omitted from cleaned JSON and PostgreSQL;
timestamped raw snapshots remain unchanged and available for reprocessing.

Extracted matches are stored in extracted_job_skills, one row per job and
skill, with the extractor version. Reprocessing replaces a job's previous
extracted skill rows instead of accumulating duplicates.

Extractor version 1.1.0 adds context checks for names with common non-skill
meanings. Excel matches only spreadsheet-related context; Java, React, Bash,
Git, pandas, Apache Spark, Azure, and the short JavaScript alias `JS` require
nearby technical wording. This filters obvious verb and everyday-language uses,
but can miss valid skills when a listing omits those cues. Other configured
skills continue to use case-insensitive word-boundary matching.

`analysis/skill_context_check.py` audits the newest local Jobicy snapshot and
writes only titles and up to 60 characters around each baseline Excel mention
to `analysis/excel_context_sample.txt`. In that snapshot, the previous matcher
matched 28 jobs and the context-aware matcher matched 10.

Apply schema.sql to create these PostgreSQL tables:

- jobs
- extracted_job_skills
- pipeline_runs
- daily_stats
- daily_skill_counts

## Composite Job Keys

Jobs are keyed by `(source, source_id)`. The loader defaults missing sources to
`remotive` and converts the existing Remotive numeric `id` to text for
`source_id`, preserving its current identity. Extracted skills use the same
composite job key and cascade deletes through a matching foreign key. Daily
tag snapshots count distinct `(source, source_id)` pairs. The dashboard reads
both sources and maps category labels at display time without changing stored
values.

For a fresh database, apply schema.sql. For an existing database, run
`migrations/001_composite_job_key.sql` once in pgAdmin before using the updated
loader or dashboard.

## Remaining TODOs

- Use Jobicy `/api/jobs/status` to mark closed jobs.
- Choose a scheduled pipeline run minute other than minute 00.
- Add provider-specific fetch and cleaning steps before ingesting sources other
  than Remotive and Jobicy, with integration coverage using local fake data.

## Data Attribution

Job data from [Remotive](https://remotive.com) and [Jobicy](https://jobicy.com).
Each listing links to its original posting. Private, non-commercial academic
project.

## Scheduling

`scripts/run_pipeline.bat` is the Windows Task Scheduler entry point. It changes
into the project root, activates `.venv`, runs `python -m src.main`, appends
standard output and errors to `logs/scheduled_run.log` with start and end
timestamps, and returns the pipeline exit code.

## Local Commands

Install dependencies with pip install -r requirements.txt, then start the
dashboard with streamlit run dashboard/app.py. Run the project tests with:

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
~~~
