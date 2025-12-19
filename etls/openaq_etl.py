from openaq import OpenAQ
import pandas as pd
from datetime import datetime, timedelta
from utils.constants import OPENAQ_API_KEY
import requests


def connect_openaq(api_key: str) -> OpenAQ:
    """
    Create OpenAQ client with API key.

    Args:
        api_key: OpenAQ API key

    Returns:
        OpenAQ: Authenticated OpenAQ client

    Raises:
        Exception: If connection fails
    """
    try:
        client = OpenAQ(api_key=api_key)
        return client
    except Exception as e:
        raise Exception(f"Failed to create OpenAQ client: {str(e)}")


def extract_locations(client: OpenAQ, city: str = None, country: str = None,
                      coordinates: tuple = None, radius: int = 25000) -> list:
    """
    Get all monitoring locations by geographic coordinates.

    Args:
        client: OpenAQ client instance
        city: City name (used for reference only, not sent to API)
        country: Country code (used for reference only, not sent to API)
        coordinates: Tuple of (latitude, longitude) for location search
        radius: Search radius in meters, max 25000 (25km). Default: 25km

    Returns:
        list: List of location IDs

    Note:
        OpenAQ API requires coordinates instead of city name.
        Coordinates should be in format (latitude, longitude).
    """
    try:
        # City coordinates mapping
        city_coords = {
            'Hanoi': (21.0285, 105.8542),
            'Ho Chi Minh City': (10.7769, 106.7009),
            'Da Nang': (16.0544, 108.2022),
            'Nha Trang': (12.2388, 109.1967),
            'Hai Phong': (20.8449, 106.6881),
        }

        # Use provided coordinates or lookup by city name
        if coordinates is None:
            if city in city_coords:
                coordinates = city_coords[city]
            else:
                raise Exception(f"City '{city}' not in predefined coordinates. Please provide coordinates tuple.")

        print(f"[INFO] Searching locations near {city} - coordinates: {coordinates}, radius: {radius}m")

        locations = client.locations.list(
            coordinates=coordinates,
            radius=radius,
            limit=1000
        )
        location_ids = [loc.id for loc in locations.results]
        print(f"[INFO] Found {len(location_ids)} locations near {city}")
        return location_ids
    except Exception as e:
        raise Exception(f"Failed to extract locations: {str(e)}")


def extract_measurements(client: OpenAQ, location_ids: list,
                        date_from: datetime, date_to: datetime) -> list:
    """
    Extract hourly air quality measurements for given locations and time range.

    Args:
        client: OpenAQ client instance
        location_ids: List of sensor/location IDs
        date_from: Start datetime
        date_to: End datetime

    Returns:
        list: List of measurement dictionaries

    Note:
        OpenAQ API uses sensors_id parameter, not locations_id.
        datetime_from/datetime_to are the correct parameter names.
    """
    all_measurements = []

    for sensor_id in location_ids:
        try:
            measurements = client.measurements.list(
                sensors_id=sensor_id,
                datetime_from=date_from.isoformat(),
                datetime_to=date_to.isoformat(),
                limit=1000
            )

            for measurement in measurements.results:
                # Get datetime from period (API returns period, not direct datetime)
                datetime_val = None
                if measurement.period and measurement.period.datetime_from:
                    datetime_val = measurement.period.datetime_from.local

                measurement_data = {
                    'location_id': sensor_id,
                    'parameter': measurement.parameter.name if measurement.parameter else None,
                    'value': measurement.value,
                    'unit': measurement.parameter.units if measurement.parameter else None,
                    'datetime': datetime_val,
                    'latitude': measurement.coordinates.latitude if measurement.coordinates else None,
                    'longitude': measurement.coordinates.longitude if measurement.coordinates else None,
                    'country': None,  # Not available in measurement object
                    'city': None  # Not available in measurement object
                }
                all_measurements.append(measurement_data)

        except Exception as e:
            print(f"[WARNING] Failed to fetch measurements for sensor {sensor_id}: {e}")
            continue

    return all_measurements


def transform_measurements(measurements: list) -> pd.DataFrame:
    """
    Transform raw measurements into structured DataFrame.

    Args:
        measurements: List of measurement dictionaries

    Returns:
        pd.DataFrame: Cleaned and pivoted DataFrame
    """
    df = pd.DataFrame(measurements)

    if df.empty:
        return df

    # Convert datetime
    df['datetime'] = pd.to_datetime(df['datetime'])

    # Add extraction timestamp
    df['extracted_at'] = datetime.now()

    # Pivot data so each parameter is a column
    df_pivot = df.pivot_table(
        index=['location_id', 'datetime', 'latitude', 'longitude', 'city', 'country', 'extracted_at'],
        columns='parameter',
        values='value',
        aggfunc='mean'
    ).reset_index()

    # Flatten column names
    df_pivot.columns.name = None

    # Sort by datetime
    df_pivot = df_pivot.sort_values('datetime').reset_index(drop=True)

    return df_pivot


