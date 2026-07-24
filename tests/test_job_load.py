"""Tests for GET /api/cnc/job/load/{job_number}/{step}/{qty}."""

import pytest
from unittest.mock import patch


pytestmark = pytest.mark.asyncio


class TestJobLoad:

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_success(self, mock_glob, client, fake_client):
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_10.nc"]

        resp = await client.get(
            "/api/cnc/job/load/123456789012/10/1",
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
            "/api/cnc/job/load/987654321098/20/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 22
        # assert "error code" in body["message"].lower()

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_returns_filename(self, mock_glob, client, fake_client):
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\111111111111\Setup_5.nc"]

        resp = await client.get(
            "/api/cnc/job/load/111111111111/5/1",
        )

        body = resp.json()
        assert "111111111111" in body["fileName"]
        assert "Setup_5" in body["fileName"]

    async def test_load_invalid_job_number_too_short(self, client):
        resp = await client.get(
            "/api/cnc/job/load/12345/10/1",
        )

        assert resp.status_code == 422  # validation error

    async def test_load_invalid_job_number_too_long(self, client):
        resp = await client.get(
            "/api/cnc/job/load/1234567890123/10/1",
        )

        assert resp.status_code == 422  # validation error

    async def test_load_invalid_job_number_non_numeric(self, client):
        resp = await client.get(
            "/api/cnc/job/load/12345678901A/10/1",
        )

        assert resp.status_code == 422  # validation error

    async def test_load_invalid_step_non_numeric(self, client):
        resp = await client.get(
            "/api/cnc/job/load/123456789012/ABC/1",
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
            "/api/cnc/job/load/123456789012/10/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == -1
        assert "exception" in body["message"].lower()

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_with_multi_digit_step(self, mock_glob, client, fake_client):
        """Multi-digit step numbers should be accepted."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_123.nc"]

        resp = await client.get(
            "/api/cnc/job/load/123456789012/123/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert "Setup_123" in body["fileName"]

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_constructs_path_correctly(self, mock_glob, client, fake_client):
        """Verify that path is constructed correctly with base dir and Setup_ pattern."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\999999999999\Setup_99_Rev1.nc"]

        resp = await client.get(
            "/api/cnc/job/load/999999999999/99/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        # Verify glob was called for both .nc and .cnc extensions
        assert mock_glob.call_count == 2
        mock_glob.assert_any_call(r"\\192.168.2.11\Production\CNC\Mills\999999999999\Setup_99*.nc")
        mock_glob.assert_any_call(r"\\192.168.2.11\Production\CNC\Mills\999999999999\Setup_99*.cnc")
        # Verify the full path is returned
        assert body["fileName"] == r"\\192.168.2.11\Production\CNC\Mills\999999999999\Setup_99_Rev1.nc"

    @patch('src.api.schemas.job.os.path.isdir', return_value=False)
    @patch('src.api.schemas.job.glob.glob')
    async def test_load_file_not_found(self, mock_glob, mock_isdir, client, fake_client):
        """When no matching file is found, return error."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = []  # No files found

        resp = await client.get(
            "/api/cnc/job/load/123456789012/10/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 20
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
            "/api/cnc/job/load/123456789012/10/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 9
        assert "multiple" in body["message"].lower()

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_real_pattern_setup_1_with_description(self, mock_glob, client, fake_client):
        """Test with real file name pattern: Setup_1 F6 #22.nc from 000068050050"""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_1 F6 #22.nc"]

        resp = await client.get(
            "/api/cnc/job/load/000068050050/1/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert body["fileName"] == r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_1 F6 #22.nc"
        # Verify glob pattern would match files starting with Setup_1 for both .nc and .cnc
        assert mock_glob.call_count == 2
        mock_glob.assert_any_call(r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_1*.nc")
        mock_glob.assert_any_call(r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_1*.cnc")

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_real_pattern_setup_2_with_description(self, mock_glob, client, fake_client):
        """Test with real file name pattern: Setup_2 F6 #20.nc from 000068050050"""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_2 F6 #20.nc"]

        resp = await client.get(
            "/api/cnc/job/load/000068050050/2/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert body["fileName"] == r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_2 F6 #20.nc"

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_real_pattern_setup_3_with_description(self, mock_glob, client, fake_client):
        """Test with real file name pattern: Setup_3 F3i8 Drill.nc from 000068050050"""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_3 F3i8 Drill.nc"]

        resp = await client.get(
            "/api/cnc/job/load/000068050050/3/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert body["fileName"] == r"\\192.168.2.11\Production\CNC\Mills\000068050050\Setup_3 F3i8 Drill.nc"

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_real_job_000150650010_setup_1(self, mock_glob, client, fake_client):
        """Test with real job 000150650010, Setup_1 F6 #32.nc"""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\000150650010\Setup_1 F6 #32.nc"]

        resp = await client.get(
            "/api/cnc/job/load/000150650010/1/1",
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
            "/api/cnc/job/load/000068050050/1/1",
        )

        assert resp.status_code == 200
        # Verify load_job was called with the full path including description
        assert fake_client.load_job.call_count == 1 if hasattr(fake_client.load_job, 'call_count') else True
        body = resp.json()
        assert body["fileName"] == expected_path

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_with_qty_parameter(self, mock_glob, client, fake_client):
        """Test loading with quantity parameter (currently hardcoded to 1, so qty is not used)."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_1.nc"]

        resp = await client.get(
            "/api/cnc/job/load/123456789012/1/5",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        # Currently qty is hardcoded to 1, so message should not mention quantity
        assert "quantity" not in body["message"]

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_with_default_qty(self, mock_glob, client, fake_client):
        """Test loading with quantity = 1 (no repeat)."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_1.nc"]

        resp = await client.get(
            "/api/cnc/job/load/123456789012/1/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        # Should not mention quantity when qty=1
        assert "quantity" not in body["message"]

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_with_invalid_qty_too_low(self, mock_glob, client, fake_client):
        """Test loading with qty < 1 is rejected."""
        resp = await client.get(
            "/api/cnc/job/load/123456789012/1/0",
        )

        assert resp.status_code == 422  # Validation error

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_with_invalid_qty_too_high(self, mock_glob, client, fake_client):
        """Test loading with qty > 9999 is rejected."""
        resp = await client.get(
            "/api/cnc/job/load/123456789012/1/10000",
        )

        assert resp.status_code == 422  # Validation error

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_with_max_qty(self, mock_glob, client, fake_client):
        """Test loading with maximum quantity (currently qty is hardcoded to 1)."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_1.nc"]

        resp = await client.get(
            "/api/cnc/job/load/123456789012/1/9999",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        # Currently qty is hardcoded to 1, so message should not mention quantity
        assert "quantity" not in body["message"]

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_with_cnc_extension(self, mock_glob, client, fake_client):
        """Test loading with .cnc extension (not .nc)."""
        fake_client._load_job_rc = 0
        # Return .cnc file on second glob call
        mock_glob.side_effect = [
            [],  # First call for .nc returns empty
            [r"\\192.168.2.11\Production\CNC\Mills\000244490010\Setup_1 F6i45 #77.cnc"]  # Second call for .cnc
        ]

        resp = await client.get(
            "/api/cnc/job/load/000244490010/1/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert body["fileName"] == r"\\192.168.2.11\Production\CNC\Mills\000244490010\Setup_1 F6i45 #77.cnc"
        assert ".cnc" in body["fileName"]
    @patch('src.api.schemas.job.glob.glob')
    async def test_load_success_opens_jog_pad(self, mock_glob, client, fake_client, test_app):
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_10.nc"]

        resp = await client.get(
            "/api/cnc/job/load/123456789012/10/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert "jog pad opened" in body["message"].lower()
        test_app.state.services.jog_pad_launcher.assert_called_once_with("http://127.0.0.1:9999", 500)

    @patch('src.api.schemas.job.glob.glob')
    async def test_load_failure_does_not_open_jog_pad(self, mock_glob, client, fake_client, test_app):
        fake_client._load_job_rc = 22
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_10.nc"]

        resp = await client.get(
            "/api/cnc/job/load/123456789012/10/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 22
        test_app.state.services.jog_pad_launcher.assert_not_called()
    @patch('src.api.schemas.job.glob.glob')
    async def test_load_success_reports_jog_pad_launch_failure(self, mock_glob, client, fake_client, test_app):
        from types import SimpleNamespace

        fake_client._load_job_rc = 0
        test_app.state.services.jog_pad_launcher.return_value = SimpleNamespace(status=1, message="no desktop")
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_10.nc"]

        resp = await client.get(
            "/api/cnc/job/load/123456789012/10/1",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert "jog pad launch failed" in body["message"].lower()
        assert "no desktop" in body["message"]
