# AWS Glue Jobs Developer Guide

## Overview

This guide documents the AWS Glue PySpark jobs used in the OpenAQ Data Pipeline for transforming raw air quality data into queryable Parquet format.

---

## Job: `process_openaq_raw.py`

**Purpose**: Transform raw NDJSON measurements from OpenAQ API into structured, partitioned Parquet files ready for Athena queries.

**Runtime**: AWS Glue 3.0 (PySpark 3.4.1, Python 3.10)  
**Workers**: G.1X (2 workers)  
**Timeout**: 48 hours (2880 seconds)  
**Location**: `glue_jobs/process_openaq_raw.py`

---

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INPUT: S3 Raw Zone                                          │
│ s3://bucket/aq_raw/YYYY/MM/DD/HH/raw_*.json                │
│ Format: NDJSON (newline-delimited JSON)                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Read Raw Data                                       │
│ - Create DynamicFrame from S3                               │
│ - Convert to Spark DataFrame                                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Parse & Clean                                       │
│ - Parse ISO 8601 timestamps → Spark timestamp              │
│ - Extract partition columns (year, month, day)             │
│ - Deduplicate by (location_id + datetime)                  │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Pivot Parameters                                    │
│ - Transform from long format to wide format                 │
│ - Create columns: pm25, pm10, no2, so2, o3, co, bc        │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Enrich Metadata                                     │
│ - Join with location metadata                               │
│ - Add: city_name, country_code, latitude, longitude        │
│ - Fill null values with defaults                           │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: Validate                                            │
│ - Check critical columns exist                              │
│ - Count null values                                         │
│ - Log record counts                                         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT: S3 Marts Zone                                       │
│ s3://bucket/aq_dev/marts/vietnam/year=Y/month=M/day=D/     │
│ Format: Parquet (Snappy compression)                        │
│ Partitioning: Hive-style by year, month, day               │
└─────────────────────────────────────────────────────────────┘
```

---

## Job Parameters

The Glue job accepts the following parameters via `--arguments`:

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--input_path` | Yes | - | S3 path to raw NDJSON files (e.g., `s3://bucket/aq_raw/`) |
| `--output_path` | Yes | - | S3 path for output Parquet (e.g., `s3://bucket/aq_dev/marts/vietnam/`) |
| `--env` | Yes | `dev` | Environment: `dev` or `prod` (affects logging) |
| `--partition_cols` | Yes | `year,month,day` | Comma-separated partition column names |
| `--TempDir` | No | - | S3 temporary directory for Glue operations |

**Example**:
```python
job_arguments = {
    '--input_path': 's3://openaq-data-pipeline/aq_raw/',
    '--output_path': 's3://openaq-data-pipeline/aq_dev/marts/vietnam/',
    '--env': 'dev',
    '--partition_cols': 'year,month,day',
    '--TempDir': 's3://openaq-data-pipeline/glue-temp/'
}
```

---

## Input Schema

### Raw NDJSON Structure

Each line in the input JSON file represents a single measurement:

```json
{
  "location_id": 18,
  "datetime": "2024-01-15T10:00:00+07:00",
  "parameter": "pm25",
  "value": 45.5,
  "unit": "µg/m³",
  "city": "Hanoi",
  "country": "VN",
  "latitude": 21.0285,
  "longitude": 105.8542
}
```

**Key Fields**:
- `location_id` (int): OpenAQ location identifier
- `datetime` (string): ISO 8601 timestamp with timezone
- `parameter` (string): Pollutant name (pm25, pm10, no2, so2, o3, co, bc)
- `value` (float): Measurement value
- `unit` (string): Measurement unit
- `city`, `country`, `latitude`, `longitude`: Location metadata

---

## Output Schema

### Transformed Parquet Structure

**Partitioning**: Hive-style by `year=YYYY/month=MM/day=DD/`

**Columns**:

| Column | Type | Description | Nullable |
|--------|------|-------------|----------|
| `location_id` | string | OpenAQ location ID | No |
| `datetime` | timestamp | Measurement timestamp (UTC) | No |
| `pm25` | double | PM2.5 value (µg/m³) | Yes |
| `pm10` | double | PM10 value (µg/m³) | Yes |
| `no2` | double | NO2 value (µg/m³) | Yes |
| `so2` | double | SO2 value (µg/m³) | Yes |
| `o3` | double | O3 value (µg/m³) | Yes |
| `co` | double | CO value (ppm) | Yes |
| `bc` | double | Black carbon value (µg/m³) | Yes |
| `city_name` | string | City name | Yes |
| `country_code` | string | ISO country code | No |
| `latitude` | double | Location latitude | Yes |
| `longitude` | double | Location longitude | Yes |
| `year` | string | Year partition (YYYY) | No |
| `month` | string | Month partition (MM) | No |
| `day` | string | Day partition (DD) | No |

**Example Row**:
```
location_id: "18"
datetime: 2024-01-15 03:00:00
pm25: 45.5
pm10: 82.3
no2: 25.1
so2: 12.0
o3: 35.2
co: 0.8
bc: 3.5
city_name: "Hanoi"
country_code: "VN"
latitude: 21.0285
longitude: 105.8542
year: "2024"
month: "01"
day: "15"
```

---

## Transformation Logic

### 1. Datetime Parsing

```python
df_transformed = df_raw.withColumn(
    "datetime",
    F.col("datetime").cast("timestamp")
)
```

**Behavior**:
- Automatically handles ISO 8601 format with timezone (`2024-01-15T10:00:00+07:00`)
- Converts to UTC timestamp
- Invalid timestamps → null (dropped in later step)

### 2. Partition Column Extraction

```python
df_transformed = df_transformed \
    .withColumn("year", F.year(F.col("datetime"))) \
    .withColumn("month", F.lpad(F.month(F.col("datetime")), 2, '0')) \
    .withColumn("day", F.lpad(F.dayofmonth(F.col("datetime")), 2, '0'))
```

**Result**: `year=2024`, `month=01`, `day=15` (zero-padded)

### 3. Deduplication

```python
window_spec = Window.partitionBy("location_id", "datetime").orderBy(F.col("datetime"))
df_transformed = df_transformed.withColumn(
    "row_num",
    F.row_number().over(window_spec)
).filter(F.col("row_num") == 1).drop("row_num")
```

**Strategy**: Keep first occurrence when multiple records have same `location_id + datetime`

### 4. Parameter Pivoting

```python
df_pivoted = df_transformed.groupBy(
    F.col("location_id"),
    F.col("datetime"),
    F.col("year"),
    F.col("month"),
    F.col("day")
).pivot("parameter").agg(
    F.mean("value")
)
```

**Before** (long format):
```
location_id | datetime | parameter | value
18          | 10:00    | pm25      | 45.5
18          | 10:00    | pm10      | 82.3
```

**After** (wide format):
```
location_id | datetime | pm25 | pm10
18          | 10:00    | 45.5 | 82.3
```

### 5. Metadata Enrichment

```python
metadata_df = df_raw.select(
    F.col("location_id").cast("string"),
    F.col("city").cast("string").alias("city_name"),
    F.col("country").cast("string").alias("country_code"),
    F.col("latitude").cast("double"),
    F.col("longitude").cast("double")
).dropDuplicates(["location_id"])

df_enriched = df_pivoted.join(metadata_df, on="location_id", how="left")
```

**Null Handling**:
- `city_name`: Fill with "Unknown"
- `country_code`: Fill with "VN"
- `latitude`, `longitude`: Fill with 0.0

---

## Monitoring

### CloudWatch Logs

**Log Group**: `/aws-glue/jobs/output`  
**Log Stream**: `openaq_transform_measurements_dev` (or `_prod`)

**Key Log Patterns**:
```
[INFO] Initializing Glue Context...
[OK] Glue job initialized: openaq_transform_measurements_dev
[OK] Read 1520 raw records from s3://...
[OK] Transformed and deduplicated 1480 records
[OK] Pivoted 1450 records
[OK] Enriched 1450 records with location metadata
[SUCCESS] Written partitioned Parquet to s3://...
[SUCCESS] Glue job openaq_transform_measurements_dev completed successfully
```

