from datetime import datetime, timedelta
from utils.constants import (
    OPENAQ_API_KEY,
    OPENAQ_TARGET_CITY,
    OPENAQ_TARGET_COUNTRY,
    OPENAQ_LOOKBACK_HOURS,
    AWS_BUCKET_NAME
)
from etls.openaq_etl import (
    connect_openaq,
    extract_locations,
    extract_measurements,
    transform_measurements,
    fetch_all_vietnam_locations,
    filter_active_locations,
    enrich_measurements_with_metadata
)
from utils.aws_utils import upload_to_s3_partitioned


def openaq_pipeline(file_name: str, city: str = None, country: str = None,
                   lookback_hours: int = None, vietnam_wide: bool = False, **kwargs):
    """
    Main OpenAQ to S3 ETL pipeline.

    Args:
        file_name: Base name for output file
        city: City name (defaults to config) - ignored if vietnam_wide=True
        country: Country code (defaults to config) - ignored if vietnam_wide=True
        lookback_hours: Hours to look back (defaults to config)
        vietnam_wide: If True, extract ALL Vietnam locations instead of single city
        **kwargs: Additional parameters for backward compatibility
    """
    # Use defaults from config if not provided
    city = city or OPENAQ_TARGET_CITY
    country = country or OPENAQ_TARGET_COUNTRY
    lookback_hours = lookback_hours or OPENAQ_LOOKBACK_HOURS

    print(f"[START] OpenAQ Pipeline - {datetime.now()}")
    if vietnam_wide:
        print(f"Target: ALL Vietnam locations | Lookback: {lookback_hours} hours")
    else:
        print(f"Target: {city}, {country} | Lookback: {lookback_hours} hours")

    try:
        # STEP 1: Connect to OpenAQ
        print("[1/5] Connecting to OpenAQ API...")
        client = connect_openaq(api_key=OPENAQ_API_KEY)
        print("[OK] Connected to OpenAQ")

        # STEP 2: Get monitoring locations
        if vietnam_wide:
            print("[2/5] Fetching ALL Vietnam locations...")
            from etls.openaq_etl import fetch_all_vietnam_locations, filter_active_locations, enrich_measurements_with_metadata
            
            all_locations = fetch_all_vietnam_locations(client)
            location_objs = filter_active_locations(all_locations, lookback_days=7, 
                                                     required_parameters=['PM2.5', 'PM10'])
            location_ids = [loc.id for loc in location_objs]
            print(f"[OK] Found {len(location_ids)} active monitoring locations")
        else:
            print(f"[2/5] Fetching locations for {city}...")
            location_ids = extract_locations(client, city, country)
            location_objs = None
            print(f"[OK] Found {len(location_ids)} monitoring locations")

        if len(location_ids) == 0:
            print("[WARNING] No locations found. Pipeline stopping.")
            client.close()
            return

        # STEP 3: Extract measurements
        print(f"[3/5] Extracting measurements...")
        date_to = datetime.now()
        date_from = date_to - timedelta(hours=lookback_hours)

        measurements = extract_measurements(client, location_ids, date_from, date_to)
        client.close()
        print(f"[OK] Extracted {len(measurements)} measurements")

        if len(measurements) == 0:
            print("[WARNING] No measurements extracted. Pipeline stopping.")
            return

        # STEP 4: Transform data
        print("[4/5] Transforming data...")
        df = transform_measurements(measurements)
        
        # Enrich with metadata if vietnam_wide
        if vietnam_wide and location_objs:
            from etls.openaq_etl import enrich_measurements_with_metadata
            df = enrich_measurements_with_metadata(df, location_objs)
        
        print(f"[OK] Transformed {len(df)} records")
        param_cols = [col for col in df.columns if col not in 
                     ['location_id', 'datetime', 'latitude', 'longitude', 'city', 'country', 
                      'extracted_at', 'year', 'month', 'day', 'location_name', 'locality', 
                      'timezone', 'country_code']]
        print(f"Parameters: {param_cols}")

        # STEP 5: Load to S3 with partitioning
        print("[5/5] Uploading to S3...")
        
        if vietnam_wide:
            # For Vietnam-wide, partition by location_id
            for location_id, location_df in df.groupby('location_id'):
                s3_base_key = f"airquality/vietnam/location_{location_id}"
                upload_to_s3_partitioned(
                    data=location_df,
                    bucket=AWS_BUCKET_NAME,
                    base_key=s3_base_key,
                    partition_cols=['year', 'month', 'day'],
                    format='parquet'
                )
            print(f"[SUCCESS] Pipeline completed - uploaded {len(df)} records for {len(location_ids)} locations")
        else:
            # For city-based, use city name
            s3_base_key = f"airquality/{city.lower()}"
            upload_to_s3_partitioned(
                data=df,
                bucket=AWS_BUCKET_NAME,
                base_key=s3_base_key,
                partition_cols=['year', 'month', 'day'],
                format='parquet'
            )
            print(f"[SUCCESS] Pipeline completed - s3://{AWS_BUCKET_NAME}/{s3_base_key}")

    except Exception as e:
        print(f"[FAIL] Pipeline failed: {str(e)}")
        raise
