"""Tests for Settings configuration."""

import json
import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

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
        assert s.job_monitor_poll_interval == 1.0

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

    def test_post_init_loads_persisted_timing(self, tmp_path):
        """Settings.__post_init__ picks up persisted timing values."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "cnc_retry_interval": 20,
            "cnc_health_interval": 30,
            "job_monitor_poll_interval": 5.0,
        }))

        with patch("src.core.config_persistence.CONFIG_FILE", config_file):
            s = Settings()

        assert s.cnc_retry_interval == 20
        assert s.cnc_health_interval == 30
        assert s.job_monitor_poll_interval == 5.0


class TestConfigAPI:

    @pytest.mark.asyncio
    async def test_get_config_includes_timing(self, client):
        """GET /api/config returns timing fields."""
        resp = await client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "cnc_retry_interval" in data
        assert "cnc_health_interval" in data
        assert "job_monitor_poll_interval" in data

    @pytest.mark.asyncio
    async def test_post_config_updates_timing(self, client, settings, tmp_path):
        """POST /api/config updates timing values in memory and persists."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("src.api.config_api.update_persisted_config") as mock_persist:
            mock_persist.return_value = True
            resp = await client.post("/api/config", json={
                "cnc_retry_interval": 15,
                "cnc_health_interval": 25,
                "job_monitor_poll_interval": 3.5,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["changes"]) == 3

        # Verify in-memory settings updated
        assert settings.cnc_retry_interval == 15
        assert settings.cnc_health_interval == 25
        assert settings.job_monitor_poll_interval == 3.5

        # Verify persist was called with timing keys
        persist_call = mock_persist.call_args[0][0]
        assert persist_call["cnc_retry_interval"] == 15
        assert persist_call["cnc_health_interval"] == 25
        assert persist_call["job_monitor_poll_interval"] == 3.5