import sys
# Đảm bảo đường dẫn import đúng trong môi trường Docker Airflow
sys.path.insert(0, '/opt/airflow/')

from utils.constants import print_config_summary, OPENAQ_API_KEY
from utils.aws_utils import check_s3_connection
from etls.openaq_etl import connect_openaq


def test_configuration():
    """Test configuration loading."""
    print("\n=== Testing Configuration ===")
    try:
        print_config_summary()
        return True
    except Exception as e:
        print(f"[FAIL] Configuration error: {e}")
        return False


def test_openaq_connection():
    """Test OpenAQ API connection (New Logic: Headers)."""
    print("\n=== Testing OpenAQ Connection ===")
    try:
        # Logic Mới: Trả về dict headers, không phải client object
        headers = connect_openaq(OPENAQ_API_KEY)
        
        if isinstance(headers, dict) and 'X-API-Key' in headers:
            print("[OK] OpenAQ headers created successfully")
            # Ẩn bớt key khi in ra log để bảo mật
            print(f"[INFO] Headers: {{'X-API-Key': '***{headers['X-API-Key'][-4:]}'}}")
            return True
        else:
            print("[FAIL] connect_openaq did not return a valid dictionary")
            return False
            
    except Exception as e:
        print(f"[FAIL] OpenAQ connection failed: {e}")
        return False


def test_s3_connection():
    """Test AWS S3 connection."""
    print("\n=== Testing S3 Connection ===")
    return check_s3_connection()


def test_mini_pipeline():
    """Run mini pipeline with 2 hours lookback."""
    print("\n=== Testing Mini Pipeline ===")
    # Import inside function to avoid top-level errors if paths are wrong
    from pipelines.openaq_pipeline import openaq_pipeline

    try:
        # Chạy pipeline ở chế độ test (lookback ngắn)
        openaq_pipeline(
            file_name='test_run',
            city='Hanoi',
            country='VN',
            lookback_hours=2,
            vietnam_wide=False # Test chế độ 1 thành phố trước cho nhanh
        )
        print("[SUCCESS] Mini pipeline test passed (City Mode)")
        return True
    except Exception as e:
        print(f"[FAIL] Mini pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mini_pipeline_vietnam():
    """Run mini pipeline Vietnam-wide mode."""
    print("\n=== Testing Mini Pipeline (Vietnam Wide) ===")
    from pipelines.openaq_pipeline import openaq_pipeline

    try:
        openaq_pipeline(
            file_name='test_run_vietnam',
            vietnam_wide=True,
            lookback_hours=2
        )
        print("[SUCCESS] Mini pipeline test passed (Vietnam Mode)")
        return True
    except Exception as e:
        print(f"[FAIL] Mini pipeline Vietnam mode failed: {e}")
        return False


if __name__ == '__main__':
    print("STARTING PIPELINE TESTS...")
    
    # Chạy tuần tự các bài test
    cfg_ok = test_configuration()
    conn_ok = test_openaq_connection()
    s3_ok = test_s3_connection()
    
    if cfg_ok and conn_ok and s3_ok:
        # Chỉ chạy pipeline test nếu các bước connection cơ bản đã OK
        test_mini_pipeline()
        # Uncomment dòng dưới nếu muốn test chế độ toàn Việt Nam (sẽ lâu hơn)
        # test_mini_pipeline_vietnam()
    else:
        print("\n[STOP] Skipping pipeline test due to connection errors.")