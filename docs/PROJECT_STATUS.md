# Project Status

## Current Scope

The project collects Remotive job listings, normalizes them, and loads them
into PostgreSQL. The new local Streamlit dashboard summarizes the stored data
without changing the pipeline code in src/.

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

## Data Attribution

Job data from the Remotive API (https://remotive.com). Each listing links to
its original Remotive posting. Private, non-commercial academic project.

## Local Commands

Install dependencies with pip install -r requirements.txt, then start the
dashboard with streamlit run dashboard/app.py. Run the project tests with:

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
~~~
