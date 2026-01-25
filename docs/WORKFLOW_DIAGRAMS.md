# Real-Time Environmental Air Quality Monitoring Pipeline - Workflow Guide

*Page 2 of 2 - Operational Workflows & Processes*

---

## Complete Pipeline Workflow

```
┌──────────────────────────────────────────────────────────────────┐
│                    INITIAL SETUP (ONE TIME)                      │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌────────────────────────────────────┐
        │  1. Install Dependencies           │
        │     pip install -r requirements.txt│
        └────────────┬───────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │  2. Initialize Database            │
        │     python setup_database.py       │
        │                                    │
        │     Creates:                       │
        │     • raw schema                   │
        │     • presentation schema          │
        │     • air_quality table            │
        │     • extraction_log table         │
        └────────────┬───────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │  3. Initial Data Load              │
        │     python extraction.py           │
        │     --start_date 2024-01           │
        │     --end_date 2024-03             │
        │                                    │
        │     Downloads 3 months of data     │
        └────────────┬───────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │  4. Create Views                   │
        │     python transformation.py       │
        │                                    │
        │     Creates analytical views       │
        └────────────┬───────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │  5. Launch Dashboard               │
        │     python app.py                  │
        │                                    │
        │     Access: http://127.0.0.1:8050  │
        └────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    REGULAR UPDATES (AUTOMATED)                   │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌────────────────────────────────────┐
        │  Daily/Weekly Schedule             │
        │  (Cron or Task Scheduler)          │
        └────────────┬───────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │  1. Incremental Extraction         │
        │     python extraction.py           │
        │     --incremental                  │
        │                                    │
        │     Auto-detects:                  │
        │     • Last extraction end date     │
        │     • Fetches only new months      │
        │     • Logs metadata                │
        └────────────┬───────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │  2. Refresh Views                  │
        │     python transformation.py       │
        │                                    │
        │     Updates analytical views       │
        └────────────┬───────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │  Dashboard Auto-Refreshes          │
        │  (Users see new data immediately)  │
        └────────────────────────────────────┘
```

---

##  Extraction Pipeline Flow

```
┌─────────────────────────────────────────────────────────┐
│  EXTRACTION DECISION TREE                               │
└─────────────────────────────────────────────────────────┘

        START: python extraction.py
               │
               ▼
        ┌──────────────────┐
        │ --incremental    │
        │   flag set?      │
        └────┬────────┬────┘
             │        │
        YES  │        │ NO
             ▼        ▼
    ┌─────────────┐  ┌─────────────────┐
    │ INCREMENTAL │  │ FULL EXTRACTION │
    │    MODE     │  │                 │
    └──────┬──────┘  └────────┬────────┘
           │                  │
           ▼                  ▼
    ┌────────────────┐  ┌──────────────────┐
    │ Check last     │  │ Use provided     │
    │ extraction     │  │ start_date &     │
    │ end_date       │  │ end_date         │
    └──────┬─────────┘  └────────┬─────────┘
           │                     │
           ▼                     ▼
    ┌────────────────┐  ┌──────────────────┐
    │ Calculate:     │  │ Delete existing  │
    │ start = last+1 │  │ data for range   │
    │ end = current  │  │                  │
    └──────┬─────────┘  └────────┬─────────┘
           │                     │
           └──────────┬──────────┘
                      ▼
            ┌───────────────────┐
            │ For each location │
            │ For each month    │
            └─────────┬─────────┘
                      │
                      ▼
            ┌───────────────────┐
            │ Build S3 path:    │
            │ locationid={id}/  │
            │ year={y}/month={m}│
            └─────────┬─────────┘
                      │
                      ▼
            ┌───────────────────┐
            │ Read CSV from S3  │
            │ (DuckDB direct)   │
            └─────────┬─────────┘
                      │
                      ▼
            ┌───────────────────┐
            │ INSERT INTO       │
            │ raw.air_quality   │
            └─────────┬─────────┘
                      │
                      ▼
            ┌───────────────────┐
            │ Log extraction    │
            │ metadata          │
            └─────────┬─────────┘
                      │
                      ▼
                    DONE
```

---

## Data Transformation Process

