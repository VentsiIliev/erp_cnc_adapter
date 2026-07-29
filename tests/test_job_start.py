"""Tests for GET /api/cnc/job/start."""

import pytest


pytestmark = pytest.mark.asyncio


class TestJobStart:

    async def test_start_endpoint_calls_cnc_run_job(self, client, fake_client):
        fake_client._run_job_rc = 0

        resp = await client.get("/api/cnc/job/start")

        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "status": 0,
            "message": "Job started successfully",
        }

    async def test_start_endpoint_allows_resume_when_cnc_state_is_running(self, client, fake_client):
        fake_client._state = 6
        fake_client._run_job_rc = 0

        resp = await client.get("/api/cnc/job/start")

        assert resp.status_code == 200
        assert resp.json() == {
            "status": 0,
            "message": "Job started successfully",
        }

    async def test_start_endpoint_does_not_block_on_monitor_was_running(self, client, test_app, fake_client):
        test_app.state.services.job_monitor._was_running = True
        fake_client._state = 6
        fake_client._run_job_rc = 0

        resp = await client.get("/api/cnc/job/start")

        assert resp.status_code == 200
        assert resp.json() == {
            "status": 0,
            "message": "Job started successfully",
        }
