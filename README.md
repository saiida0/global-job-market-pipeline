# Global Job Market Intelligence Pipeline

Batch data pipeline for collecting remote job postings from Remotive, cleaning
them into a consistent schema, and loading the result into PostgreSQL for
analysis.

## Project Structure

```text
.
|-- data/                 # Local generated data, ignored by Git
|-- logs/                 # Local pipeline logs, ignored by Git
|-- src/                  # Python source code
|   |-- fetch_jobs.py     # Remotive API ingestion
|   |-- clean_jobs.py     # Cleaning and salary parsing
|   |-- load_jobs.py      # PostgreSQL loading
|   `-- main.py           # Pipeline orchestration
|-- schema.sql            # PostgreSQL table and indexes
|-- requirements.txt      # Python dependencies
`-- .env.example          # Environment variable template
```

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your PostgreSQL credentials:

```powershell
Copy-Item .env.example .env
```

Create the database table with `schema.sql` before the first load.

## Run

From the project root:

```powershell
python -m src.main
```

The pipeline saves each raw API response to `data/raw/remotive_jobs_YYYYMMDD_HHMMSS.json` using a UTC timestamp and writes the latest cleaned dataset to `data/jobs_latest.json`. These generated data files are intentionally ignored by Git.

## Data Policy

This project retains timestamped raw snapshots for each run.
Each run overwrites only the latest cleaned dataset. Commit source
code, docs, and configuration templates only.
