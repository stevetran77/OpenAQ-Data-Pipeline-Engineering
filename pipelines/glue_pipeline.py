"""
Glue and Athena pipeline functions for Airflow DAG tasks.
"""
from utils.glue_utils import (
    start_crawler, get_crawler_status
)
from utils.athena_utils import get_table_count, list_tables
from utils.constants import GLUE_CRAWLER_NAME, ATHENA_DATABASE


def trigger_crawler_task(crawler_name: str = None, **context) -> str:
    """Trigger Glue Crawler - callable for Airflow task."""
    crawler = crawler_name or GLUE_CRAWLER_NAME
    print(f"[START] Triggering Glue Crawler: {crawler}")

    start_crawler(crawler)

    # Store crawler name in XCom for downstream tasks
    context['ti'].xcom_push(key='crawler_name', value=crawler)

    print(f"[OK] Crawler trigger completed")
    return crawler


def check_crawler_status(**context) -> bool:
    """Check if crawler has completed - callable for Airflow sensor."""
    crawler_name = context['ti'].xcom_pull(key='crawler_name') or GLUE_CRAWLER_NAME
    status = get_crawler_status(crawler_name)

    if status == 'READY':
        print(f"[SUCCESS] Crawler '{crawler_name}' is ready")
        return True
    elif status in ['STOPPING', 'RUNNING']:
        print(f"[INFO] Crawler '{crawler_name}' status: {status}")
        return False
    else:
        print(f"[WARNING] Crawler '{crawler_name}' unexpected status: {status}")
        return False


def validate_athena_data(**context) -> bool:
    """Validate data is queryable in Athena after Glue cataloging."""
    print("[START] Validating Athena data availability")

    try:
        # List available tables in Athena database
        tables = list_tables(ATHENA_DATABASE)
        print(f"[INFO] Found {len(tables)} tables in Athena database '{ATHENA_DATABASE}'")

        if not tables:
            print("[WARNING] No tables found in Athena database")
            return False

        # Look for air quality tables (created by Glue Crawler with 'aq_' prefix)
        aq_tables = [t for t in tables if t.startswith('aq_')]
        print(f"[INFO] Found {len(aq_tables)} air quality tables: {aq_tables}")

        if not aq_tables:
            print("[WARNING] No air quality tables found in Athena")
            return False

        # Validate each table has data
        for table_name in aq_tables:
            try:
                count = get_table_count(table_name, ATHENA_DATABASE)
                print(f"[OK] Table '{table_name}' has {count} rows")

                if count == 0:
                    print(f"[WARNING] Table '{table_name}' is empty")
                    return False

            except Exception as e:
                print(f"[WARNING] Failed to validate table '{table_name}': {e}")
                continue

        print("[SUCCESS] Athena data validation passed")
        return True

    except Exception as e:
        print(f"[FAIL] Athena validation failed: {e}")
        raise