```
┌──────────────────────────────────────────────────────────┐
│  SQL VIEW CREATION SEQUENCE                              │
└──────────────────────────────────────────────────────────┘

Step 1: Clean Base Data
┌─────────────────────────────────────────┐
│ CREATE VIEW presentation.air_quality   │
│                                         │
│ SELECT                                  │
│   location_id,                         │
│   location,                            │
│   datetime,                            │
│   lat, lon,                            │
│   parameter,                           │
│   value,                               │
│   units                                │
│ FROM raw.air_quality                   │
│ WHERE value IS NOT NULL                │
│   AND value > 0                        │
│   AND datetime IS NOT NULL             │
└─────────────────────────────────────────┘
                 │
                 ▼
Step 2: Latest Values Per Location
┌─────────────────────────────────────────┐
│ CREATE VIEW presentation.              │
│   latest_param_values_per_location     │
│                                         │
│ WITH latest AS (                       │
│   SELECT location,                     │
│          MAX(datetime) as max_dt       │
│   FROM presentation.air_quality        │
│   GROUP BY location                    │
│ )                                      │
│ SELECT                                 │
│   location,                            │
│   datetime,                            │
│   lat, lon,                            │
│   MAX(CASE WHEN parameter='pm25'      │
│        THEN value END) as pm25,       │
│   MAX(CASE WHEN parameter='pm10'      │
│        THEN value END) as pm10,       │
│   MAX(CASE WHEN parameter='so2'       │
│        THEN value END) as so2          │
│ FROM presentation.air_quality          │
│ JOIN latest                            │
│ GROUP BY location, datetime,           │
│          lat, lon                      │
└─────────────────────────────────────────┘
                 │
                 ▼
Step 3: Daily Statistics
┌─────────────────────────────────────────┐
│ CREATE VIEW presentation.              │
│   daily_air_quality_stats              │
│                                         │
│ SELECT                                 │
│   location,                            │
│   DATE(datetime) as measurement_date,  │
│   parameter,                           │
│   AVG(value) as average_value,        │
│   MIN(value) as min_value,            │
│   MAX(value) as max_value,            │
│   units,                               │
│   strftime(DATE(datetime), '%A')      │
│     as weekday,                        │
│   CAST(strftime(DATE(datetime), '%w') │
│     AS INTEGER) as weekday_number      │
│ FROM presentation.air_quality          │
│ GROUP BY location, DATE(datetime),     │
│          parameter, units              │
└─────────────────────────────────────────┘
```

---

##  Dashboard Component Details

```
┌──────────────────────────────────────────────────────────┐
│  SENSOR LOCATIONS TAB                                    │
└──────────────────────────────────────────────────────────┘

Data Source:
┌────────────────────────────────────────┐
│ presentation.                          │
│   latest_param_values_per_location    │
└────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ Plotly Mapbox Scatter                 │
│                                        │
│ Configuration:                         │
│ • lat/lon from database               │
│ • marker size: 20                     │
│ • marker color: red                   │
│ • marker opacity: 0.9                 │
│ • zoom: auto-calculated               │
│ • center: mean(lat), mean(lon)        │
│ • mapbox_style: open-street-map       │
│                                        │
│ Hover Data:                           │
│ • Location name                       │
│ • Latest datetime                     │
│ • PM2.5 value                         │
│ • PM10 value                          │
│ • SO2 value                           │
└────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  PARAMETER PLOTS TAB                                     │
└──────────────────────────────────────────────────────────┘

User Controls:
┌────────────────────────────────────────┐
│ 1. Parameter Dropdown                 │
│    • pm25, pm10, so2, etc.           │
│    • Auto-populated from data        │
│                                        │
│ 2. Date Range Picker                  │
│    • Start date: min(measurement_date)│
│    • End date: max(measurement_date)  │
└────────────────────────────────────────┘
         │
         ▼
Data Query:
┌────────────────────────────────────────┐
│ SELECT * FROM presentation.            │
│   daily_air_quality_stats             │
│ WHERE parameter = [selected]           │
│   AND measurement_date                 │
│       BETWEEN [start] AND [end]        │
└────────────────────────────────────────┘
         │
         ▼
Visualization 1: Line Chart
┌────────────────────────────────────────┐
│ px.line(                              │
│   data,                               │
│   x='measurement_date',               │
│   y='average_value',                  │
│   color='location'                    │
│ )                                     │
│                                        │
│ Features:                             │
│ • Multi-line (one per location)       │
│ • Color-coded automatically           │
│ • Unified hover mode                  │
│ • Legend on right side                │
│ • Height: 38vh                        │
└────────────────────────────────────────┘
         │
         ▼
Visualization 2: Bar Chart
┌────────────────────────────────────────┐
│ avg_by_location = data.groupby(       │
│   'location'                          │
│ )['average_value'].mean()            │
│                                        │
│ px.bar(                               │
│   avg_by_location,                   │
│   x='location',                       │
│   y='average_value',                  │
│   color='location'                    │
│ )                                     │
│                                        │
│ Features:                             │
│ • Sorted highest to lowest            │
│ • Color-coded by location             │
│ • No legend (uses x-axis labels)      │
│ • Angled labels (-45°)                │
│ • Height: 38vh                        │
└────────────────────────────────────────┘
```

