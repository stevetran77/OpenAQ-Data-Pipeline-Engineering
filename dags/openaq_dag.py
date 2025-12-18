import sys
sys.path.insert(0, '/opt/airflow/')

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.python import PythonSensor
from datetime import datetime, timedelta
from airflow.exceptions import AirflowException

from pipelines.openaq_pipeline import openaq_pipeline
from pipelines.glue_pipeline import (
    trigger_crawler_task,
    check_crawler_status,
    trigger_glue_job_task,
    check_glue_job_status,
    validate_redshift_load
)
from utils.constants import GLUE_CRAWLER_NAME, GLUE_ETL_JOB_NAME

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

# Generate daily filename with date
file_postfix = datetime.now().strftime("%Y%m%d")

# Define DAG
dag = DAG(
    dag_id='openaq_to_redshift_pipeline',
    default_args=default_args,
    description='Extract air quality data from OpenAQ, load to S3, transform with Glue, load to Redshift',
    schedule_interval='@daily',  # Runs at midnight daily
    catchup=False,
    tags=['openaq', 'airquality', 'etl', 's3', 'glue', 'redshift', 'pipeline']
)

# Task 1: Extract air quality data for Hanoi
extract_hanoi = PythonOperator(
    task_id='extract_hanoi_airquality',
    python_callable=openaq_pipeline,
    op_kwargs={
        'file_name': f'hanoi_{file_postfix}',
        'city': 'Hanoi',
        'country': 'VN',
        'lookback_hours': 24
    },
    dag=dag,
    retries=2,
)

# Task 2: Extract air quality data for HCMC
extract_hcmc = PythonOperator(
    task_id='extract_hcmc_airquality',
    python_callable=openaq_pipeline,
    op_kwargs={
        'file_name': f'hcmc_{file_postfix}',
        'city': 'Ho Chi Minh City',
        'country': 'VN',
        'lookback_hours': 24
    },
    dag=dag,
    retries=2,
)

# Task 3: Trigger Glue Crawler to catalog new S3 data
trigger_crawler = PythonOperator(
    task_id='trigger_glue_crawler',
    python_callable=trigger_crawler_task,
    op_kwargs={'crawler_name': GLUE_CRAWLER_NAME},
    dag=dag,
    retries=3,
)

# Task 4: Wait for Crawler to complete
wait_crawler = PythonSensor(
    task_id='wait_for_crawler',
    python_callable=check_crawler_status,
    poke_interval=60,  # Check every 60 seconds
    timeout=1800,  # 30 minutes timeout
    mode='poke',
    dag=dag,
)

# Task 5: Trigger Glue ETL Job to load data to Redshift
trigger_glue_job = PythonOperator(
    task_id='trigger_glue_etl_job',
    python_callable=trigger_glue_job_task,
    op_kwargs={'job_name': GLUE_ETL_JOB_NAME},
    dag=dag,
    retries=3,
)

# Task 6: Wait for Glue Job to complete
wait_glue_job = PythonSensor(
    task_id='wait_for_glue_job',
    python_callable=check_glue_job_status,
    poke_interval=120,  # Check every 2 minutes
    timeout=3600,  # 60 minutes timeout
    mode='poke',
    dag=dag,
)

# Task 7: Validate data in Redshift
validate_data = PythonOperator(
    task_id='validate_redshift_data',
    python_callable=validate_redshift_load,
    dag=dag,
    retries=2,
)

# Task Dependencies
# Extract tasks run in parallel, then trigger crawler -> wait -> trigger job -> wait -> validate
[extract_hanoi, extract_hcmc] >> trigger_crawler >> wait_crawler >> trigger_glue_job >> wait_glue_job >> validate_data
