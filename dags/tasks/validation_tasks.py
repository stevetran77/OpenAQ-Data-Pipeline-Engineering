"""
Validation tasks for OpenAQ data pipeline.
Handles Athena data validation and quality checks.
"""
import sys
sys.path.insert(0, '/opt/airflow/')

from airflow.operators.python import PythonOperator
from pipelines.glue_pipeline import validate_athena_data


def create_validate_athena_task(dag, retries: int = 2):
    """
    Create a task to validate data in Athena.

    Checks that:
    - Tables exist in Athena database
    - Tables have air quality data (aq_ prefix)
    - Tables contain rows

    Args:
        dag: Airflow DAG object
        retries: Number of retries on failure

    Returns:
        PythonOperator: Athena validation task
    """
    task = PythonOperator(
        task_id='validate_athena_data',
        python_callable=validate_athena_data,
        dag=dag,
        retries=retries,
    )

    return task
