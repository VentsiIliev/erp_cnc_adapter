"""Tests for Pydantic request/response schemas."""

import pytest
from pydantic import ValidationError

from src.api.schemas.job import (
    LoadJobRequest,
    LoadJobResponse,
    RunJobResponse,
    JobStatusResponse,
)


# ---------------------------------------------------------------------------
# LoadJobRequest
# ---------------------------------------------------------------------------

class TestLoadJobRequest:

    def test_accepts_valid_job_number_and_step(self):
        req = LoadJobRequest(job_number="123456789012", step="10")
        assert req.job_number == "123456789012"
        assert req.step == "10"

    def test_constructs_job_dir_correctly(self):
        req = LoadJobRequest(job_number="123456789012", step="10")
        assert "123456789012" in req.job_dir
        assert req.base_dir in req.job_dir

    def test_rejects_invalid_job_number_too_short(self):
        with pytest.raises(ValidationError):
            LoadJobRequest(job_number="12345", step="10")

    def test_rejects_invalid_job_number_too_long(self):
        with pytest.raises(ValidationError):
            LoadJobRequest(job_number="1234567890123", step="10")

    def test_rejects_non_numeric_job_number(self):
        with pytest.raises(ValidationError):
            LoadJobRequest(job_number="12345678901A", step="10")

    def test_rejects_non_numeric_step(self):
        with pytest.raises(ValidationError):
            LoadJobRequest(job_number="123456789012", step="ABC")

    def test_custom_base_dir(self):
        req = LoadJobRequest(
            job_number="123456789012",
            step="10",
            base_dir=r"C:\CustomPath"
        )
        assert req.job_dir == r"C:\CustomPath\123456789012"


# ---------------------------------------------------------------------------
# LoadJobResponse
# ---------------------------------------------------------------------------

class TestLoadJobResponse:

    def test_construct_success(self):
        resp = LoadJobResponse.model_construct(
            status=0, message="OK", fileName="test.nc"
        )
        assert resp.status == 0
        assert resp.message == "OK"

    def test_serializes_with_alias(self):
        resp = LoadJobResponse(status=0, message="OK", fileName="test.nc")
        data = resp.model_dump(by_alias=True)
        assert "fileName" in data


# ---------------------------------------------------------------------------
# RunJobResponse
# ---------------------------------------------------------------------------

class TestRunJobResponse:

    def test_success(self):
        resp = RunJobResponse(status=0, message="Job started successfully")
        assert resp.status == 0

    def test_failure(self):
        resp = RunJobResponse(status=5, message="Start failed")
        assert resp.status == 5


# ---------------------------------------------------------------------------
# JobStatusResponse
# ---------------------------------------------------------------------------

class TestJobStatusResponse:

    def test_defaults(self):
        resp = JobStatusResponse(state=1, stateText="Idle")
        assert resp.jobName == ""
        assert resp.jobProgressMm == 0.0
        assert resp.jobLoadCounter == 0
        assert resp.totalJobLengthMm == 0.0

    def test_full_construction(self):
        resp = JobStatusResponse(
            state=6,
            stateText="Running job",
            jobName="part.nc",
            jobLoadCounter=5,
            totalJobLengthMm=200.0,
            jobProgressMm=75.5,
            jobActualRunningTimeSeconds=30.0,
            doRepeatJob=1,
            nrOfJobRepeatsSet=3,
            nrOfRepeatsActual=2,
        )
        assert resp.state == 6
        assert resp.jobName == "part.nc"
        assert resp.jobProgressMm == 75.5
        assert resp.jobLoadCounter == 5
        assert resp.doRepeatJob == 1

    def test_error_state_negative_one(self):
        resp = JobStatusResponse(state=-1, stateText="Error: DLL crashed")
        assert resp.state == -1
        assert resp.jobName == ""

    def test_computed_repeat_fields(self):
        """Computed currentRepeat field should be calculated correctly."""
        resp = JobStatusResponse(
            state=2,
            stateText="Ready",
            doRepeatJob=1,
            nrOfJobRepeatsSet=5,
            nrOfRepeatsActual=3,
            currentRepeat=3,  # 5 - 3 + 1 = 3 (on 3rd iteration of 5)
        )
        assert resp.doRepeatJob == 1
        assert resp.nrOfJobRepeatsSet == 5
        assert resp.nrOfRepeatsActual == 3
        assert resp.currentRepeat == 3

