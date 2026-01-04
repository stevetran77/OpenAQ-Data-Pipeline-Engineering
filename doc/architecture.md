# Architecture: OpenAQ v3 Data Pipeline

## 1. System Overview

This document describes the architecture of the OpenAQ air quality data pipeline for Vietnam. The pipeline extracts data from OpenAQ API v3, processes it with AWS Glue/Spark, stores it in S3, and serves it through Athena for downstream analytics in OWOX and Looker Studio.

### Key Objectives

- **Extract** air quality data from OpenAQ API v3 for all Vietnam locations
- **Store** immutable raw data as JSON.gz in S3 (zone-based architecture)
- **Transform** raw data to partitioned Parquet for analytics (dev/prod environments)
- **Orchestrate** pipeline with Apache Airflow (Docker local execution)
- **Analyze** data via Athena → OWOX → Looker Studio

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│               Orchestration Layer (Airflow 2.7.1)             │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ DAG: openaq_to_athena_pipeline                         │  │
│  │ Executor: LocalExecutor                                │  │
│  │ Metadata DB: PostgreSQL                                │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│             Extraction Layer (AWS Lambda)                     │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Function: openaq-fetcher (Python 3.11)                 │  │
│  │ - Step 1: GET /v3/locations (Vietnam)                  │  │
│  │ - Step 2: GET /v3/sensors/{id}/measurements            │  │
│  │ - Output: Raw JSON.gz → s3://aq_raw/                   │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│        Storage Layer (S3: openaq-data-pipeline bucket)        │
│  ┌──────────────┬──────────────┬──────────────────────────┐  │
│  │  aq_raw/     │  aq_dev/     │  aq_prod/                │  │
│  │  (Raw zone)  │  (Dev zone)  │  (Prod zone)             │  │
│  │  JSON.gz     │  Parquet     │  Parquet                 │  │
│  │  Immutable   │  Test/QA     │  Production dashboards   │  │
│  └──────────────┴──────────────┴──────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│         Transformation Layer (AWS Glue/PySpark 3.4.1)         │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Glue Jobs:                                             │  │
│  │ - process_openaq_raw_dev (aq_raw → aq_dev)            │  │
│  │ - process_openaq_raw_prod (aq_raw → aq_prod)          │  │
│  │ Operations: JSON flatten, enrich, pivot, partition     │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Glue Crawlers:                                         │  │
│  │ - raw-crawler (aq_raw → raw_db)                        │  │
│  │ - dev-crawler (aq_dev → dev_db)                        │  │
│  │ - prod-crawler (aq_prod → prod_db)                     │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              Catalog Layer (Glue Data Catalog)                │
│  ┌──────────────┬──────────────┬──────────────────────────┐  │
│  │  raw_db      │  dev_db      │  prod_db                 │  │
│  │  openaq_raw  │  vietnam     │  vietnam                 │  │
│  └──────────────┴──────────────┴──────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              Analytics Layer (AWS Athena)                     │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Workgroups: dev_workgroup, prod_workgroup             │  │
│  │ Databases: aq_dev, aq_prod                             │  │
│  │ Query results: s3://query-results/                     │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              Visualization Layer (OWOX → Looker)              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ OWOX data sources:                                     │  │
│  │ - aq_dev.vietnam (testing)                             │  │
│  │ - aq_prod.vietnam (production dashboards)              │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Zone-Based S3 Storage Architecture

Bucket: **`openaq-data-pipeline`**

### 3.1 Zone Structure

```
s3://openaq-data-pipeline/
├── aq_raw_test/              # Test raw data (7-day retention)
│   └── year=YYYY/
│       └── month=MM/
│           └── day=DD/
│               └── hour=HH/
│                   └── raw_openaq_YYYYMMDD_HHMMSS.json
│
├── aq_raw_prod/              # Production raw data (immutable)
│   └── year=YYYY/
│       └── month=MM/
│           └── day=DD/
│               └── hour=HH/
│                   └── raw_openaq_YYYYMMDD_HHMMSS.json
│
├── aq_dev/                   # Dev zone (Parquet)
│   └── marts/
│       └── vietnam/
│           └── measurement_date=YYYY-MM-DD/
│               └── country=Vietnam/
│                   └── part-00000.snappy.parquet
│
└── aq_prod/                  # Prod zone (Parquet)
    └── marts/
        └── vietnam/
            └── measurement_date=YYYY-MM-DD/
                └── country=Vietnam/
                    └── part-00000.snappy.parquet
```

### 3.2 Zone Characteristics

