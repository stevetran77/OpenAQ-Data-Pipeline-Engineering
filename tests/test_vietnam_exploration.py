#!/usr/bin/env python3
"""
OpenAQ v3 Vietnam Location Extraction - Exploration Script
Fetches all Vietnam locations and analyzes the data structure.
"""
import requests
import json
import time
import pandas as pd
from datetime import datetime
from utils.constants import OPENAQ_API_KEY

BASE_URL = "https://api.openaq.org/v3"
HEADERS = {'X-API-KEY': OPENAQ_API_KEY}

def fetch_all_vietnam_locations():
    """Fetch ALL Vietnam locations using countries_id=56"""
    all_locations = []
    page = 1

    print("=" * 80)
    print("OPENAQ V3 VIETNAM LOCATION EXPLORATION")
    print("=" * 80)
    print("[INFO] Fetching ALL Vietnam locations (countries_id=56)...\n")

    while True:
        params = {'countries_id': 56, 'limit': 100, 'page': page}
        resp = requests.get(f"{BASE_URL}/locations", params=params, headers=HEADERS)

        if resp.status_code != 200:
            print(f"[FAIL] API Error {resp.status_code}: {resp.text}")
            break

        data = resp.json()
        locations = data.get('results', [])

        if not locations:
            print("[SUCCESS] Fetch complete!")
            break

        all_locations.extend(locations)
        print(f"[INFO] Page {page}: +{len(locations)} locations (TOTAL: {len(all_locations)})")
        time.sleep(0.2)  # Rate limit
        page += 1

    return all_locations


def analyze_locations(locations):
    """Analyze location data structure and content"""
    print("\n" + "=" * 80)
    print("LOCATION DATA ANALYSIS")
    print("=" * 80)

    if not locations:
        print("[FAIL] No locations found")
        return

    print(f"[OK] Total locations found: {len(locations)}")

    # Sample one location
    sample = locations[0]
    print(f"\n[INFO] Sample location structure:")
    print(f"  - ID: {sample.get('id')}")
    print(f"  - Name: {sample.get('name', 'N/A')}")
    print(f"  - Locality: {sample.get('locality', 'N/A')}")
    print(f"  - Timezone: {sample.get('timezone')}")
    print(f"  - Coordinates: {sample.get('coordinates')}")
    print(f"  - Sensors: {len(sample.get('sensors', []))} sensors")
    print(f"  - DateTime Last: {sample.get('datetimeLast')}")

    # Count locations by parameters
    pm25_count = 0
    pm10_count = 0
    no2_count = 0
    locations_with_recent_data = 0

    for loc in locations:
        sensors = loc.get('sensors', [])
        sensor_params = []

        for sensor in sensors:
            param = sensor.get('parameter', {})
            param_name = param.get('name', '').lower() if param else ''
            sensor_params.append(param_name)

        # Count by parameter
        if any('pm25' in p or 'pm2.5' in p for p in sensor_params):
            pm25_count += 1
        if any('pm10' in p for p in sensor_params):
            pm10_count += 1
        if any('no2' in p for p in sensor_params):
            no2_count += 1

        # Check for recent data (within 7 days)
        datetime_last = loc.get('datetimeLast')
        if datetime_last:
            last_str = datetime_last.get('utc') if isinstance(datetime_last, dict) else str(datetime_last)
            try:
                last_date = pd.to_datetime(last_str)
                days_ago = (pd.Timestamp.now(tz='UTC') - last_date).days
                if days_ago <= 7:
                    locations_with_recent_data += 1
            except:
                pass

    print(f"\n[INFO] Parameter coverage:")
    print(f"  - PM2.5 sensors: {pm25_count} locations")
    print(f"  - PM10 sensors: {pm10_count} locations")
    print(f"  - NO2 sensors: {no2_count} locations")
    print(f"  - With data in last 7 days: {locations_with_recent_data} locations")

    # Show top 10 locations by ID (avoiding encoding issues)
    print(f"\n[INFO] First 10 locations:")
    for i, loc in enumerate(sorted(locations, key=lambda x: x.get('id', 0))[:10], 1):
        sensor_count = len(loc.get('sensors', []))
        loc_id = loc.get('id', 'N/A')
        loc_name = loc.get('name', 'N/A')
        loc_locality = loc.get('locality', 'N/A')
        try:
            print(f"  {i}. ID={loc_id}, Sensors={sensor_count}, Locality={loc_locality}")
        except:
            print(f"  {i}. ID={loc_id}, Sensors={sensor_count} (encoding issue with name)")

    return {
        'total': len(locations),
        'pm25_count': pm25_count,
        'pm10_count': pm10_count,
        'no2_count': no2_count,
        'with_recent_data': locations_with_recent_data
    }


def export_to_csv(locations, filename='vietnam_locations.csv'):
    """Export locations to CSV for inspection"""
    if not locations:
        print("[FAIL] No locations to export")
        return

    records = []
    for loc in locations:
        coords = loc.get('coordinates', {})
        sensors = loc.get('sensors', [])
        sensor_params = [s.get('parameter', {}).get('name', '') for s in sensors]
        datetime_last = loc.get('datetimeLast')
        if isinstance(datetime_last, dict):
            last_str = datetime_last.get('utc', '')
        else:
            last_str = str(datetime_last) if datetime_last else ''

        records.append({
            'location_id': loc.get('id'),
            'name': loc.get('name'),
            'locality': loc.get('locality'),
            'timezone': loc.get('timezone'),
            'latitude': coords.get('latitude'),
            'longitude': coords.get('longitude'),
            'sensor_count': len(sensors),
            'sensor_parameters': '; '.join(sensor_params),
            'datetime_last': last_str
        })

    df = pd.DataFrame(records)
    df.to_csv(filename, index=False)
    print(f"\n[OK] Exported {len(records)} locations to {filename}")
    return filename


if __name__ == '__main__':
    try:
        # Fetch all Vietnam locations
        locations = fetch_all_vietnam_locations()

        # Analyze the data
        stats = analyze_locations(locations)

        # Export to CSV
        csv_file = export_to_csv(locations)

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        if stats:
            print(f"[OK] Successfully extracted {stats['total']} Vietnam locations")
            print(f"[OK] {stats['with_recent_data']} locations have data within last 7 days")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
