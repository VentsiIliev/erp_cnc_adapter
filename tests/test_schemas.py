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

    def test_accepts_valid_filename(self):
        req = LoadJobRequest(fileName=r"C:\CNC\parts\test.nc")
        assert req.file_name == r"C:\CNC\parts\test.nc"

    def test_normalizes_forward_slashes(self):
        req = LoadJobRequest(fileName="//server/share/part.nc")
        assert req.file_name == r"\\server\share\part.nc"

    def test_rejects_empty_filename(self):
        with pytest.raises(ValidationError):
            LoadJobRequest(fileName="")

    def test_accepts_populate_by_name(self):
        req = LoadJobRequest(file_name=r"C:\test.nc")
        assert req.file_name == r"C:\test.nc"

    def test_mixed_slashes_normalized(self):
        req = LoadJobRequest(fileName="C:/CNC/parts/sub\\file.nc")
        assert "\\" in req.file_name
        assert "/" not in req.file_name


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
        assert resp.jobProgress == 0.0
        assert resp.numLinesInJob == 0

    def test_full_construction(self):
        resp = JobStatusResponse(
            state=6,
            stateText="Running job",
            jobName="part.nc",
            numLinesInJob=500,
            jobProgress=75.5,
        )
        assert resp.state == 6
        assert resp.jobName == "part.nc"
        assert resp.jobProgress == 75.5