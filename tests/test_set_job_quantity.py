"""Tests for set_job_quantity functionality."""

import pytest
from unittest.mock import MagicMock, patch
from ctypes import c_int, c_uint



class TestSetJobQuantity:
    """Tests for the set_job_quantity method in CncClient."""

    def test_set_job_quantity_with_qty_1_disables_repeat(self):
        """When qty=1, doRepeat should be 0 (disabled)."""
        from src.cnc.cnc_client import CncClient
        from src.core.config import Settings

        settings = Settings()

        with patch('src.cnc.cnc_client.WinDLL') as mock_dll_class:
            mock_dll = MagicMock()
            mock_dll_class.return_value = mock_dll
            mock_dll.CncSetExtraJobOptions.return_value = 0

            client = CncClient(settings)
            result = client.set_job_quantity(1)

            assert result == 0
            # Verify doRepeat=0 when qty=1
            call_args = mock_dll.CncSetExtraJobOptions.call_args
            assert call_args[0][0] == b""  # extraLine
            assert call_args[0][1].value == 0  # doRepeat = 0
            assert call_args[0][2].value == 1  # numberOfRepeats = 1

    def test_set_job_quantity_with_qty_5_enables_repeat(self):
        """When qty>1, doRepeat should be 1 (enabled) and M02 should be set as extraLine."""
        from src.cnc.cnc_client import CncClient
        from src.core.config import Settings

        settings = Settings()

        with patch('src.cnc.cnc_client.WinDLL') as mock_dll_class:
            mock_dll = MagicMock()
            mock_dll_class.return_value = mock_dll
            mock_dll.CncSetExtraJobOptions.return_value = 0

            client = CncClient(settings)
            result = client.set_job_quantity(5)

            assert result == 0
            # Verify doRepeat=1 when qty>1 and M02 is set as workaround
            call_args = mock_dll.CncSetExtraJobOptions.call_args
            assert call_args[0][0] == b"M02"  # extraLine set to M02 for repeat bug workaround
            assert call_args[0][1].value == 1  # doRepeat = 1
            assert call_args[0][2].value == 5  # numberOfRepeats = 5

    def test_set_job_quantity_with_max_qty(self):
        """Test with maximum allowed quantity (9999)."""
        from src.cnc.cnc_client import CncClient
        from src.core.config import Settings

        settings = Settings()

        with patch('src.cnc.cnc_client.WinDLL') as mock_dll_class:
            mock_dll = MagicMock()
            mock_dll_class.return_value = mock_dll
            mock_dll.CncSetExtraJobOptions.return_value = 0

            client = CncClient(settings)
            result = client.set_job_quantity(9999)

            assert result == 0
            call_args = mock_dll.CncSetExtraJobOptions.call_args
            assert call_args[0][1].value == 1  # doRepeat = 1
            assert call_args[0][2].value == 9999  # numberOfRepeats = 9999

    def test_set_job_quantity_returns_error_code_on_failure(self):
        """Test that error codes from DLL are returned."""
        from src.cnc.cnc_client import CncClient
        from src.core.config import Settings

        settings = Settings()

        with patch('src.cnc.cnc_client.WinDLL') as mock_dll_class:
            mock_dll = MagicMock()
            mock_dll_class.return_value = mock_dll
            mock_dll.CncSetExtraJobOptions.return_value = 24  # CNC_RC_ERR_NOT_CONNECTED

            client = CncClient(settings)
            result = client.set_job_quantity(5)

            assert result == 24

    def test_set_job_quantity_handles_exception(self):
        """Test that exceptions are caught and -1 is returned."""
        from src.cnc.cnc_client import CncClient
        from src.core.config import Settings

        settings = Settings()

        with patch('src.cnc.cnc_client.WinDLL') as mock_dll_class:
            mock_dll = MagicMock()
            mock_dll_class.return_value = mock_dll
            mock_dll.CncSetExtraJobOptions.side_effect = RuntimeError("DLL crashed")

            client = CncClient(settings)
            result = client.set_job_quantity(5)

            assert result == -1

    def test_set_job_quantity_passes_correct_ctypes(self):
        """Verify correct ctypes are used for parameters."""
        from src.cnc.cnc_client import CncClient
        from src.core.config import Settings

        settings = Settings()

        with patch('src.cnc.cnc_client.WinDLL') as mock_dll_class:
            mock_dll = MagicMock()
            mock_dll_class.return_value = mock_dll
            mock_dll.CncSetExtraJobOptions.return_value = 0

            client = CncClient(settings)
            client.set_job_quantity(10)

            call_args = mock_dll.CncSetExtraJobOptions.call_args
            # Verify types
            assert isinstance(call_args[0][0], bytes)  # extraLine is bytes
            assert isinstance(call_args[0][1], c_int)  # doRepeat is c_int
            assert isinstance(call_args[0][2], c_uint)  # numberOfRepeats is c_uint

    def test_mock_client_set_job_quantity(self):
        """Test MockCncClient implementation."""
        from src.cnc.mock_cnc_client import MockCncClient

        client = MockCncClient()
        result = client.set_job_quantity(5)

        assert result == 0

    def test_fake_client_set_job_quantity(self):
        """Test FakeCncClient implementation used in tests."""
        from tests.conftest import FakeCncClient

        client = FakeCncClient()
        result = client.set_job_quantity(5)

        assert result == 0

    def test_set_job_quantity_various_quantities(self):
        """Test with various quantity values."""
        from src.cnc.cnc_client import CncClient
        from src.core.config import Settings

        settings = Settings()

        test_cases = [
            (1, 0, 1),      # qty=1, doRepeat=0, numberOfRepeats=1
            (2, 1, 2),      # qty=2, doRepeat=1, numberOfRepeats=2
            (10, 1, 10),    # qty=10, doRepeat=1, numberOfRepeats=10
            (50, 1, 50),    # qty=50, doRepeat=1, numberOfRepeats=50
            (100, 1, 100),  # qty=100, doRepeat=1, numberOfRepeats=100
            (999, 1, 999),  # qty=999, doRepeat=1, numberOfRepeats=999
        ]

        for qty, expected_do_repeat, expected_num_repeats in test_cases:
            with patch('src.cnc.cnc_client.WinDLL') as mock_dll_class:
                mock_dll = MagicMock()
                mock_dll_class.return_value = mock_dll
                mock_dll.CncSetExtraJobOptions.return_value = 0

                client = CncClient(settings)
                result = client.set_job_quantity(qty)

                assert result == 0
                call_args = mock_dll.CncSetExtraJobOptions.call_args
                assert call_args[0][1].value == expected_do_repeat, f"Failed for qty={qty}"
                assert call_args[0][2].value == expected_num_repeats, f"Failed for qty={qty}"

    def test_protocol_compliance(self):
        """Verify all implementations comply with CncClientProtocol."""
        from src.cnc.cnc_client_protocol import CncClientProtocol
        from src.cnc.mock_cnc_client import MockCncClient
        from tests.conftest import FakeCncClient

        # Verify MockCncClient has the method
        mock_client = MockCncClient()
        assert hasattr(mock_client, 'set_job_quantity')
        assert callable(mock_client.set_job_quantity)

        # Verify FakeCncClient has the method
        fake_client = FakeCncClient()
        assert hasattr(fake_client, 'set_job_quantity')
        assert callable(fake_client.set_job_quantity)

        # Verify they're runtime checkable
        assert isinstance(mock_client, CncClientProtocol)
        assert isinstance(fake_client, CncClientProtocol)


