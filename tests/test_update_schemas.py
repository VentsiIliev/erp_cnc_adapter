"""Tests for src/api/schemas/update.py — Update Pydantic models."""

from src.api.schemas.update import (
    BackupInfo,
    BackupListResponse,
    RollbackResponse,
    UpdateResponse,
)


class TestBackupInfo:

    def test_construction(self):
        info = BackupInfo(filename="backup.bak.ts", timestamp="20260101_120000", size_mb=5.25)
        assert info.filename == "backup.bak.ts"
        assert info.timestamp == "20260101_120000"
        assert info.size_mb == 5.25


class TestUpdateResponse:

    def test_defaults(self):
        resp = UpdateResponse(status=0, message="OK")
        assert resp.version_info == ""

    def test_error_case(self):
        resp = UpdateResponse(status=1, message="Bad file")
        assert resp.status == 1

    def test_with_version_info(self):
        resp = UpdateResponse(status=0, message="OK", version_info="v1.0.3")
        assert resp.version_info == "v1.0.3"


class TestRollbackResponse:

    def test_success(self):
        resp = RollbackResponse(status=0, message="Rolled back")
        assert resp.status == 0

    def test_failure(self):
        resp = RollbackResponse(status=1, message="No backups")
        assert resp.status == 1


class TestBackupListResponse:

    def test_empty_backups_default(self):
        resp = BackupListResponse(status=0, message="Found 0 backup(s).")
        assert resp.backups == []

    def test_with_backups(self):
        info = BackupInfo(filename="f.bak.ts", timestamp="ts", size_mb=1.0)
        resp = BackupListResponse(status=0, message="Found 1 backup(s).", backups=[info])
        assert len(resp.backups) == 1

    def test_nested_serialization(self):
        info = BackupInfo(filename="f.bak.ts", timestamp="ts", size_mb=1.0)
        resp = BackupListResponse(status=0, message="OK", backups=[info])
        data = resp.model_dump()
        assert data["backups"][0]["filename"] == "f.bak.ts"
