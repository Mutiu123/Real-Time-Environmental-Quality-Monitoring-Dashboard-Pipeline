-- Drop existing table if it exists
DROP TABLE IF EXISTS raw.extraction_log CASCADE;

-- Create sequence for extraction_id
CREATE SEQUENCE IF NOT EXISTS raw.extraction_log_seq START 1;

-- Create extraction log table
CREATE TABLE raw.extraction_log(
    extraction_id INTEGER PRIMARY KEY DEFAULT nextval('raw.extraction_log_seq'),
    extraction_start_datetime TIMESTAMP,
    extraction_end_datetime TIMESTAMP,
    start_date VARCHAR,  -- Format: YYYY-MM
    end_date VARCHAR,    -- Format: YYYY-MM
    status VARCHAR,      -- 'running', 'completed', 'failed'
    records_extracted INTEGER,
    error_message VARCHAR
);

-- Create a view to get the last successful extraction
CREATE OR REPLACE VIEW raw.last_successful_extraction AS
SELECT
    extraction_id,
    extraction_start_datetime,
    extraction_end_datetime,
    start_date,
    end_date,
    records_extracted
FROM raw.extraction_log
WHERE status = 'completed'
ORDER BY extraction_end_datetime DESC
LIMIT 1;
