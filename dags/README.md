# DAGs Directory

This directory contains Apache Airflow DAG (Directed Acyclic Graph) definitions for the OpenAQ Data Pipeline.

---

## Table of Contents

1. [Directory Structure](#directory-structure)
2. [Current DAGs](#current-dags)
3. [Task Organization](#task-organization)
4. [DAG Architecture Patterns](#dag-architecture-patterns)
5. [Creating New DAGs](#creating-new-dags)
6. [DAG Development Workflow](#dag-development-workflow)
7. [Testing DAGs](#testing-dags)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Directory Structure

```
dags/
├── README.md                       # This file
├── openaq_dag.py                   # Main DAG definition
├── tasks/                          # Task factory functions
│   ├── __init__.py
│   ├── extract_tasks.py            # Lambda extraction tasks
│   ├── glue_transform_tasks.py     # Glue job tasks
│   ├── catalog_tasks.py            # Crawler tasks
│   ├── lambda_extract_tasks.py     # Legacy Lambda tasks
│   ├── validation_tasks.py         # Athena validation tasks
│   └── __pycache__/
└── __pycache__/
```

---

## Current DAGs

### `openaq_to_athena_pipeline` (Main Pipeline)

**Location**: [openaq_dag.py](openaq_dag.py)

**Purpose**: Daily orchestration of air quality data extraction, transformation, cataloging, and validation

**Schedule**: Manual (schedule_interval=None) - triggered manually or by external scheduler

**Execution Environment**: LocalExecutor (Docker container)

**Task Dependencies**:
```
extract_openaq_raw
        │
        ▼
trigger_glue_job_transform
        │
        ▼
wait_for_glue_job
        │
        ▼
trigger_glue_crawler
        │
        ▼
wait_for_crawler
        │
        ▼
validate_athena_table
```

**Detailed Task Breakdown**:

| Task ID | Type | Purpose | Timeout | Retries |
|---------|------|---------|---------|---------|
| `extract_openaq_raw` | PythonOperator | Call extraction pipeline (Airflow or Lambda) | 600s | 2 |
| `trigger_glue_job_transform` | AwsGlueJobOperator | Start Glue job (dev or prod) | 7200s | 3 |
| `wait_for_glue_job` | PythonSensor | Poll job status until SUCCEEDED or FAILED | 7200s | 0 |
| `trigger_glue_crawler` | GlueCrawlerOperator | Start Glue crawler to update catalog | 1800s | 3 |
| `wait_for_crawler` | PythonSensor | Poll crawler status until READY or FAILED | 1800s | 0 |
| `validate_athena_table` | PythonOperator | Query Athena to verify data exists | 60s | 1 |

**Configuration**:

```python
# Environment-aware
PIPELINE_ENV = os.getenv('PIPELINE_ENV', 'dev')  # dev | prod

# Glue job names (auto-appended with _dev or _prod)
GLUE_JOB_NAME = f"process_openaq_raw_{PIPELINE_ENV}"

# Glue crawler names
CRAWLER_NAME = f"openaq-crawler-{PIPELINE_ENV}"

# Athena database
ATHENA_DB = f"aq_{PIPELINE_ENV}"
```

**Execution Example**:

1. **Trigger**: Manual via Airflow UI or API
2. **Extract**: Fetch data from OpenAQ API (3-5 min)
3. **Transform**: Run Glue job on raw data (2-3 min)
4. **Catalog**: Update Glue Data Catalog (1-2 min)
5. **Validate**: Query Athena to confirm data (< 1 min)
6. **Total Runtime**: 7-12 minutes

---

## Task Organization

Tasks are organized in the `tasks/` subfolder by function, following the factory pattern.

### `extract_tasks.py`

**Purpose**: Create extraction tasks (Lambda or Airflow-based)

**Functions**:
- `create_extract_tasks(dag)` - Create extraction operator
  - Returns: `PythonOperator` or `LambdaInvoke`
  - Calls: `pipelines.openaq_pipeline.openaq_pipeline()` or Lambda function
  - Output: XCom with extraction metadata

**Usage**:
```python
from dags.tasks.extract_tasks import create_extract_tasks

extract_task = create_extract_tasks(dag)
```

### `glue_transform_tasks.py`

**Purpose**: Create Glue job transformation tasks

**Functions**:
- `create_glue_transform_tasks(dag)` - Create trigger + wait tasks
  - Returns: `(trigger_task, wait_task)` tuple
  - Trigger: `AwsGlueJobOperator` to start job
  - Wait: `PythonSensor` to poll job status
  - Input: XCom from extraction task
  - Output: Glue job run ID, status

**Usage**:
```python
from dags.tasks.glue_transform_tasks import create_glue_transform_tasks

trigger_glue, wait_glue = create_glue_transform_tasks(dag)
extract_task >> trigger_glue >> wait_glue
```

**Polling Strategy**:
```python
PythonSensor(
    task_id='wait_for_glue_job',
    python_callable=check_glue_job_status,
    poke_interval=60,      # Check every 60 seconds
    timeout=7200,          # Fail after 2 hours
    mode='poke'            # Block worker (default)
)
```

### `catalog_tasks.py`

**Purpose**: Create Glue crawler cataloging tasks

**Functions**:
- `create_catalog_tasks(dag)` - Create trigger + wait tasks
  - Returns: `(trigger_task, wait_task)` tuple
  - Trigger: `GlueCrawlerOperator` to start crawler
  - Wait: `PythonSensor` to poll crawler status
  - Input: None (independent task)
  - Output: Crawler status, table count

**Usage**:
```python
from dags.tasks.catalog_tasks import create_catalog_tasks

trigger_crawler, wait_crawler = create_catalog_tasks(dag)
wait_glue >> trigger_crawler >> wait_crawler
```

### `lambda_extract_tasks.py`

**Purpose**: Legacy Lambda invocation tasks (superseded by Airflow extraction)

**Status**: Deprecated but maintained for backward compatibility

**Functions**:
- `create_lambda_extract_tasks(dag)` - Create Lambda invocation tasks
  - Invokes: `openaq-fetcher` Lambda function
  - Returns: Function response with extraction metadata

**Note**: New pipelines should use Airflow-based extraction in `extract_tasks.py`

### `validation_tasks.py`

**Purpose**: Create Athena validation tasks

**Functions**:
- `create_validate_athena_task(dag)` - Create validation operator
  - Returns: `PythonOperator`
  - Queries: Athena table for data
  - Validates: Row count > 0
  - Output: Validation result, record count

**Usage**:
```python
from dags.tasks.validation_tasks import create_validate_athena_task

validate_task = create_validate_athena_task(dag)
wait_crawler >> validate_task
```

---

## DAG Architecture Patterns

### Pattern 1: Task Separation (Current)

Separate task creation from DAG definition for reusability:

```python
# File: dags/tasks/glue_transform_tasks.py
def create_glue_transform_tasks(dag):
    """Factory function returning task tuple."""
    trigger = AwsGlueJobOperator(
        task_id='trigger_glue_job',
        job_name=GLUE_JOB_NAME,
        dag=dag
    )
    wait = PythonSensor(
        task_id='wait_for_glue_job',
        python_callable=check_glue_job_status,
        dag=dag
    )
    return (trigger, wait)

# File: dags/openaq_dag.py
trigger_glue, wait_glue = create_glue_transform_tasks(dag)
```

**Advantages**:
- ✅ Reusable task patterns
- ✅ Testable independently
- ✅ Cleaner DAG code
- ✅ Centralized task configuration

### Pattern 2: Task Grouping (Experimental)

For complex DAGs, group related tasks:

```python
from airflow.utils.task_group import TaskGroup

with TaskGroup('glue_pipeline') as glue_group:
    trigger = AwsGlueJobOperator(...)
    wait = PythonSensor(...)
    trigger >> wait

with TaskGroup('crawler_pipeline') as crawler_group:
    trigger = GlueCrawlerOperator(...)
    wait = PythonSensor(...)
    trigger >> wait

glue_group >> crawler_group
```

**Advantages**:
- ✅ Better visualization in UI
- ✅ Easier to navigate complex DAGs
- ✅ Clearer logical grouping

### Pattern 3: Branching (Future)

For conditional execution based on data:

```python
def branch_logic(ti):
    """Determine which path to take."""
    xcom_data = ti.xcom_pull(task_ids='extract_openaq_raw')
    if xcom_data['record_count'] > 1000:
        return 'process_full_dataset'
    else:
        return 'process_sample_dataset'

branch_task = BranchPythonOperator(
    task_id='branch_by_volume',
    python_callable=branch_logic
)

process_full = PythonOperator(...)
process_sample = PythonOperator(...)

branch_task >> [process_full, process_sample]
```

---

## Creating New DAGs

### Step 1: Create DAG Definition File

Create a new Python file in `dags/` directory:

```python
# File: dags/new_pipeline_dag.py

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.logging_utils import log_ok, log_fail

# DAG configuration
default_args = {
    'owner': 'data-team',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 1, 1),
}

dag = DAG(
    dag_id='new_pipeline_dag',
    default_args=default_args,
    description='Description of new pipeline',
    schedule_interval=None,  # Manual trigger
    catchup=False,
    tags=['new', 'data-pipeline'],
)

# Define tasks
def task1_callable():
    """First task implementation."""
    log_ok('Task 1 completed')

def task2_callable():
    """Second task implementation."""
    log_ok('Task 2 completed')

task1 = PythonOperator(
    task_id='task_1',
    python_callable=task1_callable,
    dag=dag,
)

task2 = PythonOperator(
    task_id='task_2',
    python_callable=task2_callable,
    dag=dag,
)

# Define dependencies
task1 >> task2
```

### Step 2: Create Task Factory (Optional)

If creating reusable tasks:

```python
# File: dags/tasks/new_tasks.py

from airflow.operators.python import PythonOperator
from utils.logging_utils import log_ok

def create_new_tasks(dag):
    """Factory function for new task pattern."""
    
    task = PythonOperator(
        task_id='new_task',
        python_callable=new_task_callable,
        dag=dag,
    )
    
    return task

def new_task_callable():
    """Task implementation."""
    log_ok('New task completed')
```

### Step 3: Register in `__init__.py`

Add to `dags/tasks/__init__.py` if creating new task module:

```python
from dags.tasks.new_tasks import create_new_tasks

__all__ = ['create_new_tasks']
```

### Step 4: Test Locally

```bash
# Verify DAG syntax
python dags/new_pipeline_dag.py
# Should run without errors

# Test DAG parsing (Docker)
docker-compose exec airflow-webserver airflow dags list
# Should show new_pipeline_dag

# Test individual task
docker-compose exec airflow-webserver airflow tasks test \
    new_pipeline_dag task_1 2024-01-15
```

---

## DAG Development Workflow

### Local Development

1. **Create DAG file** in `dags/` directory
2. **Write task definitions** using operators and callables
3. **Define dependencies** using `>>` or `<<` operators
4. **Test parsing**:
   ```bash
   python dags/your_dag.py
   ```

### Testing in Docker

1. **Restart Airflow** to pick up new DAG:
   ```bash
   docker-compose restart airflow-scheduler
   ```

2. **Check Airflow logs**:
   ```bash
   docker-compose logs -f airflow-scheduler
   # Look for DAG parsing messages
   ```

3. **View in UI**:
   - Open http://localhost:8080
   - New DAG should appear in DAG list
   - Note: Airflow rescans DAGs every 30 seconds

4. **Trigger manually**:
   - Click DAG name
   - Click ▶ (play button)
   - Click "Trigger DAG"
   - Monitor in Graph View

### Production Deployment

1. **Code review** - Review DAG code for:
   - Proper error handling
   - Correct task dependencies
   - Resource limits (memory, timeout)
   - Security (no secrets in code)

2. **Test in dev** - Run with `PIPELINE_ENV=dev`:
   ```bash
   docker-compose exec airflow-webserver \
       bash -c "export PIPELINE_ENV=dev && airflow dags test your_dag 2024-01-15"
   ```

3. **Staging validation** - Run on small dataset:
   - Test with 1-2 day lookback
   - Verify output schema
   - Check CloudWatch logs

4. **Production deployment** - Merge to main branch:
   - CI/CD pipeline auto-deploys
   - Airflow rescans and loads DAG
   - Monitor first run carefully

---

## Testing DAGs

### Unit Tests

Test individual task callables:

```python
# File: tests/test_tasks.py

import pytest
from dags.tasks.glue_transform_tasks import check_glue_job_status

def test_glue_job_status_succeeded():
    """Test polling logic for succeeded job."""
    result = check_glue_job_status(job_run_id='jr-12345')
    assert result == True

def test_glue_job_status_running():
    """Test polling logic for running job."""
    result = check_glue_job_status(job_run_id='jr-running')
    assert result == False
```

### Integration Tests

Test complete DAG execution:

```bash
# Run DAG with test date
docker-compose exec airflow-webserver \
    airflow dags test openaq_to_athena_pipeline 2024-01-15

# Check logs
docker-compose logs -f airflow-scheduler | grep openaq_to_athena_pipeline

# Verify S3 output
aws s3 ls s3://openaq-data-pipeline/aq_dev/marts/vietnam/
```

### DAG Validation Tests

```python
# File: tests/test_dag_structure.py

import pytest
from airflow import DAG
from dags.openaq_dag import dag

def test_dag_has_required_tasks():
    """Verify DAG contains expected tasks."""
    task_ids = [task.task_id for task in dag.tasks]
    assert 'extract_openaq_raw' in task_ids
    assert 'trigger_glue_job_transform' in task_ids
    assert 'wait_for_crawler' in task_ids

def test_dag_dependencies():
    """Verify task dependencies are correct."""
    extract = dag.get_task('extract_openaq_raw')
    trigger_glue = dag.get_task('trigger_glue_job_transform')
    
    assert trigger_glue in extract.downstream_list

def test_dag_no_cycles():
    """Verify DAG is acyclic (should not raise)."""
    dag.validate()  # Raises if cycles found
```

---

## Best Practices

### 1. Naming Conventions

**DAG IDs**:
```python
# ✅ Good: snake_case, descriptive
dag_id='openaq_to_athena_pipeline'

# ❌ Bad: camelCase, non-descriptive
dag_id='openaqPipeline'
```

**Task IDs**:
```python
# ✅ Good: snake_case, action-oriented
task_id='trigger_glue_job_transform'

# ❌ Bad: non-descriptive
task_id='task_1'
```

### 2. Error Handling

Always handle errors gracefully:

```python
def task_callable():
    try:
        result = perform_operation()
        log_ok(f"Operation completed: {result}")
        return result
    except Exception as e:
        log_fail(f"Operation failed: {str(e)}")
        raise  # Let Airflow handle retry

task = PythonOperator(
    task_id='my_task',
    python_callable=task_callable,
    retries=2,
    retry_delay=timedelta(minutes=5),
    dag=dag,
)
```

### 3. XCom for Data Passing

Pass data between tasks using XCom:

```python
# Task 1: Push data
def extract_data():
    data = fetch_from_api()
    return {'count': len(data), 'status': 'ok'}

task1 = PythonOperator(
    task_id='extract',
    python_callable=extract_data,
    dag=dag,
)

# Task 2: Pull data
def process_data(ti):
    extracted = ti.xcom_pull(task_ids='extract')
    print(f"Record count: {extracted['count']}")

task2 = PythonOperator(
    task_id='process',
    python_callable=process_data,
    dag=dag,
)
```

### 4. Timeouts

Always set reasonable timeouts:

```python
# ✅ Specific timeout for each operator
extract_task = PythonOperator(
    task_id='extract',
    python_callable=extract_callable,
    execution_timeout=timedelta(minutes=10),
    dag=dag,
)

# ✅ Sensor timeout
sensor_task = PythonSensor(
    task_id='wait',
    python_callable=check_status,
    timeout=1800,        # 30 minutes
    poke_interval=60,    # Check every 60 seconds
    dag=dag,
)
```

### 5. Logging

Use consistent logging utilities:

```python
from utils.logging_utils import log_info, log_ok, log_fail, log_warning

def task_callable():
    log_info("Task starting")
    
    try:
        result = perform_work()
        log_ok(f"Task completed: {result}")
    except ValueError as e:
        log_warning(f"Non-critical issue: {e}")
    except Exception as e:
        log_fail(f"Task failed: {e}")
        raise
```

### 6. Documentation

Document DAGs and tasks:

```python
dag = DAG(
    dag_id='my_pipeline',
    description='''
    Daily air quality data extraction and transformation.
    
    Flow:
    1. Extract data from OpenAQ API
    2. Transform with Glue job
    3. Update Glue catalog
    4. Validate in Athena
    
    Expected runtime: 10-15 minutes
    On failure: Retries 2x with 5min delay
    ''',
)

def task_callable():
    """
    Extract air quality measurements.
    
    Returns:
        dict: {
            'record_count': int,
            'locations': int,
            'parameters': list,
            'date_range': tuple
        }
    """
    ...
```

### 7. Avoid Common Pitfalls

```python
# ❌ BAD: Hardcoded values
database = 'my_database'
bucket = 'my-bucket'

# ✅ GOOD: Use config/constants
from utils.constants import ATHENA_DB, BUCKET_NAME
database = ATHENA_DB
bucket = BUCKET_NAME

# ❌ BAD: No error handling
result = external_api_call()
process(result)

# ✅ GOOD: Try/except with logging
try:
    result = external_api_call()
    process(result)
except Exception as e:
    log_fail(f"API call failed: {e}")
    raise

# ❌ BAD: No timeout
task = PythonOperator(task_id='long_task', python_callable=long_func)

# ✅ GOOD: Set timeout
task = PythonOperator(
    task_id='long_task',
    python_callable=long_func,
    execution_timeout=timedelta(hours=2),
)
```

---

## Troubleshooting

### Issue 1: DAG Not Appearing in UI

**Symptom**: Created DAG file but it doesn't appear in Airflow web UI

**Solution**:
```bash
# 1. Check file syntax
python dags/your_dag.py
# Should run without errors

# 2. Check Airflow logs for parsing errors
docker-compose logs airflow-scheduler | grep "Error"

# 3. List DAGs to verify parsing
docker-compose exec airflow-webserver airflow dags list

# 4. Force DAG rescan
docker-compose exec airflow-webserver airflow dags reserialize

# 5. Restart scheduler
docker-compose restart airflow-scheduler
```

### Issue 2: Task Fails with Import Error

**Symptom**: Task fails with "ModuleNotFoundError: No module named 'etls'"

**Solution**:
```bash
# 1. Verify volume mount in docker-compose.yml
docker-compose ps
# Check volumes are mounted

# 2. Add sys.path for imports in DAG
import sys
sys.path.insert(0, '/opt/airflow')

# 3. Test import in container
docker-compose exec airflow-webserver python -c "from etls.openaq_etl import connect_openaq"
```

### Issue 3: XCom Pull Returns None

**Symptom**: xcom_pull returns None instead of expected data

**Solution**:
```python
# ✅ CORRECT: Return value in task callable
def extract_task():
    data = fetch_data()
    return data  # Must return data for XCom

# ❌ INCORRECT: No return
def extract_task():
    data = fetch_data()
    # Data not returned → XCom is None

# ✅ CORRECT: Use right task_id
def process_task(ti):
    data = ti.xcom_pull(task_ids='extract_openaq_raw')
    # Must match exact task_id

# ❌ INCORRECT: Wrong task_id
data = ti.xcom_pull(task_ids='extract')  # Task is 'extract_openaq_raw'
```

### Issue 4: Sensor Timeout

**Symptom**: Sensor task times out waiting for job to complete

**Solution**:
```bash
# 1. Check job status in CloudWatch
aws logs tail /aws-glue/jobs/output --follow

# 2. Increase timeout if job legitimately takes longer
wait_task = PythonSensor(
    task_id='wait_for_glue_job',
    python_callable=check_glue_job_status,
    timeout=7200,  # Increased to 2 hours
    poke_interval=60,  # Check every 60s
)

# 3. Verify check function returns True/False
def check_glue_job_status(job_run_id):
    status = glue_client.get_job_run(RunId=job_run_id)['JobRun']['JobRunState']
    return status == 'SUCCEEDED'  # Must return boolean
```

### Issue 5: DAG has Circular Dependency

**Symptom**: "A DAG cannot have circular dependencies"

**Solution**:
```python
# ❌ WRONG: Circular
task1 >> task2
task2 >> task3
task3 >> task1  # ERROR: Creates cycle

# ✅ CORRECT: Linear flow
task1 >> task2 >> task3

# ✅ CORRECT: Branching (allowed)
task1 >> [task2, task3]
[task2, task3] >> task4
```

---

## Related Documentation

- [Main Architecture Guide](../doc/architecture_en.md) - DAG orchestration details
- [Refactoring Guide](../doc/REFACTORING_GUIDE.md) - Code patterns used in DAGs
- [Airflow Documentation](https://airflow.apache.org/docs/apache-airflow/2.7.1/) - Official Airflow docs
- [Test README](../tests/README.md) - DAG testing patterns

---

**Maintained By**: OpenAQ Pipeline Team  
**Last Updated**: January 4, 2026
