"""
Unit tests for AWS Glue utilities.
"""
import pytest
from unittest.mock import patch, MagicMock
from utils.glue_utils import (
    get_glue_client,
    start_crawler,
    get_crawler_status,
    wait_for_crawler,
    start_glue_job,
    get_job_run_status,
    wait_for_job
)


class TestGlueClient:
    """Test Glue client creation."""

    @patch('utils.glue_utils.boto3.client')
    def test_get_glue_client(self, mock_boto3_client):
        """Test that get_glue_client creates a valid Glue client."""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        result = get_glue_client()

        assert result == mock_client
        mock_boto3_client.assert_called_once()


class TestCrawler:
    """Test Glue Crawler functions."""

    @patch('utils.glue_utils.get_glue_client')
    def test_start_crawler_success(self, mock_get_client):
        """Test successful crawler start."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.start_crawler.return_value = {'CrawlerName': 'test_crawler'}

        result = start_crawler('test_crawler')

        assert result == {'CrawlerName': 'test_crawler'}
        mock_client.start_crawler.assert_called_once_with(Name='test_crawler')

    @patch('utils.glue_utils.get_glue_client')
    def test_start_crawler_failure(self, mock_get_client):
        """Test crawler start with exception."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.start_crawler.side_effect = Exception("Crawler not found")

        with pytest.raises(Exception):
            start_crawler('nonexistent_crawler')

    @patch('utils.glue_utils.get_glue_client')
    def test_get_crawler_status(self, mock_get_client):
        """Test getting crawler status."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_crawler.return_value = {
            'Crawler': {'State': 'READY'}
        }

        result = get_crawler_status('test_crawler')

        assert result == 'READY'

    @patch('utils.glue_utils.time.sleep')
    @patch('utils.glue_utils.get_crawler_status')
    def test_wait_for_crawler_success(self, mock_get_status, mock_sleep):
        """Test waiting for crawler to complete."""
        mock_get_status.return_value = 'READY'

        result = wait_for_crawler('test_crawler', timeout=300)

        assert result is True
        mock_get_status.assert_called()

    @patch('utils.glue_utils.time.sleep')
    @patch('utils.glue_utils.time.time')
    @patch('utils.glue_utils.get_crawler_status')
    def test_wait_for_crawler_timeout(self, mock_get_status, mock_time, mock_sleep):
        """Test crawler timeout."""
        mock_get_status.return_value = 'RUNNING'
        mock_time.side_effect = [0, 400, 400]  # Simulate timeout

        result = wait_for_crawler('test_crawler', timeout=300)

        assert result is False


class TestGlueJob:
    """Test Glue Job functions."""

    @patch('utils.glue_utils.get_glue_client')
    def test_start_glue_job_success(self, mock_get_client):
        """Test successful Glue job start."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.start_job_run.return_value = {'JobRunId': 'run-123'}

        result = start_glue_job('test_job', {'arg1': 'value1'})

        assert result == 'run-123'
        mock_client.start_job_run.assert_called_once()

    @patch('utils.glue_utils.get_glue_client')
    def test_start_glue_job_no_args(self, mock_get_client):
        """Test starting Glue job without arguments."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.start_job_run.return_value = {'JobRunId': 'run-456'}

        result = start_glue_job('test_job')

        assert result == 'run-456'

    @patch('utils.glue_utils.get_glue_client')
    def test_get_job_run_status(self, mock_get_client):
        """Test getting job run status."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_job_run.return_value = {
            'JobRun': {'JobRunState': 'SUCCEEDED'}
        }

        result = get_job_run_status('test_job', 'run-123')

        assert result == 'SUCCEEDED'

    @patch('utils.glue_utils.time.sleep')
    @patch('utils.glue_utils.get_job_run_status')
    def test_wait_for_job_success(self, mock_get_status, mock_sleep):
        """Test waiting for job to succeed."""
        mock_get_status.return_value = 'SUCCEEDED'

        result = wait_for_job('test_job', 'run-123', timeout=3600)

        assert result is True

    @patch('utils.glue_utils.time.sleep')
    @patch('utils.glue_utils.get_job_run_status')
    def test_wait_for_job_failure(self, mock_get_status, mock_sleep):
        """Test job failure detection."""
        mock_get_status.return_value = 'FAILED'

        result = wait_for_job('test_job', 'run-123', timeout=3600)

        assert result is False
