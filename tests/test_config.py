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
        assert s.task_username == ""
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
            "dll_path": r"D:\custom\cncapi.dll",
            "ini_path": r"D:\custom\cnc.ini",
            "cnc_retry_interval": 20,
            "cnc_health_interval": 30,
            "job_monitor_poll_interval": 5.0,
            "port": 8010,
            "task_username": r"DOMAIN\adapter",
        }))

        with patch("src.core.config_persistence.CONFIG_FILE", config_file):
            s = Settings()

        assert s.dll_path == r"D:\custom\cncapi.dll"
        assert s.ini_path == r"D:\custom\cnc.ini"
        assert s.cnc_retry_interval == 20
        assert s.cnc_health_interval == 30
        assert s.job_monitor_poll_interval == 5.0
        assert s.port == 8010
        assert s.task_username == r"DOMAIN\adapter"


class TestConfigAPI:

    @pytest.mark.asyncio
    async def test_get_config_includes_timing(self, client):
        """GET /api/config returns timing fields."""
        with patch("src.api.config_api.get_task_launch_settings") as mock_task, \
             patch("src.api.config_api.get_machine_ip", return_value="192.168.2.55"):
            mock_task.return_value = {
                "run_as_windows_user": True,
                "task_username": r"DOMAIN\adapter",
                "task_password_configured": True,
            }
            resp = await client.get("/api/config")

        assert resp.status_code == 200
        data = resp.json()
        assert "cnc_retry_interval" in data
        assert "cnc_health_interval" in data
        assert "job_monitor_poll_interval" in data
        assert data["run_as_windows_user"] is True
        assert data["task_username"] == r"DOMAIN\adapter"
        assert data["task_password_configured"] is True
        assert data["local_ip"] == "192.168.2.55"

    @pytest.mark.asyncio
    async def test_post_config_updates_timing_and_port(self, client, settings, tmp_path):
        """POST /api/config updates timing and port values in memory and persists."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch("src.api.config_api.update_persisted_config") as mock_persist:
            mock_persist.return_value = True
            resp = await client.post("/api/config", json={
                "cnc_retry_interval": 15,
                "cnc_health_interval": 25,
                "job_monitor_poll_interval": 3.5,
                "port": 8010,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["changes"]) == 4

        # Verify in-memory settings updated
        assert settings.cnc_retry_interval == 15
        assert settings.cnc_health_interval == 25
        assert settings.job_monitor_poll_interval == 3.5
        assert settings.port == 8010

        # Verify persist was called with timing keys
        persist_call = mock_persist.call_args[0][0]
        assert persist_call["cnc_retry_interval"] == 15
        assert persist_call["cnc_health_interval"] == 25
        assert persist_call["job_monitor_poll_interval"] == 3.5
        assert persist_call["port"] == 8010

    @pytest.mark.asyncio
    async def test_post_config_updates_dll_and_ini_paths(self, client, settings):
        with patch("src.api.config_api.update_persisted_config") as mock_persist:
            mock_persist.return_value = True
            resp = await client.post("/api/config", json={
                "dll_path": r"D:\custom\cncapi.dll",
                "ini_path": r"D:\custom\cnc.ini",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert settings.dll_path == r"D:\custom\cncapi.dll"
        assert settings.ini_path == r"D:\custom\cnc.ini"
        persist_call = mock_persist.call_args[0][0]
        assert persist_call["dll_path"] == r"D:\custom\cncapi.dll"
        assert persist_call["ini_path"] == r"D:\custom\cnc.ini"

    @pytest.mark.asyncio
    async def test_post_config_updates_task_credentials(self, client, settings):
        """POST /api/config can switch scheduled tasks to a Windows user."""
        with patch("src.api.config_api.update_persisted_config") as mock_persist, \
             patch("src.api.config_api.configure_task_launch_account") as mock_task_update:
            mock_persist.return_value = True
            mock_task_update.return_value = {
                "run_as_windows_user": True,
                "task_username": r"DOMAIN\adapter",
                "task_password_configured": True,
            }
            resp = await client.post("/api/config", json={
                "run_as_windows_user": True,
                "task_username": r"DOMAIN\adapter",
                "task_password": "secret",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert settings.task_username == r"DOMAIN\adapter"
        mock_task_update.assert_called_once_with(
            task_username=r"DOMAIN\adapter",
            task_password="secret",
        )
        persist_call = mock_persist.call_args[0][0]
        assert persist_call["task_username"] == r"DOMAIN\adapter"

    @pytest.mark.asyncio
    async def test_post_config_updates_task_credentials_and_restarts_task(self, client, settings):
        """POST /api/config can update credentials and immediately restart the adapter task."""
        with patch("src.api.config_api.update_persisted_config") as mock_persist, \
             patch("src.api.config_api.configure_task_launch_account") as mock_task_update, \
             patch("src.api.config_api.restart_scheduled_adapter_task") as mock_restart:
            mock_persist.return_value = True
            mock_task_update.return_value = {
                "run_as_windows_user": True,
                "task_username": r"DOMAIN\adapter",
                "task_password_configured": True,
            }
            resp = await client.post("/api/config", json={
                "run_as_windows_user": True,
                "task_username": r"DOMAIN\adapter",
                "task_password": "secret",
                "restart_adapter_task": True,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "adapter_task: restart requested" in data["changes"]
        mock_restart.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_post_config_can_restart_task_without_other_changes(self, client):
        """POST /api/config can restart the scheduled task on demand."""
        with patch("src.api.config_api.restart_scheduled_adapter_task") as mock_restart:
            resp = await client.post("/api/config", json={
                "restart_adapter_task": True,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["changes"] == ["adapter_task: restart requested"]
        mock_restart.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_post_config_requires_password_for_task_user(self, client):
        """POST /api/config rejects task-user updates without a password."""
        resp = await client.post("/api/config", json={
            "run_as_windows_user": True,
            "task_username": r"DOMAIN\adapter",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "password" in data["message"].lower()
