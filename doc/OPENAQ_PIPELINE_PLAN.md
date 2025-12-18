# OpenAQ Data Pipeline Implementation Plan

## Architecture Overview

```
OpenAQ API --> Airflow (extract) --> S3 (Parquet) --> Glue Crawler --> Glue ETL Job --> Redshift --> Looker
```

| Component | Technology | Purpose |
|-----------|------------|---------|
| Orchestration | Airflow | Main workflow orchestrator |
| Data Catalog | AWS Glue | Schema management, cataloging |
| Data Lake | S3 (Parquet) | Raw data storage |
| ETL | Glue ETL Job | Transform and load to Redshift |
| Data Warehouse | Redshift | Analytics storage |
| Visualization | Looker | Dashboards and reporting |

---

## Current State

### Already Implemented

| File | Description |
|------|-------------|
| `etls/openaq_etl.py` | ETL functions: connect_openaq(), extract_locations(), extract_measurements(), transform_measurements() |
| `pipelines/openaq_pipeline.py` | Pipeline orchestration with S3 partitioned upload (Parquet format) |
| `dags/openaq_dag.py` | Airflow DAG with daily schedule for Hanoi and HCMC |
| `utils/aws_utils.py` | S3 utilities: upload_to_s3(), upload_to_s3_partitioned(), get_s3_client() |
| `utils/constants.py` | Config reader expecting config/config.conf |

### Missing Components

- [x] Config file (config/config.conf) - needs to be created
- [x] openaq library in requirements.txt
- [ ] AWS Glue integration (crawler, ETL job)
- [ ] AWS Redshift integration
- [ ] Looker connection configuration

---

## Implementation Steps

### Step 1: Foundation Setup

#### 1.1 Create Configuration Directory and File

**Create:** `config/config.conf`

```ini
[database]
database_host = localhost
database_port = 5432
database_name = airflow_reddit
database_username = postgres
database_password = postgres

[file_paths]
input_path = /opt/airflow/data/input
output_path = /opt/airflow/data/output

[aws]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
aws_session_token =
aws_region = ap-southeast-1
aws_bucket_name = openaq-data-pipeline

[aws_glue]
glue_database_name = openaq_database
glue_crawler_name = openaq_s3_crawler
glue_etl_job_name = openaq_to_redshift
glue_iam_role = arn:aws:iam::ACCOUNT_ID:role/GlueServiceRole

[aws_redshift]
redshift_host = your-cluster.region.redshift.amazonaws.com
redshift_port = 5439
redshift_database = openaq_warehouse
redshift_username = admin
redshift_password = YOUR_PASSWORD
redshift_schema = public
redshift_iam_role = arn:aws:iam::ACCOUNT_ID:role/RedshiftS3Role

[api_keys]
openaq_api_key = YOUR_OPENAQ_API_KEY

[openaq_settings]
target_city = Hanoi
target_country = VN
data_granularity = hourly
lookback_hours = 24

[etl_settings]
batch_size = 100
error_handling = abort
log_level = info
```

**Also Create:** `config/config.conf.example` (same content with placeholder values for version control)

#### 1.2 Update requirements.txt

**Modify:** `requirements.txt`

Add the following packages:

```
# OpenAQ API Client
openaq==0.2.0

# AWS Glue and Redshift
awswrangler==3.9.1
redshift-connector==2.1.4
```

---

### Step 2: Extend Configuration

**Modify:** `utils/constants.py`

Add new configuration sections after existing AWS configuration:

```python
# ============================================================================
# AWS GLUE CONFIGURATION
# ============================================================================
GLUE_DATABASE_NAME = config.get("aws_glue", "glue_database_name", fallback="openaq_database")
GLUE_CRAWLER_NAME = config.get("aws_glue", "glue_crawler_name", fallback="openaq_s3_crawler")
GLUE_ETL_JOB_NAME = config.get("aws_glue", "glue_etl_job_name", fallback="openaq_to_redshift")
GLUE_IAM_ROLE = config.get("aws_glue", "glue_iam_role", fallback="")

# ============================================================================
# AWS REDSHIFT CONFIGURATION
# ============================================================================
REDSHIFT_HOST = config.get("aws_redshift", "redshift_host", fallback="")
REDSHIFT_PORT = config.getint("aws_redshift", "redshift_port", fallback=5439)
REDSHIFT_DATABASE = config.get("aws_redshift", "redshift_database", fallback="openaq_warehouse")
REDSHIFT_USERNAME = config.get("aws_redshift", "redshift_username", fallback="")
REDSHIFT_PASSWORD = config.get("aws_redshift", "redshift_password", fallback="")
REDSHIFT_SCHEMA = config.get("aws_redshift", "redshift_schema", fallback="public")
REDSHIFT_IAM_ROLE = config.get("aws_redshift", "redshift_iam_role", fallback="")
```

