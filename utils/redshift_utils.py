"""
AWS Redshift utility functions for connection and data operations.
"""
import redshift_connector
from utils.constants import (
    REDSHIFT_HOST, REDSHIFT_PORT, REDSHIFT_DATABASE,
    REDSHIFT_USERNAME, REDSHIFT_PASSWORD, REDSHIFT_SCHEMA
)


def get_redshift_connection():
    """Create and return a Redshift connection."""
    try:
        conn = redshift_connector.connect(
            host=REDSHIFT_HOST,
            port=REDSHIFT_PORT,
            database=REDSHIFT_DATABASE,
            user=REDSHIFT_USERNAME,
            password=REDSHIFT_PASSWORD
        )
        print("[OK] Connected to Redshift")
        return conn
    except Exception as e:
        print(f"[FAIL] Redshift connection failed: {str(e)}")
        raise


def execute_query(query: str, fetch: bool = False):
    """Execute a SQL query on Redshift."""
    conn = get_redshift_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        if fetch:
            result = cursor.fetchall()
            return result
        conn.commit()
        print("[OK] Query executed successfully")
    except Exception as e:
        print(f"[FAIL] Query execution failed: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()


def create_schema_if_not_exists() -> bool:
    """Create the openaq schema if it doesn't exist."""
    query = f"CREATE SCHEMA IF NOT EXISTS {REDSHIFT_SCHEMA};"
    execute_query(query)
    print(f"[OK] Schema '{REDSHIFT_SCHEMA}' ready")
    return True


def get_table_row_count(table: str) -> int:
    """Get the row count of a table."""
    query = f"SELECT COUNT(*) FROM {REDSHIFT_SCHEMA}.{table};"
    result = execute_query(query, fetch=True)
    return result[0][0] if result else 0


def validate_data_load(table: str, min_expected_count: int = 1) -> bool:
    """Validate that data was loaded into the table."""
    count = get_table_row_count(table)
    if count >= min_expected_count:
        print(f"[SUCCESS] Table '{table}' has {count} rows")
        return True
    else:
        print(f"[FAIL] Table '{table}' has only {count} rows (expected >= {min_expected_count})")
        return False
