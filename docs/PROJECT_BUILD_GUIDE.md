# Building the Real-Time Air Quality Monitoring Pipeline
## Complete Step-by-Step Guide from Scratch

**Purpose**: This document provides a detailed, sequential guide to recreate this entire project from nothing. Follow these steps exactly to build the complete air quality monitoring pipeline and dashboard.

---

# Table of Contents

1. [Phase 1: Project Setup & Foundation](#phase-1-project-setup--foundation)
2. [Phase 2: Database Layer](#phase-2-database-layer)
3. [Phase 3: Data Extraction Pipeline](#phase-3-data-extraction-pipeline)
4. [Phase 4: Data Transformation](#phase-4-data-transformation)
5. [Phase 5: Dashboard Development](#phase-5-dashboard-development)
6. [Phase 6: Incremental Loading](#phase-6-incremental-loading)
7. [Phase 7: Dashboard Enhancements](#phase-7-dashboard-enhancements)
8. [Phase 8: Documentation](#phase-8-documentation)
9. [Phase 9: Testing & Verification](#phase-9-testing--verification)

---

# Phase 1: Project Setup & Foundation

## Step 1.1: Create Project Directory

```bash
# Create main project folder
mkdir Real-Time-Environmental-Air-Quality-Monitoring-Dashboard-Pipeline
cd Real-Time-Environmental-Air-Quality-Monitoring-Dashboard-Pipeline
```

## Step 1.2: Initialize Git Repository

```bash
git init
```

## Step 1.3: Create Folder Structure

```bash
# Create all directories
mkdir dashboard
mkdir pipeline
mkdir sql
mkdir sql/ddl
mkdir sql/dml
mkdir sql/dml/raw
mkdir sql/dml/presentation
mkdir notebooks
mkdir Image
mkdir docs
```

**Folder purposes:**
- `dashboard/` - Dash web application
- `pipeline/` - Python extraction and transformation scripts
- `sql/ddl/` - Data Definition Language (CREATE statements)
- `sql/dml/raw/` - Raw data manipulation queries
- `sql/dml/presentation/` - Presentation layer queries
- `notebooks/` - Jupyter notebooks for exploration
- `Image/` - Dashboard screenshots
- `docs/` - Project documentation

## Step 1.4: Create Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate
```

## Step 1.5: Create requirements.txt

Create file: `requirements.txt`

```text
# Core Dashboard Dependencies
dash>=2.14.0
plotly>=5.18.0
pandas>=2.1.0

# Database
duckdb>=0.9.0

# Data Pipeline Dependencies
jinja2>=3.1.2
python-dateutil>=2.9.0

# Jupyter Notebooks (Optional - for exploration)
jupyter>=1.1.1
ipykernel>=7.1.0
ipywidgets>=8.1.5
matplotlib>=3.9.2
seaborn>=0.13.2

# Additional utilities
requests>=2.32.3
```

## Step 1.6: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 1.7: Create .gitignore

Create file: `.gitignore`

```text
# Python virtual environment
.venv/
venv/
ENV/

# Python cache
__pycache__/
*.py[cod]
*$py.class
*.so

# Jupyter Notebook checkpoints
.ipynb_checkpoints/

# IDE settings
.idea/
.vscode/
*.swp
*.swo

# Database files
*.db
*.db-shm
*.db-wal
air_quality.db*

# Project-specific
data/
output/
logs/
docs/
*.csv
*.csv.gz
.DS_Store

# Environment files
.env
.env.local
```

## Step 1.8: Create locations.json (Sensor Configuration)

Create file: `locations.json`

```json
{
    "225393": {
        "name": "Johannesburg",
        "coordinates": {
            "latitude": -26.2041,
            "longitude": 28.0473
        }
    },
    "225394": {
        "name": "Pretoria",
        "coordinates": {
            "latitude": -25.7479,
            "longitude": 28.2293
        }
    },
    "225395": {
        "name": "Cape Town",
        "coordinates": {
            "latitude": -33.9249,
            "longitude": 18.4241
        }
    },
    "225396": {
        "name": "Durban",
        "coordinates": {
            "latitude": -29.8587,
            "longitude": 31.0218
        }
    },
    "225397": {
        "name": "Port Elizabeth",
        "coordinates": {
            "latitude": -33.9608,
            "longitude": 25.6022
        }
    }
}
```

**Note**: Replace these location IDs with actual OpenAQ location IDs for your region. You can find valid IDs by exploring OpenAQ data or using their API.

---

# Phase 2: Database Layer

## Step 2.1: Create Schema SQL

Create file: `sql/ddl/0_schemas.sql`

```sql
-- Create schemas for organizing data
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS presentation;
```

**Purpose**:
- `raw` schema holds unprocessed source data
- `presentation` schema holds cleaned, analytics-ready data

## Step 2.2: Create Raw Air Quality Table

Create file: `sql/ddl/1_raw_air_quality.sql`

```sql
-- Drop existing table if it exists
DROP TABLE IF EXISTS raw.air_quality;

-- Create raw air quality table
CREATE TABLE raw.air_quality(
    location_id BIGINT,
    sensors_id VARCHAR,
    location VARCHAR,
    datetime TIMESTAMP,
    lat DOUBLE,
    lon DOUBLE,
    parameter VARCHAR,
    units VARCHAR,
    value DOUBLE,
    month VARCHAR,
    year BIGINT,
    ingestion_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Column explanations**:
- `location_id`: OpenAQ sensor station ID
- `sensors_id`: Individual sensor ID
- `location`: Human-readable location name
- `datetime`: When measurement was taken
- `lat`, `lon`: Geographic coordinates
- `parameter`: What's measured (pm25, pm10, so2, etc.)
- `units`: Measurement units (µg/m³, ppm, etc.)
- `value`: The actual measurement
- `month`, `year`: Partition keys for efficient querying
- `ingestion_datetime`: When I loaded the data

## Step 2.3: Create Metadata Extraction Log Table

Create file: `sql/ddl/2_metadata_extraction_log.sql`

```sql
-- Drop existing table if it exists
DROP TABLE IF EXISTS raw.extraction_log CASCADE;

-- Create sequence for auto-incrementing ID
CREATE SEQUENCE IF NOT EXISTS raw.extraction_log_seq START 1;

-- Create extraction log table for tracking all extractions
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

-- Create view to easily get the last successful extraction
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
```

**Purpose**: This table tracks every extraction job, enabling:
- Incremental loading (know where to continue from)
- Debugging (see what failed and why)
- Auditing (complete history of data loads)
- Monitoring (check pipeline health)

## Step 2.4: Create Database Manager Utility

Create file: `pipeline/database_manager.py`

```python
"""
Database Manager - Utilities for DuckDB database operations
"""
import duckdb
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def connect_to_database(database_path: str) -> duckdb.DuckDBPyConnection:
    """
    Create a connection to DuckDB database.

    Args:
        database_path: Path to the database file

    Returns:
        DuckDB connection object
    """
    logging.info(f"Connecting to database at {database_path}")
    con = duckdb.connect(database_path)

    # Install and load httpfs extension for S3 access
    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")

    # Configure S3 for anonymous access (OpenAQ is public)
    con.execute("SET s3_region='us-east-1';")

    logging.info("Database connection established with S3 support")
    return con


def close_database_connection(con: duckdb.DuckDBPyConnection) -> None:
    """
    Close the database connection.

    Args:
        con: DuckDB connection object
    """
    if con:
        con.close()
        logging.info("Database connection closed")


def execute_query(con: duckdb.DuckDBPyConnection, query: str) -> None:
    """
    Execute a SQL query without returning results.

    Args:
        con: DuckDB connection object
        query: SQL query to execute
    """
    con.execute(query)


def read_query(file_path: str) -> str:
    """
    Read SQL query from a file.

    Args:
        file_path: Path to the SQL file

    Returns:
        SQL query as string
    """
    with open(file_path, 'r') as f:
        return f.read()
```

**Key features**:
- Automatic httpfs extension for S3 access
- Configured for anonymous S3 (OpenAQ is public)
- Centralized logging
- Clean connection management

## Step 2.5: Create Database Setup Script

Create file: `pipeline/setup_database.py`

```python
"""
Database Setup Script - Initialize all schemas and tables

Usage:
    python setup_database.py --database_path ../air_quality.db
"""
import argparse
import logging
import os

from database_manager import (
    connect_to_database,
    close_database_connection,
    execute_query,
    read_query
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def setup_database(database_path: str):
    """
    Initialize database with all required schemas and tables.

    Args:
        database_path: Path to the DuckDB database file
    """
    logging.info(f"Setting up database at {database_path}")

    con = connect_to_database(database_path)

    try:
        # Get the SQL directory path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sql_dir = os.path.join(script_dir, "..", "sql", "ddl")

        # List of DDL scripts to execute in order
        ddl_scripts = [
            "0_schemas.sql",
            "1_raw_air_quality.sql",
            "2_metadata_extraction_log.sql"
        ]

        for script_name in ddl_scripts:
            script_path = os.path.join(sql_dir, script_name)
            logging.info(f"Executing {script_name}...")

            query = read_query(script_path)
            execute_query(con, query)

            logging.info(f"Successfully executed {script_name}")

        logging.info("Database setup completed successfully!")

    except Exception as e:
        logging.error(f"Database setup failed: {e}")
        raise
    finally:
        close_database_connection(con)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup the database")
    parser.add_argument(
        "--database_path",
        type=str,
        required=True,
        help="Path to the DuckDB database file"
    )

    args = parser.parse_args()
    setup_database(args.database_path)
```

## Step 2.6: Run Database Setup

```bash
cd pipeline
python setup_database.py --database_path ../air_quality.db
```

**Expected output**:
```
2024-01-15 10:00:00 - INFO - Setting up database at ../air_quality.db
2024-01-15 10:00:00 - INFO - Connecting to database at ../air_quality.db
2024-01-15 10:00:01 - INFO - Database connection established with S3 support
2024-01-15 10:00:01 - INFO - Executing 0_schemas.sql...
2024-01-15 10:00:01 - INFO - Successfully executed 0_schemas.sql
2024-01-15 10:00:01 - INFO - Executing 1_raw_air_quality.sql...
2024-01-15 10:00:01 - INFO - Successfully executed 1_raw_air_quality.sql
2024-01-15 10:00:01 - INFO - Executing 2_metadata_extraction_log.sql...
2024-01-15 10:00:01 - INFO - Successfully executed 2_metadata_extraction_log.sql
2024-01-15 10:00:01 - INFO - Database setup completed successfully!
```

---

# Phase 3: Data Extraction Pipeline

## Step 3.1: Create Insert Query Template

Create file: `sql/dml/raw/0_raw_air_quality_insert.sql`

```sql
-- Insert air quality data from S3 source
INSERT INTO raw.air_quality (
    location_id,
    sensors_id,
    location,
    datetime,
    lat,
    lon,
    parameter,
    units,
    value,
    month,
    year
)
SELECT
    location_id,
    sensors_id,
    location,
    datetime,
    lat,
    lon,
    parameter,
    units,
    value,
    '{{ month }}' as month,
    {{ year }} as year
FROM '{{ source_path }}';
```

**Note**: `{{ month }}`, `{{ year }}`, and `{{ source_path }}` are Jinja2 template variables that get replaced at runtime.

## Step 3.2: Create Delete Query Template

Create file: `sql/dml/raw/0_raw_air_quality_delete.sql`

```sql
-- Delete air quality data for specific year and month
DELETE FROM raw.air_quality
WHERE year = {{ year }}
  AND month = '{{ month }}';
```

## Step 3.3: Create Main Extraction Script

Create file: `pipeline/extraction.py`

```python
"""
Data Extraction Pipeline - Extract air quality data from OpenAQ S3

Usage:
    # Full extraction with date range
    python extraction.py \
        --locations_file_path ../locations.json \
        --start_date 2024-01 \
        --end_date 2024-03 \
        --database_path ../air_quality.db \
        --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql \
        --source_base_path s3://openaq-data-archive/records/csv.gz

    # Incremental extraction (automatic date detection)
    python extraction.py \
        --locations_file_path ../locations.json \
        --database_path ../air_quality.db \
        --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql \
        --source_base_path s3://openaq-data-archive/records/csv.gz \
        --incremental
"""
import argparse
import json
import logging
from datetime import datetime
from typing import Optional, Tuple

from dateutil.relativedelta import relativedelta
from jinja2 import Template

from database_manager import (
    connect_to_database,
    close_database_connection,
    execute_query,
    read_query
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def get_last_extraction_date(con) -> Optional[str]:
    """
    Get the end date of the last successful extraction.

    Args:
        con: DuckDB connection object

    Returns:
        End date string in YYYY-MM format, or None if no extraction found
    """
    try:
        result = con.execute("""
            SELECT end_date
            FROM raw.last_successful_extraction
        """).fetchone()

        if result and result[0]:
            logging.info(f"Last successful extraction end date: {result[0]}")
            return result[0]

        logging.info("No previous extraction found")
        return None

    except Exception as e:
        logging.warning(f"Could not retrieve last extraction date: {e}")
        return None


def determine_date_range(con, incremental: bool) -> Tuple[str, str]:
    """
    Determine the date range for extraction based on mode.

    Args:
        con: DuckDB connection object
        incremental: If True, start from last extraction date

    Returns:
        Tuple of (start_date, end_date) in YYYY-MM format
    """
    if incremental:
        last_end_date = get_last_extraction_date(con)

        if last_end_date:
            # Start from month after last extraction
            last_end_dt = datetime.strptime(last_end_date, "%Y-%m")
            start_dt = last_end_dt + relativedelta(months=1)
            start_date = start_dt.strftime("%Y-%m")
        else:
            # No previous extraction, start from 3 months ago
            start_dt = datetime.now() - relativedelta(months=3)
            start_date = start_dt.strftime("%Y-%m")

        # End at current month
        end_date = datetime.now().strftime("%Y-%m")

        logging.info(f"Incremental mode: Extracting from {start_date} to {end_date}")
        return start_date, end_date

    return None, None  # Will use provided dates


def log_extraction_start(con, start_date: str, end_date: str) -> int:
    """
    Log the start of an extraction job.

    Args:
        con: DuckDB connection object
        start_date: Start date of extraction
        end_date: End date of extraction

    Returns:
        extraction_id for this job
    """
    result = con.execute("""
        INSERT INTO raw.extraction_log (
            extraction_start_datetime,
            start_date,
            end_date,
            status
        ) VALUES (?, ?, ?, 'running')
        RETURNING extraction_id
    """, [datetime.now(), start_date, end_date]).fetchone()

    extraction_id = result[0]
    logging.info(f"Started extraction job {extraction_id}")
    return extraction_id


def log_extraction_complete(con, extraction_id: int, records_count: int) -> None:
    """
    Log successful completion of extraction.

    Args:
        con: DuckDB connection object
        extraction_id: ID of the extraction job
        records_count: Number of records extracted
    """
    con.execute("""
        UPDATE raw.extraction_log
        SET
            extraction_end_datetime = ?,
            status = 'completed',
            records_extracted = ?
        WHERE extraction_id = ?
    """, [datetime.now(), records_count, extraction_id])

    logging.info(f"Extraction {extraction_id} completed: {records_count} records")


def log_extraction_failed(con, extraction_id: int, error_message: str) -> None:
    """
    Log failed extraction.

    Args:
        con: DuckDB connection object
        extraction_id: ID of the extraction job
        error_message: Error description
    """
    con.execute("""
        UPDATE raw.extraction_log
        SET
            extraction_end_datetime = ?,
            status = 'failed',
            error_message = ?
        WHERE extraction_id = ?
    """, [datetime.now(), str(error_message)[:500], extraction_id])

    logging.error(f"Extraction {extraction_id} failed: {error_message}")


def delete_existing_data(con, start_date: str, end_date: str) -> None:
    """
    Delete existing data for date range before re-extraction.

    Args:
        con: DuckDB connection object
        start_date: Start date (YYYY-MM format)
        end_date: End date (YYYY-MM format)
    """
    start_dt = datetime.strptime(start_date, "%Y-%m")
    end_dt = datetime.strptime(end_date, "%Y-%m")

    index_date = start_dt
    while index_date <= end_dt:
        year = index_date.year
        month = str(index_date.month).zfill(2)

        delete_query = f"""
        DELETE FROM raw.air_quality
        WHERE year = {year} AND month = '{month}';
        """

        logging.info(f"Deleting existing data for {year}-{month}")
        execute_query(con, delete_query)

        index_date += relativedelta(months=1)

    logging.info(f"Deleted existing data from {start_date} to {end_date}")


def extract_data(
    locations_file_path: str,
    start_date: str,
    end_date: str,
    database_path: str,
    extract_query_template_path: str,
    source_base_path: str,
    incremental: bool = False
) -> None:
    """
    Main extraction function.

    Args:
        locations_file_path: Path to JSON file with location IDs
        start_date: Start date (YYYY-MM format) - optional if incremental
        end_date: End date (YYYY-MM format) - optional if incremental
        database_path: Path to DuckDB database
        extract_query_template_path: Path to SQL insert template
        source_base_path: Base S3 path for OpenAQ data
        incremental: If True, auto-detect date range
    """
    # Connect to database
    con = connect_to_database(database_path)

    # Determine date range
    if incremental:
        start_date, end_date = determine_date_range(con, incremental)

        # Check if already up to date
        if start_date > end_date:
            logging.info("Data is already up to date. No extraction needed.")
            close_database_connection(con)
            return

    # Log extraction start
    extraction_id = log_extraction_start(con, start_date, end_date)

    try:
        # Load locations
        with open(locations_file_path, 'r') as f:
            locations = json.load(f)

        logging.info(f"Loaded {len(locations)} locations to extract")

        # Read query template
        query_template = read_query(extract_query_template_path)
        template = Template(query_template)

        # Delete existing data for date range (if not incremental)
        if not incremental:
            delete_existing_data(con, start_date, end_date)

        # Parse dates
        start_dt = datetime.strptime(start_date, "%Y-%m")
        end_dt = datetime.strptime(end_date, "%Y-%m")

        total_records = 0

        # Extract data for each location and month
        for location_id, location_info in locations.items():
            location_name = location_info.get('name', location_id)
            logging.info(f"Processing location: {location_name} (ID: {location_id})")

            index_date = start_dt
            while index_date <= end_dt:
                year = index_date.year
                month = str(index_date.month).zfill(2)

                # Build S3 path
                source_path = f"{source_base_path}/locationid={location_id}/year={year}/month={month}/*.csv.gz"

                logging.info(f"  Extracting {year}-{month} from {source_path}")

                try:
                    # Render and execute query
                    query = template.render(
                        source_path=source_path,
                        month=month,
                        year=year
                    )
                    execute_query(con, query)

                    # Count records added
                    count_result = con.execute(f"""
                        SELECT COUNT(*) FROM raw.air_quality
                        WHERE location_id = {location_id}
                          AND year = {year}
                          AND month = '{month}'
                    """).fetchone()

                    records = count_result[0] if count_result else 0
                    total_records += records
                    logging.info(f"    Extracted {records} records")

                except Exception as e:
                    # Some months may not have data - this is normal
                    logging.warning(f"    No data found or error: {e}")

                index_date += relativedelta(months=1)

        # Log successful completion
        log_extraction_complete(con, extraction_id, total_records)
        logging.info(f"Extraction complete! Total records: {total_records}")

    except Exception as e:
        log_extraction_failed(con, extraction_id, str(e))
        raise

    finally:
        close_database_connection(con)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract air quality data from OpenAQ S3"
    )

    parser.add_argument(
        "--locations_file_path",
        type=str,
        required=True,
        help="Path to JSON file with location IDs"
    )
    parser.add_argument(
        "--start_date",
        type=str,
        required=False,
        help="Start date in YYYY-MM format (optional if --incremental)"
    )
    parser.add_argument(
        "--end_date",
        type=str,
        required=False,
        help="End date in YYYY-MM format (optional if --incremental)"
    )
    parser.add_argument(
        "--database_path",
        type=str,
        required=True,
        help="Path to DuckDB database file"
    )
    parser.add_argument(
        "--extract_query_template_path",
        type=str,
        required=True,
        help="Path to SQL insert query template"
    )
    parser.add_argument(
        "--source_base_path",
        type=str,
        required=True,
        help="Base S3 path for OpenAQ data"
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Enable incremental mode (auto-detect date range)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.incremental and (not args.start_date or not args.end_date):
        parser.error("--start_date and --end_date required unless --incremental")

    extract_data(
        locations_file_path=args.locations_file_path,
        start_date=args.start_date,
        end_date=args.end_date,
        database_path=args.database_path,
        extract_query_template_path=args.extract_query_template_path,
        source_base_path=args.source_base_path,
        incremental=args.incremental
    )
```

## Step 3.4: Run Initial Data Extraction

```bash
cd pipeline

python extraction.py \
  --locations_file_path ../locations.json \
  --start_date 2024-01 \
  --end_date 2024-03 \
  --database_path ../air_quality.db \
  --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql \
  --source_base_path s3://openaq-data-archive/records/csv.gz
```

**Expected output**:
```
2024-01-15 10:05:00 - INFO - Connecting to database at ../air_quality.db
2024-01-15 10:05:01 - INFO - Started extraction job 1
2024-01-15 10:05:01 - INFO - Loaded 5 locations to extract
2024-01-15 10:05:01 - INFO - Deleting existing data from 2024-01 to 2024-03
2024-01-15 10:05:02 - INFO - Processing location: Johannesburg (ID: 225393)
2024-01-15 10:05:02 - INFO -   Extracting 2024-01 from s3://openaq-data-archive/...
2024-01-15 10:05:30 - INFO -     Extracted 45000 records
...
2024-01-15 10:15:00 - INFO - Extraction complete! Total records: 1250000
```

## Step 3.5: Verify Extraction

```bash
cd pipeline
python -c "
import duckdb
con = duckdb.connect('../air_quality.db')
print('Total records:', con.execute('SELECT COUNT(*) FROM raw.air_quality').fetchone()[0])
print('Extraction log:')
print(con.execute('SELECT * FROM raw.extraction_log').fetchdf())
con.close()
"
```

---

# Phase 4: Data Transformation

## Step 4.1: Create Presentation Air Quality View

Create file: `sql/dml/presentation/0_presentation_air_quality_view.sql`

```sql
-- Clean air quality view - removes invalid measurements
CREATE OR REPLACE VIEW presentation.air_quality AS
SELECT
    location_id,
    sensors_id,
    location,
    datetime,
    lat,
    lon,
    parameter,
    units,
    value,
    month,
    year
FROM raw.air_quality
WHERE value IS NOT NULL
  AND value > 0
  AND datetime IS NOT NULL;
```

## Step 4.2: Create Latest Values View

Create file: `sql/dml/presentation/1_presentation_latest_param_values_per_location_view.sql`

```sql
-- Latest parameter values for each location (used for map display)
CREATE OR REPLACE VIEW presentation.latest_param_values_per_location AS
WITH latest_datetime AS (
    SELECT
        location,
        MAX(datetime) AS max_datetime
    FROM presentation.air_quality
    GROUP BY location
),
latest_data AS (
    SELECT
        aq.location_id,
        aq.location,
        aq.datetime,
        aq.lat,
        aq.lon,
        aq.parameter,
        aq.value,
        aq.units
    FROM presentation.air_quality aq
    INNER JOIN latest_datetime ld
        ON aq.location = ld.location
        AND aq.datetime = ld.max_datetime
)
SELECT
    location_id,
    location,
    datetime,
    lat,
    lon,
    MAX(CASE WHEN parameter = 'pm25' THEN value END) AS pm25,
    MAX(CASE WHEN parameter = 'pm10' THEN value END) AS pm10,
    MAX(CASE WHEN parameter = 'so2' THEN value END) AS so2,
    MAX(CASE WHEN parameter = 'no2' THEN value END) AS no2,
    MAX(CASE WHEN parameter = 'o3' THEN value END) AS o3,
    MAX(CASE WHEN parameter = 'co' THEN value END) AS co
FROM latest_data
GROUP BY location_id, location, datetime, lat, lon;
```

## Step 4.3: Create Daily Statistics View

Create file: `sql/dml/presentation/2_presentation_daily_air_quality_stats_view.sql`

```sql
-- Daily aggregated statistics for time series charts
CREATE OR REPLACE VIEW presentation.daily_air_quality_stats AS
SELECT
    location_id,
    location,
    DATE(datetime) AS measurement_date,
    parameter,
    AVG(value) AS average_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    COUNT(*) AS measurement_count,
    units,
    strftime(DATE(datetime), '%A') AS weekday,
    CAST(strftime(DATE(datetime), '%w') AS INTEGER) AS weekday_number
FROM presentation.air_quality
GROUP BY
    location_id,
    location,
    DATE(datetime),
    parameter,
    units;
```

## Step 4.4: Create Transformation Script

Create file: `pipeline/transformation.py`

```python
"""
Data Transformation Pipeline - Create presentation views

Usage:
    python transformation.py \
        --database_path ../air_quality.db \
        --query_directory ../sql/dml/presentation
"""
import argparse
import logging
import os
import glob

from database_manager import (
    connect_to_database,
    close_database_connection,
    execute_query,
    read_query
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def transform_data(database_path: str, query_directory: str) -> None:
    """
    Execute all transformation queries to create presentation views.

    Args:
        database_path: Path to DuckDB database
        query_directory: Directory containing transformation SQL files
    """
    logging.info(f"Starting transformation process")
    logging.info(f"Database: {database_path}")
    logging.info(f"Query directory: {query_directory}")

    con = connect_to_database(database_path)

    try:
        # Find all SQL files in the directory
        sql_files = sorted(glob.glob(os.path.join(query_directory, "*.sql")))

        if not sql_files:
            logging.warning(f"No SQL files found in {query_directory}")
            return

        logging.info(f"Found {len(sql_files)} transformation scripts")

        # Execute each transformation script
        for sql_file in sql_files:
            file_name = os.path.basename(sql_file)
            logging.info(f"Executing {file_name}...")

            query = read_query(sql_file)
            execute_query(con, query)

            logging.info(f"Successfully executed {file_name}")

        logging.info("Transformation completed successfully!")

    except Exception as e:
        logging.error(f"Transformation failed: {e}")
        raise

    finally:
        close_database_connection(con)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transform raw data into presentation views"
    )

    parser.add_argument(
        "--database_path",
        type=str,
        required=True,
        help="Path to DuckDB database file"
    )
    parser.add_argument(
        "--query_directory",
        type=str,
        required=True,
        help="Directory containing transformation SQL files"
    )

    args = parser.parse_args()

    transform_data(
        database_path=args.database_path,
        query_directory=args.query_directory
    )
```

## Step 4.5: Run Transformation

```bash
cd pipeline

python transformation.py \
  --database_path ../air_quality.db \
  --query_directory ../sql/dml/presentation
```

**Expected output**:
```
2024-01-15 10:20:00 - INFO - Starting transformation process
2024-01-15 10:20:00 - INFO - Database: ../air_quality.db
2024-01-15 10:20:00 - INFO - Query directory: ../sql/dml/presentation
2024-01-15 10:20:00 - INFO - Found 3 transformation scripts
2024-01-15 10:20:00 - INFO - Executing 0_presentation_air_quality_view.sql...
2024-01-15 10:20:01 - INFO - Successfully executed 0_presentation_air_quality_view.sql
2024-01-15 10:20:01 - INFO - Executing 1_presentation_latest_param_values_per_location_view.sql...
2024-01-15 10:20:02 - INFO - Successfully executed 1_presentation_latest_param_values_per_location_view.sql
2024-01-15 10:20:02 - INFO - Executing 2_presentation_daily_air_quality_stats_view.sql...
2024-01-15 10:20:03 - INFO - Successfully executed 2_presentation_daily_air_quality_stats_view.sql
2024-01-15 10:20:03 - INFO - Transformation completed successfully!
```

## Step 4.6: Verify Transformation

```bash
cd pipeline
python -c "
import duckdb
con = duckdb.connect('../air_quality.db')
print('Presentation air_quality records:',
      con.execute('SELECT COUNT(*) FROM presentation.air_quality').fetchone()[0])
print('\\nLocations for map:')
print(con.execute('SELECT location, lat, lon FROM presentation.latest_param_values_per_location').fetchdf())
print('\\nDaily stats sample:')
print(con.execute('SELECT * FROM presentation.daily_air_quality_stats LIMIT 5').fetchdf())
con.close()
"
```

---

# Phase 5: Dashboard Development

## Step 5.1: Create Dash Application

Create file: `dashboard/app.py`

```python
"""
Air Quality Monitoring Dashboard

Usage:
    python app.py

Access at: http://127.0.0.1:8050
"""
import duckdb
import pandas as pd
from dash import Dash, html, dcc, Input, Output
import plotly.express as px

# Initialize Dash app
app = Dash(__name__)

# Database path
DATABASE_PATH = "../air_quality.db"


def get_db_connection():
    """Create database connection."""
    return duckdb.connect(DATABASE_PATH, read_only=True)


def get_map_data():
    """Fetch data for map visualization."""
    con = get_db_connection()
    query = "SELECT * FROM presentation.latest_param_values_per_location"
    df = con.execute(query).fetchdf()
    con.close()
    return df


def get_daily_stats():
    """Fetch daily statistics data."""
    con = get_db_connection()
    query = "SELECT * FROM presentation.daily_air_quality_stats"
    df = con.execute(query).fetchdf()
    con.close()
    return df


def get_parameters():
    """Get list of available parameters."""
    con = get_db_connection()
    query = "SELECT DISTINCT parameter FROM presentation.daily_air_quality_stats ORDER BY parameter"
    params = con.execute(query).fetchdf()['parameter'].tolist()
    con.close()
    return params


def get_date_range():
    """Get min and max dates in the data."""
    con = get_db_connection()
    query = """
        SELECT
            MIN(measurement_date) as min_date,
            MAX(measurement_date) as max_date
        FROM presentation.daily_air_quality_stats
    """
    result = con.execute(query).fetchone()
    con.close()
    return result[0], result[1]


# Get initial data
parameters = get_parameters()
min_date, max_date = get_date_range()

# App layout
app.layout = html.Div([
    # Title
    html.H1(
        "Real-time Environmental Air Quality Monitoring Dashboard",
        style={
            "textAlign": "center",
            "marginBottom": "10px",
            "fontSize": "24px"
        }
    ),

    # Tabs
    dcc.Tabs([
        # Tab 1: Map View
        dcc.Tab(
            label="Sensor Locations",
            children=[
                dcc.Graph(id="map-view", style={"height": "85vh"})
            ]
        ),

        # Tab 2: Parameter Plots
        dcc.Tab(
            label="Parameter Plots",
            children=[
                # Controls
                html.Div([
                    # Parameter Dropdown
                    html.Div([
                        html.Label(
                            "Select Parameter:",
                            style={
                                "fontWeight": "bold",
                                "marginRight": "10px",
                                "fontSize": "14px"
                            }
                        ),
                        dcc.Dropdown(
                            id="parameter-dropdown",
                            options=[{"label": p.upper(), "value": p} for p in parameters],
                            value=parameters[0] if parameters else None,
                            clearable=False,
                            style={"width": "200px"}
                        ),
                    ], style={
                        "display": "flex",
                        "alignItems": "center",
                        "marginRight": "20px"
                    }),

                    # Date Range Picker
                    html.Div([
                        html.Label(
                            "Select Date Range:",
                            style={
                                "fontWeight": "bold",
                                "marginRight": "10px",
                                "fontSize": "14px"
                            }
                        ),
                        dcc.DatePickerRange(
                            id="date-picker-range",
                            start_date=min_date,
                            end_date=max_date,
                            display_format="YYYY-MM-DD"
                        ),
                    ], style={
                        "display": "flex",
                        "alignItems": "center"
                    }),
                ], style={
                    "display": "flex",
                    "alignItems": "center",
                    "marginBottom": "10px",
                    "marginTop": "10px",
                    "flexWrap": "wrap"
                }),

                # Charts
                html.Div([
                    dcc.Graph(id="line-plot", style={"height": "38vh", "marginBottom": "5px"}),
                    dcc.Graph(id="bar-plot", style={"height": "38vh"})
                ])
            ]
        )
    ])
], style={
    "padding": "10px",
    "height": "100vh",
    "boxSizing": "border-box"
})


@app.callback(
    Output("map-view", "figure"),
    Input("map-view", "id")
)
def update_map(_):
    """Update map visualization."""
    df = get_map_data()

    if df.empty:
        return px.scatter_mapbox(title="No data available")

    # Create hover text
    df['hover_text'] = df.apply(
        lambda row: f"<b>{row['location']}</b><br>"
                    f"PM2.5: {row['pm25']:.1f} µg/m³<br>" if pd.notna(row.get('pm25')) else "" +
                    f"PM10: {row['pm10']:.1f} µg/m³<br>" if pd.notna(row.get('pm10')) else "" +
                    f"SO2: {row['so2']:.2f} ppm" if pd.notna(row.get('so2')) else "",
        axis=1
    )

    # Calculate center
    center_lat = df['lat'].mean()
    center_lon = df['lon'].mean()

    # Create map
    fig = px.scatter_mapbox(
        df,
        lat="lat",
        lon="lon",
        hover_name="location",
        hover_data={
            "lat": False,
            "lon": False,
            "pm25": ":.1f",
            "pm10": ":.1f",
            "so2": ":.2f"
        },
        zoom=5,
        mapbox_style="open-street-map"
    )

    # Update markers
    fig.update_traces(
        marker=dict(size=20, opacity=0.9, color="red")
    )

    # Update layout
    fig.update_layout(
        mapbox=dict(
            center=dict(lat=center_lat, lon=center_lon),
            zoom=5
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        title="Air Quality Sensor Locations"
    )

    return fig


@app.callback(
    [Output("line-plot", "figure"),
     Output("bar-plot", "figure")],
    [Input("parameter-dropdown", "value"),
     Input("date-picker-range", "start_date"),
     Input("date-picker-range", "end_date")]
)
def update_plots(selected_parameter, start_date, end_date):
    """Update line and bar charts."""
    df = get_daily_stats()

    if df.empty or not selected_parameter:
        empty_fig = px.line(title="No data available")
        return empty_fig, empty_fig

    # Filter by parameter and date range
    filtered_df = df[
        (df['parameter'] == selected_parameter) &
        (df['measurement_date'] >= start_date) &
        (df['measurement_date'] <= end_date)
    ].copy()

    if filtered_df.empty:
        empty_fig = px.line(title="No data for selected filters")
        return empty_fig, empty_fig

    # Get units for labels
    unit = filtered_df['units'].iloc[0] if not filtered_df.empty else ""

    labels = {
        "measurement_date": "Date",
        "average_value": f"{selected_parameter.upper()} ({unit})",
        "location": "Location"
    }

    # Line chart - Time series for all locations
    line_fig = px.line(
        filtered_df.sort_values(by=["location", "measurement_date"]),
        x="measurement_date",
        y="average_value",
        color="location",
        labels=labels,
        title=f"{selected_parameter.upper()} Levels Over Time - All Locations"
    )

    line_fig.update_layout(
        hovermode="x unified",
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02
        ),
        margin=dict(l=50, r=150, t=50, b=50)
    )

    # Bar chart - Average by location
    avg_by_location = filtered_df.groupby('location')['average_value'].mean().reset_index()
    avg_by_location = avg_by_location.sort_values('average_value', ascending=False)

    bar_fig = px.bar(
        avg_by_location,
        x="location",
        y="average_value",
        labels={
            "average_value": f"Average {selected_parameter.upper()} ({unit})",
            "location": "Location"
        },
        title=f"Average {selected_parameter.upper()} Levels by Location",
        color="location"
    )

    bar_fig.update_layout(
        showlegend=False,
        xaxis_tickangle=-45,
        margin=dict(l=50, r=50, t=50, b=100)
    )

    return line_fig, bar_fig


if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
```

## Step 5.2: Run the Dashboard

```bash
cd dashboard
python app.py
```

**Expected output**:
```
Dash is running on http://127.0.0.1:8050/

 * Serving Flask app 'app'
 * Debug mode: on
```

## Step 5.3: Access Dashboard

Open browser and navigate to: `http://127.0.0.1:8050`

You should see:
1. **Tab 1 (Sensor Locations)**: Interactive map with red markers
2. **Tab 2 (Parameter Plots)**: Line chart and bar chart with filters

## Step 5.4: Take Screenshots

Once dashboard is running, take screenshots for documentation:
1. Sensor locations map → Save as `Image/Sensor locations.jpg`
2. PM2.5 time series → Save as `Image/pm25.jpg`
3. PM10 time series → Save as `Image/pm10.jpg`
4. SO2 time series → Save as `Image/so2.jpg`

---

# Phase 6: Incremental Loading

## Step 6.1: Test Incremental Mode

After initial data load, you can update data incrementally:

```bash
cd pipeline

# Run incremental extraction
python extraction.py \
  --locations_file_path ../locations.json \
  --database_path ../air_quality.db \
  --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql \
  --source_base_path s3://openaq-data-archive/records/csv.gz \
  --incremental

# Refresh views
python transformation.py \
  --database_path ../air_quality.db \
  --query_directory ../sql/dml/presentation
```

## Step 6.2: Verify Incremental Loading

```sql
-- Check extraction history
SELECT * FROM raw.extraction_log ORDER BY extraction_id DESC;

-- Verify new data was added
SELECT
    year,
    month,
    COUNT(*) as records
FROM raw.air_quality
GROUP BY year, month
ORDER BY year, month;
```

---

# Phase 7: Dashboard Enhancements

## Step 7.1: Improvements Made

The dashboard went through several iterations:

**Iteration 1: Basic Dashboard**
- Simple map and charts
- Location dropdown to select one city

**Iteration 2: Multi-Location Comparison**
- Removed location dropdown
- Show all locations together with different colors
- Easier comparison across cities

**Iteration 3: Improved Map Visibility**
- Increased marker size from 5 to 20
- Changed color to red
- Added auto-centering based on data

**Iteration 4: Responsive Layout**
- Changed from fixed pixels to viewport heights (vh)
- Map: 85vh
- Charts: 38vh each
- No scrolling needed

**Iteration 5: Bar Chart Addition**
- Replaced box plot with bar chart
- Shows average values by location
- Sorted highest to lowest
- Easy to identify pollution hotspots

---

# Phase 8: Documentation

## Step 8.1: Create Main README.md

Create comprehensive `README.md` in project root with:
- Project description
- Screenshots
- Installation instructions
- Usage examples
- Troubleshooting

## Step 8.2: Create SETUP_GUIDE.md

Create detailed setup guide with:
- System requirements
- Step-by-step installation
- Platform-specific instructions (Windows/Mac/Linux)

## Step 8.3: Create INCREMENTAL_LOADING.md

Create advanced guide covering:
- How incremental loading works
- Configuration options
- Automation examples

## Step 8.4: Create docs/ Folder Contents

Create in `docs/` folder:
- `PROJECT_ARCHITECTURE.md` - System diagrams
- `WORKFLOW_DIAGRAMS.md` - Operational workflows
- `ARCHITECTURE_EXPLANATION.md` - Design rationale
- `README.md` - Documentation guide
- `PROJECT_SUMMARY.md` - Complete summary
- `PROJECT_BUILD_GUIDE.md` - This document

---

# Phase 9: Testing & Verification

## Step 9.1: Complete System Test

Run through entire workflow:

```bash
# 1. Setup database (if starting fresh)
cd pipeline
python setup_database.py --database_path ../air_quality.db

# 2. Extract data
python extraction.py \
  --locations_file_path ../locations.json \
  --start_date 2024-01 \
  --end_date 2024-03 \
  --database_path ../air_quality.db \
  --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql \
  --source_base_path s3://openaq-data-archive/records/csv.gz

# 3. Transform data
python transformation.py \
  --database_path ../air_quality.db \
  --query_directory ../sql/dml/presentation

# 4. Launch dashboard
cd ../dashboard
python app.py
```

## Step 9.2: Verification Checklist

Run these checks after each phase:

```bash
# Check 1: Database exists
ls -la air_quality.db

# Check 2: Tables exist
python -c "
import duckdb
con = duckdb.connect('air_quality.db')
print(con.execute(\"SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('raw', 'presentation')\").fetchdf())
con.close()
"

# Check 3: Data exists
python -c "
import duckdb
con = duckdb.connect('air_quality.db')
print('Raw records:', con.execute('SELECT COUNT(*) FROM raw.air_quality').fetchone()[0])
print('Presentation records:', con.execute('SELECT COUNT(*) FROM presentation.air_quality').fetchone()[0])
con.close()
"

# Check 4: Extraction log
python -c "
import duckdb
con = duckdb.connect('air_quality.db')
print(con.execute('SELECT * FROM raw.extraction_log').fetchdf())
con.close()
"

# Check 5: Dashboard runs
cd dashboard && python -c "from app import app; print('Dashboard imports OK')"
```

## Step 9.3: Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "Schema does not exist" | Database not initialized | Run `setup_database.py` |
| "No files found" | Invalid location IDs | Check OpenAQ for valid IDs |
| "Connection refused" | Port in use | Change port in app.py |
| Empty dashboard | No data extracted | Run extraction first |
| Slow extraction | Large date range | Use incremental mode |

---

# Quick Reference Commands

## Full Pipeline (From Scratch)

```bash
# Navigate to project
cd Real-Time-Environmental-Air-Quality-Monitoring-Dashboard-Pipeline

# Activate environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Setup database
cd pipeline
python setup_database.py --database_path ../air_quality.db

# Extract data
python extraction.py \
  --locations_file_path ../locations.json \
  --start_date 2024-01 \
  --end_date 2024-03 \
  --database_path ../air_quality.db \
  --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql \
  --source_base_path s3://openaq-data-archive/records/csv.gz

# Transform data
python transformation.py \
  --database_path ../air_quality.db \
  --query_directory ../sql/dml/presentation

# Run dashboard
cd ../dashboard
python app.py
```

## Daily Update (Incremental)

```bash
cd pipeline
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

---

# Summary

## What I Built

| Component | Files Created | Purpose |
|-----------|--------------|---------|
| Database Schema | 3 SQL files | Data structure |
| Extraction Pipeline | 3 Python files + 2 SQL | Data ingestion |
| Transformation | 1 Python file + 3 SQL | Data preparation |
| Dashboard | 1 Python file | Visualization |
| Documentation | 8+ Markdown files | Reference |

## Key Design Decisions

1. **DuckDB** for fast, embedded analytics
2. **Two-schema pattern** (raw/presentation) for data integrity
3. **Incremental loading** for efficient updates
4. **Metadata tracking** for monitoring and debugging
5. **Responsive design** for multi-device support
6. **SQL views** for always-current analytics

## Skills Applied

- Data Engineering (ETL pipelines)
- Database Design (schemas, views)
- Python Development (CLI tools, web apps)
- SQL (DuckDB, templates)
- Data Visualization (Plotly, Dash)
- Documentation (technical writing)

---

**This guide was created to document the complete build process. Follow these steps exactly to recreate the project from scratch.**

**Document Version**: 1.0
**Last Updated**: January 2026
**Total Phases**: 9
**Estimated Build Time**: 4-6 hours (including data extraction)
