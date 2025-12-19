"""
Test script to verify OpenAQ data extraction using new ETL functions.
Tests the complete pipeline: fetch -> filter -> extract -> transform -> enrich
"""
import sys
sys.path.insert(0, '/opt/airflow/')

from utils.constants import OPENAQ_API_KEY
from datetime import datetime, timedelta

# Import new ETL functions
from etls.openaq_etl import (
    connect_openaq,
    fetch_all_vietnam_locations,
    filter_active_locations,
    extract_measurements,
    transform_measurements,
    enrich_measurements_with_metadata
)


def test_extract_data():
    """Test complete OpenAQ pipeline: fetch -> filter -> extract -> transform -> enrich."""

    print("\n" + "="*80)
    print("[START] Testing OpenAQ Data Extraction Pipeline - All Vietnam Locations")
    print("="*80 + "\n")

    try:
        # STEP 1: Connect to OpenAQ API
        print("[1/6] Connecting to OpenAQ API...")
        client = connect_openaq(OPENAQ_API_KEY)
        print("[OK] Connected to OpenAQ\n")

        # STEP 2: Fetch all Vietnam locations
        print("[2/6] Fetching ALL Vietnam locations...")
        all_locations = fetch_all_vietnam_locations(client)
        print(f"[OK] Found {len(all_locations)} total locations in Vietnam\n")

        if not all_locations:
            print("[FAIL] No locations found!")
            client.close()
            return

        # STEP 3: Filter active locations with recent data
        print("[3/6] Filtering active locations (7 days lookback, PM2.5/PM10 sensors)...")
        active_locations = filter_active_locations(
            all_locations,
            lookback_days=7,
            required_parameters=['PM2.5', 'PM10']
        )
        location_ids = [loc.id for loc in active_locations]
        print(f"[OK] Filtered to {len(active_locations)} active monitoring stations\n")

        if not location_ids:
            print("[WARNING] No active locations found with required parameters!")
            client.close()
            return

        # STEP 4: Extract measurements
        print("[4/6] Extracting measurements...")
        date_to = datetime.now()
        date_from = date_to - timedelta(hours=168)  # 7 days lookback for testing

        print(f"[INFO] Date range: {date_from.isoformat()} to {date_to.isoformat()}")
        print(f"[INFO] Extracting from {len(location_ids)} active locations...\n")

        all_measurements = extract_measurements(
            client=client,
            location_ids=location_ids,
            date_from=date_from,
            date_to=date_to
        )
        client.close()

        print(f"[OK] Extracted {len(all_measurements)} measurements total\n")

        if not all_measurements:
            print("[WARNING] No measurements extracted!")
            return

        # STEP 5: Transform measurements to DataFrame
        print("[5/6] Transforming measurements to DataFrame...")
        df = transform_measurements(all_measurements)
        print(f"[OK] Transformed {len(df)} records into DataFrame\n")

        # STEP 6: Enrich with location metadata
        print("[6/6] Enriching with location metadata...")
        df_enriched = enrich_measurements_with_metadata(df, active_locations)
        print(f"[OK] Enriched {len(df_enriched)} records with metadata\n")

        # ANALYSIS & DISPLAY RESULTS
        print("="*80)
        print("[SUMMARY] Pipeline Execution Results")
        print("="*80)
        print(f"\n[SUCCESS] Total measurements extracted: {len(df_enriched)}")
        print(f"[OK] Active locations used: {len(active_locations)}")

        # Show DataFrame info
        print(f"\n[INFO] DataFrame Shape: {df_enriched.shape}")
        print(f"[INFO] Columns: {', '.join(df_enriched.columns.tolist())}")

        # Data quality checks
        print(f"\n[INFO] Data Quality Checks:")
        print(f"  - Records with null datetime: {df_enriched['datetime'].isna().sum()}")
        print(f"  - Records with null location_id: {df_enriched['location_id'].isna().sum()}")
        print(f"  - Records with null location_name: {df_enriched['location_name'].isna().sum()}")

        # Parameter coverage
        print(f"\n[INFO] Parameter Coverage:")
        param_cols = [col for col in df_enriched.columns if col not in
                     ['location_id', 'datetime', 'latitude', 'longitude', 'city', 'country',
                      'extracted_at', 'year', 'month', 'day', 'location_name', 'locality',
                      'timezone', 'country_code']]
        for param in param_cols:
            non_null_count = df_enriched[param].notna().sum()
            print(f"  - {param}: {non_null_count} measurements")

        # Location distribution
        print(f"\n[INFO] Top 10 Locations by Measurement Count:")
        location_counts = df_enriched.groupby('location_name')['location_id'].count().sort_values(ascending=False)
        for idx, (loc_name, count) in enumerate(location_counts.head(10).items(), 1):
            print(f"  {idx}. {loc_name}: {count} measurements")

        # Sample records
        print(f"\n[INFO] Sample Records (first 3):")
        print("-"*80)
        for idx, row in df_enriched.head(3).iterrows():
            print(f"\nRecord {idx+1}:")
            print(f"  Location: {row['location_name']} (ID: {row['location_id']})")
            print(f"  DateTime: {row['datetime']}")
            print(f"  Locality: {row['locality']}, Timezone: {row['timezone']}")
            print(f"  Coordinates: ({row['latitude']}, {row['longitude']})")
            for param in param_cols[:3]:  # Show first 3 parameters
                print(f"  {param}: {row[param]}")

        print("\n" + "="*80)
        print("[SUCCESS] Test completed successfully!")
        print("="*80 + "\n")

    except Exception as e:
        print(f"\n[FAIL] Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        print("="*80 + "\n")

if __name__ == "__main__":
    test_extract_data()