def fetch_all_vietnam_locations(client: OpenAQ, countries_id: int = 56,
                                page_size: int = 100) -> list:
    """
    Fetch ALL Vietnam locations using countries_id parameter.

    Args:
        client: OpenAQ client instance
        countries_id: Vietnam country ID (default: 56)
        page_size: Number of results per page (default: 100)

    Returns:
        list: List of location objects from OpenAQ API

    Note:
        Uses pagination to fetch all pages.
        Returns full location objects with metadata: id, name, locality, coordinates, sensors, etc.
    """
    try:
        all_locations = []
        page = 1
        total_fetched = 0

        print(f"[INFO] Fetching ALL Vietnam locations (countries_id={countries_id})...")

        while True:
            locations = client.locations.list(
                countries_id=countries_id,
                limit=page_size,
                page=page
            )

            batch_count = len(locations.results) if locations.results else 0
            if batch_count == 0:
                print(f"[INFO] Pagination complete at page {page}")
                break

            all_locations.extend(locations.results)
            total_fetched += batch_count
            print(f"[INFO] Page {page}: +{batch_count} locations (TOTAL: {total_fetched})")

            page += 1

        print(f"[SUCCESS] Fetched {len(all_locations)} Vietnam locations")
        return all_locations

    except Exception as e:
        print(f"[FAIL] Failed to fetch Vietnam locations: {str(e)}")
        raise Exception(f"Failed to fetch Vietnam locations: {str(e)}")


def filter_active_locations(locations: list, lookback_days: int = 7,
                            required_parameters: list = None) -> list:
    """
    Filter for active locations with recent data and required sensors.

    Args:
        locations: List of location objects from OpenAQ API
        lookback_days: Only include locations with data in last N days (default: 7)
        required_parameters: List of required sensor parameter names
                           (default: ['PM2.5', 'PM10'])

    Returns:
        list: Filtered list of location objects

    Note:
        Filters based on datetimeLast field to ensure location is active.
        Checks sensors array for required parameter types (case-insensitive).
    """
    if required_parameters is None:
        required_parameters = ['PM2.5', 'PM10']

    try:
        filtered_locations = []
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        print(f"[INFO] Filtering locations: lookback={lookback_days} days, required_params={required_parameters}")

        for location in locations:
            # Check if location has recent data
            datetime_last = location.datetime_last
            if not datetime_last:
                continue

            # Handle Datetime object with 'utc' attribute (OpenAQ SDK format)
            if hasattr(datetime_last, 'utc'):
                last_datetime_str = datetime_last.utc
            elif isinstance(datetime_last, dict):
                last_datetime_str = datetime_last.get('utc')
            else:
                last_datetime_str = str(datetime_last) if datetime_last else None

            if not last_datetime_str:
                continue

            # Convert to datetime
            try:
                last_datetime = pd.to_datetime(last_datetime_str)
            except Exception:
                continue

            # Check if within lookback period
            if last_datetime.replace(tzinfo=None) < cutoff_date:
                continue

            # Check if location has required sensors
            sensors = location.sensors if hasattr(location, 'sensors') else []
            sensor_params = []

            for sensor in sensors:
                param_name = None
                if hasattr(sensor, 'parameter'):
                    if hasattr(sensor.parameter, 'name'):
                        param_name = sensor.parameter.name
                    elif isinstance(sensor.parameter, dict):
                        param_name = sensor.parameter.get('name')

                if param_name:
                    sensor_params.append(param_name)

            # Check if any required parameter is present
            has_required_param = any(
                req_param.lower() in str(p).lower()
                for req_param in required_parameters
                for p in sensor_params
            )

            if has_required_param:
                filtered_locations.append(location)

        print(f"[SUCCESS] Filtered to {len(filtered_locations)} active locations")
        return filtered_locations

    except Exception as e:
        print(f"[FAIL] Failed to filter locations: {str(e)}")
        raise Exception(f"Failed to filter locations: {str(e)}")


def enrich_measurements_with_metadata(df: pd.DataFrame, locations: list) -> pd.DataFrame:
    """
    Add location metadata to measurements DataFrame.

    Args:
        df: Measurements DataFrame
        locations: List of location objects from OpenAQ API

    Returns:
        pd.DataFrame: Enriched DataFrame with location_name, locality, timezone columns

    Note:
        Creates a mapping from location_id to location metadata.
        Adds new columns: location_name, locality, timezone, country_code
    """
    try:
        if df.empty:
            print("[WARNING] Empty DataFrame provided, returning as-is")
            return df

        # Create location_id -> metadata mapping
        location_map = {}
        for location in locations:
            location_map[location.id] = {
                'location_name': location.name if hasattr(location, 'name') else None,
                'locality': location.locality if hasattr(location, 'locality') else None,
                'timezone': location.timezone if hasattr(location, 'timezone') else None,
                'country_code': location.country.code if (hasattr(location, 'country') and
                                                          hasattr(location.country, 'code')) else None,
            }

        # Add columns to dataframe
        df['location_name'] = df['location_id'].map(lambda x: location_map.get(x, {}).get('location_name'))
        df['locality'] = df['location_id'].map(lambda x: location_map.get(x, {}).get('locality'))
        df['timezone'] = df['location_id'].map(lambda x: location_map.get(x, {}).get('timezone'))
        df['country_code'] = df['location_id'].map(lambda x: location_map.get(x, {}).get('country_code'))

        print(f"[SUCCESS] Enriched {len(df)} records with location metadata")
        return df

    except Exception as e:
        print(f"[FAIL] Failed to enrich measurements: {str(e)}")
        raise Exception(f"Failed to enrich measurements: {str(e)}")
