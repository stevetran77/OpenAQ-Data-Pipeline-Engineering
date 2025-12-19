import sys
sys.path.insert(0, '/opt/airflow/')

from airflow import DAG
from datetime import datetime, timedelta

from tasks.extract_tasks import create_extraction_tasks
from tasks.catalog_tasks import create_catalog_tasks
from tasks.validation_tasks import create_validate_athena_task

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
    schedule_interval='@daily',  # Runs at midnight daily
    catchup=False,
    tags=['openaq', 'airquality', 'etl', 's3', 'glue', 'athena', 'pipeline']
)

# Define cities to extract data from
cities_config = [
    {
        'city': 'Hanoi',
        'country': 'VN',
        'lookback_hours': 24,
        'retries': 2
    },
    {
        'city': 'Ho Chi Minh City',
        'country': 'VN',
        'lookback_hours': 24,
        'retries': 2
    }
]

# Create extraction tasks (runs in parallel)
extraction_tasks = create_extraction_tasks(dag, cities_config)

# Create catalog tasks (trigger + wait)
trigger_crawler_task, wait_crawler_task = create_catalog_tasks(dag)

# Create validation task
validate_task = create_validate_athena_task(dag)

# Task Dependencies
# Extract tasks run in parallel -> trigger crawler -> wait for crawler -> validate data
extraction_tasks >> trigger_crawler_task >> wait_crawler_task >> validate_task
