import requests
import pandas as pd
from datetime import datetime, timedelta
from utils.constants import OPENAQ_API_KEY

# Cấu hình API v3
BASE_URL = "https://api.openaq.org/v3"

# ============================================================================
# STEP 1: Authentication
# ============================================================================

def connect_openaq(api_key: str) -> dict:
    """
    Create headers for OpenAQ API authentication.

    Args:
        api_key: OpenAQ API key

    Returns:
        dict: Headers with X-API-Key for API requests
    """
    return {'X-API-Key': api_key}


# ============================================================================
# STEP 2: Fetch Locations (Vietnam-wide)
# ============================================================================

def fetch_all_vietnam_locations(headers: dict, countries_id: int = 56,
                                page_size: int = 100) -> tuple:
    """
    Fetch ALL Vietnam locations with pagination.

    This function retrieves all monitoring locations in Vietnam from the OpenAQ API
    with pagination support. Each location contains a list of sensors.

    Args:
        headers: API authentication headers from connect_openaq()
        countries_id: OpenAQ country ID (56 = Vietnam)
        page_size: Results per page (max 100)

    Returns:
        tuple: (sensor_ids_list, location_objects_list)
               - sensor_ids: List of unique sensor IDs (for measurement extraction)
               - locations: List of location objects with sensors (for enrichment)

    Raises:
        Exception: If API request fails
    """
    try:
        all_locations = []
        sensor_ids = set()
        page = 1
        total_fetched = 0

        print(f"[INFO] Fetching ALL Vietnam locations (countries_id={countries_id})...")

        while True:
            params = {
                'countries_id': countries_id,
                'limit': page_size,
                'page': page
            }

            response = requests.get(f"{BASE_URL}/locations", headers=headers, params=params, timeout=30)
            if response.status_code != 200:
                print(f"[FAIL] API Error {response.status_code}: {response.text}")
                break

            data = response.json()
            results = data.get('results', [])

            if not results:
                print(f"[INFO] Pagination complete at page {page}")
                break

            # Extract sensor IDs from locations
            for loc in results:
                sensors = loc.get('sensors', [])
                for sensor in sensors:
                    sensor_id = sensor.get('id')
                    if sensor_id:
                        sensor_ids.add(sensor_id)

            all_locations.extend(results)
            total_fetched += len(results)
            print(f"[INFO] Page {page}: +{len(results)} locations (TOTAL: {total_fetched})")
            page += 1

        print(f"[SUCCESS] Fetched {len(all_locations)} Vietnam locations with {len(sensor_ids)} sensors")
        return list(sensor_ids), all_locations

    except Exception as e:
        print(f"[FAIL] Failed to fetch Vietnam locations: {str(e)}")
        raise


# ============================================================================
# STEP 3: Filter Active Sensors
# ============================================================================

def filter_active_sensors(locations: list, lookback_days: int = 7,
                          required_parameters: list = None) -> list:
    """
    Filter sensors by activity and required parameters.

    Keeps only sensors that:
    1. Have data from the last N days (active)
    2. Measure at least one of the required parameters

    Args:
        locations: List of location objects from fetch_all_vietnam_locations()
        lookback_days: Only keep sensors with data in last N days (default: 7)
        required_parameters: List of required parameter names (default: ['PM2.5', 'PM10'])

    Returns:
        list: Filtered sensor IDs that meet all criteria

    Raises:
        Exception: If filtering fails
    """
    if required_parameters is None:
        required_parameters = ['PM2.5', 'PM10']

    try:
        active_sensor_ids = []
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        print(f"[INFO] Filtering sensors: lookback={lookback_days} days, required={required_parameters}")

        for loc in locations:
            # Check if location has recent data
            dt_last = loc.get('datetimeLast')
            if not dt_last:
                continue

            last_dt_str = dt_last.get('utc') if isinstance(dt_last, dict) else str(dt_last)
            if not last_dt_str:
                continue

            try:
                last_datetime = pd.to_datetime(last_dt_str).replace(tzinfo=None)
            except:
                continue

            # Skip if last update is older than cutoff
            if last_datetime < cutoff_date:
                continue

            # Check if location has required parameters
            sensors = loc.get('sensors', [])
            for sensor in sensors:
                param = sensor.get('parameter', {})
                param_name = param.get('name') if isinstance(param, dict) else None

                if param_name:
                    # Check if this parameter matches any required parameter
                    if any(req.lower() in param_name.lower() for req in required_parameters):
                        sensor_id = sensor.get('id')
                        if sensor_id and sensor_id not in active_sensor_ids:
                            active_sensor_ids.append(sensor_id)

        print(f"[SUCCESS] Filtered to {len(active_sensor_ids)} active sensors")
        return active_sensor_ids

    except Exception as e:
        print(f"[FAIL] Failed to filter sensors: {str(e)}")
        raise