| Zone | Format | Retention | Purpose | Mutability |
|------|--------|-----------|---------|------------|
| `aq_raw_test/` | JSON | 7 days | Testing API integration | Auto-deleted |
| `aq_raw_prod/` | JSON.gz | Indefinite | Source of truth | Immutable |
| `aq_dev/` | Parquet | Indefinite | ETL testing, schema changes | Mutable |
| `aq_prod/` | Parquet | Indefinite | Production dashboards | Immutable (versioned updates) |

### 3.3 Environment Selection

Controlled via environment variable:

```python
# utils/constants.py
ENV = os.getenv('PIPELINE_ENV', 'dev')  # dev | prod

RAW_FOLDER_MAP = {
    'dev': 'aq_raw_test',
    'prod': 'aq_raw_prod'
}

ENV_FOLDER_MAP = {
    'dev': 'aq_dev',
    'prod': 'aq_prod'
}

# Usage
raw_path = f"s3://{BUCKET_NAME}/{RAW_FOLDER_MAP[ENV]}/..."
output_path = f"s3://{BUCKET_NAME}/{ENV_FOLDER_MAP[ENV]}/marts/..."
```

---

## 4. Data Flow Details

### 4.1 Extraction Layer (Lambda + OpenAQ API v3)

**Function**: `openaq-fetcher` (Python 3.11 runtime)

**Step 1 - Fetch Vietnam Locations**:
```http
GET https://api.openaq.org/v3/locations?countries_id=56&limit=100&page=1
```

Response contains:
- Location metadata (name, city, coordinates)
- List of sensors per location
- Parameter types (PM2.5, PM10, NO2, etc.)

**Step 2 - Fetch Measurements per Sensor**:
```http
GET https://api.openaq.org/v3/sensors/{sensor_id}/measurements?
    datetime_from=2024-01-15T00:00:00Z&
    datetime_to=2024-01-15T23:59:59Z&
    limit=1000
```

**Lambda Output**:
- Raw measurements in NDJSON format
- Uploaded to S3 with hive-style partitioning
- Metadata fields set to `null` (enriched later by Glue)

See [API_INTEGRATION.md](API_INTEGRATION.md) for complete API documentation.

### 4.2 Transformation Layer (AWS Glue)

**Job**: `process_openaq_raw` (PySpark 3.4.1)

**Input**:
```
s3://openaq-data-pipeline/aq_raw_prod/year=2024/month=01/day=15/
```

**Transformation Steps** (see [GLUE_JOBS_GUIDE.md](GLUE_JOBS_GUIDE.md)):

1. **Read NDJSON**: Load raw measurements from S3
2. **Parse Datetime**: Convert ISO 8601 strings to timestamps
3. **Deduplicate**: Remove duplicates by (location_id + datetime)
4. **Enrich**: Join with location metadata (coordinates, city)
5. **Pivot**: Transform long format (parameter, value) → wide format (pm25, pm10, no2 columns)
6. **Partition**: Add `measurement_date` and `country` columns
7. **Write Parquet**: Output to `aq_dev/` or `aq_prod/`

**Output**:
```
s3://openaq-data-pipeline/aq_prod/marts/vietnam/
  measurement_date=2024-01-15/
    country=Vietnam/
      part-00000.snappy.parquet
```

**Schema After Transformation**:
```python
{
    'location_id': int,
    'location_name': str,
    'city': str,
    'country': str,
    'latitude': float,
    'longitude': float,
    'datetime': timestamp,
    'measurement_date': date,
    'pm25': float,
    'pm10': float,
    'no2': float,
    'so2': float,
    'o3': float,
    'co': float
}
```

### 4.3 Cataloging Layer (Glue Crawlers)

**Crawlers**:

| Name | S3 Path | Database | Schedule |
|------|---------|----------|----------|
| `raw-crawler` | `aq_raw_prod/` | `raw_db` | On-demand |
| `dev-crawler` | `aq_dev/marts/` | `dev_db` | On-demand |
| `prod-crawler` | `aq_prod/marts/` | `prod_db` | On-demand |

**Operations**:
- Auto-infer schema from Parquet metadata
- Detect partitions (`measurement_date`, `country`)
- Update Glue Data Catalog tables
- Enable Athena queries without manual DDL

---

## 5. Orchestration (Apache Airflow)

### 5.1 Infrastructure

**Deployment**: Docker Compose with 3 containers
- `postgres`: Airflow metadata database
- `airflow-webserver`: UI (port 8080)
- `airflow-scheduler`: DAG execution

**Executor**: LocalExecutor (single-node, suitable for development/small workloads)