---

### Step 3: Create Glue Utilities

**Create:** `utils/glue_utils.py`

```python
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
```

---

### Step 4: Create Redshift Utilities

**Create:** `utils/redshift_utils.py`

```python
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
```

---

### Step 5: Create Redshift Schema

**Create:** `sql/redshift_schema.sql`

```sql
-- ============================================================================
-- OpenAQ Data Warehouse Schema
-- ============================================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS openaq;

-- ============================================================================
-- Fact Table: Air Quality Measurements
-- ============================================================================
CREATE TABLE IF NOT EXISTS openaq.fact_measurements (
    measurement_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    location_id INTEGER NOT NULL,
    measurement_datetime TIMESTAMP NOT NULL,
    pm25 DECIMAL(10,4),
    pm10 DECIMAL(10,4),
    o3 DECIMAL(10,4),
    no2 DECIMAL(10,4),
    so2 DECIMAL(10,4),
    co DECIMAL(10,4),
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6),
    city VARCHAR(100),
    country VARCHAR(10),
    extracted_at TIMESTAMP,
    loaded_at TIMESTAMP DEFAULT GETDATE(),
    UNIQUE(location_id, measurement_datetime)
)
DISTSTYLE KEY
DISTKEY(city)
SORTKEY(measurement_datetime);

-- ============================================================================
-- Dimension Table: Locations
-- ============================================================================
CREATE TABLE IF NOT EXISTS openaq.dim_locations (
    location_id INTEGER PRIMARY KEY,
    location_name VARCHAR(255),
    city VARCHAR(100),
    country VARCHAR(10),
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT GETDATE(),
    updated_at TIMESTAMP DEFAULT GETDATE()
)
DISTSTYLE ALL;

-- ============================================================================
-- Indexes for Query Performance
-- ============================================================================
-- Note: Redshift uses sort keys instead of traditional indexes
-- The SORTKEY on measurement_datetime optimizes time-range queries

-- ============================================================================
-- Service Account for Looker (Read-Only)
-- ============================================================================
-- CREATE USER looker_readonly PASSWORD 'secure_password';
-- GRANT USAGE ON SCHEMA openaq TO looker_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA openaq TO looker_readonly;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA openaq GRANT SELECT ON TABLES TO looker_readonly;
```

---

### Step 6: Create Glue Pipeline Functions

**Create:** `pipelines/glue_pipeline.py`

```python
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
```

---

### Step 7: Update Airflow DAG

**Modify:** `dags/openaq_dag.py`

Update the DAG with new tasks:

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.python import PythonSensor

from pipelines.openaq_pipeline import openaq_pipeline
from pipelines.glue_pipeline import (
    trigger_crawler_task,
    check_crawler_status,
    trigger_glue_job_task,
    check_glue_job_status,
    validate_redshift_load
)
from utils.constants import GLUE_CRAWLER_NAME, GLUE_ETL_JOB_NAME

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=30),
}

with DAG(
    dag_id='openaq_to_redshift_pipeline',
    default_args=default_args,
    description='Extract air quality data from OpenAQ, load to S3, transform with Glue, load to Redshift',
    schedule_interval='@daily',
    catchup=False,
    tags=['openaq', 'airquality', 'etl', 's3', 'glue', 'redshift', 'pipeline'],
) as dag:

    # Task 1: Extract Hanoi air quality data
    extract_hanoi = PythonOperator(
        task_id='extract_hanoi_airquality',
        python_callable=openaq_pipeline,
        op_kwargs={'city': 'Hanoi', 'country': 'VN', 'lookback_hours': 24},
    )

    # Task 2: Extract HCMC air quality data
    extract_hcmc = PythonOperator(
        task_id='extract_hcmc_airquality',
        python_callable=openaq_pipeline,
        op_kwargs={'city': 'Ho Chi Minh City', 'country': 'VN', 'lookback_hours': 24},
    )

    # Task 3: Trigger Glue Crawler to catalog new S3 data
    trigger_crawler = PythonOperator(
        task_id='trigger_glue_crawler',
        python_callable=trigger_crawler_task,
        op_kwargs={'crawler_name': GLUE_CRAWLER_NAME},
    )

    # Task 4: Wait for Crawler to complete
    wait_crawler = PythonSensor(
        task_id='wait_for_crawler',
        python_callable=check_crawler_status,
        poke_interval=60,  # Check every 60 seconds
        timeout=1800,  # 30 minutes timeout
        mode='poke',
    )

    # Task 5: Trigger Glue ETL Job to load data to Redshift
    trigger_glue_job = PythonOperator(
        task_id='trigger_glue_etl_job',
        python_callable=trigger_glue_job_task,
        op_kwargs={'job_name': GLUE_ETL_JOB_NAME},
    )

    # Task 6: Wait for Glue Job to complete
    wait_glue_job = PythonSensor(
        task_id='wait_for_glue_job',
        python_callable=check_glue_job_status,
        poke_interval=120,  # Check every 2 minutes
        timeout=3600,  # 60 minutes timeout
        mode='poke',
    )

    # Task 7: Validate data in Redshift
    validate_data = PythonOperator(
        task_id='validate_redshift_data',
        python_callable=validate_redshift_load,
    )

    # Task Dependencies
    # Extract tasks run in parallel, then trigger crawler -> wait -> trigger job -> wait -> validate
    [extract_hanoi, extract_hcmc] >> trigger_crawler >> wait_crawler >> trigger_glue_job >> wait_glue_job >> validate_data
