"""Tests for Settings configuration."""

from src.core.config import Settings


class TestSettings:

    def test_defaults(self):
        s = Settings()
        assert s.dll_path == r"C:\CNC4.03\cncapi.dll"
        assert s.ini_path == r"C:\CNC4.03\cnc.ini"
        assert s.host == "0.0.0.0"
        assert s.port == 8002
        assert s.log_level == "DEBUG"
        assert s.cnc_retry_interval == 5
        assert s.cnc_health_interval == 10

    def test_custom_values(self):
        s = Settings(
            dll_path=r"D:\custom\cncapi.dll",
            port=9090,
            cnc_retry_interval=2,
        )
        assert s.dll_path == r"D:\custom\cncapi.dll"
        assert s.port == 9090
        assert s.cnc_retry_interval == 2
        # Unchanged defaults
        assert s.host == "0.0.0.0"