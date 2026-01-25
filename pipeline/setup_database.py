"""
Database setup script - Initializes all schemas and tables

Example usage:
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


def setup_database(database_path: str):
    """Initialize database with all required schemas and tables."""

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


def main():
    logging.getLogger().setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description="Initialize Air Quality Database")
    parser.add_argument(
        "--database_path",
        type=str,
        required=True,
        help="Path to the database file"
    )

    args = parser.parse_args()
    setup_database(args.database_path)


if __name__ == "__main__":
    main()
