"""
Glue-related pipeline functions for Airflow DAG tasks.
"""
from utils.glue_utils import (
    start_crawler, get_crawler_status, wait_for_crawler,
    start_glue_job, get_job_run_status, wait_for_job
)
from utils.redshift_utils import validate_data_load
from utils.constants import GLUE_CRAWLER_NAME, GLUE_ETL_JOB_NAME, GLUE_DATABASE_NAME, REDSHIFT_SCHEMA


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


def trigger_glue_job_task(job_name: str = None, arguments: dict = None, **context) -> str:
    """Trigger Glue ETL Job - callable for Airflow task."""
    job = job_name or GLUE_ETL_JOB_NAME

    default_args = {
        '--source_database': GLUE_DATABASE_NAME,
        '--target_schema': REDSHIFT_SCHEMA,
        '--job-language': 'python'
    }

    if arguments:
        default_args.update(arguments)

    print(f"[START] Triggering Glue ETL Job: {job}")
    run_id = start_glue_job(job, default_args)

    # Store run info in XCom for downstream tasks
    context['ti'].xcom_push(key='glue_job_name', value=job)
    context['ti'].xcom_push(key='glue_run_id', value=run_id)

    print(f"[OK] Glue job triggered with run ID: {run_id}")
    return run_id


def check_glue_job_status(**context) -> bool:
    """Check if Glue job has completed - callable for Airflow sensor."""
    job_name = context['ti'].xcom_pull(key='glue_job_name') or GLUE_ETL_JOB_NAME
    run_id = context['ti'].xcom_pull(key='glue_run_id')

    if not run_id:
        print("[FAIL] No run_id found in XCom")
        return False

    status = get_job_run_status(job_name, run_id)

    if status == 'SUCCEEDED':
        print(f"[SUCCESS] Glue job '{job_name}' completed")
        return True
    elif status in ['FAILED', 'ERROR', 'TIMEOUT', 'STOPPED']:
        print(f"[FAIL] Glue job '{job_name}' failed with status: {status}")
        raise Exception(f"Glue job failed: {status}")
    else:
        print(f"[INFO] Glue job '{job_name}' status: {status}")
        return False


def validate_redshift_load(**context) -> bool:
    """Validate data was loaded to Redshift - callable for Airflow task."""
    print("[START] Validating Redshift data load")

    # Validate fact_measurements table
    is_valid = validate_data_load('fact_measurements', min_expected_count=1)

    if is_valid:
        print("[SUCCESS] Redshift data validation passed")
    else:
        print("[FAIL] Redshift data validation failed")
        raise Exception("Data validation failed")

    return is_valid
