"""Tests for POST /api/cnc/job/unload."""

from pathlib import Path
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.asyncio


async def test_unload_loads_placeholder_job(client, fake_client, test_app, tmp_path):
    placeholder = tmp_path / "no_job_loaded.cnc"
    placeholder.write_text("(placeholder)\nM30\n", encoding="utf-8")
    test_app.state.services.last_loaded_job = {"job_number": "123456789012"}
    test_app.state.services.job_monitor._job_info = {"job_number": "123456789012"}
    test_app.state.services.job_monitor._was_running = True

    with patch("src.api.job_unload.get_placeholder_job_path", return_value=placeholder):
        resp = await client.post("/api/cnc/job/unload")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == 0
    assert "unloaded" in body["message"].lower()
    assert body["fileName"] == str(placeholder)
    assert fake_client.loaded_jobs == [str(placeholder)]
    assert test_app.state.services.last_loaded_job is None
    assert test_app.state.services.job_monitor._job_info == {}
    assert test_app.state.services.job_monitor._was_running is False


async def test_unload_rejects_running_job(client, fake_client, tmp_path):
    fake_client._state = 6
    placeholder = tmp_path / "no_job_loaded.cnc"

    with patch("src.api.job_unload.get_placeholder_job_path", return_value=placeholder):
        resp = await client.post("/api/cnc/job/unload")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == 6
    assert "running" in body["message"].lower()
    assert fake_client.loaded_jobs == []


async def test_unload_placeholder_missing_returns_file_error(client):
    missing = Path(r"C:\missing\no_job_loaded.cnc")

    with patch("src.api.job_unload.get_placeholder_job_path", side_effect=FileNotFoundError(missing)):
        resp = await client.post("/api/cnc/job/unload")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == 20
    assert "placeholder" in body["message"].lower()


async def test_status_hides_placeholder_job_name(client, fake_client):
    fake_client._job_status["jobName"] = r"C:\Program Files\ERP-CNC Adapter\resources\no_job_loaded.cnc"

    resp = await client.get("/api/cnc/job/status")

    assert resp.status_code == 200
    assert resp.json()["jobName"] == ""