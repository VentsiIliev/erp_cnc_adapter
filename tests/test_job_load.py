"""Tests for POST /api/cnc/job/load."""

import pytest


pytestmark = pytest.mark.asyncio


class TestJobLoad:

    async def test_load_success(self, client, fake_client):
        fake_client._load_job_rc = 0

        resp = await client.post(
            "/api/cnc/job/load",
            json={"fileName": r"C:\\CNC\\parts\\test.nc"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert "successfully" in body["message"].lower()

    async def test_load_failure_returns_error_code(self, client, fake_client):
        fake_client._load_job_rc = 22  # server not running

        resp = await client.post(
            "/api/cnc/job/load",
            json={"fileName": r"C:\\CNC\\test.nc"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 22
        assert "error code" in body["message"].lower()

    async def test_load_returns_filename(self, client, fake_client):
        fake_client._load_job_rc = 0

        resp = await client.post(
            "/api/cnc/job/load",
            json={"fileName": r"C:\\test\\part.nc"},
        )

        body = resp.json()
        assert "part.nc" in body["fileName"]

    async def test_load_empty_filename_rejected(self, client):
        resp = await client.post(
            "/api/cnc/job/load",
            json={"fileName": ""},
        )

        assert resp.status_code == 422  # validation error

    async def test_load_missing_filename_rejected(self, client):
        resp = await client.post(
            "/api/cnc/job/load",
            json={},
        )

        assert resp.status_code == 422

    async def test_load_with_forward_slashes(self, client, fake_client):
        """Forward slashes should be normalized to backslashes."""
        fake_client._load_job_rc = 0

        resp = await client.post(
            "/api/cnc/job/load",
            json={"fileName": "//192.168.2.11/Production/CNC/part.nc"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0

    async def test_load_exception_in_client(self, client, fake_client):
        """If the CNC client raises, the handler should catch and return -1."""
        def raise_error(fn):
            raise RuntimeError("DLL crashed")

        fake_client.load_job = raise_error

        resp = await client.post(
            "/api/cnc/job/load",
            json={"fileName": r"C:\\test.nc"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == -1
        assert "exception" in body["message"].lower()

    async def test_backslash_fix_route_unescaped_windows_path(self, client, fake_client):
        """Raw body with unescaped Windows backslashes should be auto-fixed."""
        fake_client._load_job_rc = 0

        # Send raw body with unescaped backslashes (invalid JSON normally)
        resp = await client.post(
            "/api/cnc/job/load",
            content=b'{"fileName": "C:\\CNC\\parts\\test.nc"}',
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0

    async def test_backslash_fix_route_valid_json_unchanged(self, client, fake_client):
        """Valid JSON with properly escaped backslashes passes through unchanged."""
        fake_client._load_job_rc = 0

        resp = await client.post(
            "/api/cnc/job/load",
            json={"fileName": r"C:\\CNC\\test.nc"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0

    async def test_single_char_filename(self, client, fake_client):
        """Single character filename should be accepted."""
        fake_client._load_job_rc = 0

        resp = await client.post(
            "/api/cnc/job/load",
            json={"fileName": "x"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0