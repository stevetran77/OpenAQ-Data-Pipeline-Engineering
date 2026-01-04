"""
Glue and Athena pipeline functions for Airflow DAG tasks.
Handles Glue Crawler cataloging, Glue Transform job orchestration, and Athena validation.
"""
from utils.glue_utils import (
    start_crawler, get_crawler_status, start_glue_job, get_job_run_status, get_job_run_details
)
from utils.athena_utils import get_table_count, list_tables
from utils.constants import (
    GLUE_CRAWLER_NAME, GLUE_TRANSFORM_JOB_NAME, ATHENA_DATABASE, ENV,
    RAW_FOLDER, AWS_BUCKET_NAME, OPENAQ_TARGET_COUNTRY
)
from utils.logging_utils import log_start, log_info, log_ok, log_success, log_warning, log_fail

def trigger_crawler_task(crawler_name: str = None, **context) -> str:
    """Trigger Glue Crawler - callable for Airflow task."""
    crawler = crawler_name or GLUE_CRAWLER_NAME
    log_start(f"Triggering Glue Crawler: {crawler}")

    start_crawler(crawler)

    # Store crawler name in XCom for downstream tasks
    context['ti'].xcom_push(key='crawler_name', value=crawler)

    log_ok("Crawler trigger completed")
    return crawler


def check_crawler_status(**context) -> bool:
    """Check if crawler has completed - callable for Airflow sensor."""
    crawler_name = context['ti'].xcom_pull(key='crawler_name') or GLUE_CRAWLER_NAME
    status = get_crawler_status(crawler_name)

    if status == 'READY':
        log_success(f"Crawler '{crawler_name}' is ready")
        return True
    elif status in ['STOPPING', 'RUNNING']:
        log_info(f"Crawler '{crawler_name}' status: {status}")
        return False
    else:
        log_warning(f"Crawler '{crawler_name}' unexpected status: {status}")
        return False


def validate_athena_data(**context) -> bool:
    """Validate data is queryable in Athena after Glue cataloging."""
    log_start(f"Validating Athena data availability in DB: {ATHENA_DATABASE} ({ENV} env)")

    try:
        # Get list of tables
        tables = list_tables(ATHENA_DATABASE)
        log_info(f"Found {len(tables)} tables in database '{ATHENA_DATABASE}'")

        if not tables:
            log_warning(f"No tables found in Athena database '{ATHENA_DATABASE}'")
            return False

        # Validate data in tables
        log_info(f"Validating data in {len(tables)} tables...")
        
        tables_with_data = _count_tables_with_data(tables)

        # Consider validation successful if at least one table has data
        if tables_with_data > 0:
            log_success(f"Validation Passed: {tables_with_data}/{len(tables)} tables have data.")
            return True
        else:
            log_fail(f"All tables in '{ATHENA_DATABASE}' are empty or inaccessible.")
            return False

    except Exception as e:
        log_fail(f"Athena validation failed: {e}")
        raise


def _count_tables_with_data(tables: list) -> int:
    """
    Count how many tables contain data.
    
    Args:
        tables: List of table names
        
    Returns:
        int: Number of tables with at least one row
    """
    tables_with_data = 0
    
    for table_name in tables:
        try:
            count = get_table_count(table_name, ATHENA_DATABASE)
            
            if count > 0:
                log_ok(f"Table '{table_name}' has {count} rows")
                tables_with_data += 1
            else:
                log_warning(f"Table '{table_name}' is empty")

        except Exception as e:
            log_warning(f"Failed to validate table '{table_name}': {e}")
            continue
    
    return tables_with_data


def trigger_glue_transform_job(job_name: str = None, **context) -> str:
    """
    Trigger AWS Glue PySpark transformation job.

    This function:
    1. Retrieves raw data S3 path from upstream extraction task via XCom
    2. Prepares job arguments (input/output paths)
    3. Starts Glue job with PySpark transformation script
    4. Stores job run_id in XCom for downstream monitoring

    Input: Raw JSON measurements from OpenAQ extraction
    - s3://bucket/aq_raw/year/month/day/hour/*.json

    Transformations applied by Glue job:
    - Parse datetime strings to Spark timestamps
    - Deduplicate measurements by location_id + datetime
    - Pivot parameter columns (PM2.5, PM10, NO2, SO2, O3, CO)
    - Enrich with location metadata (coordinates, city, country)
    - Extract year/month/day partition columns

    Output: Partitioned Parquet files
    - s3://bucket/aq_dev/marts/year=YYYY/month=MM/day=DD/*.parquet

    Args:
        job_name: Glue job name (uses config default if None)
        **context: Airflow context (ti, task_instance, etc.)

    Returns:
        str: Glue job run ID

    XCom Push:
        - glue_transform_job_run_id: Run ID for monitoring
        - glue_transform_job_name: Job name
    """
    job_name = job_name or GLUE_TRANSFORM_JOB_NAME

    log_start(f"Triggering Glue Transform Job: {job_name}")

    ti = context['ti']

    # Pull extraction result from upstream Lambda task
    extraction_result = _parse_lambda_extraction_result(ti)

    if not extraction_result:
        log_warning("No extraction result found. Using default paths.")
        extraction_result = {
            'status': 'WARNING',
            'location_count': 0,
            'record_count': 0,
            'raw_s3_path': f"s3://{AWS_BUCKET_NAME}/{RAW_FOLDER}/"
        }

    raw_s3_path = extraction_result.get('raw_s3_path', f"s3://{AWS_BUCKET_NAME}/{RAW_FOLDER}/")
    location_count = extraction_result.get('location_count', 0)
    record_count = extraction_result.get('record_count', 0)

    log_info("Extraction metadata:")
    log_info(f"  - Locations: {location_count}")
    log_info(f"  - Records: {record_count}")
    log_info(f"  - Raw data path: {raw_s3_path}")

    # Map country codes to full names for table naming
    country_name_map = {"VN": "vietnam", "TH": "thailand"}
    country_folder = country_name_map.get(OPENAQ_TARGET_COUNTRY, OPENAQ_TARGET_COUNTRY.lower())
    
    # Prepare Glue job arguments
    job_arguments = _build_glue_job_arguments(country_folder, raw_s3_path)

    log_info("Glue Job Arguments:")
    for key, value in job_arguments.items():
        log_info(f"  {key}: {value}")

    try:
        # Start Glue job
        run_id = start_glue_job(job_name=job_name, arguments=job_arguments)

        # Push to XCom for downstream tasks
        ti.xcom_push(key='glue_transform_job_run_id', value=run_id)
        ti.xcom_push(key='glue_transform_job_name', value=job_name)

        log_ok("Glue transform job triggered successfully")
        log_info(f"Job run ID: {run_id}")

        return run_id

    except Exception as e:
        log_fail(f"Failed to trigger Glue transform job: {str(e)}")
        raise


