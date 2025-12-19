"""
Test script to verify OpenAQ data extraction using REST API ETL functions.
Tests the complete pipeline: fetch -> filter -> extract -> transform -> enrich
"""
import sys
import json  # Thêm thư viện json để in đẹp hơn
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
    print("[START] Testing OpenAQ Data Extraction Pipeline - All Vietnam Locations (REST API)")
    print("="*80 + "\n")

    try:
        # STEP 1: Connect to OpenAQ API (Prepare Headers)
        print("[1/6] Preparing OpenAQ API Headers...")
        headers = connect_openaq(OPENAQ_API_KEY)
        print("[OK] Headers prepared\n")

        # STEP 2: Fetch all Vietnam locations
        print("[2/6] Fetching ALL Vietnam locations...")
        all_locations = fetch_all_vietnam_locations(headers)
        print(f"[OK] Found {len(all_locations)} total locations in Vietnam\n")

        if not all_locations:
            print("[FAIL] No locations found!")
            return

        # STEP 3: Filter active locations with recent data
        print("[3/6] Filtering active locations (7 days lookback)...")
        active_locations = filter_active_locations(
            all_locations,
            lookback_days=7,
            required_parameters=['PM2.5', 'PM10']
        )
        
        location_ids = [loc['id'] for loc in active_locations]
        print(f"[OK] Filtered to {len(active_locations)} active monitoring stations\n")

        if not location_ids:
            print("[WARNING] No active locations found with required parameters!")
            return

        # STEP 4: Extract measurements
        print("[4/6] Extracting measurements...")
        date_to = datetime.now()
        date_from = date_to - timedelta(hours=24)

        print(f"[INFO] Date range: {date_from.isoformat()} to {date_to.isoformat()}")
        print(f"[INFO] Extracting from {len(location_ids)} active locations...\n")

        all_measurements = extract_measurements(
            headers=headers,
            location_ids=location_ids,
            date_from=date_from,
            date_to=date_to
        )

        print(f"[OK] Extracted {len(all_measurements)} measurements total\n")

        if not all_measurements:
            print("[WARNING] No measurements extracted!")
            return

        # === PHẦN DEBUG MỚI THÊM VÀO ===
        print("="*40)
        print("[DEBUG] SAMPLE RAW DATA (First Record):")
        if len(all_measurements) > 0:
            # In ra bản ghi đầu tiên để kiểm tra cấu trúc
            # Dùng default=str để tránh lỗi khi in object datetime
            print(json.dumps(all_measurements[0], indent=2, default=str)) 
        print("="*40 + "\n")
        # ================================

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
        
        # Sample records
        print(f"\n[INFO] Sample Records (first 3):")
        print("-"*80)
        print(df_enriched.head(3).to_string())

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