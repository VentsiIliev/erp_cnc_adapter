"""Tests that FakeCncClient conforms to CncClientProtocol."""

from src.cnc.cnc_client_protocol import CncClientProtocol


class TestFakeCncClient:

    def test_implements_protocol(self, fake_client):
        assert isinstance(fake_client, CncClientProtocol)

    def test_connect_disconnect_cycle(self, fake_client):
        assert fake_client.is_connected is False

        fake_client.connect()
        assert fake_client.is_connected is True

        fake_client.disconnect()
        assert fake_client.is_connected is False

    def test_configurable_return_codes(self, fake_client):
        fake_client._connect_rc = 22
        rc = fake_client.connect()
        assert rc == 22
        assert fake_client.is_connected is False  # non-zero = fail

    def test_get_state(self, fake_client):
        fake_client._state = 6
        assert fake_client.get_state() == 6

    def test_get_job_status_returns_dict(self, fake_client):
        status = fake_client.get_job_status()
        assert isinstance(status, dict)
        assert "jobName" in status

    def test_load_job(self, fake_client):
        fake_client._load_job_rc = 0
        assert fake_client.load_job(r"C:\test.nc") == 0

    def test_run_job(self, fake_client):
        fake_client._run_job_rc = 0
        assert fake_client.run_job() == 0