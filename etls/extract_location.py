import sys
import os
import json
import requests
from datetime import datetime, timedelta
import pandas as pd

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.constants import OPENAQ_API_KEY

# Constants
BASE_URL = "https://api.openaq.org/v3"
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
MOCK_LOCATIONS_FILE = os.path.join(DATA_DIR, "mock_locations_vn.json")


def extract_location(headers: dict, vietnam_wide: bool = True, 
                    lookback_days: int = 7, 
                    required_parameters: list = None) -> tuple:
    """
    Extract locations and sensor IDs from mock JSON file or live API.
    
    Strategy: Try mock JSON first; if it fails, fall back to live API.
    Then extract sensor IDs from locations and deduplicate.
    
    Args:
        headers: OpenAQ API headers with X-API-Key
        vietnam_wide: If True, fetch all Vietnam locations; if False, use live API only
        lookback_days: Filter locations updated within this many days
        required_parameters: List of required parameters (e.g., ['PM2.5', 'PM10'])
    
    Returns:
        tuple: (sensor_ids: list[int], location_objects: list[dict])
    """
    if required_parameters is None:
        required_parameters = ['PM2.5', 'PM10']
    
    location_objects = []
    
    # STEP 1: Try mock JSON first
    print("[INFO] Attempting to load locations from mock JSON...")
    try:
        with open(MOCK_LOCATIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            location_objects = data.get('results', [])
            if location_objects:
                print(f"[OK] Loaded {len(location_objects)} locations from mock JSON")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[INFO] Mock JSON unavailable ({type(e).__name__}), falling back to live API")
        location_objects = []
    
    # STEP 2: If mock failed or is empty, fetch from live API
    if not location_objects:
        print("[INFO] Fetching locations from OpenAQ API...")
        try:
            all_locations = []
            page = 1
            page_size = 100
            countries_id = 56  # Vietnam
            
            while True:
                params = {
                    'countries_id': countries_id,
                    'limit': page_size,
                    'page': page
                }
                
                response = requests.get(f"{BASE_URL}/locations", headers=headers, params=params, timeout=30)
                
                if response.status_code != 200:
                    print(f"[FAIL] API Error {response.status_code}: {response.text}")
                    break
                
                data = response.json()
                results = data.get('results', [])
                
                if not results:
                    print(f"[INFO] Pagination complete at page {page}")
                    break
                
                all_locations.extend(results)
                print(f"[INFO] Page {page}: +{len(results)} locations (TOTAL: {len(all_locations)})")
                page += 1
            
            location_objects = all_locations
            print(f"[OK] Fetched {len(location_objects)} locations from live API")
        
        except Exception as e:
            print(f"[FAIL] Failed to fetch locations from API: {str(e)}")
            raise
    
    # STEP 3: Filter active locations (optional, for live API results)
    if location_objects and vietnam_wide:
        print(f"[INFO] Filtering active locations (lookback={lookback_days} days)...")
        filtered_locations = []
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        for loc in location_objects:
            dt_last = loc.get('datetimeLast')
            if not dt_last:
                continue
            
            last_dt_str = dt_last.get('utc') if isinstance(dt_last, dict) else str(dt_last)
            if not last_dt_str:
                continue
            
            try:
                last_datetime = pd.to_datetime(last_dt_str).replace(tzinfo=None)
            except:
                continue
            
            if last_datetime < cutoff_date:
                continue
            
            # Check for required parameters
            sensors = loc.get('sensors', [])
            sensor_params = []
            for s in sensors:
                p = s.get('parameter', {})
                p_name = p.get('name') if isinstance(p, dict) else None
                if p_name:
                    sensor_params.append(p_name)
            
            has_required = any(req.lower() in p.lower() for req in required_parameters for p in sensor_params)
            
            if has_required:
                filtered_locations.append(loc)
        
        location_objects = filtered_locations
        print(f"[OK] Filtered to {len(location_objects)} active locations")
    
    # STEP 4: Extract and deduplicate sensor IDs
    print("[INFO] Extracting sensor IDs...")
    sensor_ids = set()
    
    for loc in location_objects:
        sensors = loc.get('sensors', [])
        for sensor in sensors:
            sensor_id = sensor.get('id')
            if sensor_id:
                sensor_ids.add(sensor_id)
    
    sensor_ids = sorted(list(sensor_ids))  # Sort for consistency
    
    print(f"[OK] Extracted {len(sensor_ids)} unique sensor IDs")
    print(f"[SUCCESS] Location extraction complete: {len(location_objects)} locations, {len(sensor_ids)} sensors")
    
    return sensor_ids, location_objects