# ============================================================================
# STEP 4: Extract Measurements
# ============================================================================

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
    all_measurements = []
    total_records = 0

    print(f"[INFO] Extracting measurements from {len(sensor_ids)} sensors")
    print(f"       Period: {date_from.isoformat()} to {date_to.isoformat()}")

    for idx, sensor_id in enumerate(sensor_ids, 1):
        try:
            meas_url = f"{BASE_URL}/sensors/{sensor_id}/measurements"
            meas_params = {
                'datetime_from': date_from.isoformat(),
                'datetime_to': date_to.isoformat(),
                'limit': 1000
            }

            meas_resp = requests.get(meas_url, headers=headers, params=meas_params, timeout=30)

            if meas_resp.status_code != 200:
                continue

            meas_data = meas_resp.json()
            measurements = meas_data.get('results', [])

            if not measurements:
                continue

            for m in measurements:
                # Extract datetime from period.datetimeFrom
                period = m.get('period', {})
                dt_from = period.get('datetimeFrom', {})
                datetime_val = dt_from.get('utc') if isinstance(dt_from, dict) else dt_from

                # Extract parameter info
                param_info = m.get('parameter', {})

                measurement_record = {
                    'sensor_id': sensor_id,
                    'datetime': datetime_val,
                    'value': m.get('value'),
                    'parameter': param_info.get('name'),
                    'unit': param_info.get('units')
                }
                all_measurements.append(measurement_record)
                total_records += 1

            # Log progress every 10 sensors
            if idx % 10 == 0:
                print(f"[INFO] Processed {idx}/{len(sensor_ids)} sensors, {total_records} records so far")

        except Exception as e:
            print(f"[WARNING] Failed to extract sensor {sensor_id}: {str(e)}")
            continue

    print(f"[SUCCESS] Extracted {total_records} measurements from {len(sensor_ids)} sensors")
    return all_measurements


# ============================================================================
# STEP 5: Transform Measurements
# ============================================================================

def transform_measurements(measurements: list) -> pd.DataFrame:
    """
    Transform raw measurements into structured DataFrame.

    Converts list of measurement dicts into a pandas DataFrame with:
    - Long format: Each row = one measurement at one time
    - Columns: sensor_id, datetime, value, parameter, unit, extracted_at
    - Sorted by sensor_id and datetime
    - Ready for enrichment with location metadata

    Args:
        measurements: List of measurement dicts from extract_measurements()

    Returns:
        pd.DataFrame: Structured measurements in long format

    Note:
        Rows with invalid datetime are automatically dropped.
    """
    if not measurements:
        print("[WARNING] No measurements to transform")
        return pd.DataFrame()

    df = pd.DataFrame(measurements)

    # Ensure datetime is properly formatted
    df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
    df['extracted_at'] = datetime.now()

    # Remove rows with invalid datetime
    df = df.dropna(subset=['datetime'])

    # Sort by sensor and datetime
    df = df.sort_values(['sensor_id', 'datetime']).reset_index(drop=True)

    print(f"[SUCCESS] Transformed {len(df)} measurement records")
    return df


# ============================================================================
# STEP 6: Enrich with Metadata
# ============================================================================

def enrich_measurements_with_metadata(df: pd.DataFrame, locations: list) -> pd.DataFrame:
    """
    Enrich measurement DataFrame with location metadata (coordinates, city, etc).

    Joins measurement data with location information by mapping sensor_id
    to location details (coordinates, city name, country code, timezone).

    Args:
        df: DataFrame from transform_measurements() with sensor_id column
        locations: List of location objects from fetch_all_vietnam_locations()

    Returns:
        pd.DataFrame: Enriched with columns:
                      - location_id, location_name
                      - city, timezone, country
                      - latitude, longitude

    Raises:
        Exception: If enrichment fails
    """
    try:
        if df.empty:
            print("[WARNING] Empty DataFrame, cannot enrich")
            return df

        # Build sensor_id -> location metadata mapping
        sensor_to_location = {}
        for loc in locations:
            loc_id = loc.get('id')
            loc_name = loc.get('name')
            locality = loc.get('locality')
            timezone = loc.get('timezone')

            country = loc.get('country', {})
            country_code = country.get('code') if isinstance(country, dict) else 'VN'

            coords = loc.get('coordinates', {})
            latitude = coords.get('latitude') if coords else None
            longitude = coords.get('longitude') if coords else None

            sensors = loc.get('sensors', [])
            for sensor in sensors:
                sensor_id = sensor.get('id')
                if sensor_id:
                    sensor_to_location[sensor_id] = {
                        'location_id': loc_id,
                        'location_name': loc_name,
                        'city': locality,
                        'timezone': timezone,
                        'country_code': country_code,
                        'latitude': latitude,
                        'longitude': longitude
                    }

        # Enrich each measurement with location metadata
        df['location_id'] = df['sensor_id'].map(lambda x: sensor_to_location.get(x, {}).get('location_id'))
        df['location_name'] = df['sensor_id'].map(lambda x: sensor_to_location.get(x, {}).get('location_name'))
        df['city'] = df['sensor_id'].map(lambda x: sensor_to_location.get(x, {}).get('city') or 'Unknown')
        df['timezone'] = df['sensor_id'].map(lambda x: sensor_to_location.get(x, {}).get('timezone'))
        df['country'] = df['sensor_id'].map(lambda x: sensor_to_location.get(x, {}).get('country_code') or 'VN')
        df['latitude'] = df['sensor_id'].map(lambda x: sensor_to_location.get(x, {}).get('latitude'))
        df['longitude'] = df['sensor_id'].map(lambda x: sensor_to_location.get(x, {}).get('longitude'))

        print(f"[SUCCESS] Enriched {len(df)} records with location metadata")
        return df

    except Exception as e:
        print(f"[FAIL] Failed to enrich measurements: {str(e)}")
        raise