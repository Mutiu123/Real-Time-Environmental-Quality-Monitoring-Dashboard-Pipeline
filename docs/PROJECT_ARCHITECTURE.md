# Real-Time Environmental Air Quality Monitoring Pipeline - Architecture Guide

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AIR QUALITY MONITORING PIPELINE                          │
│                    Data → Process → Visualize                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Architecture

```
┌──────────────────┐
│   DATA SOURCE    │
│                  │
│   OpenAQ S3      │──────┐
│   Bucket         │      │
│                  │      │
│ • CSV.GZ files   │      │
│ • Partitioned    │      │
│   by location    │      │
│   & date         │      │
└──────────────────┘      │
                          │
                          ▼
        ┌─────────────────────────────────┐
        │    EXTRACTION PIPELINE          │
        │    (extraction.py)              │
        │                                 │
        │  • Pull data from S3            │
        │  • Filter by location & date    │
        │  • Incremental loading          │
        │  • Metadata tracking            │
        └─────────────────┬───────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │       DUCKDB DATABASE           │
        │                                 │
        │  ┌──────────────────────────┐  │
        │  │   RAW SCHEMA             │  │
        │  │                          │  │
        │  │  • air_quality           │  │
        │  │    - location_id         │  │
        │  │    - datetime            │  │
        │  │    - parameter (pm25,    │  │
        │  │      pm10, so2)          │  │
        │  │    - value               │  │
        │  │    - lat/lon             │  │
        │  │                          │  │
        │  │  • extraction_log        │  │
        │  │    - tracks all jobs     │  │
        │  │    - metadata            │  │
        │  └──────────────────────────┘  │
        └─────────────────┬───────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │   TRANSFORMATION PIPELINE       │
        │   (transformation.py)           │
        │                                 │
        │  • SQL-based views              │
        │  • Daily aggregations           │
        │  • Latest values                │
        │  • Statistical calculations     │
        └─────────────────┬───────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │   PRESENTATION SCHEMA           │
        │                                 │
        │  ┌──────────────────────────┐  │
        │  │  VIEWS                   │  │
        │  │                          │  │
        │  │  1. air_quality          │  │
        │  │     (cleaned data)       │  │
        │  │                          │  │
        │  │  2. latest_param_        │  │
        │  │     values_per_location  │  │
        │  │     (for map)            │  │
        │  │                          │  │
        │  │  3. daily_air_quality_   │  │
        │  │     stats                │  │
        │  │     (for charts)         │  │
        │  └──────────────────────────┘  │
        └─────────────────┬───────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │      DASH DASHBOARD             │
        │      (app.py)                   │
        │                                 │
        │  ┌──────────────────────────┐  │
        │  │   SENSOR LOCATIONS       │  │
        │  │                          │  │
        │  │   Interactive Map     │  │
        │  │   • All locations        │  │
        │  │   • Latest readings      │  │
        │  │   • Hover tooltips       │  │
        │  └──────────────────────────┘  │
        │                                 │
        │  ┌──────────────────────────┐  │
        │  │   PARAMETER PLOTS        │  │
        │  │                          │  │
        │  │   Time Series         │  │
        │  │   • Multi-location       │  │
        │  │   • Color-coded          │  │
        │  │   • Date range filter    │  │
        │  │                          │  │
        │  │   Bar Chart           │  │
        │  │   • Average by location  │  │
        │  │   • Sorted comparison    │  │
        │  └──────────────────────────┘  │
        └─────────────────────────────────┘
```

---

## Pipeline Components

### 1️ DATA INGESTION (Batch Processing)

```
┌─────────────────────────────────────────────┐
│  EXTRACTION MODES                           │
├─────────────────────────────────────────────┤
│                                             │
│  FULL EXTRACTION                            │
│  ├─ Manual date range                      │
│  ├─ Delete existing data                   │
│  ├─ Download & insert new data             │
│  └─ Use case: Initial load, backfill       │
│                                             │
│  INCREMENTAL EXTRACTION                  │
│  ├─ Auto-detect date range                 │
│  ├─ Fetch only new months                  │
│  ├─ No data deletion                       │
│  └─ Use case: Daily/weekly updates         │
│                                             │
└─────────────────────────────────────────────┘

Data Sources:
┌──────────┐
│ OpenAQ   │──┐
│ S3       │  │
│          │  ├──> CSV.GZ Files
│ Public   │  │    • Partitioned by location
│ Archive  │  │    • Partitioned by year/month
└──────────┘──┘    • Compressed format

Extraction Process:
1. Read locations.json
2. Generate file paths for each location/month
3. Connect to S3 bucket
4. Read CSV files directly (no download)
5. Insert into DuckDB raw schema
6. Log metadata (extraction_log table)
```