```

---

### Step 8: Create Glue ETL Script

**Create:** `glue_jobs/openaq_to_redshift.py`

This script runs in AWS Glue environment. Upload to S3 at `s3://openaq-data-pipeline/scripts/openaq_to_redshift.py`

```python
"""
AWS Glue ETL Job: Transform OpenAQ S3 Parquet data and load to Redshift.
This script runs in AWS Glue environment.
"""
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.sql.functions import col, lit, current_timestamp, row_number
from pyspark.sql.window import Window

# Get job arguments
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'source_database',
    'target_schema',
    'redshift_connection'
])

# Initialize Glue context
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print("[START] OpenAQ to Redshift ETL Job")

# ============================================================================
# Step 1: Read from Glue Data Catalog
# ============================================================================
print("[INFO] Reading from Glue Data Catalog...")

source_database = args['source_database']
source_table = "aq_airquality"  # Table created by Glue Crawler

datasource = glueContext.create_dynamic_frame.from_catalog(
    database=source_database,
    table_name=source_table,
    transformation_ctx="datasource"
)

print(f"[OK] Read {datasource.count()} records from source")

# Convert to DataFrame for transformations
df = datasource.toDF()

# ============================================================================
# Step 2: Data Quality Checks
# ============================================================================
print("[INFO] Applying data quality checks...")

# Filter out null measurement datetimes
df = df.filter(col("measurement_datetime").isNotNull())

# Filter out invalid coordinates
df = df.filter(
    (col("latitude").isNotNull()) &
    (col("longitude").isNotNull()) &
    (col("latitude").between(-90, 90)) &
    (col("longitude").between(-180, 180))
)

print(f"[OK] {df.count()} records passed quality checks")

# ============================================================================
# Step 3: Deduplication
# ============================================================================
print("[INFO] Removing duplicates...")

# Remove duplicates based on location_id and measurement_datetime
# Keep the most recent record if duplicates exist
window_spec = Window.partitionBy("location_id", "measurement_datetime").orderBy(col("extracted_at").desc())

df = df.withColumn("row_num", row_number().over(window_spec))
df = df.filter(col("row_num") == 1).drop("row_num")

print(f"[OK] {df.count()} records after deduplication")

# ============================================================================
# Step 4: Add metadata columns
# ============================================================================
print("[INFO] Adding metadata columns...")

df = df.withColumn("loaded_at", current_timestamp())

# ============================================================================
# Step 5: Write to Redshift
# ============================================================================
print("[INFO] Writing to Redshift...")

# Convert back to DynamicFrame
output_frame = DynamicFrame.fromDF(df, glueContext, "output_frame")

# Write to Redshift using Glue Connection
glueContext.write_dynamic_frame.from_jdbc_conf(
    frame=output_frame,
    catalog_connection=args['redshift_connection'],
    connection_options={
        "dbtable": f"{args['target_schema']}.fact_measurements",
        "database": "openaq_warehouse"
    },
    redshift_tmp_dir=f"s3://openaq-data-pipeline/temp/",
    transformation_ctx="redshift_sink"
)

print(f"[SUCCESS] Loaded {df.count()} records to Redshift")

# Commit the job
job.commit()
print("[SUCCESS] OpenAQ to Redshift ETL Job completed")
```

---

### Step 9: Update .gitignore

**Modify:** `.gitignore`

Ensure config file with credentials is ignored:

```
# Configuration with credentials
config/config.conf

# Keep example config
!config/config.conf.example
```

---

## AWS Resources Setup (Manual via Console)

### 1. S3 Bucket

| Property | Value |
|----------|-------|
| Bucket Name | `openaq-data-pipeline` |
| Region | `ap-southeast-1` |
| Versioning | Enabled |
| Encryption | SSE-S3 |

Folder structure:
```
openaq-data-pipeline/
  |-- airquality/
  |     |-- Hanoi/
  |     |     |-- year=2024/month=01/day=15/data.parquet
  |     |-- Ho Chi Minh City/
  |           |-- year=2024/month=01/day=15/data.parquet
  |-- scripts/
  |     |-- openaq_to_redshift.py
  |-- temp/
```