---

##  Monitoring & Logging

```
┌──────────────────────────────────────────────────────────┐
│  EXTRACTION LOG MONITORING                               │
└──────────────────────────────────────────────────────────┘

View Recent Extractions:
┌────────────────────────────────────────┐
│ SELECT                                 │
│   extraction_id,                      │
│   extraction_start_datetime,          │
│   extraction_end_datetime,            │
│   start_date,                         │
│   end_date,                           │
│   status,                             │
│   records_extracted                   │
│ FROM raw.extraction_log               │
│ ORDER BY extraction_id DESC           │
│ LIMIT 10;                             │
└────────────────────────────────────────┘

Check Failed Extractions:
┌────────────────────────────────────────┐
│ SELECT *                              │
│ FROM raw.extraction_log               │
│ WHERE status = 'failed'               │
│ ORDER BY extraction_start_datetime    │
│   DESC;                               │
└────────────────────────────────────────┘

View Last Successful:
┌────────────────────────────────────────┐
│ SELECT *                              │
│ FROM raw.last_successful_extraction;  │
└────────────────────────────────────────┘

Extraction Statistics:
┌────────────────────────────────────────┐
│ SELECT                                 │
│   COUNT(*) as total_runs,             │
│   SUM(CASE WHEN status='completed'    │
│       THEN 1 ELSE 0 END)              │
│     as successful,                    │
│   SUM(CASE WHEN status='failed'       │
│       THEN 1 ELSE 0 END)              │
│     as failed,                        │
│   SUM(records_extracted)              │
│     as total_records                  │
│ FROM raw.extraction_log;              │
└────────────────────────────────────────┘
```

---

## Deployment Options

```
┌──────────────────────────────────────────────────────────┐
│  LOCAL DEVELOPMENT                                       │
└──────────────────────────────────────────────────────────┘
✓ Run on localhost:8050
✓ Use for testing & development
✓ Single user access
✓ Command: python app.py

┌──────────────────────────────────────────────────────────┐
│  SCHEDULED AUTOMATION                                    │
└──────────────────────────────────────────────────────────┘
✓ Windows Task Scheduler / Cron
✓ Daily/weekly data updates
✓ Incremental extraction
✓ Email notifications on failure

┌──────────────────────────────────────────────────────────┐
│  CLOUD DEPLOYMENT (Future)                               │
└──────────────────────────────────────────────────────────┘
• Heroku, AWS, Google Cloud, Azure
• Use gunicorn for production server
• Configure environment variables
• Set up CI/CD pipeline
• Add authentication if needed
```

---

## Key Terminology

```
┌────────────────────────────────────────────────────────┐
│ TERM              MEANING                              │
├────────────────────────────────────────────────────────┤
│ ETL               Extract, Transform, Load             │
│ DuckDB            Embedded analytical SQL database     │
│ Incremental Load  Fetch only new data since last run  │
│ Batch Processing  Process data in chunks/batches      │
│ View              Virtual table from SQL query         │
│ Presentation      Schema for analytics-ready data      │
│ Raw               Schema for unprocessed source data   │
│ Viewport Height   CSS unit (vh) = 1% of screen height │
│ OpenAQ            Open Air Quality data platform       │
│ S3                Amazon's object storage service      │
│ Partitioning      Organizing data by date/location    │
└────────────────────────────────────────────────────────┘
```

---

## Performance Optimizations

```
┌────────────────────────────────────────────────────────┐
│ OPTIMIZATION         IMPLEMENTATION                    │
├────────────────────────────────────────────────────────┤
│ Direct S3 Reading    DuckDB reads CSV.GZ without      │
│                      downloading to disk               │
│                                                        │
│ Incremental          Only fetch new months,           │
│ Loading              not all historical data          │
│                                                        │
│ SQL Views            Pre-calculated aggregations,     │
│                      faster dashboard queries         │
│                                                        │
│ Compressed Files     CSV.GZ reduces bandwidth         │
│                                                        │
│ Date Partitioning    Efficient filtering by           │
│                      year/month                        │
│                                                        │
│ Responsive Design    Viewport units ensure            │
│                      no scrolling lag                  │
└────────────────────────────────────────────────────────┘
```

---

*End of Architecture Guide - For questions, see README.md or SETUP_GUIDE.md*
