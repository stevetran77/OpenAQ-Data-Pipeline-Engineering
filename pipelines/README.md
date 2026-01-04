# Pipelines Directory

This directory contains orchestration modules that coordinate data extraction, transformation, and loading operations for the OpenAQ Data Pipeline.

---

## Table of Contents

1. [Overview](#overview)
2. [Pipeline Modules](#pipeline-modules)
3. [Architecture](#architecture)
4. [Common Patterns](#common-patterns)
5. [Usage Examples](#usage-examples)
6. [Error Handling](#error-handling)
7. [Testing](#testing)
8. [Best Practices](#best-practices)

---

## Overview

### Purpose

Pipelines provide **middle-layer orchestration** between Airflow DAGs (high-level workflow) and ETL functions (low-level operations):

```
Airflow DAG (What to do)
    ↓
Pipeline Module (How to do it)
    ↓
ETL Functions (Do it)
    ↓
AWS/External Systems (Data destination)
```

### Design Philosophy

**Separation of Concerns**:
- **DAGs** (`dags/`) - Define workflow: which tasks, order, dependencies
- **Pipelines** (`pipelines/`) - Implement logic: orchestrate ETL operations
- **ETLs** (`etls/`) - Extract/transform data: API calls, data manipulation
- **Utils** (`utils/`) - Reusable utilities: AWS clients, logging, constants

**Benefits**:
- ✅ Testable independently (unit test pipelines without Airflow)
- ✅ Reusable (same pipeline in Airflow, Lambda, or standalone scripts)
- ✅ Maintainable (changes in one place affect all consumers)
- ✅ Monitorable (detailed logging at each step)

---

## Pipeline Modules

### 1. `openaq_pipeline.py`

**Purpose**: Orchestrate OpenAQ data extraction and upload

**Main Function**: `openaq_pipeline()`

```python
def openaq_pipeline(
    vietnam_wide: bool = True,
    lookback_days: int = 1,
    required_parameters: list = None,
    output_format: str = 'json',
    s3_folder_override: str = None,
) -> dict:
    """
    Extract OpenAQ data and upload to S3.
    
    Args:
        vietnam_wide (bool): Fetch entire Vietnam (default) or specific location
        lookback_days (int): How many days back to extract (default: 1)
        required_parameters (list): Filter to specific parameters
        output_format (str): 'json' or 'parquet'
        s3_folder_override (str): Override S3 path (for testing)
    
    Returns:
        dict: {
            'status': 'SUCCESS'|'FAIL',
            'record_count': int,
            'location_count': int,
            's3_path': str,
            'duration_seconds': float,
            'error': str  # Only if status='FAIL'
        }
    
    Flow:
        1. Load configuration
        2. Connect to OpenAQ API
        3. Fetch Vietnam locations and sensors
        4. Filter active sensors (updated last N days)
        5. Extract measurements per sensor
        6. Transform measurements (normalize, flatten)
        7. Enrich with metadata (coordinates, city)
        8. Upload to S3 (aq_raw/ zone)
        9. Return summary
    """
```

**Usage in Airflow**:

```python
from pipelines.openaq_pipeline import openaq_pipeline
from airflow.operators.python import PythonOperator

def extract_task_callable():
    result = openaq_pipeline(
        vietnam_wide=True,
        lookback_days=1,
        required_parameters=['PM2.5', 'PM10', 'NO2']
    )
    
    if result['status'] != 'SUCCESS':
        raise Exception(f"Extraction failed: {result['error']}")
    
    return result

extract_task = PythonOperator(
    task_id='extract_openaq_raw',
    python_callable=extract_task_callable,
    dag=dag,
)
```

**Configuration Integration**:

```python
# Constants used from utils/constants.py
from utils.constants import (
    OPENAQ_API_KEY,
    DEFAULT_LOOKBACK_DAYS,
    API_REQUEST_TIMEOUT,
    ENV_FOLDER_MAP,
    RAW_FOLDER_MAP,
)

# Logging utilities
from utils.logging_utils import log_info, log_ok, log_fail

# AWS utilities
from utils.aws_utils import upload_to_s3, get_s3_client
```

**Example Output**:

```python
{
    'status': 'SUCCESS',
    'record_count': 312,
    'location_count': 53,
    'active_sensor_count': 39,
    's3_path': 's3://openaq-data-pipeline/aq_raw/2025/12/28/raw_vietnam_national_20251228.json',
    'duration_seconds': 45.23
}
```

**Key Features**:
- ✅ Automatic environment awareness (reads PIPELINE_ENV for S3 path selection)
- ✅ Comprehensive error handling with rollback
- ✅ Detailed CloudWatch-compatible logging
- ✅ XCom-friendly return format
- ✅ Configurable lookback period (prevents duplicate extraction)

### 2. `glue_pipeline.py`

**Purpose**: Orchestrate AWS Glue job execution and validation

**Main Functions**:

```python
def run_glue_transformation(
    env: str = 'dev',
    input_path: str = None,
    output_path: str = None,
    wait_for_completion: bool = False,
    timeout_seconds: int = 7200,
) -> dict:
    """
    Trigger Glue job for transformation.
    
    Args:
        env (str): 'dev' or 'prod'
        input_path (str): Override input S3 path (testing only)
        output_path (str): Override output S3 path (testing only)
        wait_for_completion (bool): Block until job completes
        timeout_seconds (int): Max wait time
    
    Returns:
        dict: {
            'status': 'SUBMITTED'|'SUCCEEDED'|'FAILED',
            'job_run_id': str,
            'job_name': str,
            'duration_seconds': float,
            'output_records': int,  # Only if succeeded
            'error': str  # Only if failed
        }
    """
```

**Polling Function**:

```python
def check_glue_job_status(job_run_id: str, job_name: str = None) -> bool:
    """
    Poll Glue job status (used by Airflow sensors).
    
    Returns:
        True: Job succeeded
        False: Job still running or failed
    
    Raises:
        Exception: Job failed with error
    """
```

**Usage in Airflow**:

```python
from pipelines.glue_pipeline import run_glue_transformation, check_glue_job_status
from airflow.operators.python import PythonOperator
from airflow.sensors.python import PythonSensor

# Trigger Glue job
def trigger_glue():
    result = run_glue_transformation(env='prod', wait_for_completion=False)
    if result['status'] != 'SUBMITTED':
        raise Exception(f"Failed to submit job: {result['error']}")
    return result['job_run_id']

trigger_task = PythonOperator(
    task_id='trigger_glue_job',
    python_callable=trigger_glue,
    dag=dag,
)

# Wait for job completion
wait_task = PythonSensor(
    task_id='wait_for_glue_job',
    python_callable=check_glue_job_status,
    poke_interval=60,
    timeout=7200,
    mode='poke',
    dag=dag,
)

trigger_task >> wait_task
```

**Key Features**:
- ✅ Environment-aware (dev/prod resource naming)
- ✅ XCom-compatible job_run_id passing
- ✅ Sensor-compatible status checking
- ✅ Detailed job metrics (input/output record counts)
- ✅ CloudWatch log integration

---

## Architecture

### Folder Structure

```
pipelines/
├── README.md                    # This file
├── __init__.py                  # Package initialization
├── openaq_pipeline.py           # Extraction orchestration
├── glue_pipeline.py             # Transformation orchestration
└── __pycache__/
```

### Data Flow Through Pipelines

```
┌─────────────────────────────────────────────────────────────┐
│              Airflow DAG Execution                          │
│          (openaq_to_athena_pipeline)                        │
└────┬─────────────────────────────────────────────────────┬──┘
     │                                                      │
     ▼                                                      ▼
┌────────────────────────────────┐         ┌───────────────────────────┐
│ extract_openaq_raw Task        │         │ Airflow Task 2+ (parallel)│
│                                │         │                           │
│ PythonOperator calls:          │         └───────────────────────────┘
│ openaq_pipeline()              │
│                                │
│ Flow:                          │
│ 1. Load config                 │
│ 2. Connect OpenAQ API          │
│ 3. Fetch locations/sensors     │
│ 4. Filter active sensors       │
│ 5. Extract measurements        │
│ 6. Transform data              │
│ 7. Enrich with metadata        │
│ 8. Upload to S3 (aq_raw/)      │
│ 9. Return metadata             │
│                                │
│ Output (XCom):                 │
│ {                              │
│   'status': 'SUCCESS',         │
│   'record_count': 312,         │
│   's3_path': 's3://...'        │
│ }                              │
└────┬─────────────────────────────┘
     │
     ▼ (Pass XCom to next task)
┌──────────────────────────────────────────┐
│ trigger_glue_job_transform Task          │
│                                          │
│ PythonOperator calls:                    │
│ run_glue_transformation()                │
│                                          │
│ Flow:                                    │
│ 1. Build job parameters                  │
│ 2. Submit Glue job                       │
│ 3. Return job_run_id                     │
│                                          │
│ Output (XCom):                           │
│ {                                        │
│   'status': 'SUBMITTED',                 │
│   'job_run_id': 'jr-12345',              │
│   'job_name': 'process_openaq_raw_prod'  │
│ }                                        │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ wait_for_glue_job Task                   │
│                                          │
│ PythonSensor calls:                      │
│ check_glue_job_status()                  │
│ (polls every 60 seconds until SUCCEEDED) │
│                                          │
│ Flow:                                    │
│ 1. Get job run status                    │
│ 2. If RUNNING: return False (continue)   │
│ 3. If SUCCEEDED: return True (success)   │
│ 4. If FAILED: raise Exception            │
└──────────────────────────────────────────┘
```

### Module Dependencies

```
openaq_pipeline.py
├── etls.openaq_etl
│   ├── connect_openaq()
│   ├── fetch_all_vietnam_locations()
│   ├── extract_measurements()
│   └── enrich_measurements_with_metadata()
├── utils.constants
│   ├── OPENAQ_API_KEY
│   ├── DEFAULT_LOOKBACK_DAYS
│   ├── API_REQUEST_TIMEOUT
│   └── ENV_FOLDER_MAP
├── utils.logging_utils
│   ├── log_info()
│   ├── log_ok()
│   └── log_fail()
└── utils.aws_utils
    ├── upload_to_s3()
    └── get_s3_client()

glue_pipeline.py
├── utils.glue_utils
│   ├── get_glue_client()
│   └── get_job_status()
├── utils.constants
│   ├── GLUE_JOB_NAMES
│   └── GLUE_JOB_POLL_INTERVAL
└── utils.logging_utils
```

---

## Common Patterns

### Pattern 1: Try-Except-Log-Raise

All pipeline functions follow consistent error handling:

```python
def openaq_pipeline(vietnam_wide: bool = True):
    """Pipeline with error handling."""
    try:
        log_info("Starting extraction pipeline")
        
        # Step 1
        log_info("Step 1: Loading config")
        config = load_config()
        log_ok("Config loaded")
        
        # Step 2
        log_info("Step 2: Connecting to API")
        headers = connect_openaq()
        log_ok("API connection successful")
        
        # Step 3
        log_info("Step 3: Fetching locations")
        locations = fetch_locations(headers)
        log_ok(f"Found {len(locations)} locations")
        
        log_success("Pipeline complete")
        return {
            'status': 'SUCCESS',
            'location_count': len(locations),
        }
        
    except ValueError as e:
        log_fail(f"Invalid value: {str(e)}")
        raise
    except Exception as e:
        log_fail(f"Unexpected error: {type(e).__name__}: {str(e)}")
        raise
```

### Pattern 2: Return Dictionary with Status

All pipelines return consistent structure:

```python
{
    'status': 'SUCCESS' | 'FAIL' | 'SUBMITTED',
    'record_count': int,
    'location_count': int,
    's3_path': str,
    'duration_seconds': float,
    'error': str,  # Only if status != 'SUCCESS'
}
```

### Pattern 3: XCom Passthrough

Pass data between Airflow tasks using XCom:

```python
# Task 1: Extract data
def extract_callable(ti):
    result = openaq_pipeline()
    ti.xcom_push(key='extraction_result', value=result)
    return result['s3_path']

# Task 2: Transform data
def transform_callable(ti):
    s3_path = ti.xcom_pull(task_ids='extract', key='return_value')
    result = glue_pipeline(input_path=s3_path)
    return result['job_run_id']
```

### Pattern 4: Environment-Aware Configuration

All pipelines respect PIPELINE_ENV:

```python
# pipelines/openaq_pipeline.py
from utils.constants import ENV_FOLDER_MAP, RAW_FOLDER_MAP

ENV = os.getenv('PIPELINE_ENV', 'dev')

# S3 path automatically uses dev or prod
s3_folder = ENV_FOLDER_MAP[ENV]  # aq_dev or aq_prod
raw_folder = RAW_FOLDER_MAP[ENV]  # aq_raw_test or aq_raw_prod
```

---

## Usage Examples

### Example 1: Direct Pipeline Invocation (Testing)

```python
# Test extraction without Airflow
from pipelines.openaq_pipeline import openaq_pipeline

result = openaq_pipeline(
    vietnam_wide=True,
    lookback_days=1,
    required_parameters=['PM2.5', 'PM10']
)

print(f"Records: {result['record_count']}")
print(f"S3 Path: {result['s3_path']}")
```

### Example 2: Lambda Integration

```python
# Use pipeline in Lambda function
from pipelines.openaq_pipeline import openaq_pipeline

def lambda_handler(event, context):
    try:
        result = openaq_pipeline(
            vietnam_wide=event.get('vietnam_wide', True),
            lookback_days=event.get('lookback_days', 1),
        )
        return {
            'statusCode': 200,
            'body': result
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }
```

### Example 3: DAG Integration

```python
# Use pipeline in Airflow DAG
from pipelines.openaq_pipeline import openaq_pipeline
from airflow.operators.python import PythonOperator

def extract_task():
    return openaq_pipeline(vietnam_wide=True)

task = PythonOperator(
    task_id='extract',
    python_callable=extract_task,
    dag=dag,
)
```

### Example 4: Glue Job Orchestration

```python
# Sequential Glue jobs
from pipelines.glue_pipeline import run_glue_transformation

# Trigger job
result = run_glue_transformation(env='prod', wait_for_completion=False)
job_run_id = result['job_run_id']

# Wait for completion (in separate task)
status = check_glue_job_status(job_run_id)
```

---

## Error Handling

### Exception Hierarchy

```
Exception
├── ValueError
│   └── Invalid parameter values
├── requests.Timeout
│   └── API timeout
├── requests.ConnectionError
│   └── Network error
├── botocore.exceptions.ClientError
│   └── AWS service error
└── Custom exceptions
    └── PipelineError (future)
```

### Error Recovery

**Automatic Retry** (via Airflow):
```python
# Airflow automatically retries failed tasks
extract_task = PythonOperator(
    task_id='extract',
    python_callable=extract_task_callable,
    retries=2,
    retry_delay=timedelta(minutes=5),
    dag=dag,
)
```

**Manual Recovery** (in pipeline):
```python
import time

def extract_with_retry(max_retries=3):
    for attempt in range(max_retries):
        try:
            return openaq_pipeline()
        except requests.Timeout:
            if attempt < max_retries - 1:
                log_warning(f"Timeout, retrying in 30s (attempt {attempt+1})")
                time.sleep(30)
            else:
                raise
```

---

## Testing

### Unit Tests

```python
# tests/test_openaq_pipeline.py

import pytest
from pipelines.openaq_pipeline import openaq_pipeline

def test_extraction_returns_dict():
    """Verify pipeline returns expected structure."""
    result = openaq_pipeline(vietnam_wide=False, lookback_days=1)
    
    assert isinstance(result, dict)
    assert 'status' in result
    assert result['status'] in ['SUCCESS', 'FAIL']
    assert 'record_count' in result
    assert isinstance(result['record_count'], int)

def test_extraction_success():
    """Verify successful extraction."""
    result = openaq_pipeline(vietnam_wide=True)
    
    assert result['status'] == 'SUCCESS'
    assert result['record_count'] > 0
    assert result['s3_path'].startswith('s3://')

def test_extraction_with_parameters():
    """Verify parameter filtering works."""
    result = openaq_pipeline(
        required_parameters=['PM2.5', 'PM10']
    )
    
    assert result['status'] == 'SUCCESS'
```

### Integration Tests

```python
# tests/test_e2e_glue_pipeline.py

def test_extract_to_glue_pipeline():
    """Test complete extraction + transformation."""
    # Extract
    extract_result = openaq_pipeline()
    assert extract_result['status'] == 'SUCCESS'
    
    # Transform
    glue_result = run_glue_transformation(
        input_path=extract_result['s3_path'],
        wait_for_completion=True,
        timeout_seconds=600
    )
    assert glue_result['status'] == 'SUCCEEDED'
    assert glue_result['output_records'] > 0
```

---

## Best Practices

### 1. Fail Fast

```python
# ✅ GOOD: Validate early
def openaq_pipeline(vietnam_wide: bool = True):
    if not isinstance(vietnam_wide, bool):
        raise ValueError(f"vietnam_wide must be bool, got {type(vietnam_wide)}")
    # ... rest of pipeline

# ❌ BAD: Fail late
def openaq_pipeline(vietnam_wide):
    locations = fetch_locations()  # Crashes here if vietnam_wide is wrong
```

### 2. Return Consistent Data

```python
# ✅ GOOD: Always return same structure
def run_glue_transformation():
    return {
        'status': 'SUCCESS',
        'job_run_id': 'jr-123',
        'output_records': 100,
        'duration_seconds': 45.2
    }

# ❌ BAD: Inconsistent returns
def run_glue_transformation():
    if success:
        return job_run_id  # Returns string
    else:
        return {'error': 'msg'}  # Returns dict
```

### 3. Use Logging Utilities

```python
# ✅ GOOD: Consistent logging
from utils.logging_utils import log_info, log_ok, log_fail

log_info("Starting extraction")
log_ok("Config loaded")
log_fail("API connection failed")

# ❌ BAD: Inconsistent logging
print("Starting...")
print("OK")
raise Exception("ERROR")
```

### 4. Handle Timeouts

```python
# ✅ GOOD: Set reasonable timeout
response = requests.get(url, timeout=30)

# ❌ BAD: No timeout (request hangs)
response = requests.get(url)
```

### 5. Document Expected Behavior

```python
# ✅ GOOD: Clear docstring
def openaq_pipeline(vietnam_wide: bool = True):
    """
    Extract OpenAQ data and upload to S3.
    
    Args:
        vietnam_wide (bool): Extract entire Vietnam or specific location
    
    Returns:
        dict: {
            'status': 'SUCCESS'|'FAIL',
            'record_count': int,
            's3_path': str,
        }
    
    Raises:
        ValueError: Invalid parameters
        requests.Timeout: API timeout
    """

# ❌ BAD: No documentation
def openaq_pipeline(vietnam_wide=True):
    # Extract data
```

---

## Related Documentation

- [Airflow DAG Guide](../dags/README.md) - How DAGs use pipelines
- [ETL Functions](../etls/openaq_etl.py) - Low-level extraction logic
- [Utils Reference](utils/README.md) - Shared utilities
- [Architecture Guide](../doc/architecture_en.md) - System design
- [Refactoring Guide](../doc/REFACTORING_GUIDE.md) - Code patterns

---

## Quick Reference

### Extract Data
```python
from pipelines.openaq_pipeline import openaq_pipeline

result = openaq_pipeline(
    vietnam_wide=True,
    lookback_days=1,
    required_parameters=['PM2.5', 'PM10']
)

print(result['s3_path'])
```

### Run Glue Job
```python
from pipelines.glue_pipeline import run_glue_transformation

result = run_glue_transformation(env='prod')
job_run_id = result['job_run_id']
```

### Check Job Status
```python
from pipelines.glue_pipeline import check_glue_job_status

status = check_glue_job_status(job_run_id)
```

---

**Maintained By**: OpenAQ Pipeline Team  
**Last Updated**: January 4, 2026
