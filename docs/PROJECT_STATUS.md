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
and counts per tag for the current UTC date. daily_stats is upserted by day;
daily_skill_counts is refreshed for that day using its (day, skill) key, so a
same-day rerun replaces the snapshot instead of adding duplicate rows.

Apply schema.sql to create these PostgreSQL tables:

- jobs
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
