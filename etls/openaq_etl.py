import requests
import pandas as pd
from datetime import datetime, timedelta
from utils.constants import OPENAQ_API_KEY

# Cấu hình API v3
BASE_URL = "https://api.openaq.org/v3"

def connect_openaq(api_key: str) -> dict:
    """Create headers for OpenAQ API authentication."""
    return {'X-API-Key': api_key}


def extract_locations(headers: dict, city: str = None, country: str = None,
                      coordinates: tuple = None, radius: int = 25000) -> list:
    """
    Get all monitoring locations by geographic coordinates using REST API.
    """
    # City coordinates mapping (Lat, Lon)
    city_coords = {
        'Hanoi': (21.0285, 105.8542),
        'Ho Chi Minh City': (10.7769, 106.7009),
        'Da Nang': (16.0544, 108.2022),
        'Nha Trang': (12.2388, 109.1967),
        'Hai Phong': (20.8449, 106.6881),
    }

    if coordinates is None:
        if city in city_coords:
            coordinates = city_coords[city]
        else:
            raise Exception(f"City '{city}' not found. Please provide coordinates.")

    print(f"[INFO] Searching locations near {city} - coordinates: {coordinates}, radius: {radius}m")

    try:
        # Gọi API: GET /locations
        # FIX: Đổi thứ tự thành lat,lng (coordinates[0], coordinates[1])
        params = {
            'coordinates': f"{coordinates[0]},{coordinates[1]}", 
            'radius': radius,
            'limit': 1000
        }
        
        response = requests.get(f"{BASE_URL}/locations", headers=headers, params=params, timeout=30)
        
        # Thêm xử lý lỗi chi tiết hơn để debug nếu cần
        if response.status_code != 200:
            print(f"[FAIL] API Error {response.status_code}: {response.text}")
            
        response.raise_for_status()
        
        data = response.json()
        locations = data.get('results', [])
        
        location_ids = [loc['id'] for loc in locations]
        print(f"[INFO] Found {len(location_ids)} locations near {city}")
        return location_ids
        
    except Exception as e:
        raise Exception(f"Failed to extract locations: {str(e)}")


def extract_measurements(headers: dict, location_ids: list,
                        date_from: datetime, date_to: datetime) -> list:
    """Extract hourly air quality measurements using REST API."""
    all_measurements = []

    for loc_id in location_ids:
        try:
            # BƯỚC 1: Lấy sensors của Location
            url = f"{BASE_URL}/locations/{loc_id}"
            resp = requests.get(url, headers=headers, timeout=30)
            
            if resp.status_code != 200:
                continue

            data = resp.json()
            results = data.get('results', [])
            
            if not results:
                continue
                
            loc_details = results[0]
            sensors = loc_details.get('sensors', [])

            if not sensors:
                continue

            # BƯỚC 2: Duyệt từng Sensor
            for sensor in sensors:
                sensor_id = sensor.get('id')
                if not sensor_id:
                    continue

                try:
                    # BƯỚC 3: Lấy measurements
                    meas_url = f"{BASE_URL}/sensors/{sensor_id}/measurements"
                    meas_params = {
                        'datetime_from': date_from.isoformat(),
                        'datetime_to': date_to.isoformat(),
                        'limit': 1000
                    }
                    
                    meas_resp = requests.get(meas_url, headers=headers, params=meas_params, timeout=30)
                    
                    if meas_resp.status_code != 200:
                        continue
                        
                    meas_data = meas_resp.json()
                    measurements = meas_data.get('results', [])

                    for m in measurements:
                        datetime_val = None
                        period = m.get('period', {})
                        if period and 'datetimeFrom' in period:
                            dt_obj = period['datetimeFrom']
                            if isinstance(dt_obj, dict):
                                datetime_val = dt_obj.get('local')
                            else:
                                datetime_val = dt_obj

                        param_info = m.get('parameter', {})
                        # Coordinates thường null ở level measurement, sẽ enrich sau
                        
                        measurement_data = {
                            'location_id': loc_id,
                            'parameter': param_info.get('name'),
                            'value': m.get('value'),
                            'unit': param_info.get('units'),
                            'datetime': datetime_val,
                            # Để null ở đây, sẽ điền ở bước enrich
                            'latitude': None, 
                            'longitude': None,
                            'city': None,
                            'country': None
                        }
                        all_measurements.append(measurement_data)
                
                except Exception:
                    continue

        except Exception as e:
            print(f"[WARNING] Failed to process location {loc_id}: {e}")
            continue

    return all_measurements


