import sys
from pathlib import Path

import pytest

from src.api import jog_pad_launcher


@pytest.mark.asyncio
async def test_open_jog_pad_launches_source_script_in_dev(client, monkeypatch, test_app):
    launched = {}

    class FakeProcess:
        pid = 4321

    def fake_popen(command, **kwargs):
        launched["command"] = command
        launched["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(jog_pad_launcher.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(jog_pad_launcher.sys, "frozen", False, raising=False)
    test_app.state.services.jog_pad_launcher = jog_pad_launcher.launch_jog_pad

    response = await client.post("/api/jog-pad/open")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert body["pid"] == 4321
    assert body["command"][0] == sys.executable
    assert body["command"][1].endswith(str(Path("src") / "jog_pad" / "jog_pad.py"))
    assert body["command"][-4:] == ["--adapter-url", "http://127.0.0.1:9999", "--pause-hold-interval-ms", "0"]
    assert launched["kwargs"]["close_fds"] is True


@pytest.mark.asyncio
async def test_open_jog_pad_reports_launch_failure(client, monkeypatch, test_app):
    def fake_popen(command, **kwargs):
        raise OSError("no desktop")

    monkeypatch.setattr(jog_pad_launcher.subprocess, "Popen", fake_popen)
    test_app.state.services.jog_pad_launcher = jog_pad_launcher.launch_jog_pad

    response = await client.post("/api/jog-pad/open")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 1
    assert "no desktop" in body["message"]


def test_frozen_jog_pad_command_uses_adapter_exe(monkeypatch):
    monkeypatch.setattr(jog_pad_launcher.sys, "frozen", True, raising=False)
    monkeypatch.setattr(jog_pad_launcher.sys, "executable", r"C:\Adapter\erp-cnc-adapter.exe")

    assert jog_pad_launcher._jog_pad_command("http://127.0.0.1:7777", 750) == [
        r"C:\Adapter\erp-cnc-adapter.exe",
        "--jog-pad",
        "--adapter-url",
        "http://127.0.0.1:7777",
        "--pause-hold-interval-ms",
        "750",
    ]

@pytest.mark.asyncio
async def test_open_jog_pad_does_not_allow_get(client):
    response = await client.get("/api/jog-pad/open")

    assert response.status_code == 405