### 2️ DATA TRANSFORMATION (SQL-Based)

```
┌─────────────────────────────────────────────┐
│  TRANSFORMATION LAYERS                      │
├─────────────────────────────────────────────┤
│                                             │
│  RAW → PRESENTATION                         │
│                                             │
│  Step 1: Clean & Standardize               │
│  ├─ Remove nulls                           │
│  ├─ Filter valid readings                  │
│  └─ Standardize units                      │
│                                             │
│  Step 2: Latest Values                     │
│  ├─ Get most recent reading per location   │
│  ├─ Pivot parameters (pm25, pm10, so2)     │
│  └─ Join with location metadata            │
│                                             │
│  Step 3: Daily Statistics                  │
│  ├─ GROUP BY date, location, parameter     │
│  ├─ Calculate AVG, MIN, MAX                │
│  ├─ Extract weekday information            │
│  └─ Create time series data                │
│                                             │
└─────────────────────────────────────────────┘

Views Created:
┌──────────────────────────────────────┐
│ 1. air_quality                       │
│    → Cleaned base data               │
│                                      │
│ 2. latest_param_values_per_location │
│    → For sensor map                  │
│                                      │
│ 3. daily_air_quality_stats          │
│    → For time series charts          │
└──────────────────────────────────────┘
```

### 3️ DATA VISUALIZATION (Interactive Dashboard)

```
┌─────────────────────────────────────────────┐
│  DASHBOARD COMPONENTS                       │
├─────────────────────────────────────────────┤
│                                             │
│  TAB 1: SENSOR LOCATIONS                   │
│  ┌───────────────────────────────────┐     │
│  │  Plotly Mapbox Scatter            │     │
│  │                                   │     │
│  │   [Interactive Map]            │     │
│  │                                   │     │
│  │  Features:                        │     │
│  │  • OpenStreetMap base             │     │
│  │  • Red markers (size 20)          │     │
│  │  • Auto-centered                  │     │
│  │  • Hover: location + values       │     │
│  │  • Zoom controls                  │     │
│  └───────────────────────────────────┘     │
│                                             │
│  TAB 2: PARAMETER PLOTS                    │
│  ┌───────────────────────────────────┐     │
│  │  Controls:                        │     │
│  │  [Parameter ▼] [Date Range ▼]    │     │
│  └───────────────────────────────────┘     │
│                                             │
│  ┌───────────────────────────────────┐     │
│  │  Line Chart (Time Series)         │     │
│  │                                   │     │
│  │   Multi-line plot               │     │
│  │     • One line per location       │     │
│  │     • Color-coded                 │     │
│  │     • Unified hover mode          │     │
│  │     • Height: 38vh                │     │
│  └───────────────────────────────────┘     │
│                                             │
│  ┌───────────────────────────────────┐     │
│  │  Bar Chart (Comparison)           │     │
│  │                                   │     │
│  │   Sorted bars                   │     │
│  │     • Average values              │     │
│  │     • Highest to lowest           │     │
│  │     • Color-coded                 │     │
│  │     • Height: 38vh                │     │
│  └───────────────────────────────────┘     │
│                                             │
└─────────────────────────────────────────────┘

Technology Stack:
• Dash (Flask-based)
• Plotly Express
• Pandas (data manipulation)
• DuckDB (database queries)
```

---

##  Key Technologies

