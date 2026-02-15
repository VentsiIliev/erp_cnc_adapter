"""Tests for health/status endpoints: GET / and GET /api/health."""

import pytest

from src.api.health import _build_status_data, _format_uptime


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

class TestBuildStatusData:

    def test_connected(self, fake_client, connection_manager):
        connection_manager._state = "connected"
        connection_manager._retry_count = 0
        connection_manager._last_error = None

        data = _build_status_data(connection_manager)

        assert data["status"] == "healthy"
        assert data["cnc"]["connected"] is True
        assert data["cnc"]["state"] == "connected"

    def test_disconnected(self, connection_manager):
        data = _build_status_data(connection_manager)

        assert data["status"] == "degraded"
        assert data["cnc"]["connected"] is False

    def test_includes_version(self, connection_manager):
        data = _build_status_data(connection_manager)
        assert "version" in data


class TestFormatUptime:

    def test_none(self):
        assert _format_uptime(None) == "&mdash;"

    def test_seconds(self):
        assert _format_uptime(45.0) == "45s"

    def test_minutes(self):
        assert _format_uptime(125.0) == "2m 5s"

    def test_hours(self):
        assert _format_uptime(3665.0) == "1h 1m"


# ---------------------------------------------------------------------------
# Integration tests via HTTP
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    async def test_health_json_connected(self, client, fake_client, connection_manager):
        connection_manager._state = "connected"
        fake_client._connected = True

        resp = await client.get("/api/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["cnc"]["connected"] is True

    async def test_health_json_disconnected(self, client):
        resp = await client.get("/api/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "degraded"

    async def test_health_json_with_error(self, client, connection_manager):
        connection_manager._last_error = "connect() timed out"
        connection_manager._retry_count = 3

        resp = await client.get("/api/health")
        body = resp.json()

        assert body["cnc"]["last_error"] == "connect() timed out"
        assert body["cnc"]["retry_count"] == 3


class TestHomeEndpoint:

    async def test_home_returns_html_for_browser(self, client, connection_manager):
        connection_manager._state = "connected"

        resp = await client.get("/", headers={"Accept": "text/html"})

        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "ERP-CNC Adapter" in resp.text

    async def test_home_returns_json_by_default(self, client):
        resp = await client.get("/", headers={"Accept": "application/json"})

        assert resp.status_code == 503  # disconnected
        body = resp.json()
        assert "status" in body

    async def test_home_html_shows_start_button_when_cnc_not_running(
        self, client, connection_manager
    ):
        connection_manager._state = "cnc_not_running"

        resp = await client.get("/", headers={"Accept": "text/html"})

        assert "Start CNC" in resp.text

    async def test_home_html_shows_stop_button_when_connected(
        self, client, connection_manager
    ):
        connection_manager._state = "connected"

        resp = await client.get("/", headers={"Accept": "text/html"})

        assert "Stop CNC" in resp.text