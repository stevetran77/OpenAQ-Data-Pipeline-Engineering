"""
Unit tests for AWS Redshift utilities.
"""
import pytest
from unittest.mock import patch, MagicMock
from utils.redshift_utils import (
    get_redshift_connection,
    execute_query,
    create_schema_if_not_exists,
    get_table_row_count,
    validate_data_load
)


class TestRedshiftConnection:
    """Test Redshift connection functions."""

    @patch('utils.redshift_utils.redshift_connector.connect')
    def test_get_redshift_connection_success(self, mock_connect):
        """Test successful Redshift connection."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        result = get_redshift_connection()

        assert result == mock_conn
        mock_connect.assert_called_once()

    @patch('utils.redshift_utils.redshift_connector.connect')
    def test_get_redshift_connection_failure(self, mock_connect):
        """Test connection failure."""
        mock_connect.side_effect = Exception("Connection failed")

        with pytest.raises(Exception):
            get_redshift_connection()


class TestQuery:
    """Test query execution functions."""

    @patch('utils.redshift_utils.get_redshift_connection')
    def test_execute_query_success(self, mock_get_conn):
        """Test successful query execution."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        execute_query("SELECT 1;")

        mock_cursor.execute.assert_called_once_with("SELECT 1;")
        mock_conn.commit.assert_called_once()

    @patch('utils.redshift_utils.get_redshift_connection')
    def test_execute_query_with_fetch(self, mock_get_conn):
        """Test query execution with fetch."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(100,)]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = execute_query("SELECT COUNT(*);", fetch=True)

        assert result == [(100,)]
        mock_cursor.fetchall.assert_called_once()

    @patch('utils.redshift_utils.get_redshift_connection')
    def test_execute_query_failure(self, mock_get_conn):
        """Test query execution failure."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Query error")
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        with pytest.raises(Exception):
            execute_query("SELECT * FROM invalid_table;")


class TestSchema:
    """Test schema operations."""

    @patch('utils.redshift_utils.execute_query')
    def test_create_schema_if_not_exists(self, mock_execute):
        """Test schema creation."""
        create_schema_if_not_exists()

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0][0]
        assert "CREATE SCHEMA" in call_args


class TestValidation:
    """Test data validation functions."""

    @patch('utils.redshift_utils.execute_query')
    def test_get_table_row_count(self, mock_execute):
        """Test getting table row count."""
        mock_execute.return_value = [(150,)]

        result = get_table_row_count('fact_measurements')

        assert result == 150

    @patch('utils.redshift_utils.execute_query')
    def test_get_table_row_count_empty_result(self, mock_execute):
        """Test row count with no results."""
        mock_execute.return_value = None

        result = get_table_row_count('fact_measurements')

        assert result == 0

    @patch('utils.redshift_utils.get_table_row_count')
    def test_validate_data_load_success(self, mock_get_count):
        """Test successful data validation."""
        mock_get_count.return_value = 1000

        result = validate_data_load('fact_measurements', min_expected_count=100)

        assert result is True

    @patch('utils.redshift_utils.get_table_row_count')
    def test_validate_data_load_failure(self, mock_get_count):
        """Test data validation failure."""
        mock_get_count.return_value = 50

        result = validate_data_load('fact_measurements', min_expected_count=100)

        assert result is False

    @patch('utils.redshift_utils.get_table_row_count')
    def test_validate_data_load_default_threshold(self, mock_get_count):
        """Test validation with default threshold."""
        mock_get_count.return_value = 1

        result = validate_data_load('fact_measurements')

        assert result is True
