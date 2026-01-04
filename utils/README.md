# Utils Directory

Shared utility modules providing reusable functions for AWS integration, configuration management, logging, and common operations across the pipeline.

---

## Table of Contents

1. [Overview](#overview)
2. [Utility Modules](#utility-modules)
3. [Configuration System](#configuration-system)
4. [Logging Standards](#logging-standards)
5. [AWS Utilities](#aws-utilities)
6. [Usage Examples](#usage-examples)
7. [Best Practices](#best-practices)

---

## Overview

### Purpose

Utils provide **shared infrastructure** across the entire pipeline:

```
ETL Modules (etls/)
    ↓
Pipeline Modules (pipelines/)
    ↓
Utils (utils/) ← Shared across all
    ↓
External Systems (AWS S3, Glue, Athena, CloudWatch)
```

### What's Included

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `constants.py` | Configuration constants | `OPENAQ_API_KEY`, `ENV_FOLDER_MAP`, timeouts |
| `logging_utils.py` | Shared logging functions | `log_info()`, `log_ok()`, `log_fail()` |
| `aws_utils.py` | AWS S3 operations | `get_s3_client()`, `upload_to_s3()`, `query_athena()` |
| `glue_utils.py` | AWS Glue operations | `get_glue_client()`, `get_job_status()` |
| `athena_utils.py` | AWS Athena queries | `execute_query()`, `get_query_results()` |

---

## Utility Modules

### 1. `constants.py` - Configuration Management

**Purpose**: Single source of truth for configuration values

**Key Sections**:

#### Environment Configuration
```python
# Load from environment variable
PIPELINE_ENV = os.getenv('PIPELINE_ENV', 'dev')

# Environment-aware resource naming
ENV_FOLDER_MAP = {
    'dev': 'aq_dev',
    'prod': 'aq_prod'
}

RAW_FOLDER_MAP = {
    'dev': 'aq_raw_test',
    'prod': 'aq_raw_prod'
}

# Usage
output_folder = ENV_FOLDER_MAP[PIPELINE_ENV]  # aq_dev or aq_prod
raw_folder = RAW_FOLDER_MAP[PIPELINE_ENV]     # aq_raw_test or aq_raw_prod
```

#### API Configuration
```python
OPENAQ_API_KEY = config.get('api_keys', 'openaq_api_key')
API_REQUEST_TIMEOUT = 30  # seconds
DEFAULT_PAGE_SIZE = 100
DEFAULT_MEASUREMENT_LIMIT = 1000
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_REQUIRED_PARAMETERS = ['PM2.5', 'PM10', 'NO2', 'O3', 'SO2', 'CO', 'BC']
```

#### AWS Configuration
```python
AWS_REGION = config.get('aws', 'region_name')
BUCKET_NAME = config.get('s3', 'bucket_name')
AWS_ACCESS_KEY = config.get('aws', 'aws_access_key_id')
AWS_SECRET_KEY = config.get('aws', 'aws_secret_access_key')
```

#### Execution Timeouts
```python
CRAWLER_POLL_INTERVAL = 60        # seconds
CRAWLER_DEFAULT_TIMEOUT = 1800    # 30 minutes
GLUE_JOB_POLL_INTERVAL = 60       # seconds
GLUE_JOB_DEFAULT_TIMEOUT = 7200   # 2 hours
ATHENA_QUERY_TIMEOUT = 600        # 10 minutes
LOG_PROGRESS_INTERVAL = 10        # Log every 10 items
```

**ConfigParser Integration**:
```python
import configparser
import os

config = configparser.ConfigParser()
config_path = os.path.expanduser('config/config.conf')
config.read(config_path)

# Safe access with defaults
OPENAQ_API_KEY = config.get('api_keys', 'openaq_api_key', fallback=None)
```

**Usage**:
```python
from utils.constants import (
    PIPELINE_ENV,
    ENV_FOLDER_MAP,
    DEFAULT_LOOKBACK_DAYS,
    API_REQUEST_TIMEOUT,
)

# Build S3 path
s3_path = f"s3://bucket/{ENV_FOLDER_MAP[PIPELINE_ENV]}/data/"

# Use timeout
response = requests.get(url, timeout=API_REQUEST_TIMEOUT)
```

### 2. `logging_utils.py` - Shared Logging

**Purpose**: Consistent status logging across all modules

**Functions**:

```python
def log_info(message: str):
    """Log informational message."""
    print(f"[INFO] {message}")

def log_ok(message: str):
    """Log successful operation."""
    print(f"[OK] {message}")

def log_success(message: str):
    """Log pipeline/task completion."""
    print(f"[SUCCESS] {message}")

def log_fail(message: str):
    """Log operation failure (before raising exception)."""
    print(f"[FAIL] {message}")

def log_warning(message: str):
    """Log non-critical warning."""
    print(f"[WARNING] {message}")

def log_start(message: str):
    """Log task/pipeline start."""
    print(f"[START] {message}")
```

**Status Indicators** (Text-based, no emojis):
- `[INFO]` - Informational messages
- `[OK]` - Operation succeeded
- `[SUCCESS]` - Task/pipeline completed
- `[FAIL]` - Operation failed (before raising)
- `[WARNING]` - Non-critical issues
- `[START]` - Task/pipeline starting

**Usage**:
```python
from utils.logging_utils import log_info, log_ok, log_fail

def extract_data():
    log_start("Data extraction")
    
    try:
        log_info("Loading config")
        config = load_config()
        log_ok("Config loaded")
        
        log_info("Fetching data")
        data = fetch_data(config)
        log_ok(f"Fetched {len(data)} records")
        
        log_success("Extraction complete")
        return data
        
    except Exception as e:
        log_fail(f"Extraction failed: {str(e)}")
        raise
```

**CloudWatch Compatibility**:
All logs are CloudWatch-compatible and searchable:
```bash
# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/openaq-fetcher \
  --filter-pattern "[FAIL]"

# Search for warnings
aws logs filter-log-events \
  --filter-pattern "[WARNING]"
```

### 3. `aws_utils.py` - AWS S3 Operations

**Purpose**: Simplified S3 client creation and file operations

**Main Functions**:

```python
def get_s3_client(
    access_key: str = None,
    secret_key: str = None,
    region: str = None
):
    """
    Create boto3 S3 client with credentials.
    
    Uses config/config.conf if credentials not provided.
    """

def upload_to_s3(
    data: Union[str, pd.DataFrame],
    s3_path: str,
    format: str = 'json',
    replace: bool = False
) -> dict:
    """
    Upload data to S3.
    
    Args:
        data: String, dict, or DataFrame
        s3_path: s3://bucket/path/to/file.json
        format: 'json' (NDJSON) or 'parquet'
        replace: Overwrite if exists
    
    Returns:
        dict: {'status': 'SUCCESS', 'size_bytes': int}
    
    Examples:
        # Upload JSON
        upload_to_s3(
            data=measurements,
            s3_path='s3://bucket/aq_raw/data.json',
            format='json'
        )
        
        # Upload Parquet
        upload_to_s3(
            data=df,
            s3_path='s3://bucket/aq_prod/data.parquet',
            format='parquet'
        )
    """

def download_from_s3(s3_path: str) -> Union[str, pd.DataFrame]:
    """
    Download file from S3.
    
    Returns:
        String (JSON) or DataFrame (Parquet)
    """

def query_athena(
    query: str,
    database: str = 'aq_prod',
    output_location: str = 's3://bucket/query-results/',
    timeout_seconds: int = 600
) -> pd.DataFrame:
    """
    Execute Athena query and return results as DataFrame.
    
    Args:
        query: SQL query string
        database: Athena database name
        output_location: S3 path for query results
        timeout_seconds: Query timeout
    
    Returns:
        pd.DataFrame: Query results
    
    Example:
        df = query_athena(
            query="SELECT * FROM vietnam WHERE measurement_date = CURRENT_DATE",
            database='aq_prod'
        )
    """

def list_s3_objects(
    s3_path: str,
    recursive: bool = True
) -> list:
    """
    List objects in S3 path.
    
    Returns:
        list: Object keys
    """
```

**JSON Upload (NDJSON Format)**:
```python
measurements = [
    {'location_id': 18, 'pm25': 45.5, 'datetime': '2024-01-15T10:00:00'},
    {'location_id': 19, 'pm25': 32.1, 'datetime': '2024-01-15T10:00:00'},
]

# Uploaded as NDJSON (newline-delimited JSON)
upload_to_s3(
    data=measurements,
    s3_path='s3://openaq-data-pipeline/aq_raw/data.json',
    format='json'  # Uses lines=True for NDJSON
)

# File content:
# {"location_id": 18, "pm25": 45.5, ...}
# {"location_id": 19, "pm25": 32.1, ...}
```

**Usage**:
```python
from utils.aws_utils import get_s3_client, upload_to_s3

# Upload measurements
result = upload_to_s3(
    data=measurements_df,
    s3_path=f's3://openaq-data-pipeline/aq_raw/{partition}/data.json',
    format='json'
)

print(f"[SUCCESS] Uploaded {result['size_bytes']} bytes")
```

### 4. `glue_utils.py` - AWS Glue Operations

**Purpose**: Glue job and crawler management

**Main Functions**:

```python
def get_glue_client(
    access_key: str = None,
    secret_key: str = None,
    region: str = None
):
    """Create boto3 Glue client."""

def submit_glue_job(
    job_name: str,
    input_path: str,
    output_path: str,
    env: str = 'dev',
) -> str:
    """
    Submit Glue job for execution.
    
    Returns:
        job_run_id: Glue job run identifier
    """

def get_job_status(job_run_id: str, job_name: str) -> str:
    """
    Get Glue job status.
    
    Returns:
        'SUCCEEDED' | 'FAILED' | 'RUNNING' | 'STOPPING' | 'STOPPED'
    """

def get_job_metrics(job_run_id: str, job_name: str) -> dict:
    """
    Get job execution metrics.
    
    Returns:
        dict: {
            'total_records': int,
            'success_records': int,
            'failed_records': int,
            'execution_time': int,
        }
    """

def start_crawler(crawler_name: str) -> str:
    """
    Start Glue crawler.
    
    Returns:
        crawler_run_id
    """

def get_crawler_status(crawler_name: str) -> str:
    """
    Get crawler status.
    
    Returns:
        'READY' | 'RUNNING' | 'STOPPING' | 'ERROR'
    """
```

**Usage**:
```python
from utils.glue_utils import submit_glue_job, get_job_status

# Submit job
job_run_id = submit_glue_job(
    job_name='process_openaq_raw',
    input_path='s3://bucket/aq_raw/',
    output_path='s3://bucket/aq_prod/',
    env='prod'
)

# Check status
status = get_job_status(job_run_id, 'process_openaq_raw')
```

### 5. `athena_utils.py` - AWS Athena Queries

**Purpose**: Simplified Athena query execution

**Main Functions**:

```python
def execute_athena_query(
    query: str,
    database: str = 'aq_prod',
    output_location: str = None,
    timeout_seconds: int = 600
) -> pd.DataFrame:
    """
    Execute Athena query and return results.
    
    Args:
        query: SQL query string
        database: Athena database
        output_location: S3 path for results
        timeout_seconds: Query timeout
    
    Returns:
        pd.DataFrame: Query results
    
    Example:
        df = execute_athena_query(
            query='''
                SELECT location_name, AVG(pm25) as avg_pm25
                FROM vietnam
                WHERE measurement_date = CURRENT_DATE
                GROUP BY location_name
            ''',
            database='aq_prod'
        )
    """

def table_exists(table_name: str, database: str = 'aq_prod') -> bool:
    """Check if Athena table exists."""

def get_table_schema(table_name: str, database: str = 'aq_prod') -> dict:
    """Get table schema (columns and types)."""

def count_records(table_name: str, database: str = 'aq_prod') -> int:
    """Count records in table."""
```

**Usage**:
```python
from utils.athena_utils import execute_athena_query

# Query data
df = execute_athena_query(
    query="SELECT * FROM vietnam WHERE measurement_date = CURRENT_DATE LIMIT 10",
    database='aq_prod'
)

print(f"Found {len(df)} records")
print(df.head())
```

---

## Configuration System

### Configuration File Structure

**Location**: `config/config.conf` (gitignored for security)

```ini
[aws]
aws_access_key_id = YOUR_KEY_ID
aws_secret_access_key = YOUR_SECRET_KEY
aws_session_token = 
region_name = ap-southeast-1

[database]
postgres_user = airflow
postgres_password = airflow
postgres_db = airflow_reddit

[s3]
bucket_name = openaq-data-pipeline

[api_keys]
openaq_api_key = YOUR_API_KEY

[glue]
glue_job_name = process_openaq_raw
crawler_name_prefix = openaq-crawler

[athena]
database_name = aq_${PIPELINE_ENV}
output_location = s3://openaq-data-pipeline/athena-results/
```

### Configuration Loading

```python
import configparser
import os

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.expanduser('config/config.conf')
config.read(config_path)

# Access values
api_key = config.get('api_keys', 'openaq_api_key')
region = config.get('aws', 'region_name')
```

### Environment Variable Overrides

```python
# Environment variable takes precedence over config file
ENV = os.getenv('PIPELINE_ENV', 'dev')

# Environment-aware folder selection
folder = ENV_FOLDER_MAP.get(ENV, 'aq_dev')
```

---

## Logging Standards

### Consistent Logging Pattern

All modules follow this pattern:

```python
from utils.logging_utils import log_info, log_ok, log_fail

def process_data():
    log_start("Processing data")
    
    try:
        log_info("Step 1: Loading")
        data = load()
        log_ok("Data loaded")
        
        log_info("Step 2: Transforming")
        result = transform(data)
        log_ok("Data transformed")
        
        log_success("Processing complete")
        return result
    
    except Exception as e:
        log_fail(f"Processing failed: {str(e)}")
        raise
```

### CloudWatch Integration

Logs are automatically sent to CloudWatch (Lambda/Glue):

```bash
# View logs
aws logs tail /aws/lambda/openaq-fetcher --follow

# Search for patterns
aws logs filter-log-events \
  --log-group-name /aws/lambda/openaq-fetcher \
  --filter-pattern "[FAIL]"
```

---

## AWS Utilities

### S3 Operations

```python
from utils.aws_utils import upload_to_s3, download_from_s3

# Upload
upload_to_s3(
    data=df,
    s3_path='s3://bucket/data.parquet',
    format='parquet'
)

# Download
df = download_from_s3('s3://bucket/data.parquet')
```

### Athena Queries

```python
from utils.athena_utils import execute_athena_query

# Execute query
results = execute_athena_query(
    query="SELECT COUNT(*) as count FROM vietnam WHERE measurement_date = CURRENT_DATE",
    database='aq_prod'
)

print(results['count'][0])
```

### Glue Jobs

```python
from utils.glue_utils import submit_glue_job, get_job_status

# Start job
job_run_id = submit_glue_job(
    job_name='process_openaq_raw',
    input_path='s3://bucket/aq_raw/',
    output_path='s3://bucket/aq_prod/'
)

# Check status
status = get_job_status(job_run_id, 'process_openaq_raw')
```

---

## Usage Examples

### Example 1: Extract and Upload

```python
from utils.constants import BUCKET_NAME, DEFAULT_LOOKBACK_DAYS
from utils.aws_utils import upload_to_s3
from utils.logging_utils import log_info, log_ok

# Extract data
measurements = extract_api_data(lookback_days=DEFAULT_LOOKBACK_DAYS)

# Upload to S3
log_info(f"Uploading {len(measurements)} records to S3")
result = upload_to_s3(
    data=measurements,
    s3_path=f"s3://{BUCKET_NAME}/aq_raw/2025/01/15/data.json",
    format='json'
)
log_ok(f"Uploaded {result['size_bytes']} bytes")
```

### Example 2: Query Athena

```python
from utils.athena_utils import execute_athena_query
from utils.logging_utils import log_info

# Query data
log_info("Querying Athena for daily average PM2.5")
df = execute_athena_query(
    query="""
        SELECT 
            location_name,
            measurement_date,
            AVG(pm25) as avg_pm25,
            MAX(pm25) as max_pm25
        FROM vietnam
        WHERE measurement_date = CURRENT_DATE
        GROUP BY location_name, measurement_date
    """,
    database='aq_prod'
)

print(df)
```

### Example 3: Glue Job Management

```python
from utils.glue_utils import submit_glue_job, get_job_status
from utils.logging_utils import log_info, log_ok

# Submit job
log_info("Submitting Glue transformation job")
job_run_id = submit_glue_job(
    job_name='process_openaq_raw',
    input_path='s3://openaq-data-pipeline/aq_raw/',
    output_path='s3://openaq-data-pipeline/aq_prod/'
)
log_ok(f"Job submitted: {job_run_id}")

# Check status
status = get_job_status(job_run_id, 'process_openaq_raw')
log_info(f"Job status: {status}")
```

---

## Best Practices

### 1. Import Only What You Need

```python
# ✅ GOOD: Import specific items
from utils.constants import DEFAULT_LOOKBACK_DAYS, API_REQUEST_TIMEOUT
from utils.logging_utils import log_info, log_ok

# ❌ BAD: Import entire modules
from utils import *
```

### 2. Use Constants

```python
# ✅ GOOD: Use named constants
from utils.constants import API_REQUEST_TIMEOUT

response = requests.get(url, timeout=API_REQUEST_TIMEOUT)

# ❌ BAD: Magic numbers
response = requests.get(url, timeout=30)
```

### 3. Consistent Logging

```python
# ✅ GOOD: Use logging utilities
from utils.logging_utils import log_info, log_ok, log_fail

log_info("Processing started")
log_ok("Data loaded")

# ❌ BAD: Inconsistent logging
print("Processing...")
print("OK")
```

### 4. Error Handling

```python
# ✅ GOOD: Log then raise
try:
    data = process()
except Exception as e:
    log_fail(f"Processing failed: {str(e)}")
    raise

# ❌ BAD: Silent failures
try:
    data = process()
except:
    pass
```

### 5. Reuse Clients

```python
# ✅ GOOD: Reuse connections (in Lambda context)
class Context:
    s3_client = None

if Context.s3_client is None:
    Context.s3_client = get_s3_client()

# ❌ BAD: Create new client every time
s3_client = get_s3_client()  # Slow!
```

---

## Related Documentation

- [Architecture Guide](../doc/architecture_en.md) - System overview
- [Refactoring Guide](../doc/REFACTORING_GUIDE.md) - Code patterns
- [API Integration](../doc/API_INTEGRATION.md) - OpenAQ API usage
- [ETL Functions](../etls/README.md) - Extract/transform logic
- [Pipeline Modules](../pipelines/README.md) - Orchestration

---

## Quick Reference

### Constants
```python
from utils.constants import (
    PIPELINE_ENV,
    OPENAQ_API_KEY,
    DEFAULT_LOOKBACK_DAYS,
    BUCKET_NAME,
    ENV_FOLDER_MAP,
)
```

### Logging
```python
from utils.logging_utils import (
    log_info,
    log_ok,
    log_fail,
    log_warning,
    log_start,
    log_success,
)
```

### AWS S3
```python
from utils.aws_utils import (
    get_s3_client,
    upload_to_s3,
    download_from_s3,
    query_athena,
)
```

### AWS Glue
```python
from utils.glue_utils import (
    get_glue_client,
    submit_glue_job,
    get_job_status,
)
```

### AWS Athena
```python
from utils.athena_utils import (
    execute_athena_query,
    table_exists,
    count_records,
)
```

---

**Maintained By**: OpenAQ Pipeline Team  
**Last Updated**: January 4, 2026
