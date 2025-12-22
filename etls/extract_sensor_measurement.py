import sys
import os
import json
import requests
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.constants import OPENAQ_API_KEY

BASE_URL = "https://api.openaq.org/v3"


def extract_sensor_measurement(headers: dict, sensor_ids: list, 
                               date_from: datetime, date_to: datetime) -> list:
    """
    Extract measurements for given sensor IDs from OpenAQ API.
    
    Args:
        headers: OpenAQ API headers with X-API-Key
        sensor_ids: List of sensor IDs to fetch measurements for
        date_from: Start datetime for measurements
        date_to: End datetime for measurements
    
    Returns:
        list[dict]: List of measurement records with sensor and parameter info
    """
    print(f"[INFO] Extracting measurements for {len(sensor_ids)} sensors...")
    all_measurements = []
    
    for idx, sensor_id in enumerate(sensor_ids, 1):
        try:
            # Call API: GET /sensors/{sensor_id}/measurements
            url = f"{BASE_URL}/sensors/{sensor_id}/measurements"
            params = {
                'datetime_from': date_from.isoformat(),
                'datetime_to': date_to.isoformat(),
                'limit': 1000
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                print(f"[WARNING] Sensor {sensor_id} ({idx}/{len(sensor_ids)}): API Error {response.status_code}")
                continue
            
            data = response.json()
            measurements = data.get('results', [])
            
            if measurements:
                print(f"[INFO] Sensor {sensor_id} ({idx}/{len(sensor_ids)}): +{len(measurements)} measurements")
            
            for m in measurements:
                # Extract datetime from period
                datetime_val = None
                period = m.get('period', {})
                if period and 'datetimeFrom' in period:
                    dt_obj = period['datetimeFrom']
                    if isinstance(dt_obj, dict):
                        datetime_val = dt_obj.get('local')
                    else:
                        datetime_val = dt_obj
                
                # Extract parameter info
                param_info = m.get('parameter', {})
                
                measurement_data = {
                    'sensor_id': sensor_id,
                    'parameter': param_info.get('name'),
                    'value': m.get('value'),
                    'unit': param_info.get('units'),
                    'datetime': datetime_val,
                    'latitude': None,  # Will be filled during enrichment
                    'longitude': None,
                    'city': None,
                    'country': None
                }
                all_measurements.append(measurement_data)
        
        except requests.RequestException as e:
            print(f"[WARNING] Sensor {sensor_id} ({idx}/{len(sensor_ids)}): Request failed - {e}")
            continue
        except Exception as e:
            print(f"[WARNING] Sensor {sensor_id} ({idx}/{len(sensor_ids)}): Error - {e}")
            continue
    
    print(f"[SUCCESS] Extracted {len(all_measurements)} total measurements from {len(sensor_ids)} sensors")
    return all_measurements

if __name__ == "__main__":
    print("Extracting sensor IDs from mock locations...")

    locations_json = fetch_mock_locations_vn()
    sensor_ids = extract_sensor_ids(locations_json)

    print(f"Found {len(sensor_ids)} sensors")

    for sensor_id in sensor_ids:
        print(f"Fetching measurements for sensor {sensor_id}")
        sensor_data = fetch_sensor_data(sensor_id)

        if sensor_data:
            save_sensor_data_to_file(sensor_id, sensor_data)
