-- One-time migration from the Remotive numeric jobs.id key to a source key.
BEGIN;

-- Step 1: Add source_id while the old numeric id is still available.
ALTER TABLE jobs
    ADD COLUMN source_id TEXT;

-- Step 2: Keep existing sources, fill blank sources, and stringify the old IDs.
UPDATE jobs
SET source = 'remotive'
WHERE source IS NULL OR BTRIM(source) = '';

UPDATE jobs
SET source_id = id::text
WHERE source_id IS NULL OR BTRIM(source_id) = '';

-- Step 3: Add the new key fields to extracted skills and backfill from old job IDs.
ALTER TABLE extracted_job_skills
    ADD COLUMN source VARCHAR(100);

ALTER TABLE extracted_job_skills
    ADD COLUMN source_id TEXT;

UPDATE extracted_job_skills AS skills
SET source = jobs.source,
    source_id = jobs.source_id
FROM jobs
WHERE skills.job_id = jobs.id;

-- Step 4: Remove the old skills foreign key and primary key before changing jobs.
ALTER TABLE extracted_job_skills
    DROP CONSTRAINT IF EXISTS extracted_job_skills_job_id_fkey;

ALTER TABLE extracted_job_skills
    DROP CONSTRAINT IF EXISTS extracted_job_skills_pkey;

-- Step 5: Replace jobs.id with the composite primary key.
ALTER TABLE jobs
    DROP CONSTRAINT IF EXISTS jobs_pkey;

ALTER TABLE jobs
    DROP COLUMN id;

ALTER TABLE jobs
    ALTER COLUMN source SET NOT NULL,
    ALTER COLUMN source_id SET NOT NULL;

ALTER TABLE jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (source, source_id);

-- Step 6: Require both skill key columns and remove the obsolete numeric job_id.
ALTER TABLE extracted_job_skills
    ALTER COLUMN source SET NOT NULL,
    ALTER COLUMN source_id SET NOT NULL;

ALTER TABLE extracted_job_skills
    DROP COLUMN job_id;

-- Step 7: Add the composite skills key and cascading foreign key to jobs.
ALTER TABLE extracted_job_skills
    ADD CONSTRAINT extracted_job_skills_pkey
    PRIMARY KEY (source, source_id, skill_name);

ALTER TABLE extracted_job_skills
    ADD CONSTRAINT extracted_job_skills_source_source_id_fkey
    FOREIGN KEY (source, source_id)
    REFERENCES jobs(source, source_id)
    ON DELETE CASCADE;

-- Step 8: Commit all key and foreign-key changes together.
COMMIT;
