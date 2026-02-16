"""Tests for src/cnc/mock_cnc_client.py — MockCncClient."""

from src.cnc.mock_cnc_client import MockCncClient


class TestMockCncClient:

    def test_initial_state_disconnected(self):
        client = MockCncClient()
        assert client.is_connected is False

    def test_connect_returns_0_and_sets_connected(self):
        client = MockCncClient()
        rc = client.connect()
        assert rc == 0
        assert client.is_connected is True

    def test_disconnect_sets_disconnected(self):
        client = MockCncClient()
        client.connect()
        client.disconnect()
        assert client.is_connected is False

    def test_is_server_process_alive_returns_false(self):
        assert MockCncClient.is_server_process_alive() is False

    def test_get_state_returns_0(self):
        client = MockCncClient()
        assert client.get_state() == 0

    def test_get_job_status_returns_dict_with_expected_keys(self):
        client = MockCncClient()
        status = client.get_job_status()
        assert isinstance(status, dict)
        # Check minimal fields with unit suffixes
        expected_keys = [
            "jobName", "jobLoadCounter",
            "totalJobLengthMm", "jobProgressMm",
            "jobActualRunningTimeSeconds", "jobEstimatedTimeSeconds",
            "doRepeatJob", "nrOfJobRepeatsSet",
        ]
        for key in expected_keys:
            assert key in status

    def test_load_job_returns_0(self):
        client = MockCncClient()
        assert client.load_job(r"C:\test.nc") == 0

    def test_run_job_returns_0(self):
        client = MockCncClient()
        assert client.run_job() == 0

    def test_is_server_connected_reflects_connection(self):
        client = MockCncClient()
        assert client.is_server_connected() is False
        client.connect()
        assert client.is_server_connected() is True
