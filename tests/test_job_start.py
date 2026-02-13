"""Tests for POST /api/cnc/job/start."""

import pytest


pytestmark = pytest.mark.asyncio


class TestJobStart:

    async def test_start_success(self, client, fake_client):
        fake_client._run_job_rc = 0

        resp = await client.post("/api/cnc/job/start")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert "successfully" in body["message"].lower()

    async def test_start_failure(self, client, fake_client):
        fake_client._run_job_rc = 24  # not connected

        resp = await client.post("/api/cnc/job/start")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 24
        assert "error code" in body["message"].lower()

    async def test_start_exception(self, client, fake_client):
        """If run_job() raises, the handler should catch and return -1."""
        def raise_error():
            raise RuntimeError("DLL timeout")

        fake_client.run_job = raise_error

        resp = await client.post("/api/cnc/job/start")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == -1
        assert "exception" in body["message"].lower()