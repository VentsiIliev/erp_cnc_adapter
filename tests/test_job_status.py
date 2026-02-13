"""Tests for GET /api/cnc/job/status."""

import pytest

from src.handlers.job_status import STATE_MAP


class TestJobStatus:

    async def test_status_returns_state_and_job_data(self, client, fake_client):
        fake_client._state = 6  # Running job
        fake_client._job_status["jobName"] = "production_part.nc"
        fake_client._job_status["jobProgress"] = 75.0

        resp = await client.get("/api/cnc/job/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == 6
        assert body["stateText"] == "Running job"
        assert body["jobName"] == "production_part.nc"
        assert body["jobProgress"] == 75.0

    async def test_status_idle(self, client, fake_client):
        fake_client._state = 1

        resp = await client.get("/api/cnc/job/status")

        body = resp.json()
        assert body["state"] == 1
        assert body["stateText"] == "Idle"

    async def test_status_unknown_state(self, client, fake_client):
        fake_client._state = 999

        resp = await client.get("/api/cnc/job/status")

        body = resp.json()
        assert body["state"] == 999
        assert "Unknown" in body["stateText"]

    async def test_status_exception_returns_error(self, client, fake_client):
        """If get_state() raises, the handler should return state -1."""
        def raise_error():
            raise RuntimeError("DLL error")

        fake_client.get_state = raise_error

        resp = await client.get("/api/cnc/job/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == -1
        assert "Error" in body["stateText"]

    async def test_all_job_fields_present(self, client, fake_client):
        fake_client._state = 2  # Ready

        resp = await client.get("/api/cnc/job/status")

        body = resp.json()
        expected_fields = [
            "state", "stateText", "jobName", "jobLoadCounter",
            "numLinesInJob", "numLinesInMacro", "numLinesInUserMacro",
            "isLongJob", "isSuperLongJob", "jobIsRendered",
            "totalJobLength", "jobProgress",
            "jobActualRunningTime", "jobRemainingRunningTime", "jobEstimatedTime",
            "TCACollision", "MCACollision",
            "xCollision", "yCollision", "zCollision",
            "jobRenderLine", "jobRenderProgressPercentage",
            "curIpLine", "curExLine",
            "lastKnownExecutedLineNumber", "lastKnownToolChangeLineNumber",
            "doRepeatJob", "nrOfJobRepeatsSet", "nrOfRepeatsActual",
            "extraLineWhenEndOfJob",
            "stockDiameterTurning", "stockLengthTurning", "stockZAtWorkOffset",
        ]
        for field in expected_fields:
            assert field in body, f"Missing field: {field}"


class TestStateMap:

    def test_all_states_0_to_23(self):
        for i in range(24):
            assert i in STATE_MAP, f"STATE_MAP missing key {i}"

    def test_key_states(self):
        assert STATE_MAP[0] == "Power-up"
        assert STATE_MAP[1] == "Idle"
        assert STATE_MAP[2] == "Ready"
        assert STATE_MAP[6] == "Running job"