def _parse_lambda_extraction_result(ti) -> dict:
    """
    Parse Lambda extraction result from XCom.
    
    Handles multiple response formats:
    - String JSON
    - Lambda response wrapper with Payload
    - HTTP response with statusCode and body
    
    Args:
        ti: Airflow task instance
        
    Returns:
        dict: Parsed extraction result or None
    """
    import json
    import traceback
    
    try:
        # Lambda task stores response in 'return_value' key
        extraction_result = ti.xcom_pull(
            task_ids='lambda_extract_vietnam',
            key='return_value'
        )

        log_info(f"Raw XCom data type: {type(extraction_result)}")
        log_info(f"Raw XCom preview: {str(extraction_result)[:500]}")

        # Parse the Lambda response - handle multiple possible formats
        if extraction_result:
            # Case 1: String JSON - parse it
            if isinstance(extraction_result, str):
                extraction_result = json.loads(extraction_result)

            # Case 2: Dict - check for wrapper formats
            if isinstance(extraction_result, dict):
                # Lambda response wrapper with Payload
                if 'Payload' in extraction_result:
                    payload_str = extraction_result['Payload'].read().decode('utf-8')
                    extraction_result = json.loads(payload_str)

                # Lambda HTTP response with statusCode and body
                if 'statusCode' in extraction_result:
                    body = extraction_result.get('body')
                    if isinstance(body, str):
                        extraction_result = json.loads(body)
                    elif isinstance(body, dict):
                        extraction_result = body

        log_info(f"Parsed result type: {type(extraction_result)}")
        if isinstance(extraction_result, dict):
            log_info(f"Parsed result keys: {list(extraction_result.keys())}")
        
        return extraction_result

    except Exception as e:
        log_warning(f"Failed to pull extraction result: {e}")
        log_info(f"Traceback: {traceback.format_exc()}")
        return None


def _build_glue_job_arguments(country_folder: str, raw_s3_path: str = None) -> dict:
    """
    Build Glue job arguments for transformation.
    
    Args:
        country_folder: Country folder name for output path
        raw_s3_path: Optional specific raw data path
        
    Returns:
        dict: Glue job arguments
    """
    input_path = raw_s3_path or f"s3://{AWS_BUCKET_NAME}/{RAW_FOLDER}/"
    output_path = f"s3://{AWS_BUCKET_NAME}/aq_dev/marts/{country_folder}/"

    return {
        '--input_path': input_path,
        '--output_path': output_path,
        '--env': ENV,
        '--partition_cols': 'year,month,day',
        '--TempDir': f"s3://{AWS_BUCKET_NAME}/glue-temp/",
    }


def check_glue_transform_status(**context) -> bool:
    """Check if Glue transform job has completed - callable for Airflow sensor."""
    run_id = context['ti'].xcom_pull(key='glue_transform_job_run_id')
    job_name = context['ti'].xcom_pull(key='glue_transform_job_name') or GLUE_TRANSFORM_JOB_NAME

    if not run_id:
        log_warning("No job run ID found in XCom. Waiting...")
        return False

    status = get_job_run_status(job_name, run_id)

    log_info(f"Glue transform job status: {status}")
    log_info(f"  Job: {job_name}")
    log_info(f"  Run ID: {run_id}")

    if status == 'SUCCEEDED':
        log_success(f"Glue transform job '{job_name}' completed successfully")
        return True
    elif status in ['RUNNING', 'STARTING']:
        log_info(f"Glue transform job '{job_name}' status: {status}")
        return False
    else:
        # FAILED, ERROR, TIMEOUT
        details = get_job_run_details(job_name, run_id)
        error_msg = details.get('error_message', 'Unknown error')
        log_fail(f"Glue transform job '{job_name}' failed: {error_msg}")
        raise Exception(f"Glue job {job_name} failed with status: {status}")