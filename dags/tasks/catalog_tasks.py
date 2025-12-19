"""
Catalog tasks for OpenAQ data pipeline.
Handles Glue Crawler cataloging of S3 data.
"""
import sys
sys.path.insert(0, '/opt/airflow/')

from airflow.operators.python import PythonOperator
from airflow.sensors.python import PythonSensor
from pipelines.glue_pipeline import trigger_crawler_task, check_crawler_status
from utils.constants import GLUE_CRAWLER_NAME


def create_trigger_crawler_task(dag, crawler_name: str = None, retries: int = 3):
    """
    Create a task to trigger Glue Crawler.

    Args:
        dag: Airflow DAG object
        crawler_name: Name of Glue Crawler (uses config default if None)
        retries: Number of retries on failure

    Returns:
        PythonOperator: Trigger crawler task
    """
    task = PythonOperator(
        task_id='trigger_glue_crawler',
        python_callable=trigger_crawler_task,
        op_kwargs={'crawler_name': crawler_name or GLUE_CRAWLER_NAME},
        dag=dag,
        retries=retries,
    )

    return task


def create_wait_crawler_task(dag, poke_interval: int = 60, timeout: int = 1800):
    """
    Create a sensor task to wait for Glue Crawler completion.

    Args:
        dag: Airflow DAG object
        poke_interval: Check crawler status every N seconds
        timeout: Timeout in seconds (default: 30 minutes)

    Returns:
        PythonSensor: Wait for crawler task
    """
    task = PythonSensor(
        task_id='wait_for_crawler',
        python_callable=check_crawler_status,
        poke_interval=poke_interval,
        timeout=timeout,
        mode='poke',
        dag=dag,
    )

    return task


def create_catalog_tasks(dag):
    """
    Create all catalog-related tasks (trigger + wait).

    Args:
        dag: Airflow DAG object

    Returns:
        tuple: (trigger_task, wait_task)
    """
    trigger_task = create_trigger_crawler_task(dag)
    wait_task = create_wait_crawler_task(dag)

    return trigger_task, wait_task