**Error Indicators**:
```
[FAIL] Failed to read raw JSON: ...
[FAIL] Transformation failed: ...
[WARNING] Output DataFrame is empty!
```

### Metrics to Monitor

1. **Record Counts**:
   - Input records vs output records
   - Duplicate count (input - deduplicated)
   - Null value counts in critical columns

2. **Execution Time**:
   - Total job duration (typical: 3-5 minutes)
   - Alert if > 15 minutes

3. **Data Quality**:
   - Partitions created (should match input date range)
   - File sizes (typical: 50-200 KB per partition)
   - Schema validation (all expected columns present)

---

## Local Testing

### Prerequisites

1. **Java**: OpenJDK 11 or 17 (for PySpark)
2. **Python**: 3.10+
3. **Dependencies**:
   ```bash
   pip install pyspark==3.4.1 pandas pyarrow
   ```

### Test Data Setup

Create test NDJSON file `test_input.json`:
```json
{"location_id":18,"datetime":"2024-01-15T10:00:00+07:00","parameter":"pm25","value":45.5,"city":"Hanoi","country":"VN","latitude":21.0285,"longitude":105.8542}
{"location_id":18,"datetime":"2024-01-15T10:00:00+07:00","parameter":"pm10","value":82.3,"city":"Hanoi","country":"VN","latitude":21.0285,"longitude":105.8542}
```

### Run Locally

```python
from pyspark.sql import SparkSession

# Create Spark session
spark = SparkSession.builder \
    .appName("OpenAQ Test") \
    .master("local[*]") \
    .getOrCreate()

# Read test data
df = spark.read.json("test_input.json")

# Test transformation logic
df.show()
```

---

## Troubleshooting

### Issue: Job Timeout

**Symptom**: Job exceeds 48-hour timeout  
**Cause**: Too much data or inefficient transformations  
**Solution**:
- Reduce input date range
- Increase worker count
- Add data filters early in pipeline

### Issue: Memory Errors

**Symptom**: `java.lang.OutOfMemoryError`  
**Cause**: Large datasets don't fit in worker memory  
**Solution**:
- Use larger worker type (G.2X instead of G.1X)
- Repartition data: `df.repartition(10, "location_id")`
- Process data in smaller batches

### Issue: Schema Mismatch

**Symptom**: Athena queries fail with type errors  
**Cause**: Partition columns duplicated in Parquet files  
**Solution**: Ensure partition columns removed before write (already handled in code)

### Issue: Missing Data

**Symptom**: Record count drops significantly  
**Cause**: Deduplication too aggressive or datetime parsing failures  
**Solution**:
- Check input data quality
- Review deduplication window specification
- Validate datetime format matches ISO 8601

---

## Performance Optimization

### Best Practices

1. **Partitioning Strategy**:
   - Current: By `year/month/day` ✅
   - Avoids small files (< 1 MB)
   - Enables efficient Athena queries with date filters

2. **Compression**:
   - Snappy compression (default) ✅
   - Good balance between compression ratio and query speed

3. **File Size**:
   - Target: 128-256 MB per file
   - Use `coalesce()` if too many small files
   - Use `repartition()` if files too large

4. **Caching**:
   - Add `df.cache()` if reading same DataFrame multiple times
   - Call `df.unpersist()` when done to free memory

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2026-01-04 | Refactored with shared logging utilities |
| 1.1 | 2025-12-29 | Added metadata enrichment with city mapping |
| 1.0 | 2025-12-01 | Initial implementation |

---

## Related Documentation

- [Main README](../README.md) - Pipeline overview
- [Architecture Guide](architecture.md) - System architecture
- [API Integration Guide](API_INTEGRATION.md) - OpenAQ API details
- [Refactoring Guide](REFACTORING_GUIDE.md) - Code patterns

---

**Maintained By**: OpenAQ Pipeline Team  
**Last Updated**: January 4, 2026