**Code Organization**:
```
dags/
  openaq_dag.py                # DAG definition
  tasks/
    extract_tasks.py           # Lambda invocation tasks
    glue_transform_tasks.py    # Glue job tasks
    catalog_tasks.py           # Crawler tasks
    validation_tasks.py        # Athena validation tasks

etls/
  openaq_etl.py                # API extraction logic

pipelines/
  openaq_pipeline.py           # Extraction orchestration
  glue_pipeline.py             # Glue job orchestration

utils/
  constants.py                 # Configuration constants
  logging_utils.py             # Shared logging functions
  aws_utils.py                 # S3, Athena clients
  glue_utils.py                # Glue job/crawler clients
```

### 5.2 DAG Flow

**DAG ID**: `openaq_to_athena_pipeline`  
**Schedule**: Manual (schedule_interval=None)  
**Catchup**: False

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

**Task Details**:

| Task ID | Operator | Purpose | Retries |
|---------|----------|---------|---------|
| `extract_openaq_raw` | `PythonOperator` | Call Lambda/direct extraction | 2 |
| `trigger_glue_job_transform` | `AwsGlueJobOperator` | Start Glue job | 3 |
| `wait_for_glue_job` | `PythonSensor` | Poll job status (60s interval) | 0 |
| `trigger_glue_crawler` | `GlueCrawlerOperator` | Start crawler | 3 |
| `wait_for_crawler` | `PythonSensor` | Poll crawler status (60s) | 0 |
| `validate_athena_table` | `PythonOperator` | Query Athena for data | 1 |

See [dags/openaq_dag.py](../dags/openaq_dag.py) for implementation.

### 5.3 Recent Refactoring (January 2026)

The orchestration layer underwent major refactoring for improved maintainability:

**New Modules**:
- `utils/logging_utils.py`: Centralized status logging (`log_info`, `log_ok`, `log_fail`, etc.)
- Execution constants: `DEFAULT_LOOKBACK_DAYS=7`, `API_REQUEST_TIMEOUT=30`, `CRAWLER_POLL_INTERVAL=60`

**Improvements**:
- Eliminated ~200 lines of duplicate logging code
- Extracted helper functions for complex operations:
  - `_parse_lambda_extraction_result()` in `glue_pipeline.py`
  - `_build_sensor_metadata_map()` in `openaq_etl.py`
- Replaced magic numbers with named constants
- Standardized error handling patterns

See [REFACTORING_GUIDE.md](REFACTORING_GUIDE.md) for complete patterns.

---

## 6. Analytics Layer

### 6.1 Athena Configuration

**Workgroups**:

| Workgroup | Database | Result Location | Purpose |
|-----------|----------|----------------|---------|
| `dev_workgroup` | `aq_dev` | `s3://.../aq_dev/query-results/` | Testing |
| `prod_workgroup` | `aq_prod` | `s3://.../aq_prod/query-results/` | Production |

**Example Query**:
```sql
SELECT
  location_name,
  city,
  measurement_date,
  AVG(pm25) AS avg_pm25,
  MAX(pm25) AS max_pm25
FROM aq_prod.vietnam
WHERE measurement_date BETWEEN DATE '2024-01-01' AND DATE '2024-01-31'
  AND city = 'Ho Chi Minh'
GROUP BY location_name, city, measurement_date
ORDER BY avg_pm25 DESC
LIMIT 10;
```

**Partition Pruning**:
- Queries automatically use `measurement_date` and `country` partitions
- Reduces scanned data and costs
- Example: `WHERE measurement_date = DATE '2024-01-15'` scans only that partition

### 6.2 OWOX Integration

OWOX connects to Athena to pull data into Google ecosystem:

**Data Sources**:
- `aq_dev.vietnam`: Testing/validation
- `aq_prod.vietnam`: Production dashboards

**Refresh Strategy**:
- Daily incremental updates (new partitions only)
- Full refresh on schema changes

### 6.3 Looker Studio Dashboards

**Datasets**:
- Dev environment: `aq_dev.vietnam`
- Prod environment: `aq_prod.vietnam`

**Typical Visualizations**:
- Time series: PM2.5 trends over time
- Heatmaps: Air quality by city/location
- Comparisons: Location-to-location AQI
- Alerts: Threshold exceedances (PM2.5 > 50 µg/m³)

---

## 7. Development vs Production Strategy

### 7.1 Shared Components

Both environments share:
- **Raw data** (`aq_raw_prod/`): Single source of truth, immutable
- **Extraction logic** (`etls/openaq_etl.py`): Same API integration
- **Transformation code** (`glue_jobs/process_openaq_raw.py`): Same PySpark job

### 7.2 Environment-Specific Resources

