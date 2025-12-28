import sys
sys.path.insert(0, '/opt/airflow/')

from airflow import DAG
from datetime import datetime, timedelta

from tasks.catalog_tasks import create_catalog_tasks
from tasks.validation_tasks import create_validate_athena_task
from tasks.glue_transform_tasks import create_glue_transform_tasks
from tasks.lambda_extract_tasks import create_lambda_extract_task

# DAG Configuration
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=30),
}

# Define DAG
dag = DAG(
    dag_id='openaq_to_athena_pipeline',
    default_args=default_args,
    description='Extract air quality data from OpenAQ, load to S3, catalog with Glue Crawler, validate with Athena',
    schedule_interval=None,  # Runs at midnight daily
    catchup=False,
    tags=['openaq', 'airquality', 'etl', 's3', 'glue', 'athena', 'pipeline']
)

# Lambda extraction task - Serverless extraction on AWS
# Extracts all Vietnam locations with all 7 air quality parameters
lambda_extract_task = create_lambda_extract_task(dag, function_name='openaq-fetcher')

# Create Glue transform tasks (trigger + wait)
# These transform raw JSON to partitioned Parquet using Spark
trigger_glue_transform_task, wait_glue_transform_task = create_glue_transform_tasks(dag)

# Create catalog tasks (trigger + wait)
# Glue Crawler scans S3 marts and updates Glue Data Catalog
trigger_crawler_task, wait_crawler_task = create_catalog_tasks(dag)

# Create validation task
# Verify data is queryable in Athena
validate_task = create_validate_athena_task(dag)

# Task Dependencies (Lambda-based Pipeline Flow)
# 1. Lambda extracts raw measurements from OpenAQ API → S3 (JSON)
# 2. Glue transforms raw JSON to Parquet using Spark
# 3. Glue Crawler catalogs transformed data
# 4. Validate data queryable in Athena
lambda_extract_task >> trigger_glue_transform_task >> wait_glue_transform_task >> trigger_crawler_task >> wait_crawler_task >> validate_task
