"""
OpenAQ DAG Example - Lambda Version

This is an example of how to update the DAG to use Lambda instead of PythonOperator.
You can copy the relevant sections to your main openaq_dag.py file.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Import Lambda task factory
from tasks.lambda_extract_tasks import create_lambda_extract_task, create_lambda_response_parser_task
from tasks.glue_transform_tasks import create_glue_transform_tasks
from tasks.catalog_tasks import create_catalog_tasks
from tasks.validation_tasks import create_validate_athena_task

# Import constants
from utils.constants import ENV

# Default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,
}

# Create DAG
dag = DAG(
    'openaq_to_athena_pipeline_lambda',
    default_args=default_args,
    description='OpenAQ to Athena pipeline using Lambda extraction',
    schedule_interval='0 0 * * *',  # Daily at midnight
    start_date=datetime(2025, 12, 1),
    catchup=False,
    tags=['openaq', 'lambda', 'etl', 'air-quality'],
)

# TASK 1: Lambda Extraction (replaces PythonOperator)
extract_lambda = create_lambda_extract_task(dag, env=ENV)

# TASK 2: Parse Lambda Response
parse_response = create_lambda_response_parser_task(dag)

# TASK 3: Glue Transform Job (trigger + wait)
trigger_glue, wait_glue = create_glue_transform_tasks(dag)

# TASK 4: Glue Crawler (trigger + wait)
trigger_crawler, wait_crawler = create_catalog_tasks(dag)

# TASK 5: Validate Athena Data
validate_athena = create_validate_athena_task(dag)

# Define task dependencies
extract_lambda >> parse_response >> trigger_glue >> wait_glue >> trigger_crawler >> wait_crawler >> validate_athena
