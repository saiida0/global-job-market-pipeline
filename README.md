# Global Job Market Intelligence Pipeline

Batch data pipeline for collecting remote job postings from Remotive, cleaning
them into a consistent schema, and loading the result into PostgreSQL for
analysis. The local dashboard reads the stored listings and summarizes demand,
skills, salaries, and publication activity.

## Project Structure

~~~text
.
|-- analysis/               # Exploratory analysis notebook
|-- dashboard/
|   |-- app.py              # Local Streamlit dashboard
|   +-- queries.py          # Read-only query and tested shaping functions
|-- docs/
|   +-- PROJECT_STATUS.md   # Current project status
|-- tests/                  # Pipeline and dashboard tests
|-- src/
|   |-- fetch_jobs.py       # Remotive API ingestion
|   |-- clean_jobs.py       # Cleaning and salary parsing
|   |-- load_jobs.py        # PostgreSQL loading
|   |-- main.py             # Pipeline orchestration
|   +-- reprocess.py        # Reprocess a saved snapshot without fetching
|-- schema.sql              # PostgreSQL table and indexes
|-- requirements.txt        # Python dependencies
+-- .env.example             # Environment variable template
~~~

## Setup

Create and activate a virtual environment:

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
~~~

Install dependencies:

~~~powershell
pip install -r requirements.txt
~~~

Copy .env.example to .env and fill in your PostgreSQL credentials:

~~~powershell
Copy-Item .env.example .env
~~~

Create the database table with schema.sql before the first load.

## Run the Pipeline

From the project root, run the full pipeline:

~~~powershell
python -m src.main
~~~

The pipeline saves each raw API response to
data/raw/remotive_jobs_YYYYMMDD_HHMMSS.json using a UTC timestamp and writes
the latest cleaned dataset to data/jobs_latest.json. If the newest raw
snapshot is less than 6 hours old, the pipeline reuses it instead of making
another API request. Remotive advises a maximum of 4 fetches per day and blocks
requests over 2 per minute. Set FORCE_FETCH=true in .env to force a live
fetch despite the reuse guard; the default is FORCE_FETCH=false.

To clean and load the newest existing raw snapshot without fetching from
Remotive, run:

~~~powershell
python -m src.reprocess
~~~

## Run the Dashboard

After installing the requirements and configuring PostgreSQL, start the
read-only local dashboard from the project root:

~~~powershell
streamlit run dashboard/app.py
~~~

The dashboard uses the same PostgreSQL settings as the pipeline, caches query
results for 5 minutes, and provides category, job type, and location filters.
Its salary chart includes yearly USD listings only; hourly and non-USD salaries
are excluded.

Job data from the Remotive API (https://remotive.com). Each listing links to
its original Remotive posting. Private, non-commercial academic project.

## Data Policy

This project retains timestamped raw snapshots for each run. Each run
overwrites only the latest cleaned dataset. Commit source code, docs, and
configuration templates only.
