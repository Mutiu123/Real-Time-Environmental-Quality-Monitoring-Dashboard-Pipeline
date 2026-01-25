"""
Example usage:
    Full extraction: python extraction.py --locations_file_path ../locations.json --start_date 2024-01 --end_date 2024-03 --database_path ../air_quality.db --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql --source_base_path s3://openaq-data-archive/records/csv.gz

    Incremental extraction: python extraction.py --locations_file_path ../locations.json --database_path ../air_quality.db --extract_query_template_path ../sql/dml/raw/0_raw_air_quality_insert.sql --source_base_path s3://openaq-data-archive/records/csv.gz --incremental
"""
import argparse
import json
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import List, Optional, Tuple

from duckdb import IOException
from jinja2 import Template

from database_manager import (
    connect_to_database,
    close_database_connection,
    execute_query,
    read_query
)


def read_location_ids(file_path: str) -> List[str]:
    with open(file_path, "r") as f:
        locations = json.load(f)
        f.close()

    location_ids = [str(id) for id in locations.keys()]
    return location_ids


def get_last_extraction_date(con) -> Optional[str]:
    """Get the end date of the last successful extraction."""
    try:
        result = con.execute("""
            SELECT end_date
            FROM raw.last_successful_extraction
        """).fetchone()

        if result and result[0]:
            return result[0]
        return None
    except Exception as e:
        logging.warning(f"Could not retrieve last extraction date: {e}")
        return None


def determine_date_range(con, incremental: bool) -> Tuple[str, str]:
    """Determine the date range for extraction.

    If incremental mode:
        - Start from the month after last successful extraction
        - End at current month
    Otherwise:
        - Requires manual start_date and end_date
    """
    if incremental:
        last_end_date = get_last_extraction_date(con)

        if last_end_date:
            # Start from the month after the last extraction
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

    raise ValueError("Date range must be determined before calling this function in non-incremental mode")


def log_extraction_start(con, start_date: str, end_date: str) -> int:
    """Log the start of an extraction job and return the extraction_id."""
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


def log_extraction_complete(con, extraction_id: int, records_extracted: int):
    """Mark extraction as completed."""
    con.execute("""
        UPDATE raw.extraction_log
        SET extraction_end_datetime = ?,
            status = 'completed',
            records_extracted = ?
        WHERE extraction_id = ?
    """, [datetime.now(), records_extracted, extraction_id])
    logging.info(f"Completed extraction job {extraction_id} with {records_extracted} records")


def log_extraction_failed(con, extraction_id: int, error_message: str):
    """Mark extraction as failed."""
    con.execute("""
        UPDATE raw.extraction_log
        SET extraction_end_datetime = ?,
            status = 'failed',
            error_message = ?
        WHERE extraction_id = ?
    """, [datetime.now(), error_message, extraction_id])
    logging.error(f"Failed extraction job {extraction_id}: {error_message}")


def compile_data_file_paths(
    data_file_path_template: str, location_ids: List[str], start_date: str, end_date: str
) -> List[str]:
    
    start_date = datetime.strptime(start_date, "%Y-%m")
    end_date = datetime.strptime(end_date, "%Y-%m")

    data_file_paths = []
    for location_id in location_ids:
        index_date = start_date
        while index_date <= end_date:
            data_file_path = Template(data_file_path_template).render(
                location_id=location_id,
                year=str(index_date.year),
                month=str(index_date.month).zfill(2)
            )
            data_file_paths.append(data_file_path)
            index_date += relativedelta(months=1)
    return data_file_paths

def compile_data_file_query(
    base_path: str, data_file_path: str, extract_query_template: str
) -> str:
    extract_query = Template(extract_query_template).render(
        data_file_path=f"{base_path}/{data_file_path}"
    )
    return extract_query