**Dev Environment** (`PIPELINE_ENV=dev`):
- S3 output: `aq_dev/marts/`
- Glue database: `dev_db`
- Glue job: `process_openaq_raw_dev`
- Glue crawler: `dev-crawler`
- Athena database: `aq_dev`
- Purpose: Test schema changes, ETL logic, new features

**Prod Environment** (`PIPELINE_ENV=prod`):
- S3 output: `aq_prod/marts/`
- Glue database: `prod_db`
- Glue job: `process_openaq_raw_prod`
- Glue crawler: `prod-crawler`
- Athena database: `aq_prod`
- Purpose: Stable pipeline for downstream consumers

### 7.3 Promotion Workflow

```
1. Develop in Dev
   - Modify transformation logic in glue_jobs/process_openaq_raw.py
   - Test with PIPELINE_ENV=dev
   - Validate output in Athena (aq_dev.vietnam)

2. Validate in Dev
   - Run integration tests (tests/test_e2e_glue_pipeline.py)
   - Compare row counts, schema, sample values

3. Promote to Prod
   - No code changes needed (same codebase)
   - Set PIPELINE_ENV=prod
   - Run DAG with prod configuration
   - Monitor in Athena (aq_prod.vietnam)

4. Monitor Prod
   - Check CloudWatch logs
   - Validate Looker Studio dashboards
   - Monitor data freshness
```

---

## 8. Infrastructure as Code

### 8.1 Docker Compose Stack

See [docker-compose.yml](../docker-compose.yml):

**Services**:
- `postgres`: PostgreSQL 13 for Airflow metadata
- `airflow-init`: One-time database initialization
- `airflow-webserver`: Web UI on port 8080
- `airflow-scheduler`: DAG scheduling and execution

**Volume Mounts**:
```yaml
volumes:
  - ./dags:/opt/airflow/dags           # DAG files
  - ./plugins:/opt/airflow/plugins     # Custom plugins
  - ./logs:/opt/airflow/logs           # Execution logs
  - ./etls:/opt/airflow/etls           # ETL modules
  - ./utils:/opt/airflow/utils         # Utilities
  - ./pipelines:/opt/airflow/pipelines # Pipeline orchestration
  - ./config:/opt/airflow/config       # Configuration files
```

**Key Feature**: Code changes on host immediately reflected in containers (hot reload)

### 8.2 AWS Resources

**Created via AWS Console** (Infrastructure as Code pending):

- S3 bucket: `openaq-data-pipeline`
- Lambda function: `openaq-fetcher`
- Glue databases: `raw_db`, `dev_db`, `prod_db`
- Glue jobs: `process_openaq_raw_dev`, `process_openaq_raw_prod`
- Glue crawlers: `raw-crawler`, `dev-crawler`, `prod-crawler`
- Athena workgroups: `dev_workgroup`, `prod_workgroup`

**Future**: Terraform/CloudFormation templates for reproducible infrastructure

---

## 9. Monitoring & Observability

### 9.1 Airflow Monitoring

**Web UI**: http://localhost:8080
- DAG runs: Success/failure status
- Task logs: Click task → View logs
- Gantt chart: Task execution timeline
- Calendar view: Historical run patterns

**Logs Location**:
```
logs/
  dag_id=openaq_to_athena_pipeline/
    run_id=manual__2024-01-15T10:00:00/
      task_id=extract_openaq_raw/
        attempt=1.log
```

### 9.2 AWS CloudWatch Logs

**Glue Jobs**:
- Log group: `/aws-glue/jobs/output`
- Filter by job name: `process_openaq_raw_dev`
- Typical queries:
  - `[INFO] Processing complete` - Success indicator
  - `[FAIL]` - Error indicator
  - `"Record count"` - Data volume

**Lambda Functions**:
- Log group: `/aws/lambda/openaq-fetcher`
- Filter patterns:
  - `ERROR` - Exceptions
  - `"Uploaded"` - Successful S3 uploads
  - `"Status code"` - API response codes

### 9.3 Data Quality Monitoring

**Validation Checks** (see [dags/tasks/validation_tasks.py](../dags/tasks/validation_tasks.py)):

```python
def validate_athena_table():
    """Ensure data exists in Athena after pipeline run."""
    query = f"""
        SELECT COUNT(*) AS record_count
        FROM {ENV}_db.vietnam
        WHERE measurement_date = CURRENT_DATE
    """
    results = execute_athena_query(query)
    
    if results == 0:
        raise ValueError("No data found in Athena for today")
    
    log_ok(f"Athena validation passed: {results} records")
```

**Metrics to Monitor**:
- Record count per partition
- Null percentage in key columns (pm25, location_id)
- Duplicates after deduplication step
- Partition freshness (latest measurement_date)

