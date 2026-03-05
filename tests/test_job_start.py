"""Tests for GET /api/cnc/job/start."""

import pytest


pytestmark = pytest.mark.asyncio


class TestJobStart:

    async def test_start_success(self, client, fake_client):
        fake_client._run_job_rc = 0

        resp = await client.get("/api/cnc/job/start")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert "successfully" in body["message"].lower()

    async def test_start_failure(self, client, fake_client):
        fake_client._run_job_rc = 24  # not connected

        resp = await client.get("/api/cnc/job/start")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 24
        assert "not connected to cnc. no connection to cnc controller - call connect() first or check /api/cnc/start" in body["message"].lower()

    async def test_start_exception(self, client, fake_client):
        """If run_job() raises, the handler should catch and return -1."""
        def raise_error():
            raise RuntimeError("DLL timeout")

        fake_client.run_job = raise_error

        resp = await client.get("/api/cnc/job/start")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == -1
        assert "exception" in body["message"].lower()