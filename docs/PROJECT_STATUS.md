# Project Status

## Current Scope

The project collects Remotive and Jobicy job listings, normalizes them, and
loads them into PostgreSQL. Pipeline run history and daily job and skill
snapshots are stored in PostgreSQL.

Remotive is fetched, cleaned, and loaded as before. Jobicy has a separate
fetch-and-clean path using its public cursor API. It requests up to five pages
of 100 jobs, pauses 1.5 seconds between pages, retries HTTP 429 and 503 using
Retry-After, and reuses its own raw snapshot for up to six hours. Jobicy's API
provides a rolling seven-day window with an approximately three-hour update
delay. Its cleaned records use an empty tag list and save extracted skills
without copying description text into cleaned JSON or PostgreSQL.

The main pipeline attempts both sources even if one source fails. It records
combined run totals and exits unsuccessfully if either source fails.

## Dashboard

- Run from the project root with streamlit run dashboard/app.py.
- Currently reads Remotive rows from PostgreSQL using the shared settings in
  src/config.py; Jobicy dashboard queries remain a TODO.
- Uses a read-only PostgreSQL transaction and caches results for 300 seconds.
- Filters listings by category, job type, and location.
- Shows job and salary metrics, tagged skills, category totals, yearly USD
  salary summaries, publication dates, and links to original postings.
- The salary chart uses only yearly USD listings; hourly and non-USD salaries
  are excluded.
- Query and shaping helpers live in dashboard/queries.py, with pandas-only
  tests in tests/test_dashboard_queries.py.

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

The dictionary only matches configured terms and aliases. It can miss skills
outside the list and can produce false positives for ambiguous terms; it does
not infer context or related skills.

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
tag snapshots count distinct `(source, source_id)` pairs. The dashboard still
shows Remotive listings and keeps its existing layout.

For a fresh database, apply schema.sql. For an existing database, run
`migrations/001_composite_job_key.sql` once in pgAdmin before using the updated
loader or dashboard.

## Remaining TODOs

- Add dashboard queries for Jobicy listings while preserving the current
  dashboard layout.
- Use Jobicy `/api/jobs/status` to mark closed jobs.
- Choose a scheduled pipeline run minute other than minute 00.
- Add provider-specific fetch and cleaning steps before ingesting sources other
  than Remotive and Jobicy, with integration coverage using local fake data.

## Data Attribution

Job data from [Remotive](https://remotive.com) and [Jobicy](https://jobicy.com).
Each listing links to its original posting. Private, non-commercial academic
project.

## Local Commands

Install dependencies with pip install -r requirements.txt, then start the
dashboard with streamlit run dashboard/app.py. Run the project tests with:

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
~~~
