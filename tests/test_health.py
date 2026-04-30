"""Tests for health/status endpoints: GET / and GET /api/health."""

import pytest

from src.api.health import _build_status_data, _format_uptime, _render_html


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

    def test_uptime_rounded_when_connected(self, fake_client, connection_manager):
        connection_manager._state = "connected"
        from datetime import datetime, timezone, timedelta
        connection_manager._last_connected_at = datetime.now(timezone.utc) - timedelta(seconds=123.456)
        data = _build_status_data(connection_manager)
        uptime = data["cnc"]["uptime_seconds"]
        assert uptime is not None
        # Rounded to 1 decimal
        assert uptime == round(uptime, 1)


class TestRenderHtml:

    def _make_data(self, connected=False, state="disconnected", last_error=None, retry_count=0, uptime=None):
        return {
            "status": "healthy" if connected else "degraded",
            "version": "1.0.0",
            "cnc": {
                "connected": connected,
                "state": state,
                "retry_count": retry_count,
                "last_error": last_error,
                "uptime_seconds": uptime,
            },
        }

    def test_retrying_state_shows_disconnected(self):
        html = _render_html(self._make_data(state="retrying"))
        assert "Disconnected" in html
        assert "#dc2626" in html  # red color

    def test_error_row_rendered(self):
        html = _render_html(self._make_data(last_error="connect() timed out"))
        assert "connect() timed out" in html
        assert "Last error" in html

    def test_retry_row_rendered(self):
        html = _render_html(self._make_data(retry_count=5))
        assert "Retry count" in html
        assert "5" in html

    def test_no_action_button_in_retrying(self):
        html = _render_html(self._make_data(state="retrying"))
        assert "Start CNC" not in html
        assert "Stop CNC" not in html

    def test_no_error_row_when_no_error(self):
        html = _render_html(self._make_data())
        assert "Last error" not in html


class TestFormatUptime:

    def test_none(self):
        assert _format_uptime(None) == "&mdash;"

    def test_seconds(self):
        assert _format_uptime(45.0) == "45s"

    def test_minutes(self):
        assert _format_uptime(125.0) == "2m 5s"

    def test_hours(self):
        assert _format_uptime(3665.0) == "1h 1m"

    def test_exact_one_minute_boundary(self):
        assert _format_uptime(60.0) == "1m 0s"

    def test_exact_one_hour_boundary(self):
        assert _format_uptime(3600.0) == "1h 0m"


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
        assert resp.headers["cache-control"] == "no-store"
        assert "Operations Dashboard" in resp.text
        assert 'const INITIAL_VIEW = "overview"' in resp.text

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
        assert "Operations Dashboard" in resp.text

    async def test_home_html_shows_stop_button_when_connected(
        self, client, connection_manager
    ):
        connection_manager._state = "connected"

        resp = await client.get("/", headers={"Accept": "text/html"})

        assert "Stop CNC" in resp.text
        assert "Operations Dashboard" in resp.text