class TestSetJobQuantityIntegration:
    """Integration tests for set_job_quantity with job loading."""

    @pytest.mark.asyncio
    @patch('src.api.schemas.job.glob.glob')
    async def test_load_job_sets_quantity_on_success(self, mock_glob, client, fake_client):
        """Test that loading with qty>1 calls set_job_quantity."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_1.nc"]

        # Track if set_job_quantity was called
        calls = []
        original_set_qty = fake_client.set_job_quantity

        def tracked_set_qty(qty):
            calls.append(qty)
            return original_set_qty(qty)

        fake_client.set_job_quantity = tracked_set_qty

        resp = await client.get("/api/cnc/job/load/123456789012/1/5")

        assert resp.status_code == 200
        assert len(calls) == 1
        assert calls[0] == 5

    @pytest.mark.asyncio
    @patch('src.api.schemas.job.glob.glob')
    async def test_load_job_does_not_set_quantity_when_qty_is_1(self, mock_glob, client, fake_client):
        """Test that loading with qty=1 does not mention quantity in message."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_1.nc"]

        resp = await client.get("/api/cnc/job/load/123456789012/1/1")

        assert resp.status_code == 200
        body = resp.json()
        # Should not mention quantity when qty=1
        assert "quantity" not in body["message"].lower()

    @pytest.mark.asyncio
    @patch('src.api.schemas.job.glob.glob')
    async def test_load_job_continues_on_set_quantity_failure(self, mock_glob, client, fake_client):
        """Test that job load succeeds even if set_quantity fails."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_1.nc"]

        # Make set_job_quantity fail
        def failing_set_qty(qty):
            return 24  # CNC_RC_ERR_NOT_CONNECTED

        fake_client.set_job_quantity = failing_set_qty

        resp = await client.get("/api/cnc/job/load/123456789012/1/5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0  # Load still succeeded
        assert "quantity set failed: 24" in body["message"]

    @pytest.mark.asyncio
    @patch('src.api.schemas.job.glob.glob')
    async def test_load_job_handles_set_quantity_exception(self, mock_glob, client, fake_client):
        """Test that exceptions in set_quantity don't break the load."""
        fake_client._load_job_rc = 0
        mock_glob.return_value = [r"\\192.168.2.11\Production\CNC\Mills\123456789012\Setup_1.nc"]

        # Make set_job_quantity raise exception
        def exception_set_qty(qty):
            raise RuntimeError("DLL crashed")

        fake_client.set_job_quantity = exception_set_qty

        resp = await client.get("/api/cnc/job/load/123456789012/1/5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0  # Load still succeeded
        assert "quantity set error" in body["message"].lower()

    @pytest.mark.asyncio
    @patch('src.api.schemas.job.glob.glob')
    async def test_job_status_shows_repeat_info(self, mock_glob, client, fake_client):
        """Test that job status includes repeat information."""
        # Update fake_client's job status to show repeat info
        fake_client._job_status["doRepeatJob"] = 1
        fake_client._job_status["nrOfJobRepeatsSet"] = 10
        fake_client._job_status["nrOfRepeatsActual"] = 7

        resp = await client.get("/api/cnc/job/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["doRepeatJob"] == 1
        assert body["nrOfJobRepeatsSet"] == 10
        assert body["nrOfRepeatsActual"] == 7


class TestSetJobQuantityEdgeCases:
    """Edge case tests for set_job_quantity."""

    def test_set_job_quantity_with_boundary_value_2(self):
        """Test boundary between no-repeat (1) and repeat (2)."""
        from src.cnc.cnc_client import CncClient
        from src.core.config import Settings

        settings = Settings()

        with patch('src.cnc.cnc_client.WinDLL') as mock_dll_class:
            mock_dll = MagicMock()
            mock_dll_class.return_value = mock_dll
            mock_dll.CncSetExtraJobOptions.return_value = 0

            client = CncClient(settings)

            # qty=1 should disable repeat
            client.set_job_quantity(1)
            call_args = mock_dll.CncSetExtraJobOptions.call_args
            assert call_args[0][1].value == 0  # doRepeat = 0

            # qty=2 should enable repeat
            client.set_job_quantity(2)
            call_args = mock_dll.CncSetExtraJobOptions.call_args
            assert call_args[0][1].value == 1  # doRepeat = 1

    def test_set_job_quantity_empty_extra_line(self):
        """Verify that extraLine is M02 when repeat enabled, empty when disabled."""
        from src.cnc.cnc_client import CncClient
        from src.core.config import Settings

        settings = Settings()

        with patch('src.cnc.cnc_client.WinDLL') as mock_dll_class:
            mock_dll = MagicMock()
            mock_dll_class.return_value = mock_dll
            mock_dll.CncSetExtraJobOptions.return_value = 0

            client = CncClient(settings)

            # When qty=1 (no repeat), extraLine should be empty
            client.set_job_quantity(1)
            call_args = mock_dll.CncSetExtraJobOptions.call_args
            assert call_args[0][0] == b""  # extraLine should be empty

            # When qty>1 (repeat enabled), extraLine should be M02
            client.set_job_quantity(5)
            call_args = mock_dll.CncSetExtraJobOptions.call_args
            assert call_args[0][0] == b"M02"  # extraLine should be M02 for repeat bug workaround

    def test_set_job_quantity_logging(self):
        """Verify that set_job_quantity logs appropriately."""
        from src.cnc.cnc_client import CncClient
        from src.core.config import Settings
        import logging

        settings = Settings()

        with patch('src.cnc.cnc_client.WinDLL') as mock_dll_class:
            mock_dll = MagicMock()
            mock_dll_class.return_value = mock_dll
            mock_dll.CncSetExtraJobOptions.return_value = 0

            with patch('src.cnc.cnc_client.logger') as mock_logger:
                client = CncClient(settings)
                client.set_job_quantity(5)

                # Verify info log was called
                assert mock_logger.info.called
                log_message = mock_logger.info.call_args[0][0]
                assert "CncSetExtraJobOptions" in log_message
                assert "qty=5" in log_message or "5" in str(mock_logger.info.call_args)

    def test_set_job_quantity_exception_logging(self):
        """Verify that exceptions are logged."""
        from src.cnc.cnc_client import CncClient
        from src.core.config import Settings

        settings = Settings()

        with patch('src.cnc.cnc_client.WinDLL') as mock_dll_class:
            mock_dll = MagicMock()
            mock_dll_class.return_value = mock_dll
            mock_dll.CncSetExtraJobOptions.side_effect = RuntimeError("Test error")

            with patch('src.cnc.cnc_client.logger') as mock_logger:
                client = CncClient(settings)
                result = client.set_job_quantity(5)

                assert result == -1
                # Verify error log was called
                assert mock_logger.error.called
                log_message = mock_logger.error.call_args[0][0]
                assert "Failed to set job quantity" in log_message

