# AWS Lambda Functions

This directory contains serverless functions for the OpenAQ Data Pipeline. Lambda functions provide an alternative to Airflow operators for compute-intensive tasks.

---

## Table of Contents

1. [Overview](#overview)
2. [Lambda Functions](#lambda-functions)
3. [Architecture](#architecture)
4. [Deployment Strategy](#deployment-strategy)
5. [Configuration Management](#configuration-management)
6. [Integration with Airflow](#integration-with-airflow)
7. [Monitoring](#monitoring)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### Why Lambda Functions?

Lambda functions provide **serverless compute** for the OpenAQ pipeline, offering:

| Benefit | Details |
|---------|---------|
| **Scalability** | Auto-scales from 0 to 1000s of concurrent executions |
| **Cost-Effective** | Pay only for compute time used (sub-second billing) |
| **No Infrastructure** | AWS manages servers, patching, scaling |
| **Integration** | Direct access to AWS services (S3, Glue, CloudWatch) |
| **Resilience** | Built-in retry and error handling |
| **Monitoring** | CloudWatch Logs and Metrics integration |

### When to Use Lambda vs Airflow

**Use Lambda for**:
- ✅ Scheduled extraction (OpenAQ API fetching)
- ✅ Lightweight data transformations
- ✅ Event-driven workflows
- ✅ API integrations with short execution time

**Use Airflow for**:
- ✅ Long-running jobs (> 15 min)
- ✅ Complex multi-step orchestration
- ✅ Conditional logic and branching
- ✅ DAG-wide monitoring and alerting

### Current Implementation

The pipeline uses **Lambda for extraction** and **Airflow for orchestration**:

```
Airflow DAG (Orchestration)
    ↓
Airflow → LambdaInvokeFunctionOperator → Lambda Function
    ↓
Lambda ← Config from S3
    ↓
API Calls → OpenAQ API v3
    ↓
Lambda → Upload to S3 (aq_raw/)
    ↓
Glue Job (in Airflow) → Transform & Load
```

---

## Lambda Functions

### 1. `openaq-fetcher` (Main Function)

**Location**: [openaq_fetcher/](openaq_fetcher/)

**Purpose**: Extract air quality data from OpenAQ API v3 and upload raw data to S3

**Key Details**:
- **Runtime**: Python 3.11
- **Memory**: 1024 MB
- **Timeout**: 300 seconds (5 minutes)
- **Handler**: `handler.lambda_handler`
- **Input**: Event payload with extraction parameters
- **Output**: S3 path to raw NDJSON file + metadata

**Workflow**:
```
1. Load config from S3
   ↓
2. Fetch all Vietnam locations
   ↓
3. Filter active sensors (updated last 7 days)
   ↓
4. Extract measurements per sensor (hourly data)
   ↓
5. Transform measurements (flatten, normalize)
   ↓
6. Enrich with metadata (coordinates, city)
   ↓
7. Upload to S3 (aq_raw/YYYY/MM/DD/HH/)
```

**Configuration**:
```ini
# config/config.conf
[aws]
aws_access_key_id = YOUR_KEY
aws_secret_access_key = YOUR_SECRET
region_name = ap-southeast-1

[s3]
bucket_name = openaq-data-pipeline

[api_keys]
openaq_api_key = YOUR_OPENAQ_KEY
```

**Deployment**: See [openaq_fetcher/README.md](openaq_fetcher/README.md)

**Example Invocation** (from Airflow):
```python
from airflow.providers.amazon.aws.operators.lambda_function import LambdaInvokeFunctionOperator

lambda_task = LambdaInvokeFunctionOperator(
    task_id='fetch_openaq_data',
    function_name='openaq-fetcher',
    payload=json.dumps({
        'file_name': 'vietnam_national_20240115',
        'vietnam_wide': True,
        'lookback_hours': 24,
        'required_parameters': ['PM2.5', 'PM10', 'NO2']
    }),
    invocation_type='RequestResponse',
)
```

**Recent Improvements** (December 2025):
- ✅ Fixed critical parameter filtering bug (HCMC now included)
- ✅ Migrated to S3-based configuration (no hardcoded keys)
- ✅ Added comprehensive error handling
- ✅ Added detailed CloudWatch logging

**Documentation**: Full guide in [openaq_fetcher/README.md](openaq_fetcher/README.md)

---

## Architecture

### Folder Structure

```
lambda_functions/
├── README.md                           # This file
├── openaq_fetcher/                     # Main extraction function
│   ├── README.md                       # Deployment & usage guide
│   ├── handler.py                      # Lambda entry point
│   ├── extract_api.py                  # OpenAQ API logic
│   ├── s3_uploader.py                  # S3 upload logic
│   ├── requirements.txt                # Python dependencies
│   ├── deploy.ps1                      # Automated deployment script
│   ├── deployment/                     # Build artifacts (gitignored)
│   ├── test_data_sample.ndjson        # Test data for local testing
│   ├── etls/                           # Shared ETL modules
│   │   └── openaq_etl.py              # Core extraction functions
│   └── utils/                          # Shared utilities
│       ├── s3_utils.py                # S3 operations
│       └── config_utils.py            # Config loading
└── [future_functions]/                 # Placeholder for future functions
```

### Data Flow

**Complete Pipeline**:
```
┌─────────────────────────────────────────────────────────────────┐
│                    Airflow DAG (Orchestration)                  │
│                 openaq_to_athena_pipeline (daily)               │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │ extract_openaq_raw  │  (LambdaInvokeFunctionOperator)
        │ Task (Airflow)      │
        └────────┬────────────┘
                 │
                 ▼ Invoke
        ┌─────────────────────────────────────────────┐
        │   Lambda Function: openaq-fetcher           │
        │  ┌──────────────────────────────────────┐  │
        │  │ 1. Load Config from S3               │  │
        │  │ 2. Connect to OpenAQ API             │  │
        │  │ 3. Fetch Vietnam locations & sensors│  │
        │  │ 4. Filter active sensors (7-day)    │  │
        │  │ 5. Extract hourly measurements      │  │
        │  │ 6. Transform data (flatten, enrich) │  │
        │  │ 7. Upload to S3 (NDJSON)            │  │
        │  └──────────────────────────────────────┘  │
        │           Runtime: 3-5 minutes              │
        └────────┬────────────────────────────────────┘
                 │
                 ▼ S3 Upload
        s3://openaq-data-pipeline/
        └── aq_raw/YYYY/MM/DD/HH/
            └── raw_vietnam_national_*.json (NDJSON)
                 │
                 ▼ (back to Airflow)
        ┌─────────────────────────────────────────┐
        │ trigger_glue_job_transform (Airflow)   │
        │ → Glue Job reads aq_raw/, outputs Parquet to aq_prod/
        └─────────────────────────────────────────┘
```

### Lambda Execution Environment

**Runtime Details**:
- **Language**: Python 3.11
- **Execution Role**: `lambda-openaq-role` (AWS IAM)
- **Permissions**:
  - S3 read: `s3://openaq-data-pipeline/config/*`
  - S3 write: `s3://openaq-data-pipeline/aq_raw/*`
  - CloudWatch Logs: `/aws/lambda/openaq-fetcher`
- **Environment Variables** (optional):
  - `PIPELINE_ENV`: `dev` or `prod` (default: dev)
- **Max File Size**: 50 MB deployment package
- **Ephemeral Storage**: 512 MB (configurable up to 10 GB)

**Resource Allocation**:
- **Memory**: 1024 MB (512 MB for Python, 512 MB for data processing)
- **CPU**: Proportional to memory (1024 MB ≈ 0.33 vCPU)
- **Timeout**: 300 seconds (5 minutes) - enough for OpenAQ extraction

---

## Deployment Strategy

### Pre-Deployment Checklist

```
1. Configuration
   [ ] S3 bucket created: openaq-data-pipeline
   [ ] Config file uploaded: s3://openaq-data-pipeline/config/config.conf
   [ ] Config contains openaq_api_key
   
2. AWS IAM
   [ ] Role created: lambda-openaq-role
   [ ] Role has AmazonS3FullAccess (or custom S3 policy)
   [ ] Role has AWSLambdaBasicExecutionRole
   
3. Code
   [ ] Parameter filtering fix applied (see openaq_fetcher/README.md)
   [ ] All tests passing: pytest tests/
   [ ] Code linted: flake8 lambda_functions/
```

### Deployment Methods

#### Option 1: Automated PowerShell Script (Windows - Recommended)

```powershell
cd lambda_functions\openaq_fetcher
.\deploy.ps1
```

**What it does**:
1. Gets AWS account ID
2. Creates/verifies IAM role
3. Installs dependencies
4. Builds deployment package
5. Creates/updates Lambda function
6. Sets timeout, memory, environment variables

**Expected Output**:
```
[OK] Account ID: 387158739004
[OK] Role exists: arn:aws:iam::387158739004:role/lambda-openaq-role
[SUCCESS] Lambda Function Deployed!
Function Name: openaq-fetcher
Runtime: Python 3.11
Memory: 1024 MB
Timeout: 300 seconds
```

#### Option 2: Manual Deployment (Linux/Mac/Windows)

See [openaq_fetcher/README.md - Deployment Methods](openaq_fetcher/README.md#deployment-methods)

#### Option 3: AWS Console UI

1. AWS Console → Lambda → Create function
2. Upload `openaq-fetcher.zip` deployment package
3. Set timeout (300s) and memory (1024 MB)
4. Attach `lambda-openaq-role`

### Post-Deployment Verification

```bash
# 1. Check Lambda function exists and is updated
aws lambda get-function \
  --function-name openaq-fetcher \
  --region ap-southeast-1 | grep LastModified

# 2. Run test event
aws lambda invoke \
  --function-name openaq-fetcher \
  --payload '{"file_name":"test","vietnam_wide":true,"lookback_hours":24}' \
  --region ap-southeast-1 \
  response.json

# 3. Check CloudWatch logs
aws logs tail /aws/lambda/openaq-fetcher --follow --region ap-southeast-1

# 4. Verify S3 data uploaded
aws s3 ls s3://openaq-data-pipeline/aq_raw/ --recursive | tail -5

# 5. CRITICAL: Verify HCMC data (location ID 3276359)
aws s3 cp s3://openaq-data-pipeline/aq_raw/2025/12/29/XX/raw_*.json - \
  | grep -c 3276359
# Expected: >70 records from HCMC
```

---

## Configuration Management

### S3-Based Configuration

The Lambda function reads configuration from **S3** at runtime (not environment variables):

**File**: `s3://openaq-data-pipeline/config/config.conf`

```ini
[aws]
aws_access_key_id = YOUR_AWS_KEY
aws_secret_access_key = YOUR_AWS_SECRET
aws_session_token = 
region_name = ap-southeast-1

[database]
postgres_user = airflow
postgres_password = airflow
postgres_db = airflow_reddit

[s3]
bucket_name = openaq-data-pipeline

[api_keys]
openaq_api_key = YOUR_OPENAQ_KEY

[glue]
glue_job_name = process_openaq_raw
crawler_name_prefix = openaq-crawler

[athena]
database_name = aq_${PIPELINE_ENV}
output_location = s3://openaq-data-pipeline/athena-results/
```

### Why S3 Config?

✅ **Advantages**:
- No hardcoded credentials in Lambda environment
- Centralized configuration (same file for Airflow + Lambda)
- Easy to update without redeploying Lambda
- Secure credential storage (S3 access controlled by IAM)

❌ **Disadvantages**:
- Slight latency (S3 read at function start)
- Dependency on S3 availability

### Configuration Loading

**Function**: `handler.load_config_from_s3()`

```python
def load_config_from_s3(config_path: str = 'config/config.conf'):
    """Load configuration from S3."""
    import boto3
    import configparser
    
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    
    try:
        response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=config_path
        )
        config_content = response['Body'].read().decode('utf-8')
        config = configparser.ConfigParser()
        config.read_string(config_content)
        return config
    except Exception as e:
        print(f"[FAIL] Failed to load config from S3: {str(e)}")
        raise
```

### Environment Variable Overrides

Can be set in Lambda configuration (optional):

| Variable | Purpose | Default |
|----------|---------|---------|
| `PIPELINE_ENV` | Environment (dev/prod) | `dev` |
| `AWS_REGION` | AWS region | `ap-southeast-1` |
| `CONFIG_PATH` | S3 config location | `config/config.conf` |

---

## Integration with Airflow

### Airflow Task Creation

**File**: `dags/tasks/extract_tasks.py`

```python
from airflow.providers.amazon.aws.operators.lambda_function \
    import LambdaInvokeFunctionOperator
import json

def create_extract_tasks(dag):
    """Create Lambda invocation task."""
    
    payload = {
        'file_name': 'vietnam_national_{{ ts_nodash }}',
        'vietnam_wide': True,
        'lookback_hours': 24,
        'required_parameters': [
            'PM2.5', 'PM10', 'NO2', 'O3', 'SO2', 'CO', 'BC'
        ]
    }
    
    task = LambdaInvokeFunctionOperator(
        task_id='extract_openaq_raw',
        function_name='openaq-fetcher',
        payload=json.dumps(payload),
        aws_conn_id='aws_default',
        invocation_type='RequestResponse',
        log_type='Tail',
        dag=dag,
    )
    
    return task
```

### Airflow AWS Connection Setup

**Option 1: Environment Variable** (`airflow.env`):
```bash
AIRFLOW_CONN_AWS_DEFAULT=aws://ACCESS_KEY:SECRET@?region_name=ap-southeast-1
```

**Option 2: Airflow UI**:
1. Admin → Connections → Add Connection
2. Connection ID: `aws_default`
3. Connection Type: `Amazon Web Services`
4. AWS Access Key ID: Your access key
5. AWS Secret Access Key: Your secret key
6. Extra: `{"region_name": "ap-southeast-1"}`

### XCom Data Passing

Lambda response is automatically stored in XCom:

```python
def process_lambda_output(ti):
    """Retrieve Lambda output."""
    lambda_response = ti.xcom_pull(task_ids='extract_openaq_raw')
    
    status = lambda_response['statusCode']
    body = lambda_response['body']
    
    print(f"Lambda Status: {status}")
    print(f"Records Extracted: {body['record_count']}")
    print(f"S3 Path: {body['raw_s3_path']}")
```

---

## Monitoring

### CloudWatch Logs

**Log Group**: `/aws/lambda/openaq-fetcher`

**Log Format**: Consistent status indicators
```
[START] OpenAQ Lambda Extraction - 2025-12-28T07:30:00.123456
[INFO] Event payload: {...}
[1/8] Loading environment configuration...
[OK] Config loaded
[2/8] Validating event payload...
[OK] Event validated
...
[SUCCESS] Extraction complete
```

### View Logs

```bash
# Tail live logs
aws logs tail /aws/lambda/openaq-fetcher --follow --region ap-southeast-1

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/openaq-fetcher \
  --filter-pattern "[FAIL]" \
  --region ap-southeast-1

# View specific execution
aws logs filter-log-events \
  --log-group-name /aws/lambda/openaq-fetcher \
  --filter-pattern "2025-12-28T07:30" \
  --region ap-southeast-1
```

### CloudWatch Metrics

**Available Metrics**:
- `Duration` - Execution time (milliseconds)
- `Errors` - Number of failed invocations
- `Throttles` - Concurrency limit exceeded
- `ConcurrentExecutions` - Parallel executions
- `Invocations` - Total function calls

**Check Metrics**:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=openaq-fetcher \
  --statistics Average,Maximum \
  --start-time 2025-12-28T00:00:00Z \
  --end-time 2025-12-29T00:00:00Z \
  --period 3600 \
  --region ap-southeast-1
```

### Alarms (Optional)

Create CloudWatch alarm for failures:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name openaq-fetcher-failures \
  --alarm-description "Alert if Lambda fails" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --dimensions Name=FunctionName,Value=openaq-fetcher \
  --alarm-actions arn:aws:sns:ap-southeast-1:ACCOUNT_ID:email-topic
```

---

## Best Practices

### 1. Configuration Security

```python
# ✅ GOOD: Load from S3 (encrypted at rest)
config = load_config_from_s3()
api_key = config.get('api_keys', 'openaq_api_key')

# ❌ BAD: Hardcode in environment variable
api_key = os.getenv('OPENAQ_API_KEY')

# ❌ BAD: Hardcode in source code
api_key = 'your_api_key_here'
```

### 2. Error Handling

```python
# ✅ GOOD: Detailed error messages
try:
    data = fetch_data()
except requests.Timeout:
    log_fail(f"API timeout after {TIMEOUT} seconds")
    raise
except Exception as e:
    log_fail(f"Unexpected error: {type(e).__name__}: {str(e)}")
    raise

# ❌ BAD: Silent failures
try:
    data = fetch_data()
except:
    pass  # Swallows error
```

### 3. Logging Standards

```python
# ✅ GOOD: Consistent status indicators
log_info("Processing started")
log_ok("Config loaded successfully")
log_fail("API returned 429 (rate limit)")
log_warning("Sensor 123 has no recent data")

# ❌ BAD: Inconsistent logging
print("Starting...")
print(f"OK")
print("ERROR")
```

### 4. Resource Optimization

```python
# ✅ GOOD: Reuse connections
class LambdaContext:
    s3_client = None
    api_session = None

def handler(event, context):
    # Reuse s3_client across invocations
    if LambdaContext.s3_client is None:
        LambdaContext.s3_client = boto3.client('s3')
    return process(LambdaContext.s3_client)

# ❌ BAD: Create new connection per invocation
def handler(event, context):
    s3_client = boto3.client('s3')  # Creates new connection every time
    return process(s3_client)
```

### 5. Timeouts and Retries

```python
# ✅ GOOD: Set reasonable timeout
response = requests.get(
    url,
    timeout=30,  # 30 second timeout
    retries=Retry(total=3, backoff_factor=0.5)
)

# ❌ BAD: No timeout (request hangs indefinitely)
response = requests.get(url)
```

### 6. Cost Optimization

**Reduce Execution Time**:
```python
# ✅ GOOD: Cache location metadata (doesn't change hourly)
LOCATION_CACHE = {}
if not LOCATION_CACHE:
    LOCATION_CACHE = fetch_locations()  # Cache for 1 hour
locations = LOCATION_CACHE

# ❌ BAD: Fetch same data every invocation
locations = fetch_locations()  # Every Lambda execution
```

**Reduce Memory Usage**:
```python
# ✅ GOOD: Stream data processing
for measurement in stream_measurements():
    process(measurement)

# ❌ BAD: Load all data into memory
measurements = fetch_all_measurements()  # Could be 1GB+
for measurement in measurements:
    process(measurement)
```

---

## Troubleshooting

### Error 1: "Failed to load config from S3"

**Cause**: S3 config file not found or Lambda role lacks S3 read permission

**Solution**:
```bash
# 1. Verify config file exists
aws s3 ls s3://openaq-data-pipeline/config/config.conf

# 2. Check Lambda role has S3 read permission
aws iam list-attached-role-policies --role-name lambda-openaq-role

# 3. If missing, attach S3 policy
aws iam attach-role-policy \
  --role-name lambda-openaq-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
```

### Error 2: "openaq_api_key not found in config"

**Cause**: Config file doesn't contain required API key

**Solution**:
```bash
# 1. Check config file content
aws s3 cp s3://openaq-data-pipeline/config/config.conf - | grep openaq_api_key

# 2. Update config with API key
cat config/config.conf.example > config/config.conf
# Edit config.conf with your OpenAQ API key
aws s3 cp config/config.conf s3://openaq-data-pipeline/config/config.conf
```

### Error 3: "Task timeout after 300 seconds"

**Cause**: Lambda took too long (>5 min)

**Solution**:
1. **Increase timeout** (if extraction is complex):
   ```bash
   aws lambda update-function-configuration \
     --function-name openaq-fetcher \
     --timeout 600 \
     --region ap-southeast-1
   ```

2. **Reduce data volume** (limit lookback_hours in Airflow):
   ```python
   payload = {
       'lookback_hours': 12,  # Reduced from 24
   }
   ```

3. **Optimize code** (parallelize sensor fetching):
   - Use concurrent requests with ThreadPoolExecutor
   - Reduce API response parsing overhead

### Error 4: "User is not authorized to perform: s3:PutObject"

**Cause**: Lambda role lacks S3 write permission

**Solution**:
```bash
aws iam attach-role-policy \
  --role-name lambda-openaq-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
```

### Error 5: "No data in S3 after successful execution"

**Causes**:
1. No active sensors found (API returned empty list)
2. S3 upload failed silently
3. Lambda returned success but data was malformed

**Debug**:
```bash
# 1. Check CloudWatch logs for details
aws logs tail /aws/lambda/openaq-fetcher --follow --region ap-southeast-1

# 2. Look for "Active sensors" count
aws logs filter-log-events \
  --log-group-name /aws/lambda/openaq-fetcher \
  --filter-pattern "active_sensor_count" \
  --region ap-southeast-1

# 3. If sensor count is 0, check location filtering
# 4. If count > 0, check S3 upload success message
```

### Error 6: "HCMC data not appearing in S3"

**Cause**: Parameter filtering bug (if not using latest version)

**Solution**:
1. **Update Lambda** with latest code (parameter filtering fix):
   ```bash
   cd lambda_functions/openaq_fetcher
   .\deploy.ps1  # Redeploy with fix
   ```

2. **Verify fix is in place**:
   ```bash
   grep -A 5 "param_normalized" extract_api.py
   # Should show normalization logic
   ```

3. **Test with manual invocation**:
   ```bash
   aws lambda invoke \
     --function-name openaq-fetcher \
     --payload '{"file_name":"test_hcmc","vietnam_wide":true,"lookback_hours":24}' \
     --region ap-southeast-1 \
     response.json
   ```

4. **Verify HCMC in output**:
   ```bash
   aws s3 cp s3://openaq-data-pipeline/aq_raw/2025/12/29/XX/raw_test_hcmc.json - \
     | grep -c 3276359  # HCMC location ID
   # Expected: >70 records
   ```

---

## Related Documentation

- **Lambda Function**: [openaq_fetcher/README.md](openaq_fetcher/README.md) - Deployment and usage
- **Architecture**: [doc/architecture_en.md](../doc/architecture_en.md) - System design
- **Airflow Integration**: [dags/README.md](../dags/README.md) - DAG patterns
- **API Guide**: [doc/API_INTEGRATION.md](../doc/API_INTEGRATION.md) - OpenAQ API details
- **Bug Fix Report**: [doc/archive/LAMBDA_BUG_FIX_REPORT.md](../doc/archive/LAMBDA_BUG_FIX_REPORT.md) - Parameter filtering issue

---

## Quick Reference

### Deploy Lambda
```powershell
cd lambda_functions\openaq_fetcher
.\deploy.ps1
```

### Test Lambda
```bash
aws lambda invoke \
  --function-name openaq-fetcher \
  --payload '{"file_name":"test","vietnam_wide":true,"lookback_hours":24}' \
  --region ap-southeast-1 \
  response.json

cat response.json
```

### Monitor Logs
```bash
aws logs tail /aws/lambda/openaq-fetcher --follow --region ap-southeast-1
```

### Verify Data
```bash
aws s3 ls s3://openaq-data-pipeline/aq_raw/ --recursive | tail -5
```

### Check Config
```bash
aws s3 cp s3://openaq-data-pipeline/config/config.conf - | head -20
```

---

**Maintained By**: OpenAQ Pipeline Team  
**Last Updated**: January 4, 2026
