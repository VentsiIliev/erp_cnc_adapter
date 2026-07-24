"""Tests for GET /api/cnc/job/start."""

import pytest


pytestmark = pytest.mark.asyncio


class TestJobStart:

    async def test_start_endpoint_temporarily_disabled(self, client, fake_client):
        fake_client._run_job_rc = 0

        resp = await client.get("/api/cnc/job/start")

        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "status": 503,
            "message": "Start endpoint temporarily disabled",
        }

