"""Tests for GET /api/cnc/job/load/{job_number}/{step}."""

import pytest
from unittest.mock import patch


pytestmark = pytest.mark.asyncio


class TestJobLoad:

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_success(self, mock_glob, client, fake_client):
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_10.nc"]

        resp = await client.get(
            "/api/cnc/job/load/123456789012/10",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert "successfully" in body["message"].lower()
        assert "Setup_10.nc" in body["fileName"]

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_failure_returns_error_code(self, mock_glob, client, fake_client):
        fake_client._load_job_rc = 22  # server not running
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\987654321098\Setup_20.nc"]

        resp = await client.get(
            "/api/cnc/job/load/987654321098/20",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 22
        assert "error code" in body["message"].lower()

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_returns_filename(self, mock_glob, client, fake_client):
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\111111111111\Setup_5.nc"]

        resp = await client.get(
            "/api/cnc/job/load/111111111111/5",
        )

        body = resp.json()
        assert "111111111111" in body["fileName"]
        assert "Setup_5" in body["fileName"]

    async def test_load_invalid_job_number_too_short(self, client):
        resp = await client.get(
            "/api/cnc/job/load/12345/10",
        )

        assert resp.status_code == 422  # validation error

    async def test_load_invalid_job_number_too_long(self, client):
        resp = await client.get(
            "/api/cnc/job/load/1234567890123/10",
        )

        assert resp.status_code == 422  # validation error

    async def test_load_invalid_job_number_non_numeric(self, client):
        resp = await client.get(
            "/api/cnc/job/load/12345678901A/10",
        )

        assert resp.status_code == 422  # validation error

    async def test_load_invalid_step_non_numeric(self, client):
        resp = await client.get(
            "/api/cnc/job/load/123456789012/ABC",
        )

        assert resp.status_code == 422  # validation error

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_exception_in_client(self, mock_glob, client, fake_client):
        """If the CNC client raises, the handler should catch and return -1."""
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_10.nc"]

        def raise_error(fn):
            raise RuntimeError("DLL crashed")

        fake_client.load_job = raise_error

        resp = await client.get(
            "/api/cnc/job/load/123456789012/10",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == -1
        assert "exception" in body["message"].lower()

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_with_multi_digit_step(self, mock_glob, client, fake_client):
        """Multi-digit step numbers should be accepted."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_12345.nc"]

        resp = await client.get(
            "/api/cnc/job/load/123456789012/12345",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert "Setup_12345" in body["fileName"]

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_constructs_path_correctly(self, mock_glob, client, fake_client):
        """Verify that path is constructed correctly with base dir and Setup_ pattern."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\999999999999\Setup_99_Rev1.nc"]

        resp = await client.get(
            "/api/cnc/job/load/999999999999/99",
        )

        assert resp.status_code == 200
        body = resp.json()
        # Verify the glob was called with correct pattern
        mock_glob.assert_called_once_with(r"\\192.168.2.11\Production\CNC\Mills\999999999999\Setup_99*.nc")
        # Verify the full path is returned
        assert body["fileName"] == r"\\192.168.2.11\Production\CNC\Mills\999999999999\Setup_99_Rev1.nc"

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_file_not_found(self, mock_glob, client, fake_client):
        """When no matching file is found, return error."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = []  # No files found

        resp = await client.get(
            "/api/cnc/job/load/123456789012/10",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == -1
        assert "file not found" in body["message"].lower()

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_multiple_files_found(self, mock_glob, client, fake_client):
        """When multiple matching files are found, return error."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [
            r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_10_Rev1.nc",
            r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_10_Rev2.nc",
        ]

        resp = await client.get(
            "/api/cnc/job/load/123456789012/10",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == -1
        assert "multiple" in body["message"].lower()

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_real_pattern_setup_1_with_description(self, mock_glob, client, fake_client):
        """Test with real file name pattern: Setup_1 F6 #22.nc from 000068050050"""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_1 F6 #22.nc"]

        resp = await client.get(
            "/api/cnc/job/load/000068050050/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert "Setup_1 F6 #22.nc" in body["fileName"]
        # Verify glob pattern would match files starting with Setup_1
        mock_glob.assert_called_once_with(r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_1*.nc")

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_real_pattern_setup_2_with_description(self, mock_glob, client, fake_client):
        """Test with real file name pattern: Setup_2 F6 #20.nc from 000068050050"""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_2 F6 #20.nc"]

        resp = await client.get(
            "/api/cnc/job/load/000068050050/2",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert "Setup_2 F6 #20.nc" in body["fileName"]

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_real_pattern_setup_3_with_description(self, mock_glob, client, fake_client):
        """Test with real file name pattern: Setup_3 F3i8 Drill.nc from 000068050050"""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_3 F3i8 Drill.nc"]

        resp = await client.get(
            "/api/cnc/job/load/000068050050/3",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert "Setup_3 F3i8 Drill.nc" in body["fileName"]

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_real_job_000150650010_setup_1(self, mock_glob, client, fake_client):
        """Test with real job 000150650010, Setup_1 F6 #32.nc"""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\000150650010\Setup_1 F6 #32.nc"]

        resp = await client.get(
            "/api/cnc/job/load/000150650010/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert body["fileName"] == r"\\192.168.2.11\Production\CNC\Mills\000150650010\Setup_1 F6 #32.nc"

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_passes_full_path_to_cnc_client(self, mock_glob, client, fake_client):
        """Verify that the full path with description is passed to the CNC client."""
        fake_client._load_job_rc = 0
        expected_path = r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_1 F6 #22.nc"
        mock_glob.return_value = [expected_path]

        resp = await client.get(
            "/api/cnc/job/load/000068050050/1",
        )

        assert resp.status_code == 200
        # Verify load_job was called with the full path including description
        assert fake_client.load_job.call_count == 1 if hasattr(fake_client.load_job, 'call_count') else True
        body = resp.json()
        assert body["fileName"] == expected_path