def transform_measurements(measurements: list) -> pd.DataFrame:
    """Transform raw measurements into structured DataFrame."""
    df = pd.DataFrame(measurements)

    if df.empty:
        return df

    df['datetime'] = pd.to_datetime(df['datetime'])
    df['extracted_at'] = datetime.now()

    # SỬA QUAN TRỌNG: Chỉ pivot trên location_id và datetime
    # Bỏ latitude, longitude ra khỏi index để tránh bị drop do null
    df_pivot = df.pivot_table(
        index=['location_id', 'datetime', 'extracted_at'],
        columns='parameter',
        values='value',
        aggfunc='mean'
    ).reset_index()

    # Khởi tạo lại các cột metadata để enrich
    df_pivot['latitude'] = None
    df_pivot['longitude'] = None
    df_pivot['city'] = None
    df_pivot['country'] = None

    df_pivot.columns.name = None
    df_pivot = df_pivot.sort_values('datetime').reset_index(drop=True)

    return df_pivot


def fetch_all_vietnam_locations(headers: dict, countries_id: int = 56,
                                page_size: int = 100) -> list:
    """Fetch ALL Vietnam locations."""
    try:
        all_locations = []
        page = 1
        total_fetched = 0

        print(f"[INFO] Fetching ALL Vietnam locations (countries_id={countries_id})...")

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
            total_fetched += len(results)
            print(f"[INFO] Page {page}: +{len(results)} locations (TOTAL: {total_fetched})")
            page += 1

        print(f"[SUCCESS] Fetched {len(all_locations)} Vietnam locations")
        return all_locations

    except Exception as e:
        print(f"[FAIL] Failed to fetch Vietnam locations: {str(e)}")
        raise


def filter_active_locations(locations: list, lookback_days: int = 7,
                            required_parameters: list = None) -> list:
    """Filter active locations."""
    if required_parameters is None:
        required_parameters = ['PM2.5', 'PM10']

    try:
        filtered_locations = []
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        print(f"[INFO] Filtering locations: lookback={lookback_days} days")

        for loc in locations:
            dt_last = loc.get('datetimeLast')
            if not dt_last: continue
                
            last_dt_str = dt_last.get('utc') if isinstance(dt_last, dict) else str(dt_last)
            if not last_dt_str: continue

            try:
                last_datetime = pd.to_datetime(last_dt_str).replace(tzinfo=None)
            except: continue

            if last_datetime < cutoff_date: continue

            sensors = loc.get('sensors', [])
            sensor_params = []
            for s in sensors:
                p = s.get('parameter', {})
                p_name = p.get('name') if isinstance(p, dict) else None
                if p_name: sensor_params.append(p_name)

            has_required = any(req.lower() in p.lower() for req in required_parameters for p in sensor_params)

            if has_required:
                filtered_locations.append(loc)

        print(f"[SUCCESS] Filtered to {len(filtered_locations)} active locations")
        return filtered_locations

    except Exception as e:
        print(f"[FAIL] Failed to filter locations: {str(e)}")
        raise


def enrich_measurements_with_metadata(df: pd.DataFrame, locations: list) -> pd.DataFrame:
    """
    Enrich DataFrame with metadata including COORDINATES from location list.
    """
    try:
        if df.empty:
            return df

        location_map = {}
        for loc in locations:
            loc_id = loc.get('id')
            country = loc.get('country', {})
            coords = loc.get('coordinates', {}) # Lấy tọa độ từ thông tin trạm
            
            location_map[loc_id] = {
                'location_name': loc.get('name'),
                'locality': loc.get('locality'),
                'timezone': loc.get('timezone'),
                'country_code': country.get('code') if isinstance(country, dict) else None,
                'latitude': coords.get('latitude') if coords else None,
                'longitude': coords.get('longitude') if coords else None
            }

        # Enrich tất cả thông tin metadata
        df['location_name'] = df['location_id'].map(lambda x: location_map.get(x, {}).get('location_name'))
        df['locality'] = df['location_id'].map(lambda x: location_map.get(x, {}).get('locality'))
        df['timezone'] = df['location_id'].map(lambda x: location_map.get(x, {}).get('timezone'))
        df['country_code'] = df['location_id'].map(lambda x: location_map.get(x, {}).get('country_code'))
        
        # CẬP NHẬT: Điền Lat/Lon từ Metadata
        df['latitude'] = df['location_id'].map(lambda x: location_map.get(x, {}).get('latitude'))
        df['longitude'] = df['location_id'].map(lambda x: location_map.get(x, {}).get('longitude'))

        # Điền City/Country
        df['city'] = df['locality'].fillna('Unknown')
        df['country'] = df['country_code'].fillna('VN')

        print(f"[SUCCESS] Enriched {len(df)} records")
        return df

    except Exception as e:
        print(f"[FAIL] Failed to enrich: {str(e)}")
        raise