# Project Status

## Current Scope

The project collects Remotive job listings, normalizes them, and loads them
into PostgreSQL. The local Streamlit dashboard summarizes the stored data.
Pipeline run history and daily job and skill snapshots are stored in PostgreSQL.

## Dashboard

- Run from the project root with streamlit run dashboard/app.py.
- Reads Remotive rows from PostgreSQL using the shared settings in src/config.py.
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
and counts per Remotive tag for the current UTC date. daily_stats is upserted
by day; daily_skill_counts is refreshed for that day using its (day, skill)
key, so a same-day rerun replaces the snapshot instead of adding duplicate
rows. These counts continue to represent provider tags, not extracted skills.

## Independent Skill Extraction

src/skill_extractor.py checks the job title and description against a
deterministic, case-insensitive dictionary and returns canonical skill names.
Cleaning stores the results in extracted_skills while keeping Remotive tags
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

## Data Attribution

Job data from the Remotive API (https://remotive.com). Each listing links to
its original Remotive posting. Private, non-commercial academic project.

## Local Commands

Install dependencies with pip install -r requirements.txt, then start the
dashboard with streamlit run dashboard/app.py. Run the project tests with:

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
~~~
