#!/usr/bin/env python3
"""
OpenAQ v3 VIETNAM → FULL CSV (ALL FIELDS) /opt/airflow/tests/
"""
import requests
import json
import time
import csv
import os

API_KEY = r'4417e9a6bba30a0bff7af8ec79240fcb19aded4cfdf587f1d48c0fbfbff883b3'
BASE_URL = "https://api.openaq.org/v3"
HEADERS = {'X-API-KEY': API_KEY}

print("="*80)
print("🚀 OPENAQ V3 VIETNAM → FULL CSV (ALL FIELDS)")
print("="*80)

def ensure_tests_dir():
    tests_dir = '/opt/airflow/tests'
    os.makedirs(tests_dir, exist_ok=True)
    return tests_dir

def fetch_all_vietnam_locations():
    """Fetch ALL VN locations (countries_id=56)"""
    all_locations = []
    page = 1
    
    print("📥 Fetching ALL Vietnam locations...")
    while True:
        params = {'countries_id': 56, 'limit': 100, 'page': page}
        resp = requests.get(f"{BASE_URL}/locations", params=params, headers=HEADERS)
        
        if resp.status_code != 200:
            print(f"❌ Stop: {resp.status_code}")
            break
            
        data = resp.json()
        locations = data.get('results', [])
        if not locations:
            print("✅ Fetch COMPLETE!")
            break
            
        all_locations.extend(locations)
        print(f"📊 Page {page}: +{len(locations)} locations (TOTAL: {len(all_locations)})")
        time.sleep(0.2)  # Rate limit
        page += 1
    
    return all_locations

def export_full_csv(locations):
    """FULL FIELDS CSV - ALL OpenAQ v3 data"""
    tests_dir = ensure_tests_dir()
    csv_file = f'{tests_dir}/vietnam_locations_FULL.csv'
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # FULL HEADER - All v3 fields
        headers = [
            'location_id', 'name', 'locality', 'timezone',
            'country_id', 'country_code', 'country_name',
            'owner_id', 'owner_name', 'provider_id', 'provider_name',
            'is_mobile', 'is_monitor',
            'instruments', 'sensors_count', 'pm25_sensors', 'pm10_sensors', 'no2_sensors',
            'latitude', 'longitude',
            'bounds_min_lon', 'bounds_min_lat', 'bounds_max_lon', 'bounds_max_lat',
            'datetime_first_utc', 'datetime_last_utc'
        ]
        writer.writerow(headers)
        
        for loc in locations:
            coords = loc.get('coordinates', {})
            country = loc.get('country', {})
            owner = loc.get('owner', {})
            provider = loc.get('provider', {})
            instruments = loc.get('instruments', [])
            sensors = loc.get('sensors', [])
            
            # Count sensors by parameter
            pm25_count = sum(1 for s in sensors if 'pm25' in s.get('parameter', {}).get('name', '').lower())
            pm10_count = sum(1 for s in sensors if 'pm10' in s.get('parameter', {}).get('name', '').lower())
            no2_count = sum(1 for s in sensors if 'no2' in s.get('parameter', {}).get('name', '').lower())
            
            # datetimeFirst/Last (handle nested UTC)
            first_utc = loc.get('datetimeFirst', {}).get('utc', '') if loc.get('datetimeFirst') else ''
            last_utc = loc.get('datetimeLast', {}).get('utc', '') if loc.get('datetimeLast') else ''
            
            # Bounds array → individual columns
            bounds = loc.get('bounds', [])
            b_min_lon, b_min_lat, b_max_lon, b_max_lat = bounds[:4] if len(bounds) >= 4 else [None]*4
            
            writer.writerow([
                loc.get('id'),
                loc.get('name', ''),
                loc.get('locality', ''),
                loc.get('timezone', ''),
                country.get('id'),
                country.get('code', ''),
                country.get('name', ''),
                owner.get('id'),
                owner.get('name', ''),
                provider.get('id'),
                provider.get('name', ''),
                loc.get('isMobile', ''),
                loc.get('isMonitor', ''),
                ';'.join([i.get('name', '') for i in instruments]),
                len(sensors),
                pm25_count,
                pm10_count,
                no2_count,
                coords.get('latitude'),
                coords.get('longitude'),
                b_min_lon, b_min_lat, b_max_lon, b_max_lat,
                first_utc,
                last_utc
            ])
    
    print(f"💾 FULL CSV: {csv_file} ({len(locations)} rows, {len(headers)} columns)")
    return csv_file

# MAIN - FULL EXECUTE
locations = fetch_all_vietnam_locations()

if locations:
    csv_file = export_full_csv(locations)
    
    print("\n📈 FULL STATS:")
    print(f"   📍 Locations: {len(locations)}")
    pm25_total = sum(1 for loc in locations for s in loc.get('sensors', []) if 'pm25' in s.get('parameter', {}).get('name', '').lower())
    print(f"   🧬 PM2.5 sensors: {pm25_total}")
    print(f"   📁 File: /opt/airflow/tests/vietnam_locations_FULL.csv")
    
    # Copy local command
    container_id = os.popen('hostname').read().strip()
    print(f"\n💾 SYNC LOCAL: docker cp {container_id}:/opt/airflow/tests/vietnam_locations_FULL.csv ./tests/")
    
else:
    print("❌ No data fetched!")

print("="*80)
