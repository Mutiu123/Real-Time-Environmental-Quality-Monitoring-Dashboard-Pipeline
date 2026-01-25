# Incremental Loading Guide

This guide explains how to use the incremental loading feature to automatically update your air quality data.

## Overview

Incremental loading allows the pipeline to:
- Track the last successful data extraction
- Automatically determine which new data to fetch
- Only extract data that hasn't been loaded yet
- Maintain an extraction log for monitoring

## Setup

### 1. Initialize the Database

Before using incremental loading, set up the database with required tables:

```bash
cd pipeline
python setup_database.py --database_path ../air_quality.db
```

This creates:
- `raw` and `presentation` schemas
- `raw.air_quality` table
- `raw.extraction_log` metadata table
- `raw.last_successful_extraction` view

## Usage

### First-Time Full Load

For the initial data load, specify explicit date ranges:

```bash
python extraction.py \
  --locations_file_path ../locations.json \
  --start_date 2024-01 \
  --end_date 2024-03 \
  --database_path ../air_quality.db \
  --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql \
  --source_base_path s3://openaq-data-archive/records/csv.gz
```

### Incremental Updates

After the initial load, use incremental mode to fetch only new data:

```bash
python extraction.py \
  --locations_file_path ../locations.json \
  --database_path ../air_quality.db \
  --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql \
  --source_base_path s3://openaq-data-archive/records/csv.gz \
  --incremental
```

**How it works:**
- Checks `raw.extraction_log` for the last successful extraction end date
- Automatically sets start_date to the month after the last extraction
- Sets end_date to the current month
- Skips extraction if already up to date

### Refresh Specific Date Range

To refresh data for a specific period (replaces existing data):

```bash
python extraction.py \
  --locations_file_path ../locations.json \
  --start_date 2024-01 \
  --end_date 2024-03 \
  --database_path ../air_quality.db \
  --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql \
  --source_base_path s3://openaq-data-archive/records/csv.gz
```

*Note: Without `--incremental`, existing data for the date range is deleted and re-extracted.*

## Automation

### Windows Task Scheduler

Create a scheduled task to run incremental extraction daily:

```batch
@echo off
cd C:\path\to\Real-Time-Environmental-Air-Quality-Monitoring-Dashboard-Pipeline\pipeline
call .venv\Scripts\activate.bat
python extraction.py --locations_file_path ../locations.json --database_path ../air_quality.db --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql --source_base_path s3://openaq-data-archive/records/csv.gz --incremental
python transformation.py --database_path ../air_quality.db --query_directory ../sql/dml/presentation
```

Save as `daily_update.bat` and schedule it in Task Scheduler.

### Linux/Mac Cron Job

Add to crontab (`crontab -e`):

```bash
# Run incremental extraction daily at 2 AM
0 2 * * * cd /path/to/project/pipeline && source .venv/bin/activate && python extraction.py --locations_file_path ../locations.json --database_path ../air_quality.db --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql --source_base_path s3://openaq-data-archive/records/csv.gz --incremental && python transformation.py --database_path ../air_quality.db --query_directory ../sql/dml/presentation
```

## Monitoring

### Check Extraction History

Query the extraction log to view all extraction jobs:

```sql
SELECT
    extraction_id,
    extraction_start_datetime,
    extraction_end_datetime,
    start_date,
    end_date,
    status,
    records_extracted,
    error_message
FROM raw.extraction_log
ORDER BY extraction_start_datetime DESC
LIMIT 10;
```

### View Last Successful Extraction

```sql
SELECT * FROM raw.last_successful_extraction;
```

### Check for Failed Extractions

```sql
SELECT *
FROM raw.extraction_log
WHERE status = 'failed'
ORDER BY extraction_start_datetime DESC;
```

## Best Practices

1. **Run incremental extractions regularly** (daily or weekly) to keep data up to date
2. **Monitor extraction logs** for failures or gaps in data
3. **Use full refresh** when you need to backfill or fix data quality issues
4. **Test incremental mode** before scheduling automated runs
5. **Always run transformation.py** after extraction to update views

## Troubleshooting

### "No new data to extract"

This means the last extraction already includes the current month. This is normal if running multiple times in the same month.

### "Schema with name presentation does not exist"

Run the setup script first:
```bash
python setup_database.py --database_path ../air_quality.db
```

### Missing data for certain locations/months

Check the extraction logs for warnings. Some sensors may not have data for all time periods.

## Complete Pipeline Example

```bash
# 1. Setup database (first time only)
python setup_database.py --database_path ../air_quality.db

# 2. Initial full load
python extraction.py \
  --locations_file_path ../locations.json \
  --start_date 2024-01 \
  --end_date 2024-03 \
  --database_path ../air_quality.db \
  --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql \
  --source_base_path s3://openaq-data-archive/records/csv.gz

# 3. Run transformations
python transformation.py \
  --database_path ../air_quality.db \
  --query_directory ../sql/dml/presentation

# 4. Start dashboard
cd ../dashboard
python app.py

# 5. Future updates (run periodically)
cd ../pipeline
python extraction.py \
  --locations_file_path ../locations.json \
  --database_path ../air_quality.db \
  --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql \
  --source_base_path s3://openaq-data-archive/records/csv.gz \
  --incremental

python transformation.py \
  --database_path ../air_quality.db \
  --query_directory ../sql/dml/presentation
```
