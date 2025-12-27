"""
Airflow Task Factory for Lambda-based Extraction

Creates LambdaInvokeFunctionOperator task to invoke OpenAQ Fetcher Lambda function.
Replaces the PythonOperator-based extraction with serverless Lambda execution.
"""

import json
from airflow.providers.amazon.aws.operators.lambda_function import LambdaInvokeFunctionOperator
from airflow.operators.python import PythonOperator


def create_lambda_extract_task(dag, env='dev'):
    """
    Create Lambda extraction task.
    
    Args:
        dag: Airflow DAG object
        env: Environment (dev or prod)
    
    Returns:
        LambdaInvokeFunctionOperator: Task that invokes Lambda function
    """
    
    lambda_task = LambdaInvokeFunctionOperator(
        task_id='extract_all_vietnam_locations_lambda',
        function_name=f'openaq-fetcher-{env}',
        payload=json.dumps({
            'file_name': 'vietnam_national_{{ ts_nodash }}',
            'vietnam_wide': True,
            'lookback_hours': 24,
            'required_parameters': ['PM2.5', 'PM10', 'NO2', 'SO2', 'O3', 'CO']
        }),
        aws_conn_id='aws_default',
        log_type='Tail',  # Return last 4KB of logs
        invocation_type='RequestResponse',  # Synchronous invocation
        dag=dag,
        retries=2,
        retry_delay='5m'
    )
    
    return lambda_task


def parse_lambda_response(ti, **kwargs):
    """
    Parse Lambda response from XCom.
    
    Extracts metadata from Lambda response and makes it available
    for downstream tasks via XCom.
    
    Args:
        ti: Task instance
        **kwargs: Additional Airflow context
    
    Returns:
        dict: Parsed Lambda response body
    """
    lambda_response = ti.xcom_pull(task_ids='extract_all_vietnam_locations_lambda')
    
    if not lambda_response:
        raise ValueError("No response from Lambda function")
    
    # Lambda response format: {"statusCode": 200, "body": "{...}"}
    status_code = lambda_response.get('StatusCode') or lambda_response.get('statusCode')
    body_str = lambda_response.get('Payload') or lambda_response.get('body')
    
    if status_code != 200:
        raise ValueError(f"Lambda execution failed with status code: {status_code}")
    
    # Parse body if it's a string
    if isinstance(body_str, str):
        body = json.loads(body_str)
    else:
        body = body_str
    
    print(f"[INFO] Lambda execution result:")
    print(f"  - Status: {body.get('status')}")
    print(f"  - Locations: {body.get('location_count')}")
    print(f"  - Sensors: {body.get('sensor_count')}")
    print(f"  - Records: {body.get('record_count')}")
    print(f"  - S3 Path: {body.get('raw_s3_path')}")
    
    return body


def create_lambda_response_parser_task(dag):
    """
    Create task to parse Lambda response.
    
    Args:
        dag: Airflow DAG object
    
    Returns:
        PythonOperator: Task that parses Lambda response
    """
    
    parser_task = PythonOperator(
        task_id='parse_lambda_response',
        python_callable=parse_lambda_response,
        dag=dag
    )
    
    return parser_task
