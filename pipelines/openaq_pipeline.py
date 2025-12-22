from datetime import datetime, timedelta
import pandas as pd

# Import các biến môi trường và folder từ constants
from utils.constants import (
    OPENAQ_API_KEY,
    OPENAQ_TARGET_CITY,
    OPENAQ_TARGET_COUNTRY,
    OPENAQ_LOOKBACK_HOURS,
    AWS_BUCKET_NAME,
    ENV,
    CURRENT_ENV_FOLDER,
    RAW_FOLDER,
    GLUE_TRANSFORM_JOB_NAME,
    GLUE_JOB_TIMEOUT,
    GLUE_WORKER_TYPE,
    GLUE_NUM_WORKERS,
)

# Import new refactored extraction functions
from etls.extract_location import extract_location
from etls.extract_sensor_measurement import extract_sensor_measurement

from etls.openaq_etl import (
    connect_openaq,
    enrich_measurements_with_metadata
)

# Import S3 upload functions
from utils.aws_utils import upload_to_s3

# Import Glue job utilities for triggering transform job
from utils.glue_utils import start_glue_job


def openaq_pipeline(file_name: str, city: str = None, country: str = None,
                   lookback_hours: int = None, vietnam_wide: bool = False, **kwargs):
    """
    Main OpenAQ Extraction Pipeline (Simplified for Spark processing)

    This pipeline ONLY handles:
    1. Extract locations and sensor IDs (from mock JSON or live API)
    2. Extract measurements for those sensor IDs
    3. Enrich with metadata
    4. Upload raw JSON to S3

    Transformation (pivot, dedup, etc.) is now handled by AWS Glue PySpark job.
    Glue job is triggered separately in Airflow DAG.

    Args:
        file_name: Unique filename for raw data archive
        city: Target city (currently not used - reserved for future)
        country: Target country (currently not used - reserved for future)
        lookback_hours: Hours of historical data to extract
        vietnam_wide: If True, extract all Vietnam locations (currently required)
        **kwargs: Additional Airflow context (ti, task_instance, etc.)

    Returns:
        dict: Metadata about extracted data (status, location_count, record_count, raw_s3_path)
    """
    # Use defaults from config if not provided
    city = city or OPENAQ_TARGET_CITY
    country = country or OPENAQ_TARGET_COUNTRY
    lookback_hours = lookback_hours or OPENAQ_LOOKBACK_HOURS

    print(f"[START] OpenAQ Extraction Pipeline - {datetime.now()}")
    if vietnam_wide:
        print(f"Target: ALL Vietnam locations | Lookback: {lookback_hours} hours")
    else:
        print(f"Target: {city}, {country} | Lookback: {lookback_hours} hours")

    try:
        # STEP 1: Connect to OpenAQ (Get Headers)
        print("[1/5] Preparing OpenAQ API Headers...")
        headers = connect_openaq(api_key=OPENAQ_API_KEY)
        print("[OK] Headers prepared")

        # STEP 2: Extract locations and get sensor IDs
        print("[2/5] Extracting locations and sensor IDs...")
        sensor_ids, location_objs = extract_location(
            headers=headers,
            vietnam_wide=vietnam_wide,
            lookback_days=7,
            required_parameters=['PM2.5', 'PM10']
        )
        
        location_count = len(location_objs)
        sensor_count = len(sensor_ids)
        
        if sensor_count == 0:
            print("[WARNING] No sensors found. Pipeline stopping.")
            return {
                'status': 'WARNING',
                'location_count': location_count,
                'record_count': 0,
                'raw_s3_path': None
            }
        
        print(f"[OK] Found {location_count} locations with {sensor_count} sensors")

        # STEP 3: Extract measurements from API
        print(f"[3/5] Extracting measurements from sensor API...")
        date_to = datetime.now()
        date_from = date_to - timedelta(hours=lookback_hours)

        measurements = extract_sensor_measurement(headers, sensor_ids, date_from, date_to)
        
        if len(measurements) == 0:
            print("[WARNING] No measurements extracted. Pipeline stopping.")
            return {
                'status': 'WARNING',
                'location_count': location_count,
                'record_count': 0,
                'raw_s3_path': None
            }
        
        print(f"[OK] Extracted {len(measurements)} measurements")

        # STEP 4: Enrich measurements with location metadata (city, coordinates)
        print(f"[4/5] Enriching measurements with location metadata...")
        df_raw = pd.DataFrame(measurements)
        df_enriched = enrich_measurements_with_metadata(df_raw, location_objs)
        print(f"[OK] Enriched {len(df_enriched)} records with location metadata")

        # STEP 5: Archive raw data to S3 (JSON format for Glue to process)
        print(f"[5/5] Archiving raw data to S3...")
        now = datetime.now()

        # Structure: aq_raw/year/month/day/hour/raw_measurements.json
        raw_key = f"{RAW_FOLDER}/{now.year}/{now.strftime('%m')}/{now.strftime('%d')}/{now.strftime('%H')}/raw_{file_name}.json"

        # Upload enriched DataFrame to S3
        upload_to_s3(df_enriched, AWS_BUCKET_NAME, raw_key, format='json')

        result = {
            'status': 'SUCCESS',
            'location_count': location_count,
            'record_count': len(measurements),
            'raw_s3_path': f"s3://{AWS_BUCKET_NAME}/{raw_key}"
        }

        print(f"[SUCCESS] Extraction complete:")
        print(f"  - Locations: {result['location_count']}")
        print(f"  - Sensors: {sensor_count}")
        print(f"  - Records: {result['record_count']}")
        print(f"  - Raw data: {result['raw_s3_path']}")

        return result

    except Exception as e:
        print(f"[FAIL] Pipeline failed: {str(e)}")
        raise