---

## 10. Security & Access Control

### 10.1 AWS IAM

**Glue Job Role** (`AWSGlueServiceRole-OpenAQ`):
- Permissions:
  - S3: Read `aq_raw/`, Write `aq_dev/`, `aq_prod/`
  - Glue: Access to Data Catalog
  - CloudWatch: Write logs

**Lambda Execution Role** (`openaq-fetcher-role`):
- Permissions:
  - S3: Write to `aq_raw/`
  - CloudWatch: Write logs

**Athena Query Role**:
- Permissions:
  - S3: Read `aq_dev/`, `aq_prod/`
  - Glue: Read Data Catalog
  - S3: Write query results

### 10.2 Secrets Management

**Configuration**:
```ini
# config/config.conf (gitignored)
[aws]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

[api_keys]
openaq_api_key = your_openaq_key_here
```

**Security Rules**:
- ❌ Never commit `config/config.conf`
- ✅ Use environment variables in production
- ✅ Rotate credentials quarterly
- ✅ Use AWS Secrets Manager for production deployments

---

## 11. Scalability Considerations

### 11.1 Current Limits

- **Lambda**: Extracts ~50 locations, ~150 sensors daily
  - Runtime: 3-5 minutes
  - Concurrency: 1 (sequential sensor fetching)

- **Glue Job**: Processes ~1500 measurements/day
  - DPUs: 2 (default)
  - Runtime: 2-3 minutes

- **Airflow**: LocalExecutor (single worker)
  - Parallel tasks: Limited to concurrent operator support
  - Not suitable for 100+ daily DAG runs

### 11.2 Scaling Path

**For 10x Data Volume**:
1. **Lambda**: Parallelize sensor fetching (concurrent invocations)
2. **Glue**: Increase DPUs (2 → 5 for faster processing)
3. **Airflow**: Migrate to CeleryExecutor + worker pool

**For Production Workloads**:
1. **Airflow**: Deploy on Amazon MWAA (Managed Workflows for Apache Airflow)
2. **Lambda**: Use Step Functions for orchestration (replace Airflow extraction step)
3. **Glue**: Enable job bookmarks for incremental processing
4. **S3**: Enable S3 Intelligent-Tiering for cost optimization

---

## 12. Disaster Recovery

### 12.1 Data Backup

- **Raw data** (`aq_raw_prod/`): Immutable, versioned via S3 versioning
- **Processed data** (`aq_prod/`): Regenerable from raw data
- **Metadata DB** (PostgreSQL): Daily snapshots via pg_dump

### 12.2 Recovery Procedures

**Scenario 1: Corrupted Prod Data**
```bash
# Re-run Glue job for specific date partition
aws glue start-job-run \
  --job-name process_openaq_raw_prod \
  --arguments='--measurement_date=2024-01-15'
```

**Scenario 2: Lost Glue Catalog**
```bash
# Re-crawl all prod data
aws glue start-crawler --name prod-crawler
```

**Scenario 3: Airflow Metadata Lost**
```bash
# Restore from latest pg_dump backup
docker-compose down
docker volume rm postgres-db-volume
docker-compose up -d postgres
docker exec -i postgres psql -U airflow < backup_2024-01-15.sql
```

---

## 13. Future Enhancements

### 13.1 Planned Features

- [ ] **Real-time Processing**: Replace batch Lambda with Kinesis Firehose
- [ ] **AQI Calculation**: Add Air Quality Index computation in Glue job
- [ ] **Alerting**: SNS notifications for data quality failures
- [ ] **Historical Backfill**: Ingest 2024 historical data (see [historical_backfill_2025_plan.md](historical_backfill_2025_plan.md))
- [ ] **Infrastructure as Code**: Terraform modules for all AWS resources

### 13.2 Performance Optimizations

- [ ] Glue job: Enable job bookmarks for incremental processing
- [ ] S3: Optimize Parquet file sizes (target: 128 MB per file)
- [ ] Athena: Create materialized views for common aggregations
- [ ] Lambda: Cache location metadata (reduce API calls by 50%)

---

## Related Documentation

- [Main README](../README.md) - Project overview and setup
- [Glue Jobs Guide](GLUE_JOBS_GUIDE.md) - Transformation logic details
- [API Integration](API_INTEGRATION.md) - OpenAQ API v3 integration
- [Refactoring Guide](REFACTORING_GUIDE.md) - Code patterns and standards
- [CLAUDE.md](../CLAUDE.md) - Comprehensive developer guide

---

**Document Version**: 2.0  
**Last Updated**: January 4, 2026  
**Maintained By**: OpenAQ Pipeline Team
