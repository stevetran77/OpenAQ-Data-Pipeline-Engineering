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
