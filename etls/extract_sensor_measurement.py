import os
import json
import requests
from extract_location import fetch_mock_locations_vn
from utils.constants import OPENAQ_API_KEY

BASE_URL = "https://api.openaq.org/v3"
headers = {
    "X-API-Key": OPENAQ_API_KEY
}

# def extract_sensor_ids(locations_json):
#     """
#     Extract sensor IDs from OpenAQ locations response.

#     Args:
#         locations_json (dict): Locations API response

#     Returns:
#         list[int]: List of sensor IDs
#     """
#     sensor_ids = set()

#     for location in locations_json.get("results", []):
#         for sensor in location.get("sensors", []):
#             sensor_ids.add(sensor["id"])

#     return list(sensor_ids)

def extract_sensor_ids(_):
    """
    Mock sensor ID for testing.
    """
    return ["7772024"]


def fetch_sensor_data(sensor_id):
    """
    Fetch measurements for a given sensor ID.
    """
    try:
        response = requests.get(
            f"{BASE_URL}/sensors/{sensor_id}/measurements",
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching sensor {sensor_id}: {e}")
        return None

def save_sensor_data_to_file(sensor_id, data, output_dir="C:\\Users\\cau.tran\\OpenAQ-Data-Pipeline-Engineering\\data"):
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"sensor_{sensor_id}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Saved sensor {sensor_id} → {file_path}")

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