def delete_existing_data(con, start_date: str, end_date: str):
    """Delete existing data for the specified date range before extracting new data."""

    start_dt = datetime.strptime(start_date, "%Y-%m")
    end_dt = datetime.strptime(end_date, "%Y-%m")

    # Delete data for the entire date range
    index_date = start_dt
    while index_date <= end_dt:
        delete_query = f"""
        DELETE FROM raw.air_quality
        WHERE year = {index_date.year} AND month = '{str(index_date.month).zfill(2)}';
        """
        logging.info(f"Deleting existing data for {index_date.year}-{str(index_date.month).zfill(2)}")
        execute_query(con, delete_query)
        index_date += relativedelta(months=1)

    logging.info(f"Deleted all existing data from {start_date} to {end_date}")


def extract_data(args):

    location_ids = read_location_ids(args.locations_file_path)
    con = connect_to_database(path=args.database_path)

    try:
        # Determine date range
        if args.incremental:
            start_date, end_date = determine_date_range(con, incremental=True)
        else:
            if not args.start_date or not args.end_date:
                raise ValueError("start_date and end_date are required when not in incremental mode")
            start_date = args.start_date
            end_date = args.end_date

        # Check if there's new data to extract
        if args.incremental:
            last_end_date = get_last_extraction_date(con)
            if last_end_date:
                last_end_dt = datetime.strptime(last_end_date, "%Y-%m")
                current_month = datetime.now().replace(day=1)
                if last_end_dt >= current_month:
                    logging.info("No new data to extract. Already up to date.")
                    close_database_connection(con)
                    return

        # Log extraction start
        extraction_id = log_extraction_start(con, start_date, end_date)

        # Compile file paths
        data_file_path_template = "locationid={{location_id}}/year={{year}}/month={{month}}/*"
        data_file_paths = compile_data_file_paths(
            data_file_path_template=data_file_path_template,
            location_ids=location_ids,
            start_date=start_date,
            end_date=end_date
        )

        extract_query_template = read_query(path=args.extract_query_template_path)

        # Delete existing data before extracting new data (only in non-incremental mode)
        if not args.incremental:
            logging.info("Deleting existing data for the specified date range...")
            delete_existing_data(con, start_date, end_date)

        # Extract data
        successful_extractions = 0
        for data_file_path in data_file_paths:
            logging.info(f"Extracting data from {data_file_path}")
            query = compile_data_file_query(
                base_path=args.source_base_path,
                data_file_path=data_file_path,
                extract_query_template=extract_query_template
            )

            try:
                execute_query(con, query)
                successful_extractions += 1
                logging.info(f"Extracted data from {data_file_path}!")
            except IOException as e:
                logging.warning(f"Could not find data from {data_file_path}: {e}")

        # Get total records extracted
        records_extracted = con.execute("""
            SELECT COUNT(*) FROM raw.air_quality
            WHERE year || '-' || month >= ? AND year || '-' || month <= ?
        """, [start_date, end_date]).fetchone()[0]

        # Log extraction completion
        log_extraction_complete(con, extraction_id, records_extracted)

    except Exception as e:
        if 'extraction_id' in locals():
            log_extraction_failed(con, extraction_id, str(e))
        logging.error(f"Extraction failed: {e}")
        raise
    finally:
        close_database_connection(con)


def main():
    logging.getLogger().setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description="CLI for ELT Extraction with Incremental Loading Support")
    parser.add_argument(
        "--locations_file_path",
        type=str,
        required=True,
        help="Path to the locations JSON file",
    )
    parser.add_argument(
        "--start_date",
        type=str,
        required=False,
        help="Start date in YYYY-MM format (optional if --incremental is used)"
    )
    parser.add_argument(
        "--end_date",
        type=str,
        required=False,
        help="End date in YYYY-MM format (optional if --incremental is used)"
    )
    parser.add_argument(
        "--extract_query_template_path",
        type=str,
        required=True,
        help="Path to the SQL extraction query template",
    )
    parser.add_argument(
        "--database_path", type=str, required=True, help="Path to the database"
    )
    parser.add_argument(
        "--source_base_path",
        type=str,
        required=True,
        help="Base path for the remote data files",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Enable incremental loading mode (automatically determines date range from last extraction)"
    )

    args = parser.parse_args()
    extract_data(args)


if __name__ == "__main__":
    main()