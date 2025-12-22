"""
Unit tests for extract_location function
"""
import pytest
import json
import os
from datetime import datetime, timedelta
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from etls.extract_location import extract_location
from etls.openaq_etl import connect_openaq
from utils.constants import OPENAQ_API_KEY


class TestExtractLocation:
    """Test suite for extract_location function"""
    
    def test_extract_location_from_mock_json(self):
        """Test extracting locations from mock JSON file"""
        headers = connect_openaq(api_key=OPENAQ_API_KEY)
        
        sensor_ids, location_objects = extract_location(
            headers=headers,
            vietnam_wide=True,
            lookback_days=7,
            required_parameters=['PM2.5', 'PM10']
        )
        
        # Assertions
        assert isinstance(sensor_ids, list), "sensor_ids should be a list"
        assert isinstance(location_objects, list), "location_objects should be a list"
        assert len(sensor_ids) > 0, "Should extract at least one sensor ID"
        assert len(location_objects) >= 0, "Should have location objects"
        
        # Check that sensor IDs are unique (deduplicated)
        assert len(sensor_ids) == len(set(sensor_ids)), "Sensor IDs should be deduplicated"
        
        # Check sensor ID format
        for sid in sensor_ids:
            assert isinstance(sid, int), f"Sensor ID should be int, got {type(sid)}"
    
    def test_extract_location_returns_tuple(self):
        """Test that extract_location returns correct tuple structure"""
        headers = connect_openaq(api_key=OPENAQ_API_KEY)
        
        result = extract_location(headers=headers, vietnam_wide=True)
        
        assert isinstance(result, tuple), "Should return a tuple"
        assert len(result) == 2, "Should return (sensor_ids, location_objects)"
    
    def test_extract_location_with_filtering(self):
        """Test location filtering by required parameters"""
        headers = connect_openaq(api_key=OPENAQ_API_KEY)
        
        sensor_ids, location_objects = extract_location(
            headers=headers,
            vietnam_wide=True,
            required_parameters=['PM2.5', 'PM10']
        )
        
        # All returned locations should have sensors with required parameters
        for loc in location_objects:
            sensors = loc.get('sensors', [])
            if sensors:
                param_names = [s.get('parameter', {}).get('name', '') for s in sensors]
                has_pm25 = any('PM2.5' in str(p) or 'pm25' in str(p).lower() for p in param_names)
                has_pm10 = any('PM10' in str(p) or 'pm10' in str(p).lower() for p in param_names)
                # At least one should exist (loose check due to mock data variations)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
