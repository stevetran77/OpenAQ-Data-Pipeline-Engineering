# OpenAQ API v3 Integration Guide

## Overview

This guide documents the integration with the OpenAQ API v3 for extracting air quality data. The integration is implemented in `etls/openaq_etl.py` and used by both Airflow tasks and AWS Lambda functions.

**API Version**: v3  
**Base URL**: `https://api.openaq.org/v3`  
**Documentation**: https://api.openaq.org/docs  
**Authentication**: API Key (X-API-Key header)

---

## Table of Contents

1. [Authentication](#authentication)
2. [Endpoints Used](#endpoints-used)
3. [Rate Limiting](#rate-limiting)
4. [Error Handling](#error-handling)
5. [Pagination](#pagination)
6. [Parameter Filtering](#parameter-filtering)
7. [Data Extraction Flow](#data-extraction-flow)
8. [Recent Bug Fixes](#recent-bug-fixes)

---

## Authentication

### API Key Setup

**Obtain API Key**:
1. Visit https://openaq.org/
2. Create account
3. Generate API key from dashboard

**Configuration**:
```ini
# config/config.conf
[api_keys]
openaq_api_key = your_api_key_here
```

**Usage in Code**:
```python
from utils.constants import OPENAQ_API_KEY

def connect_openaq(api_key: str = OPENAQ_API_KEY) -> dict:
    """Create headers for OpenAQ API authentication."""
    return {'X-API-Key': api_key}

# Use in requests
headers = connect_openaq()
response = requests.get(url, headers=headers)
```

**Security Notes**:
- ✅ Never commit API keys to version control
- ✅ Use environment variables in production
- ✅ Rotate keys periodically
- ✅ Monitor API usage for unauthorized access

---

## Endpoints Used

### 1. GET `/v3/locations`

**Purpose**: Fetch all monitoring locations in Vietnam

**Request**:
```http
GET https://api.openaq.org/v3/locations?countries_id=56&limit=100&page=1
Headers:
  X-API-Key: your_api_key
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `countries_id` | int | Yes | Country ID (56 = Vietnam) |
| `limit` | int | No | Results per page (max: 100, default: 100) |
| `page` | int | No | Page number (1-based) |

**Response**:
```json
{
  "meta": {
    "name": "openaq-api",
    "website": "https://docs.openaq.org/",
    "page": 1,
    "limit": 100,
    "found": 53
  },
  "results": [
    {
      "id": 18,
      "name": "CMT8-HCM",
      "locality": "Ho Chi Minh",
      "timezone": "Asia/Ho_Chi_Minh",
      "country": {
        "id": 56,
        "code": "VN",
        "name": "Vietnam"
      },
      "coordinates": {
        "latitude": 10.7769,
        "longitude": 106.7009
      },
      "datetimeLast": {
        "utc": "2024-01-15T10:00:00Z",
        "local": "2024-01-15T17:00:00+07:00"
      },
      "sensors": [
        {
          "id": 12345,
          "parameter": {
            "id": 2,
            "name": "pm25",
            "units": "µg/m³",
            "displayName": "PM2.5"
          }
        }
      ]
    }
  ]
}
```

**Implementation**:
```python
def fetch_all_vietnam_locations(headers: dict, countries_id: int = 56,
                                page_size: int = DEFAULT_PAGE_SIZE) -> tuple:
    """
    Fetch ALL Vietnam locations with pagination.
    
    Returns:
        tuple: (sensor_ids_list, location_objects_list)
    """
    all_locations = []
    sensor_ids = set()
    page = 1
    
    while True:
        params = {
            'countries_id': countries_id,
            'limit': page_size,
            'page': page
        }
        response = requests.get(
            f"{BASE_URL}/locations",
            headers=headers,
            params=params,
            timeout=API_REQUEST_TIMEOUT
        )
        
        if response.status_code != 200:
            log_fail(f"API Error {response.status_code}: {response.text}")
            break
            
        data = response.json()
        results = data.get('results', [])
        
        if not results:
            break
            
        # Extract sensor IDs
        for loc in results:
            for sensor in loc.get('sensors', []):
                if sensor_id := sensor.get('id'):
                    sensor_ids.add(sensor_id)
        
        all_locations.extend(results)
        page += 1
    
    return list(sensor_ids), all_locations
```

### 2. GET `/v3/sensors/{sensor_id}/measurements`

**Purpose**: Fetch measurements for a specific sensor

**Request**:
```http
GET https://api.openaq.org/v3/sensors/12345/measurements?datetime_from=2024-01-15T00:00:00Z&datetime_to=2024-01-15T23:59:59Z&limit=1000
Headers:
  X-API-Key: your_api_key
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sensor_id` | int | Yes | Sensor ID (from locations endpoint) |
| `datetime_from` | ISO 8601 | Yes | Start datetime (UTC) |
| `datetime_to` | ISO 8601 | Yes | End datetime (UTC) |
| `limit` | int | No | Max results (default: 1000, max: 10000) |

**Response**:
```json
{
  "meta": {
    "name": "openaq-api",
    "found": 24,
    "limit": 1000
  },
  "results": [
    {
      "value": 45.5,
      "parameter": {
        "id": 2,
        "name": "pm25",
        "units": "µg/m³"
      },
      "period": {
        "datetimeFrom": {
          "utc": "2024-01-15T10:00:00Z",
          "local": "2024-01-15T17:00:00+07:00"
        },
        "datetimeTo": {
          "utc": "2024-01-15T11:00:00Z",
          "local": "2024-01-15T18:00:00+07:00"
        },
        "interval": "1 hr"
      }
    }
  ]
}
```

**Implementation**:
```python
def extract_measurements(headers: dict, sensor_ids: list,
                        date_from: datetime, date_to: datetime) -> list:
    """Extract hourly air quality measurements from sensors."""
    all_measurements = []
    
    for idx, sensor_id in enumerate(sensor_ids, 1):
        try:
            meas_url = f"{BASE_URL}/sensors/{sensor_id}/measurements"
            meas_params = {
                'datetime_from': date_from.isoformat(),
                'datetime_to': date_to.isoformat(),
                'limit': DEFAULT_MEASUREMENT_LIMIT
            }
            
            response = requests.get(
                meas_url,
                headers=headers,
                params=meas_params,
                timeout=API_REQUEST_TIMEOUT
            )
            
            if response.status_code != 200:
                continue
                
            measurements = response.json().get('results', [])
            
            for m in measurements:
                period = m.get('period', {})
                dt_from = period.get('datetimeFrom', {})
                datetime_val = dt_from.get('utc')
                
                param_info = m.get('parameter', {})
                
                all_measurements.append({
                    'sensor_id': sensor_id,
                    'datetime': datetime_val,
                    'value': m.get('value'),
                    'parameter': param_info.get('name'),
                    'unit': param_info.get('units')
                })
            
            if idx % LOG_PROGRESS_INTERVAL == 0:
                log_info(f"Processed {idx}/{len(sensor_ids)} sensors")
                
        except Exception as e:
            log_warning(f"Failed to extract sensor {sensor_id}: {str(e)}")
            continue
    
    return all_measurements
```

---

## Rate Limiting

### Limits

| Tier | Requests/Minute | Requests/Hour | Requests/Day |
|------|----------------|---------------|--------------|
| Free | 60 | 1,000 | 10,000 |
| Pro | 300 | 10,000 | 100,000 |

**Current Implementation**: Free tier

### Handling Rate Limits

**Status Code**: `429 Too Many Requests`

**Response**:
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

**Best Practices**:
```python
import time

def make_api_request(url, headers, params, max_retries=3):
    """Make API request with rate limit handling."""
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            log_warning(f"Rate limit hit, waiting {retry_after}s")
            time.sleep(retry_after)
            continue
        
        return response
    
    raise Exception("Max retries exceeded")
```

**Optimization Strategies**:
1. ✅ Batch requests (fetch multiple sensors in parallel)
2. ✅ Cache location data (changes infrequently)
3. ✅ Use appropriate time ranges (avoid overlapping queries)
4. ✅ Filter inactive sensors (reduce unnecessary requests)

---

## Error Handling

### Common Error Codes

| Code | Meaning | Handling |
|------|---------|----------|
| 200 | Success | Process normally |
| 400 | Bad Request | Check parameters, log and skip |
| 401 | Unauthorized | Check API key, fail pipeline |
| 404 | Not Found | Log warning, continue |
| 429 | Rate Limit | Wait and retry |
| 500 | Server Error | Retry with exponential backoff |
| 503 | Service Unavailable | Retry after delay |

### Implementation Pattern

```python
def safe_api_request(url, headers, params):
    """Make API request with comprehensive error handling."""
    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=API_REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 400:
            log_fail(f"Bad request: {response.text}")
            return None
        elif response.status_code == 401:
            log_fail("Unauthorized - check API key")
            raise Exception("Invalid API key")
        elif response.status_code == 404:
            log_warning(f"Resource not found: {url}")
            return None
        elif response.status_code == 429:
            # Handle rate limiting
            time.sleep(60)
            return safe_api_request(url, headers, params)
        else:
            log_fail(f"API Error {response.status_code}: {response.text}")
            return None
            
    except requests.Timeout:
        log_warning(f"Request timeout for {url}")
        return None
    except requests.ConnectionError as e:
        log_fail(f"Connection error: {str(e)}")
        raise
```

---

## Pagination

### Strategy

OpenAQ API uses **offset-based pagination**:
- `page` parameter (1-based indexing)
- `limit` parameter (max 100 for locations, 10000 for measurements)

### Implementation

```python
def fetch_all_pages(base_url, headers, params):
    """Fetch all pages of results."""
    all_results = []
    page = 1
    
    while True:
        params['page'] = page
        response = requests.get(base_url, headers=headers, params=params)
        
        if response.status_code != 200:
            break
        
        data = response.json()
        results = data.get('results', [])
        
        if not results:
            log_info(f"Pagination complete at page {page}")
            break
        
        all_results.extend(results)
        log_info(f"Page {page}: +{len(results)} results (TOTAL: {len(all_results)})")
        page += 1
    
    return all_results
```

**Performance Tip**: For large datasets, use `limit=100` to minimize API calls.

---

## Parameter Filtering

### Available Parameters

OpenAQ tracks these air quality parameters:

| Parameter | Name in API | Unit | Description |
|-----------|-------------|------|-------------|
| PM2.5 | `pm25` | µg/m³ | Fine particulate matter |
| PM10 | `pm10` | µg/m³ | Coarse particulate matter |
| NO2 | `no2` | µg/m³ | Nitrogen dioxide |
| SO2 | `so2` | µg/m³ | Sulfur dioxide |
| O3 | `o3` | µg/m³ | Ozone |
| CO | `co` | ppm | Carbon monoxide |
| BC | `bc` | µg/m³ | Black carbon |

### Filtering Active Sensors

**Criteria**:
1. Sensor has data from last N days (default: 7)
2. Sensor measures at least one required parameter

**Implementation**:
```python
def filter_active_sensors(locations: list, 
                         lookback_days: int = DEFAULT_LOOKBACK_DAYS,
                         required_parameters: list = None) -> list:
    """Filter sensors by activity and required parameters."""
    if required_parameters is None:
        required_parameters = DEFAULT_REQUIRED_PARAMETERS
    
    active_sensor_ids = []
    cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
    
    for loc in locations:
        # Check last update time
        dt_last = loc.get('datetimeLast')
        if not dt_last:
            continue
        
        last_dt_str = dt_last.get('utc') if isinstance(dt_last, dict) else str(dt_last)
        last_datetime = pd.to_datetime(last_dt_str).replace(tzinfo=None)
        
        if last_datetime < cutoff_date:
            continue  # Skip inactive location
        
        # Check for required parameters
        for sensor in loc.get('sensors', []):
            param = sensor.get('parameter', {})
            param_name = param.get('name')
            
            # Normalize parameter names for matching
            if param_name and any(
                req.lower().replace('.', '').replace('_', '') in 
                param_name.lower().replace('.', '').replace('_', '')
                for req in required_parameters
            ):
                sensor_id = sensor.get('id')
                if sensor_id and sensor_id not in active_sensor_ids:
                    active_sensor_ids.append(sensor_id)
    
    return active_sensor_ids
```

### Parameter Name Normalization

**Issue**: Parameter names vary in format:
- API returns: `pm25`, `PM2.5`, `pm2.5`
- User specifies: `PM2.5`, `PM10`

**Solution**: Normalize for comparison
```python
def normalize_parameter_name(param: str) -> str:
    """Normalize parameter name for matching."""
    return param.lower().replace('.', '').replace('_', '')

# Example
normalize_parameter_name('PM2.5')  # → 'pm25'
normalize_parameter_name('pm25')    # → 'pm25'
normalize_parameter_name('pm2_5')   # → 'pm25'
```

---

## Data Extraction Flow

### Complete Pipeline

```
┌─────────────────────────────────────────────┐
│ 1. Authentication                            │
│    headers = connect_openaq(api_key)        │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 2. Fetch All Locations (Vietnam)            │
│    sensor_ids, locations =                  │
│      fetch_all_vietnam_locations(headers)   │
│    Result: 53 locations, 150 sensors        │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 3. Filter Active Sensors                    │
│    active_sensors =                         │
│      filter_active_sensors(locations)       │
│    Result: 39 active sensors                │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 4. Extract Measurements                     │
│    measurements =                           │
│      extract_measurements(                  │
│        headers, active_sensors,             │
│        date_from, date_to                   │
│      )                                      │
│    Result: 1520 measurement records         │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 5. Transform to DataFrame                   │
│    df = transform_measurements(measurements)│
│    Result: Structured DataFrame             │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 6. Enrich with Metadata                     │
│    df_enriched =                            │
│      enrich_measurements_with_metadata(     │
│        df, locations                        │
│      )                                      │
│    Result: DataFrame with city, coordinates │
└─────────────────────────────────────────────┘
```

### Typical Execution Time

| Step | Duration | Notes |
|------|----------|-------|
| Authentication | < 1s | Header creation only |
| Fetch Locations | 2-3s | 1 page (53 locations) |
| Filter Sensors | < 1s | Client-side filtering |
| Extract Measurements | 2-4 min | 39 sensors × 3s each |
| Transform | 1-2s | Pandas operations |
| Enrich | 1-2s | DataFrame joins |
| **Total** | **3-5 min** | For 24-hour lookback |

---

## Recent Bug Fixes

### Bug Fix #1: Parameter Filtering (December 2025)

**Issue**: HCMC location (ID 3276359) wasn't extracted despite having active PM2.5 sensor

**Root Cause**: Parameter name mismatch
```python
# Required parameter
'PM2.5' → normalized: 'pm25'

# API returns
'pm25'  → normalized: 'pm25'

# Old logic used substring matching
'PM2.5' in 'pm25'  # ❌ False (case-sensitive)
```

**Fix**: Normalize both sides before comparison
```python
# Old (incorrect)
if any(req.lower() in param_name.lower() for req in required_parameters):
    # 'pm2.5' in 'pm25' → False

# New (correct)
if any(
    normalize_parameter_name(req) in normalize_parameter_name(param_name)
    for req in required_parameters
):
    # 'pm25' in 'pm25' → True
```

**Impact**: Increased coverage from 3 to 4 locations (33% increase)

### Bug Fix #2: City Name Mapping (December 2025)

**Issue**: HCMC appeared as `city_name = "Unknown"` in Athena

**Root Cause**: OpenAQ API returns `locality: null` for some locations

**Fix**: Added manual location ID → city mapping
```python
LOCATION_CITY_MAP = {
    3276359: "Ho Chi Minh",  # CMT8 - HCMC
}

# In enrichment logic
city = LOCATION_CITY_MAP.get(location_id) or loc.get('locality') or 'Unknown'
```

**Impact**: Proper city names for all Vietnam locations

---

## Testing

### Test API Connection

```python
from etls.openaq_etl import connect_openaq, fetch_all_vietnam_locations
from utils.constants import OPENAQ_API_KEY

# Test authentication
headers = connect_openaq(OPENAQ_API_KEY)
assert 'X-API-Key' in headers

# Test location fetch
sensor_ids, locations = fetch_all_vietnam_locations(headers)
assert len(locations) > 0
assert len(sensor_ids) > 0

print(f"✅ Found {len(locations)} locations with {len(sensor_ids)} sensors")
```

### Validate Response Structure

```bash
# Test location endpoint
curl -H "X-API-Key: your_key" \
  "https://api.openaq.org/v3/locations?countries_id=56&limit=1" | jq .

# Test measurements endpoint
curl -H "X-API-Key: your_key" \
  "https://api.openaq.org/v3/sensors/12345/measurements?limit=1" | jq .
```

---

## Related Documentation

- [Main README](../README.md) - Project overview
- [Glue Jobs Guide](GLUE_JOBS_GUIDE.md) - Data transformation
- [Refactoring Guide](REFACTORING_GUIDE.md) - Code patterns

---

**Maintained By**: OpenAQ Pipeline Team  
**Last Updated**: January 4, 2026
