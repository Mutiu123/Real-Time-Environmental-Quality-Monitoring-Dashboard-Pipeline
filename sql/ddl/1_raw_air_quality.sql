CREATE TABLE IF NOT EXISTS raw.air_quality(
    location_id BIGINT,
    sensors_id VARCHAR,  -- Changed from BIGINT to VARCHAR
    "location" VARCHAR,
    "datetime" TIMESTAMP,
    lat DOUBLE,
    lon DOUBLE,
    "parameter" VARCHAR,
    units VARCHAR,
    "value" DOUBLE,
    "month" VARCHAR,
    "year" BIGINT,
    ingestion_datetime TIMESTAMP
);