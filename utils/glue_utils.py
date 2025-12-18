"""
AWS Glue utility functions for crawler and ETL job management.
"""
import boto3
import time
from utils.constants import (
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, AWS_REGION,
    GLUE_DATABASE_NAME, GLUE_CRAWLER_NAME, GLUE_ETL_JOB_NAME
)


def get_glue_client():
    """Create and return a boto3 Glue client."""
    return boto3.client(
        'glue',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        aws_session_token=AWS_SESSION_TOKEN if AWS_SESSION_TOKEN else None,
        region_name=AWS_REGION
    )


def start_crawler(crawler_name: str) -> dict:
    """Start a Glue Crawler."""
    client = get_glue_client()
    try:
        response = client.start_crawler(Name=crawler_name)
        print(f"[OK] Crawler '{crawler_name}' started")
        return response
    except Exception as e:
        print(f"[FAIL] Failed to start crawler: {str(e)}")
        raise


def get_crawler_status(crawler_name: str) -> str:
    """Get the status of a Glue Crawler."""
    client = get_glue_client()
    response = client.get_crawler(Name=crawler_name)
    return response['Crawler']['State']


def wait_for_crawler(crawler_name: str, timeout: int = 1800) -> bool:
    """Wait for crawler to complete. Returns True if successful."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = get_crawler_status(crawler_name)
        if status == 'READY':
            print(f"[SUCCESS] Crawler '{crawler_name}' completed")
            return True
        elif status == 'STOPPING':
            print(f"[WARNING] Crawler '{crawler_name}' is stopping")
        time.sleep(30)
    print(f"[FAIL] Crawler '{crawler_name}' timed out after {timeout}s")
    return False


def start_glue_job(job_name: str, arguments: dict = None) -> str:
    """Start a Glue ETL Job. Returns the job run ID."""
    client = get_glue_client()
    try:
        params = {'JobName': job_name}
        if arguments:
            params['Arguments'] = arguments
        response = client.start_job_run(**params)
        run_id = response['JobRunId']
        print(f"[OK] Glue job '{job_name}' started with run ID: {run_id}")
        return run_id
    except Exception as e:
        print(f"[FAIL] Failed to start Glue job: {str(e)}")
        raise


def get_job_run_status(job_name: str, run_id: str) -> str:
    """Get the status of a Glue job run."""
    client = get_glue_client()
    response = client.get_job_run(JobName=job_name, RunId=run_id)
    return response['JobRun']['JobRunState']


def wait_for_job(job_name: str, run_id: str, timeout: int = 3600) -> bool:
    """Wait for Glue job to complete. Returns True if successful."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = get_job_run_status(job_name, run_id)
        if status == 'SUCCEEDED':
            print(f"[SUCCESS] Glue job '{job_name}' completed successfully")
            return True
        elif status in ['FAILED', 'ERROR', 'TIMEOUT']:
            print(f"[FAIL] Glue job '{job_name}' failed with status: {status}")
            return False
        time.sleep(60)
    print(f"[FAIL] Glue job '{job_name}' timed out after {timeout}s")
    return False
