import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from machine_health_dashboard.server import (
    collect_health,
    fetch_machine_health,
    load_config,
    machine_base_url,
)


def test_machine_config_contains_requested_ips():
    config = load_config(Path(__file__).resolve().parent.parent / "machine_health_dashboard" / "machines.json")
    hosts = {machine["id"]: machine["host"] for machine in config["machines"]}

    assert hosts == {
        "CNC1": "192.168.13.83",
        "CNC3": "192.168.13.88",
        "CNC4": "192.168.13.89",
        "CNC5": "192.168.13.86",
        "CNC6": "192.168.13.87",
        "CNC7": "192.168.13.85",
    }


def test_machine_base_url_defaults_to_adapter_port():
    assert machine_base_url({"host": "192.168.13.83"}) == "http://192.168.13.83:8002"


def test_fetch_machine_health_maps_adapter_payload():
    response = MagicMock()
    response.read.return_value = json.dumps(
        {
            "status": "healthy",
            "cnc": {
                "connected": True,
                "state": "connected",
                "machine_state_text": "Ready",
                "retry_count": 0,
                "last_error": None,
                "uptime_seconds": 12.4,
            },
        }
    ).encode("utf-8")
    response.__enter__.return_value = response

    with patch("urllib.request.urlopen", return_value=response):
        data = fetch_machine_health({"id": "CNC1", "host": "192.168.13.83"}, timeout=1)

    assert data["id"] == "CNC1"
    assert data["dashboard_url"] == "http://192.168.13.83:8002/dashboard"
    assert data["online"] is True
    assert data["connected"] is True
    assert data["cnc_state"] == "connected"
    assert data["machine_state_text"] == "Ready"


def test_collect_health_summarizes_machine_states():
    config = {
        "poll_interval_seconds": 10,
        "request_timeout_seconds": 1,
        "machines": [
            {"id": "CNC1", "host": "192.168.13.83"},
            {"id": "CNC3", "host": "192.168.13.88"},
        ],
    }
    responses = [
        {
            "id": "CNC1",
            "online": True,
            "connected": True,
        },
        {
            "id": "CNC3",
            "online": False,
            "connected": False,
        },
    ]

    with patch("machine_health_dashboard.server.fetch_machine_health", side_effect=responses):
        data = collect_health(config)

    assert data["summary"]["total"] == 2
    assert data["summary"]["online"] == 1
    assert data["summary"]["connected"] == 1
    assert data["summary"]["offline"] == 1
