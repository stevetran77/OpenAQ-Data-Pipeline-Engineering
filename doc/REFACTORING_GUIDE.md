# Code Refactoring Guide

## Overview

This guide documents the code patterns and standards introduced during the January 2026 refactoring. All new code and updates to existing code should follow these patterns.

**Last Refactoring**: January 4, 2026  
**Files Affected**: 12 files across `etls/`, `pipelines/`, `utils/`, `dags/tasks/`, `glue_jobs/`

---

## Table of Contents

1. [Shared Logging Module](#shared-logging-module)
2. [Configuration Constants](#configuration-constants)
3. [Helper Function Patterns](#helper-function-patterns)
4. [Error Handling](#error-handling)
5. [Code Organization](#code-organization)
6. [Migration Guide](#migration-guide)

---

## Shared Logging Module

### Overview

**Location**: `utils/logging_utils.py`  
**Purpose**: Centralized logging functions with consistent formatting

### Available Functions

```python
from utils.logging_utils import (
    log_info,      # Informational messages
    log_ok,        # Successful operations
    log_success,   # Task/pipeline completion
    log_fail,      # Operation failures
    log_warning,   # Non-critical issues
    log_start      # Task/pipeline start
)
```

### Usage Examples

#### ❌ Old Pattern (Deprecated)
```python
print(f"[INFO] Processing {count} records")
print(f"[OK] Upload completed")
print(f"[SUCCESS] Pipeline finished")
print(f"[FAIL] Connection failed: {error}")
print(f"[WARNING] Sensor {sensor_id} skipped")
print(f"[START] Extraction pipeline")
```

#### ✅ New Pattern (Current)
```python
log_info(f"Processing {count} records")
log_ok("Upload completed")
log_success("Pipeline finished")
log_fail(f"Connection failed: {error}")
log_warning(f"Sensor {sensor_id} skipped")
log_start("Extraction pipeline")
```

### When to Use Each Function

| Function | Use Case | Example |
|----------|----------|---------|
| `log_info()` | General information, progress updates | `log_info("Fetching locations...")` |
| `log_ok()` | Single operation succeeded | `log_ok("S3 connection successful")` |
| `log_success()` | Complete task/pipeline finished | `log_success("ETL pipeline completed")` |
| `log_fail()` | Operation failed (before raising exception) | `log_fail(f"API error: {e}")` |
| `log_warning()` | Non-critical issue, continuing execution | `log_warning("Empty result, skipping")` |
| `log_start()` | Starting a major task/pipeline | `log_start("Triggering Glue job")` |

### Timestamp Support

```python
# Add timestamp to log message
log_info("Processing started", include_timestamp=True)
# Output: [INFO] 2026-01-04T10:30:00.123456 - Processing started
```

### AWS Glue Exception

**Note**: Glue jobs (`glue_jobs/*.py`) cannot import from `utils/` due to AWS Glue environment constraints. Use inline logging functions in Glue scripts:

```python
# In Glue jobs only
def log_info(msg: str):
    print(f"[INFO] {msg}")
    logger.info(msg)
```

---

## Configuration Constants

### Overview

**Location**: `utils/constants.py`  
**Purpose**: Replace magic numbers with named constants for better maintainability

### Available Constants

#### Sensor Filtering
```python
DEFAULT_LOOKBACK_DAYS = 7                    # Sensor activity window
DEFAULT_REQUIRED_PARAMETERS = [              # Air quality parameters
    'PM2.5', 'PM10', 'NO2', 'O3', 'SO2', 'CO', 'BC'
]
```

#### API Pagination
```python
DEFAULT_PAGE_SIZE = 100                      # API results per page (max 100)
DEFAULT_MEASUREMENT_LIMIT = 1000             # Measurements per sensor query
```

#### Timeouts (seconds)
```python
API_REQUEST_TIMEOUT = 30                     # HTTP request timeout
CRAWLER_DEFAULT_TIMEOUT = 1800               # Glue Crawler (30 min)
GLUE_JOB_DEFAULT_TIMEOUT = 7200              # Glue Job (2 hours)
```

#### Polling Intervals (seconds)
```python
LOG_PROGRESS_INTERVAL = 10                   # Log every N sensors
CRAWLER_POLL_INTERVAL = 60                   # Check crawler every 60s
GLUE_JOB_POLL_INTERVAL = 60                  # Check Glue job every 60s
```

### Usage Examples

#### ❌ Old Pattern (Magic Numbers)
```python
def fetch_locations(page_size=100):          # What is 100?
    pass

response = requests.get(url, timeout=30)     # Why 30?

if idx % 10 == 0:                            # What does 10 mean?
    log_progress()

filter_active_sensors(lookback_days=7)       # Why 7 days?
```

#### ✅ New Pattern (Named Constants)
```python
from utils.constants import (
    DEFAULT_PAGE_SIZE,
    API_REQUEST_TIMEOUT,
    LOG_PROGRESS_INTERVAL,
    DEFAULT_LOOKBACK_DAYS
)

def fetch_locations(page_size=DEFAULT_PAGE_SIZE):
    pass

response = requests.get(url, timeout=API_REQUEST_TIMEOUT)

if idx % LOG_PROGRESS_INTERVAL == 0:
    log_progress()

filter_active_sensors(lookback_days=DEFAULT_LOOKBACK_DAYS)
```

### When to Create New Constants

**Create a constant when**:
- ✅ Value used in 2+ places
- ✅ Value has business meaning (timeout, batch size, threshold)
- ✅ Value might need adjustment over time

**Don't create a constant for**:
- ❌ Single-use values
- ❌ Values inherent to algorithm (e.g., array index 0)
- ❌ Values that are truly arbitrary

---

## Helper Function Patterns

### Overview

**Purpose**: Break complex logic into focused, testable functions

### Naming Conventions

#### Private Helper Functions (Internal Use)
```python
def _build_sensor_metadata_map(locations: list) -> dict:
    """Extract sensor metadata from locations."""
    pass

def _parse_lambda_extraction_result(ti) -> dict:
    """Parse XCom data from Lambda task."""
    pass

def _count_tables_with_data(tables: list) -> int:
    """Count tables containing data."""
    pass
```

**Pattern**: Start with underscore `_` + verb + noun  
**Verbs**: `_build_`, `_parse_`, `_extract_`, `_count_`, `_validate_`, `_format_`

#### Public Utility Functions
```python
def get_s3_client():
    """Create and return authenticated S3 client."""
    pass

def upload_to_s3(data: pd.DataFrame, bucket: str, key: str):
    """Upload DataFrame to S3."""
    pass
```

**Pattern**: No underscore + verb + noun

### When to Extract Helper Functions

#### Complexity Thresholds

**Extract when**:
- ✅ Function > 50 lines
- ✅ Nested loops > 2 levels deep
- ✅ Complex conditional logic (> 3 nested if/else)
- ✅ Logic reused 2+ times
- ✅ Single Responsibility Principle violated

#### Example: Before Refactoring

```python
def enrich_measurements(df, locations):
    # 60 lines of nested loops and conditionals
    sensor_to_location = {}
    for loc in locations:
        loc_id = loc.get('id')
        loc_name = loc.get('name')
        locality = loc.get('locality')
        # ... 20 more lines ...
        for sensor in sensors:
            sensor_id = sensor.get('id')
            if sensor_id:
                sensor_to_location[sensor_id] = {...}
    
    # ... 30 more lines mapping DataFrame columns ...
```

#### Example: After Refactoring

```python
def enrich_measurements(df, locations):
    """Enrich measurements with location metadata."""
    sensor_to_location = _build_sensor_metadata_map(locations)
    return _apply_metadata_to_dataframe(df, sensor_to_location)


def _build_sensor_metadata_map(locations: list) -> dict:
    """Build sensor ID to metadata mapping."""
    sensor_map = {}
    for loc in locations:
        metadata = _extract_location_metadata(loc)
        for sensor in loc.get('sensors', []):
            if sensor_id := sensor.get('id'):
                sensor_map[sensor_id] = metadata
    return sensor_map


def _extract_location_metadata(location: dict) -> dict:
    """Extract metadata from single location object."""
    country = location.get('country', {})
    coords = location.get('coordinates', {})
    
    return {
        'location_id': location.get('id'),
        'location_name': location.get('name'),
        'city': location.get('locality'),
        'country_code': country.get('code') if isinstance(country, dict) else 'VN',
        'latitude': coords.get('latitude') if coords else None,
        'longitude': coords.get('longitude') if coords else None
    }


def _apply_metadata_to_dataframe(df, metadata_map):
    """Apply metadata mapping to DataFrame columns."""
    df['location_id'] = df['sensor_id'].map(lambda x: metadata_map.get(x, {}).get('location_id'))
    # ... more mappings ...
    return df
```

**Benefits**:
- ✅ Main function reduced from 60 → 3 lines
- ✅ Each helper has single, clear purpose
- ✅ Easier to test individual pieces
- ✅ Easier to understand data flow

---

## Error Handling

### Pattern: Log Before Raise

```python
# ❌ Old Pattern
def fetch_data():
    try:
        response = api.get()
    except Exception as e:
        raise  # No context logged

# ✅ New Pattern
def fetch_data():
    try:
        response = api.get()
    except Exception as e:
        log_fail(f"Failed to fetch data: {str(e)}")
        raise
```

### Pattern: Meaningful Error Messages

```python
# ❌ Generic
log_fail("Error occurred")

# ✅ Specific
log_fail(f"API Error {response.status_code}: {response.text}")
log_fail(f"Failed to extract sensor {sensor_id}: {str(e)}")
log_fail(f"S3 upload failed for key {key}: {str(e)}")
```

### Pattern: Warning vs Fail

```python
# Use log_warning for recoverable errors
for sensor_id in sensor_ids:
    try:
        extract_sensor_data(sensor_id)
    except Exception as e:
        log_warning(f"Failed to extract sensor {sensor_id}: {str(e)}")
        continue  # Skip and continue

# Use log_fail for critical errors
try:
    start_glue_job(job_name)
except Exception as e:
    log_fail(f"Failed to start Glue job: {str(e)}")
    raise  # Stop execution
```

---

## Code Organization

### File Structure

```
utils/
├── __init__.py
├── logging_utils.py        # [NEW] Shared logging
├── constants.py            # [UPDATED] Added execution constants
├── aws_utils.py            # AWS S3 operations
├── glue_utils.py           # AWS Glue operations
└── athena_utils.py         # AWS Athena operations
```

### Import Order

```python
# Standard library
import os
import json
from datetime import datetime

# Third-party
import boto3
import pandas as pd
import requests

# Local - constants first
from utils.constants import (
    OPENAQ_API_KEY,
    DEFAULT_PAGE_SIZE,
    API_REQUEST_TIMEOUT
)

# Local - logging second
from utils.logging_utils import log_info, log_ok, log_success, log_fail

# Local - other utilities
from utils.aws_utils import get_s3_client
```

### Function Documentation

```python
def extract_measurements(headers: dict, sensor_ids: list,
                        date_from: datetime, date_to: datetime) -> list:
    """
    Extract hourly air quality measurements from sensors.

    Fetches measurements from OpenAQ API for each sensor ID in the specified
    date range. Returns raw measurement data with sensor_id, datetime, value, etc.

    Args:
        headers: API authentication headers from connect_openaq()
        sensor_ids: List of sensor IDs to fetch measurements from
        date_from: Start datetime (UTC)
        date_to: End datetime (UTC)

    Returns:
        list: Measurement records, each with:
              {sensor_id, datetime, value, parameter, unit}

    Raises:
        (No exception raised - continues on individual sensor failures)
    """
    pass
```

**Required sections**:
- Short description (1 sentence)
- Detailed description (if needed)
- Args with types
- Returns with type and structure
- Raises (if any)

---

## Migration Guide

### Migrating Existing Code

#### Step 1: Add Logging Import
```python
# Add to top of file
from utils.logging_utils import log_info, log_ok, log_success, log_fail, log_warning
```

#### Step 2: Replace Print Statements
```bash
# Find all print statements
grep -n "print(f\"\[" your_file.py

# Replace manually (avoid sed for safety)
print(f"[INFO] ...") → log_info("...")
print(f"[OK] ...") → log_ok("...")
```

#### Step 3: Extract Magic Numbers
```python
# Identify magic numbers
grep -n "timeout=" your_file.py
grep -n "page_size=" your_file.py

# Add to utils/constants.py if reusable
# Import in your file
```

#### Step 4: Extract Complex Logic
```python
# Identify candidates (functions > 50 lines)
# Look for nested loops
# Extract to _helper_functions()
```

#### Step 5: Test
```bash
# Run tests to verify refactoring didn't break functionality
pytest tests/test_your_module.py -v
```

### Checklist for Code Reviews

- [ ] Uses `log_*()` functions instead of `print()`
- [ ] No magic numbers (uses named constants)
- [ ] Functions < 50 lines (or well-justified)
- [ ] Helper functions follow `_verb_noun()` naming
- [ ] Error messages are specific and actionable
- [ ] Docstrings present for public functions
- [ ] Imports organized (stdlib → 3rd party → local)

---

## Anti-Patterns to Avoid

### ❌ Don't Mix Logging Styles
```python
# Bad: Mixing old and new
log_info("Starting process")
print("[OK] Process completed")  # ❌ Should use log_ok()
```

### ❌ Don't Create Overly Granular Helpers
```python
# Bad: Too granular
def _get_id(obj):
    return obj.get('id')

# Good: Inline simple operations
location_id = location.get('id')
```

### ❌ Don't Ignore Constant Naming Convention
```python
# Bad: Unclear naming
TIMEOUT = 30
SIZE = 100

# Good: Descriptive naming
API_REQUEST_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 100
```

---

## Examples from Production Code

### Example 1: ETL Module Refactoring

**File**: `etls/openaq_etl.py`

**Before** (201 lines, 3 main functions):
```python
def enrich_measurements_with_metadata(df, locations):
    # 60 lines of nested loops
    sensor_to_location = {}
    for loc in locations:
        # 30 lines of metadata extraction
        for sensor in sensors:
            # 20 lines of mapping logic
```

**After** (201 lines, 6 functions - same total, better organized):
```python
def enrich_measurements_with_metadata(df, locations):
    sensor_to_location = _build_sensor_metadata_map(locations)
    return _apply_metadata_mappings(df, sensor_to_location)

def _build_sensor_metadata_map(locations):
    # 15 lines - focused on building map

def _extract_location_metadata(location):
    # 10 lines - focused on single location
```

### Example 2: Pipeline Refactoring

**File**: `pipelines/glue_pipeline.py`

**Before**:
```python
def trigger_glue_transform_job(**context):
    ti = context['ti']
    # 50 lines of XCom parsing
    extraction_result = ti.xcom_pull(...)
    if isinstance(extraction_result, str):
        extraction_result = json.loads(...)
    # ... 30 more lines ...
```

**After**:
```python
def trigger_glue_transform_job(**context):
    extraction_result = _parse_lambda_extraction_result(context['ti'])
    job_arguments = _build_glue_job_arguments(country_folder, raw_s3_path)
    run_id = start_glue_job(job_name, job_arguments)
    return run_id

def _parse_lambda_extraction_result(ti):
    # 50 lines - isolated XCom parsing logic
```

---

## Related Documentation

- [Main README](../README.md) - Project overview
- [Glue Jobs Guide](GLUE_JOBS_GUIDE.md) - Glue job documentation
- [API Integration Guide](API_INTEGRATION.md) - OpenAQ API details

---

**Maintained By**: OpenAQ Pipeline Team  
**Last Updated**: January 4, 2026