```
┌──────────────────────────────────────────────────────┐
│  TECHNOLOGY STACK                                    │
├──────────────────────────────────────────────────────┤
│                                                      │
│  DATABASE                                            │
│  ├─ DuckDB (Analytical SQL database)                │
│  ├─ Embedded (no server needed)                     │
│  ├─ Fast analytical queries                         │
│  └─ Direct S3 reading capability                    │
│                                                      │
│  DATA PROCESSING                                     │
│  ├─ Python 3.8+                                     │
│  ├─ Pandas (data manipulation)                      │
│  ├─ Jinja2 (SQL templating)                        │
│  └─ python-dateutil (date handling)                │
│                                                      │
│  VISUALIZATION                                       │
│  ├─ Dash (web framework)                           │
│  ├─ Plotly (interactive charts)                    │
│  ├─ Plotly Express (simplified API)                │
│  └─ HTML/CSS (responsive layout)                   │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## Key Features

```
┌────────────────────────────────────────────────┐
│  INCREMENTAL LOADING                           │
├────────────────────────────────────────────────┤
│                                                │
│  Problem: Don't want to re-download all data  │
│  Solution: Smart date range detection         │
│                                                │
│  How it works:                                 │
│  1. Check extraction_log table                │
│  2. Get last successful end_date              │
│  3. Start from next month                     │
│  4. End at current month                      │
│  5. Only fetch new data                       │
│                                                │
│  Benefits:                                     │
│  ✓ Faster updates                             │
│  ✓ Lower bandwidth                            │
│  ✓ No duplicates                              │
│  ✓ Automated scheduling                       │
│                                                │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│  METADATA TRACKING                             │
├────────────────────────────────────────────────┤
│                                                │
│  extraction_log table tracks:                 │
│  • extraction_id (auto-increment)             │
│  • start_datetime                             │
│  • end_datetime                               │
│  • date_range (start_date, end_date)         │
│  • status (running/completed/failed)          │
│  • records_extracted                          │
│  • error_message (if failed)                  │
│                                                │
│  Use cases:                                    │
│  • Monitor pipeline health                    │
│  • Debug failures                             │
│  • Track data volume                          │
│  • Audit trail                                │
│                                                │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│  RESPONSIVE DESIGN                             │
├────────────────────────────────────────────────┤
│                                                │
│  Layout uses viewport units (vh):             │
│  • Dashboard: 100vh total                     │
│  • Map: 85vh                                  │
│  • Line chart: 38vh                           │
│  • Bar chart: 38vh                            │
│                                                │
│  Benefits:                                     │
│  ✓ Fits any screen size                       │
│  ✓ No scrolling needed                        │
│  ✓ Desktop & mobile ready                     │
│  ✓ Professional appearance                    │
│                                                │
└────────────────────────────────────────────────┘
```

---

##  Data Model

```
┌────────────────────────────────────────────────────────┐
│  raw.air_quality (Source Data)                        │
├────────────────────────────────────────────────────────┤
│  location_id        BIGINT                             │
│  sensors_id         VARCHAR                            │
│  location           VARCHAR                            │
│  datetime           TIMESTAMP                          │
│  lat                DOUBLE                             │
│  lon                DOUBLE                             │
│  parameter          VARCHAR (pm25, pm10, so2, etc.)   │
│  units              VARCHAR (µg/m³, ppm, etc.)        │
│  value              DOUBLE                             │
│  month              VARCHAR                            │
│  year               BIGINT                             │
│  ingestion_datetime TIMESTAMP                          │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│  presentation.daily_air_quality_stats (Analytics)     │
├────────────────────────────────────────────────────────┤
│  location           VARCHAR                            │
│  measurement_date   DATE                               │
│  parameter          VARCHAR                            │
│  average_value      DOUBLE                             │
│  min_value          DOUBLE                             │
│  max_value          DOUBLE                             │
│  units              VARCHAR                            │
│  weekday            VARCHAR                            │
│  weekday_number     INTEGER                            │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│  presentation.latest_param_values_per_location        │
├────────────────────────────────────────────────────────┤
│  location           VARCHAR                            │
│  datetime           TIMESTAMP                          │
│  lat                DOUBLE                             │
│  lon                DOUBLE                             │
│  pm25               DOUBLE                             │
│  pm10               DOUBLE                             │
│  so2                DOUBLE                             │
└────────────────────────────────────────────────────────┘
```

---

*Page 1 of 2 - Continue to next page for workflow diagrams*
