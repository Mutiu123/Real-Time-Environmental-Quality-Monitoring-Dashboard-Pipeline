# Detailed Setup Guide

This guide provides step-by-step instructions for setting up the Real-Time Environmental Air Quality Monitoring Dashboard from scratch.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Environment Setup](#environment-setup)
3. [Database Initialization](#database-initialization)
4. [Initial Data Load](#initial-data-load)
5. [Running the Dashboard](#running-the-dashboard)
6. [Verification](#verification)
7. [Common Issues](#common-issues)

## System Requirements

### Minimum Requirements
- **OS**: Windows 10/11, macOS 10.15+, or Linux (Ubuntu 18.04+)
- **Python**: 3.8 or higher
- **RAM**: 4GB minimum, 8GB recommended
- **Disk Space**: 2GB+ for data storage
- **Internet**: Broadband connection for data download

### Software Dependencies
- Git (for cloning the repository)
- Python 3.8+
- pip (Python package installer)

## Environment Setup

### Step 1: Install Python

#### Windows

1. Download Python from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. **IMPORTANT**: Check "Add Python to PATH"
4. Click "Install Now"
5. Verify installation:
   ```cmd
   python --version
   ```

#### macOS

```bash
# Using Homebrew
brew install python@3.11

# Verify installation
python3 --version
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Verify installation
python3 --version
```

### Step 2: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/yourusername/Real-Time-Environmental-Air-Quality-Monitoring-Dashboard-Pipeline.git

# Navigate to project directory
cd Real-Time-Environmental-Air-Quality-Monitoring-Dashboard-Pipeline
```

### Step 3: Create Virtual Environment

#### Windows

```cmd
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# You should see (.venv) in your command prompt
```

#### macOS/Linux

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# You should see (.venv) in your terminal prompt
```

### Step 4: Install Dependencies

With the virtual environment activated:

```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt

# Verify installation
pip list
```

Expected packages:
- dash
- plotly
- pandas
- duckdb
- jinja2
- python-dateutil

## Database Initialization

### Step 1: Navigate to Pipeline Directory

```bash
cd pipeline
```

### Step 2: Initialize Database

```bash
python setup_database.py --database_path ../air_quality.db
```

**Expected Output:**
```
INFO:root:Setting up database at ../air_quality.db
INFO:root:Connecting to database at ../air_quality.db
INFO:root:Executing 0_schemas.sql...
INFO:root:Successfully executed 0_schemas.sql
INFO:root:Executing 1_raw_air_quality.sql...
INFO:root:Successfully executed 1_raw_air_quality.sql
INFO:root:Executing 2_metadata_extraction_log.sql...
INFO:root:Successfully executed 2_metadata_extraction_log.sql
INFO:root:Database setup completed successfully!
INFO:root:Closing database connection
```

This creates:
- `raw` schema with `air_quality` table
- `raw.extraction_log` metadata table
- `presentation` schema
- Necessary database views

## Initial Data Load

### Step 1: Extract Data

Start with a manageable date range (3 months):

```bash
python extraction.py \
  --locations_file_path ../locations.json \
  --start_date 2024-01 \
  --end_date 2024-03 \
  --database_path ../air_quality.db \
  --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql \
  --source_base_path s3://openaq-data-archive/records/csv.gz
```

**What Happens:**
1. Connects to OpenAQ S3 bucket
2. Downloads CSV files for each location and month
3. Inserts data into `raw.air_quality` table
4. Logs extraction metadata

**Expected Duration**: 5-15 minutes depending on internet speed

**Expected Output:**
```
INFO:root:Connecting to database at ../air_quality.db
INFO:root:Deleting existing data for the specified date range...
INFO:root:Deleting existing data for 2024-01
INFO:root:Deleting existing data for 2024-02
INFO:root:Deleting existing data for 2024-03
INFO:root:Deleted all existing data from 2024-01 to 2024-03
INFO:root:Started extraction job 1
INFO:root:Extracting data from locationid=225393/year=2024/month=01/*
INFO:root:Extracted data from locationid=225393/year=2024/month=01/*!
...
INFO:root:Completed extraction job 1 with 45678 records
```

**Note**: Some locations may show warnings like:
```
WARNING:root:Could not find data from locationid=352828/year=2024/month=01/*
```
This is normal - not all sensors have data for all months.

### Step 2: Transform Data

```bash
python transformation.py \
  --database_path ../air_quality.db \
  --query_directory ../sql/dml/presentation
```

**What Happens:**
1. Creates `presentation.air_quality` view
2. Creates `presentation.latest_param_values_per_location` view
3. Creates `presentation.daily_air_quality_stats` view

**Expected Output:**
```
INFO:root:Connecting to database at ../air_quality.db
INFO:root:Found 3 sql scripts at location ../sql/dml/presentation
INFO:root:Executing query from 0_presentation_air_quality_view.sql
INFO:root:Executing query from 1_presentation_latest_param_values_per_location_view.sql
INFO:root:Executing query from 2_presentation_daily_air_quality_stats_view.sql
INFO:root:Closing database connection
```

## Running the Dashboard

### Step 1: Navigate to Dashboard Directory

```bash
cd ../dashboard
```

### Step 2: Start the Dashboard

```bash
python app.py
```

**Expected Output:**
```
Dash is running on http://127.0.0.1:8050/

 * Serving Flask app 'app'
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment.
 * Running on http://127.0.0.1:8050
Press CTRL+C to quit
```

### Step 3: Access Dashboard

1. Open your web browser
2. Navigate to: `http://127.0.0.1:8050`
3. You should see the dashboard with two tabs:
   - **Sensor Locations**: Interactive map
   - **Parameter Plots**: Time series and comparison charts

## Verification

### Verify Database

```bash
# From the pipeline directory
python -c "import duckdb; con = duckdb.connect('../air_quality.db'); print('Tables:', con.execute('SHOW TABLES').fetchall()); con.close()"
```

**Expected Output:**
```
Tables: [('raw', 'air_quality'), ('raw', 'extraction_log'), ...]
```

### Verify Data

```bash
python -c "import duckdb; con = duckdb.connect('../air_quality.db'); print('Record count:', con.execute('SELECT COUNT(*) FROM raw.air_quality').fetchone()[0]); con.close()"
```

You should see a non-zero record count.

### Verify Dashboard

1. **Sensor Locations Tab**:
   - Map should display
   - Red markers should be visible
   - Hovering should show location names and values

2. **Parameter Plots Tab**:
   - Dropdown menus should populate
   - Date range should show your data range
   - Line chart should display
   - Bar chart should display

## Common Issues

### Issue: "python: command not found"

**Solution**:
- Windows: Use `py` instead of `python`
- Mac/Linux: Use `python3` instead of `python`

### Issue: "No module named 'dash'"

**Solution**:
```bash
# Make sure virtual environment is activated
# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: "Schema with name presentation does not exist"

**Solution**:
```bash
cd pipeline
python setup_database.py --database_path ../air_quality.db
```

### Issue: "Port 8050 is already in use"

**Solution**:
- Check if dashboard is already running
- Kill the process using port 8050
- Or edit `dashboard/app.py` to use a different port:
  ```python
  app.run_server(debug=True, port=8051)
  ```

### Issue: Dashboard loads but shows no data

**Solution**:
1. Check database exists: `ls -la air_quality.db` (Mac/Linux) or `dir air_quality.db` (Windows)
2. Verify data was extracted (check record count above)
3. Run transformation script again
4. Restart dashboard

### Issue: Extraction is very slow

**Solution**:
- Start with a smaller date range (1-2 months)
- Check your internet connection
- Some locations may have large datasets

## Next Steps

After successful setup:

1. **Explore the Dashboard**: Navigate through different parameters and locations
2. **Set up Incremental Loading**: See [INCREMENTAL_LOADING.md](INCREMENTAL_LOADING.md)
3. **Configure Automation**: Set up scheduled data updates
4. **Add More Locations**: Edit `locations.json` to monitor additional sensors
5. **Extend Date Range**: Extract more historical data

## Getting Help

If you encounter issues not covered here:

1. Check the [Troubleshooting](README.md#troubleshooting) section in README
2. Review error messages carefully
3. Search existing GitHub issues
4. Open a new issue with:
   - Error message
   - Steps to reproduce
   - Your environment (OS, Python version)

## Summary Checklist

- [ ] Python 3.8+ installed
- [ ] Repository cloned
- [ ] Virtual environment created and activated
- [ ] Dependencies installed
- [ ] Database initialized
- [ ] Data extracted for at least one month
- [ ] Data transformed
- [ ] Dashboard running and accessible
- [ ] Both tabs (Map and Plots) working

Congratulations! Your air quality monitoring dashboard is now up and running.
