import sys
import os
import json
import requests
# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.constants import OPENAQ_API_KEY

DATA_DIR = r"C:\Users\cau.tran\OpenAQ-Data-Pipeline-Engineering\data"
OUTPUT_FILE = os.path.join(DATA_DIR, "mock_locations_vn.json")

# def fetch_locations_vn():
#     print("Fetching sensors in Vietnam...")
#     headers = {"X-API-Key": OPENAQ_API_KEY}
#     url = "https://api.openaq.org/v3/locations?iso=VN"
#     resp = requests.get(url, headers=headers, timeout=30)
#     print(resp.raise_for_status())
#     data = resp.json()
#         # Write JSON file
#     with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#         json.dump(data, f, ensure_ascii=False, indent=2)

#     print(f"Data successfully written to:\n{OUTPUT_FILE}")
#     return data

# if __name__ == "__main__":
#     fetch_locations_vn()

# Fetch Mockup data from local file
def fetch_mock_locations_vn():
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data