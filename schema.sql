BEGIN;

CREATE TABLE IF NOT EXISTS jobs (
    id                          BIGINT PRIMARY KEY,
    title                       TEXT NOT NULL,
    company_name                TEXT NOT NULL,
    candidate_required_location TEXT,
    salary_min                  INTEGER,
    salary_max                  INTEGER,
    salary_type                 VARCHAR(20),
    currency                    VARCHAR(10),
    publication_date            TIMESTAMPTZ,
    fetched_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source                      VARCHAR(100) NOT NULL,
    category                    VARCHAR(100),
    job_type                    VARCHAR(50),
    tags                        TEXT[],
    url                         TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
