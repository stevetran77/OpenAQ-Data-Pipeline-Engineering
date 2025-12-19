"""
Test script to inspect raw OpenAQ API data extraction.
Fetches all Vietnam locations using OpenAQ API v3.
"""
import sys
sys.path.insert(0, '/opt/airflow/')

import requests
from utils.constants import OPENAQ_API_KEY
from datetime import datetime, timedelta
import json

def fetch_all_vietnam_locations(api_key: str) -> list:
    """Fetch all locations in Vietnam using API v3."""
    all_location_ids = []
    page = 1
    base_url = "https://api.openaq.org/v3"
    headers = {'X-API-KEY': api_key}

    print("[INFO] Fetching all Vietnam locations using API v3...")
    print("[INFO] Using country_id=56 (Vietnam)\n")

    try:
        while True:
            params = {
                'countries_id': '56',
                'limit': 1000,
                'page': page
            }

            response = requests.get(f"{base_url}/locations", params=params, headers=headers, timeout=30)

            if response.status_code != 200:
                print(f"[WARNING] API returned status {response.status_code}, stopping pagination")
                break

            data = response.json()
            locations = data.get('results', [])

            if not locations:
                print(f"[INFO] Page {page} is empty - reached end of results")
                break

            location_ids = [loc.get('id') for loc in locations if loc.get('id')]
            all_location_ids.extend(location_ids)

            print(f"[OK] Page {page}: +{len(location_ids)} locations (total: {len(all_location_ids)})")
            page += 1

    except Exception as e:
        print(f"[WARNING] Error fetching locations: {str(e)}")

    return all_location_ids


def test_extract_data():
    """Test OpenAQ data extraction and display results."""

    print("\n" + "="*80)
    print("[START] Testing OpenAQ Data Extraction - All Vietnam Locations")
    print("="*80 + "\n")

    # Extract all Vietnam locations
    print("[1/4] Fetching all Vietnam locations...")
    location_ids = fetch_all_vietnam_locations(OPENAQ_API_KEY)
    print(f"\n[OK] Found {len(location_ids)} locations in Vietnam")
    print(f"[INFO] First 10 location IDs: {location_ids[:10]}\n")

    if not location_ids:
        print("[FAIL] No locations found!")
        return

    # Extract measurements from all Vietnam locations
    print("[2/4] Extracting measurements from all Vietnam locations...")

    date_to = datetime.now()
    date_from = date_to - timedelta(hours=168)  # Test with 7 days (168 hours)

    print(f"[INFO] Date range: {date_from} to {date_to}")
    print(f"[INFO] Testing {len(location_ids)} locations to find active ones...\n")

    # Extract measurements using direct API calls
    from etls.openaq_etl import connect_openaq, extract_measurements

    client = connect_openaq(OPENAQ_API_KEY)
    all_measurements = extract_measurements(
        client=client,
        location_ids=location_ids,
        date_from=date_from,
        date_to=date_to
    )
    client.close()

    print(f"\n[OK] Extracted {len(all_measurements)} measurements total\n")

    # Display results
    print("[3/4] Analyzing extracted data...")
    print("="*80)

    if all_measurements:
        print(f"\n[SUCCESS] Total measurements extracted: {len(all_measurements)}\n")

        # Show first 3 measurements in detail
        print("Sample measurements (first 3):")
        print("-"*80)
        for i, m in enumerate(all_measurements[:3], 1):
            print(f"\nMeasurement {i}:")
            print(json.dumps(m, indent=2, default=str))
            print("-"*80)

        # Show summary statistics
        print("\n[SUMMARY]")
        print(f"  Total measurements: {len(all_measurements)}")

        # Count by parameter
        parameters = {}
        for m in all_measurements:
            param = m.get('parameter', 'unknown')
            parameters[param] = parameters.get(param, 0) + 1

        print(f"  Parameters found:")
        for param, count in parameters.items():
            print(f"    - {param}: {count} measurements")

        # Check data quality
        null_datetime = sum(1 for m in all_measurements if m.get('datetime') is None)
        null_value = sum(1 for m in all_measurements if m.get('value') is None)

        print(f"\n  Data quality:")
        print(f"    - Measurements with null datetime: {null_datetime}")
        print(f"    - Measurements with null value: {null_value}")

        # Show location distribution
        locations_with_data = {}
        for m in all_measurements:
            loc_id = m.get('location_id')
            locations_with_data[loc_id] = locations_with_data.get(loc_id, 0) + 1

        print(f"\n  Locations with data: {len(locations_with_data)}")
        for loc_id, count in sorted(locations_with_data.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"    - Location {loc_id}: {count} measurements")

    else:
        print("[WARNING] No measurements extracted from any location!")
        print("\nPossible reasons:")
        print("  1. All locations may be inactive or have no recent data")
        print("  2. API rate limiting or authentication issue")
        print("  3. Date range may be incorrect")
        print("\nDebug: Try checking individual location details in the OpenAQ API directly.")

    print("\n" + "="*80)
    print("[END] Test completed")
    print("="*80 + "\n")

if __name__ == "__main__":
    test_extract_data()
