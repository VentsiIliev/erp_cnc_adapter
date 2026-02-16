"""Tests for GET /api/cnc/job/status."""

import pytest

from src.api.job_status import STATE_MAP


class TestJobStatus:

    async def test_status_returns_state_and_job_data(self, client, fake_client):
        fake_client._state = 6  # Running job
        fake_client._job_status["jobName"] = "production_part.nc"
        fake_client._job_status["jobProgressMm"] = 75.0

        resp = await client.get("/api/cnc/job/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == 6
        assert body["stateText"] == "Running job"
        assert body["jobName"] == "production_part.nc"
        assert body["jobProgressMm"] == 75.0

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
        # Check minimal fields currently returned (with unit suffixes)
        expected_fields = [
            "state", "stateText", "jobName", "jobLoadCounter",
            "totalJobLengthMm", "jobProgressMm", "jobProgressPercentage",
            "jobActualRunningTimeSeconds", "jobRemainingRunningTimeSeconds", "jobEstimatedTimeSeconds",
            "doRepeatJob", "nrOfJobRepeatsSet", "nrOfRepeatsActual",
            "currentRepeat",  # Only computed field
        ]
        for field in expected_fields:
            assert field in body, f"Missing field: {field}"

        # Optional: Verify commented-out fields are NOT present
        # (uncomment if you want to ensure they're truly removed)
        # excluded_fields = [
        #     "numLinesInJob", "numLinesInMacro", "numLinesInUserMacro",
        #     "isLongJob", "isSuperLongJob", "jobIsRendered",
        #     "TCACollision", "MCACollision", "xCollision", "yCollision", "zCollision",
        #     "jobRenderLine", "jobRenderProgressPercentage",
        #     "curIpLine", "curIpLineText", "curExLine",
        #     "lastKnownExecutedLineNumber", "lastKnownToolChangeLineNumber",
        #     "extraLineWhenEndOfJob",
        #     "stockDiameterTurning", "stockLengthTurning", "stockZAtWorkOffset",
        # ]
        # for field in excluded_fields:
        #     assert field not in body, f"Field should be excluded: {field}"


    async def test_get_state_ok_but_get_job_status_raises(self, client, fake_client):
        """If get_state() works but get_job_status() raises, state should be -1."""
        fake_client._state = 1

        def raise_error():
            raise RuntimeError("DLL error in get_job_status")

        fake_client.get_job_status = raise_error

        resp = await client.get("/api/cnc/job/status")
        body = resp.json()
        assert body["state"] == -1

    async def test_job_progress_boundary_zero(self, client, fake_client):
        fake_client._state = 1
        fake_client._job_status["jobProgressMm"] = 0.0

        resp = await client.get("/api/cnc/job/status")
        body = resp.json()
        assert body["jobProgressMm"] == 0.0

    async def test_job_progress_boundary_100(self, client, fake_client):
        fake_client._state = 6
        fake_client._job_status["jobProgressMm"] = 100.0

        resp = await client.get("/api/cnc/job/status")
        body = resp.json()
        assert body["jobProgressMm"] == 100.0

    async def test_job_progress_percentage_calculation(self, client, fake_client):
        """Test that jobProgressPercentage is calculated correctly."""
        fake_client._state = 6
        fake_client._job_status["totalJobLengthMm"] = 200.0
        fake_client._job_status["jobProgressMm"] = 50.0

        resp = await client.get("/api/cnc/job/status")
        body = resp.json()
        assert body["jobProgressPercentage"] == 25.0  # 50/200 * 100 = 25%

    async def test_job_progress_percentage_over_100(self, client, fake_client):
        """Test that percentage can exceed 100% (normal CNC behavior)."""
        fake_client._state = 6
        fake_client._job_status["totalJobLengthMm"] = 100.0
        fake_client._job_status["jobProgressMm"] = 110.0

        resp = await client.get("/api/cnc/job/status")
        body = resp.json()
        assert body["jobProgressPercentage"] == pytest.approx(110.0)  # 110/100 * 100 = 110%

    async def test_job_progress_percentage_zero_length(self, client, fake_client):
        """Test that percentage is 0 when totalJobLengthMm is 0."""
        fake_client._state = 2
        fake_client._job_status["totalJobLengthMm"] = 0.0
        fake_client._job_status["jobProgressMm"] = 0.0

        resp = await client.get("/api/cnc/job/status")
        body = resp.json()
        assert body["jobProgressPercentage"] == 0.0


class TestStateMap:

    def test_all_states_0_to_23(self):
        for i in range(24):
            assert i in STATE_MAP, f"STATE_MAP missing key {i}"

    def test_key_states(self):
        assert STATE_MAP[0] == "Power-up"
        assert STATE_MAP[1] == "Idle"
        assert STATE_MAP[2] == "Ready"
        assert STATE_MAP[6] == "Running job"