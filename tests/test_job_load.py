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