### 2. IAM Roles

**GlueServiceRole:**
- Trust: glue.amazonaws.com
- Policies: AWSGlueServiceRole, AmazonS3FullAccess, AmazonRedshiftFullAccess

**RedshiftS3Role:**
- Trust: redshift.amazonaws.com
- Policies: AmazonS3ReadOnlyAccess

### 3. Glue Database

| Property | Value |
|----------|-------|
| Database Name | `openaq_database` |
| Description | OpenAQ Air Quality Data Catalog |

### 4. Glue Crawler

| Property | Value |
|----------|-------|
| Crawler Name | `openaq_s3_crawler` |
| Database | `openaq_database` |
| S3 Path | `s3://openaq-data-pipeline/airquality/` |
| IAM Role | `GlueServiceRole` |
| Schedule | On-demand |
| Table Prefix | `aq_` |

### 5. Glue ETL Job

| Property | Value |
|----------|-------|
| Job Name | `openaq_to_redshift` |
| Type | Spark |
| Glue Version | 4.0 |
| Worker Type | G.1X |
| Number of Workers | 2 |
| Script Location | `s3://openaq-data-pipeline/scripts/openaq_to_redshift.py` |
| Connections | RedshiftConnection |

### 6. Glue Connection (for Redshift)

| Property | Value |
|----------|-------|
| Connection Name | `RedshiftConnection` |
| Connection Type | JDBC |
| JDBC URL | `jdbc:redshift://your-cluster.region.redshift.amazonaws.com:5439/openaq_warehouse` |
| Username | admin |
| VPC | Your VPC |
| Security Group | Allow inbound 5439 |

### 7. Redshift Cluster

| Property | Value |
|----------|-------|
| Cluster Identifier | `openaq-warehouse` |
| Node Type | dc2.large |
| Number of Nodes | 1 (for dev) |
| Database Name | `openaq_warehouse` |
| Master Username | admin |
| Port | 5439 |
| VPC | Your VPC |
| Publicly Accessible | Yes (for Looker) |

---

## Files Summary

### New Files to Create

| File | Purpose |
|------|---------|
| `config/config.conf` | Main configuration with credentials |
| `config/config.conf.example` | Template for version control |
| `utils/glue_utils.py` | AWS Glue client utilities |
| `utils/redshift_utils.py` | Redshift connection utilities |
| `pipelines/glue_pipeline.py` | Glue-related DAG task functions |
| `glue_jobs/openaq_to_redshift.py` | Glue ETL script (upload to S3) |
| `sql/redshift_schema.sql` | Redshift DDL statements |
| `tests/test_glue_utils.py` | Unit tests for Glue utilities |
| `tests/test_redshift_utils.py` | Unit tests for Redshift utilities |

### Files to Modify

| File | Changes |
|------|---------|
| `requirements.txt` | Add openaq, awswrangler, redshift-connector |
| `utils/constants.py` | Add Glue and Redshift configuration sections |
| `dags/openaq_dag.py` | Add Glue Crawler, ETL Job, and validation tasks |
| `.gitignore` | Ensure config.conf is ignored |

---

## Error Handling Strategy

| Task | Retries | Retry Delay | Timeout |
|------|---------|-------------|---------|
| extract_hanoi | 2 | 5 min | 30 min |
| extract_hcmc | 2 | 5 min | 30 min |
| trigger_crawler | 3 | 2 min | 5 min |
| wait_crawler | 0 | N/A | 30 min |
| trigger_glue_job | 3 | 5 min | 10 min |
| wait_glue_job | 0 | N/A | 60 min |
| validate_redshift | 2 | 3 min | 10 min |

Status indicators: `[OK]`, `[FAIL]`, `[SUCCESS]`, `[WARNING]`, `[INFO]`, `[START]`

---

## Looker Configuration

Connect Looker directly to Redshift:

| Property | Value |
|----------|-------|
| Connection Type | Amazon Redshift |
| Host | your-cluster.region.redshift.amazonaws.com |
| Port | 5439 |
| Database | openaq_warehouse |
| Schema | openaq |
| User | looker_readonly |
| SSL | Required |

---

## Implementation Order

```
1. Create config/config.conf and config/config.conf.example
2. Update requirements.txt
3. Update utils/constants.py
4. Create utils/glue_utils.py
5. Create utils/redshift_utils.py
6. Create pipelines/glue_pipeline.py
7. Create sql/redshift_schema.sql
8. Update dags/openaq_dag.py
9. Create glue_jobs/openaq_to_redshift.py
10. Update .gitignore
11. Create tests
12. Set up AWS resources via Console
13. Test end-to-end pipeline
14. Configure Looker connection
```
