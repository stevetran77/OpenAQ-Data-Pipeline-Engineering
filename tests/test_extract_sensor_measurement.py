"""
Unit tests for extract_sensor_measurement function
"""
import pytest
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from etls.extract_sensor_measurement import extract_sensor_measurement
from etls.openaq_etl import connect_openaq
from utils.constants import OPENAQ_API_KEY


class TestExtractSensorMeasurement:
    """Test suite for extract_sensor_measurement function"""
    
    def test_extract_sensor_measurement_returns_list(self):
        """Test that extract_sensor_measurement returns a list"""
        headers = connect_openaq(api_key=OPENAQ_API_KEY)
        
        date_to = datetime.now()
        date_from = date_to - timedelta(hours=24)
        
        # Use a real sensor ID from the API
        sensor_ids = [7772024]  # Example sensor ID
        
        result = extract_sensor_measurement(headers, sensor_ids, date_from, date_to)
        
        assert isinstance(result, list), "Should return a list"
    
    def test_extract_sensor_measurement_empty_sensor_ids(self):
        """Test with empty sensor IDs list"""
        headers = connect_openaq(api_key=OPENAQ_API_KEY)
        
        date_to = datetime.now()
        date_from = date_to - timedelta(hours=24)
        
        result = extract_sensor_measurement(headers, [], date_from, date_to)
        
        assert isinstance(result, list), "Should return a list"
        assert len(result) == 0, "Empty sensor IDs should return empty list"
    
    def test_extract_sensor_measurement_structure(self):
        """Test that measurements have correct structure"""
        headers = connect_openaq(api_key=OPENAQ_API_KEY)
        
        date_to = datetime.now()
        date_from = date_to - timedelta(hours=24)
        
        sensor_ids = [7772024]
        
        measurements = extract_sensor_measurement(headers, sensor_ids, date_from, date_to)
        
        if len(measurements) > 0:
            # Check first measurement has expected keys
            m = measurements[0]
            expected_keys = ['sensor_id', 'parameter', 'value', 'unit', 'datetime']
            for key in expected_keys:
                assert key in m, f"Measurement should have '{key}' key"
    
    def test_extract_sensor_measurement_datetime_format(self):
        """Test that datetime values are properly formatted"""
        headers = connect_openaq(api_key=OPENAQ_API_KEY)
        
        date_to = datetime.now()
        date_from = date_to - timedelta(hours=24)
        
        sensor_ids = [7772024]
        
        measurements = extract_sensor_measurement(headers, sensor_ids, date_from, date_to)
        
        if len(measurements) > 0:
            # Check that datetime is either string or can be parsed
            for m in measurements[:5]:  # Check first 5
                datetime_val = m.get('datetime')
                # Should be a string or None
                assert datetime_val is None or isinstance(datetime_val, str), \
                    f"Datetime should be string or None, got {type(datetime_val)}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
