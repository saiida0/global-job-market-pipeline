BEGIN;

CREATE TABLE IF NOT EXISTS jobs (
    source                      VARCHAR(100) NOT NULL,
    source_id                   TEXT NOT NULL,
    title                       TEXT NOT NULL,
    company_name                TEXT NOT NULL,
    candidate_required_location TEXT,
    salary_min                  INTEGER,
    salary_max                  INTEGER,
    salary_type                 VARCHAR(20),
    currency                    VARCHAR(10),
    publication_date            TIMESTAMPTZ,
    fetched_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    category                    VARCHAR(100),
    job_type                    VARCHAR(50),
    tags                        TEXT[],
    url                         TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS extracted_job_skills (
    source            VARCHAR(100) NOT NULL,
    source_id         TEXT NOT NULL,
    skill_name        TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    PRIMARY KEY (source, source_id, skill_name),
    FOREIGN KEY (source, source_id)
        REFERENCES jobs(source, source_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id               BIGSERIAL PRIMARY KEY,
    started_at       TIMESTAMPTZ NOT NULL,
    finished_at      TIMESTAMPTZ NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    jobs_fetched     INTEGER NOT NULL DEFAULT 0,
    jobs_cleaned     INTEGER NOT NULL DEFAULT 0,
    jobs_skipped     INTEGER NOT NULL DEFAULT 0,
    jobs_upserted    INTEGER NOT NULL DEFAULT 0,
    reused_snapshot  BOOLEAN NOT NULL DEFAULT FALSE,
    error_message    TEXT
);

CREATE TABLE IF NOT EXISTS daily_stats (
    day               DATE PRIMARY KEY,
    total_jobs        INTEGER NOT NULL DEFAULT 0,
    jobs_with_salary  INTEGER NOT NULL DEFAULT 0,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_skill_counts (
    day    DATE NOT NULL,
    skill  TEXT NOT NULL,
    jobs   INTEGER NOT NULL,
    PRIMARY KEY (day, skill)
);

CREATE INDEX IF NOT EXISTS idx_jobs_tags
    ON jobs USING GIN(tags);

CREATE INDEX IF NOT EXISTS idx_jobs_category
    ON jobs(category);

CREATE INDEX IF NOT EXISTS idx_jobs_publication_date
    ON jobs(publication_date DESC);

CREATE INDEX IF NOT EXISTS idx_jobs_fetched_at
    ON jobs(fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_jobs_salary_min
    ON jobs(salary_min);

CREATE INDEX IF NOT EXISTS idx_jobs_source
    ON jobs(source);

CREATE INDEX IF NOT EXISTS idx_extracted_job_skills_skill_name
    ON extracted_job_skills(skill_name);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_jobs_updated_at ON jobs;

CREATE TRIGGER trg_jobs_updated_at
BEFORE UPDATE ON jobs
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
