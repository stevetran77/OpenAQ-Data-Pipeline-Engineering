"""
Lambda extraction tasks for OpenAQ data pipeline.
Uses AWS Lambda for serverless extraction instead of running in Airflow.
"""
import sys
sys.path.insert(0, '/opt/airflow/')

import json
from airflow.providers.amazon.aws.operators.lambda_function import LambdaInvokeFunctionOperator
from datetime import datetime
from utils.constants import ENV


def create_lambda_extract_task(dag, function_name: str = 'openaq-fetcher'):
    """
    Create Lambda extraction task for Vietnam-wide data extraction.
    
    Args:
        dag: Airflow DAG object
        function_name: AWS Lambda function name (default: 'openaq-fetcher')
    
    Returns:
        AwsLambdaInvokeFunctionOperator: Lambda invoke task
    """
    # Generate unique filename with timestamp
    timestamp = "{{ ts_nodash }}"

    # Event payload for Lambda (must be JSON string)
    payload = {
        "file_name": f"vietnam_national_{timestamp}",
        "vietnam_wide": True,
        "lookback_hours": 24,
        "required_parameters": ['PM2.5', 'PM10', 'NO2', 'O3', 'SO2', 'CO', 'BC']
    }

    task = LambdaInvokeFunctionOperator(
        task_id='lambda_extract_vietnam',
        function_name=function_name,
        payload=json.dumps(payload),  # Convert dict to JSON string
        aws_conn_id='aws_default',
        invocation_type='RequestResponse',
        log_type='Tail',
        dag=dag,
        do_xcom_push=True  # Explicitly enable XCom push for Lambda response
    )
    
    return task
