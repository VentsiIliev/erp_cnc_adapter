"""Tests for src/api/update.py - update endpoints and helpers."""

import base64
import os
import urllib.error
import urllib.request
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from src.api.update import (
    _get_project_root,
    _get_exe_path,
    _list_backups,
    _rotate_backups,
    router,
    EXE_NAME,
    MAX_BACKUPS,
)
from src.api.schemas.update import BackupInfo


# ---------------------------------------------------------------------------
# _get_project_root
# ---------------------------------------------------------------------------

class TestGetProjectRoot:

    def test_returns_path_from_source(self):
        """Non-frozen: returns two levels up from the source file."""
        root = _get_project_root()
        assert os.path.isdir(root)

    @patch("src.api.update.sys")
    def test_returns_exe_dir_when_frozen(self, mock_sys):
        mock_sys.frozen = True
        mock_sys.executable = r"C:\Install\erp-cnc-adapter.exe"
        assert _get_project_root() == r"C:\Install"


# ---------------------------------------------------------------------------
# _get_exe_path
# ---------------------------------------------------------------------------

class TestGetExePath:

    @patch("src.api.update.os.path.exists", return_value=True)
    @patch("src.api.update._get_project_root", return_value=r"C:\Install")
    def test_returns_direct_path_when_exists(self, _root, _exists):
        assert _get_exe_path() == os.path.join(r"C:\Install", EXE_NAME)

    @patch("src.api.update.os.path.exists", return_value=False)
    @patch("src.api.update._get_project_root", return_value=r"C:\Install")
    def test_falls_back_to_dist_subdir(self, _root, _exists):
        assert _get_exe_path() == os.path.join(r"C:\Install", "dist", EXE_NAME)


# ---------------------------------------------------------------------------
# _list_backups
# ---------------------------------------------------------------------------

class TestListBackups:

    @patch("src.api.update._get_exe_dir", return_value=r"C:\Install")
    @patch("src.api.update.os.listdir", return_value=[])
    def test_empty_directory(self, _listdir, _dir):
        assert _list_backups() == []

    @patch("src.api.update.os.path.getsize", return_value=5 * 1024 * 1024)
    @patch("src.api.update._get_exe_dir", return_value=r"C:\Install")
    @patch("src.api.update.os.listdir")
    def test_finds_and_sorts_newest_first(self, mock_listdir, _dir, _size):
        mock_listdir.return_value = [
            "erp-cnc-adapter.exe.bak.20260101_100000",
            "erp-cnc-adapter.exe.bak.20260201_100000",
        ]
        result = _list_backups()
        assert len(result) == 2
        assert result[0].timestamp == "20260201_100000"
        assert result[1].timestamp == "20260101_100000"

    @patch("src.api.update._get_exe_dir", return_value=r"C:\Install")
    @patch("src.api.update.os.listdir", return_value=["readme.txt", "config.ini"])
    def test_ignores_non_backup_files(self, _listdir, _dir):
        assert _list_backups() == []

    @patch("src.api.update._get_exe_dir", return_value=r"C:\Install")
    @patch("src.api.update.os.listdir", return_value=["other-app.exe.bak.20260101_100000"])
    def test_ignores_files_not_starting_with_exe_name(self, _listdir, _dir):
        assert _list_backups() == []

    @patch("src.api.update._get_exe_dir", return_value=r"C:\missing")
    @patch("src.api.update.os.listdir", side_effect=OSError("no such dir"))
    def test_returns_empty_on_oserror(self, _listdir, _dir):
        assert _list_backups() == []

    @patch("src.api.update.os.path.getsize", return_value=1024 * 1024)
    @patch("src.api.update._get_exe_dir", return_value=r"C:\Install")
    @patch("src.api.update.os.listdir")
    def test_handles_new_format_with_version(self, mock_listdir, _dir, _size):
        mock_listdir.return_value = [
            "erp-cnc-adapter.exe.v1.0.0.bak.20260215_120000",
        ]
        result = _list_backups()
        assert len(result) == 1
        assert result[0].timestamp == "20260215_120000"
        assert "v1.0.0" in result[0].filename


# ---------------------------------------------------------------------------
# _rotate_backups
# ---------------------------------------------------------------------------

class TestRotateBackups:

    @patch("src.api.update._list_backups")
    def test_noop_when_under_limit(self, mock_list):
        mock_list.return_value = [
            BackupInfo(filename=f"f{i}.bak.ts{i}", timestamp=f"ts{i}", size_mb=1.0)
            for i in range(MAX_BACKUPS)
        ]
        _rotate_backups()  # should not raise

    @patch("src.api.update.os.remove")
    @patch("src.api.update._get_exe_dir", return_value=r"C:\Install")
    @patch("src.api.update._list_backups")
    def test_deletes_oldest_when_over_limit(self, mock_list, _dir, mock_remove):
        backups = [
            BackupInfo(filename=f"erp-cnc-adapter.exe.bak.ts{i:02d}", timestamp=f"ts{i:02d}", size_mb=1.0)
            for i in range(MAX_BACKUPS + 2)
        ]
        mock_list.return_value = backups
        _rotate_backups()
        assert mock_remove.call_count == 2

    @patch("src.api.update.os.remove", side_effect=OSError("access denied"))
    @patch("src.api.update._get_exe_dir", return_value=r"C:\Install")
    @patch("src.api.update._list_backups")
    def test_continues_on_remove_oserror(self, mock_list, _dir, mock_remove):
        backups = [
            BackupInfo(filename=f"erp-cnc-adapter.exe.bak.ts{i:02d}", timestamp=f"ts{i:02d}", size_mb=1.0)
            for i in range(MAX_BACKUPS + 2)
        ]
        mock_list.return_value = backups
        _rotate_backups()  # should not raise
        assert mock_remove.call_count == 2


# ---------------------------------------------------------------------------
# HTTP endpoint helpers
# ---------------------------------------------------------------------------

def _make_update_app():
    """Create a minimal FastAPI app with only the update router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture()
async def update_client():
    app = _make_update_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /api/update/check and POST /api/update/apply-latest
# ---------------------------------------------------------------------------

class TestLatestUpdateFlow:
    def test_frozen_spawn_updater_runs_temp_worker_copy(self, monkeypatch):
        from src.api import update

        popen_calls = []
        copy_calls = []

        def fake_copy(source, destination):
            copy_calls.append((source, destination))

        def fake_popen(command, **kwargs):
            popen_calls.append((command, kwargs))

            class Process:
                pid = 123

            return Process()

        monkeypatch.setattr(update.sys, "frozen", True, raising=False)
        monkeypatch.setattr(update.sys, "executable", r"C:\Install\erp-cnc-adapter.exe")
        monkeypatch.setattr(update.os, "getpid", lambda: 456)
        monkeypatch.setattr(update.tempfile, "gettempdir", lambda: r"C:\Temp")
        monkeypatch.setattr(update.shutil, "copy2", fake_copy)
        monkeypatch.setattr(update.subprocess, "Popen", fake_popen)

        update._spawn_updater(r"C:\Install\erp-cnc-adapter.exe", r"C:\Install\staged-update.zip", "zip")

        temp_worker = r"C:\Temp\erp-cnc-adapter-update-worker-456.exe"
        assert copy_calls == [(r"C:\Install\erp-cnc-adapter.exe", temp_worker)]
        assert popen_calls[0][0][0] == temp_worker
        assert popen_calls[0][0][2:4] == ["--exe-path", r"C:\Install\erp-cnc-adapter.exe"]

    def test_update_tls_verification_disabled_by_default(self, monkeypatch):
        from src.api.update import _verify_update_tls

        monkeypatch.delenv("ERP_CNC_UPDATE_VERIFY_TLS", raising=False)

        assert _verify_update_tls() is False

    def test_update_tls_verification_can_be_enabled(self, monkeypatch):
        from src.api.update import _verify_update_tls

        monkeypatch.setenv("ERP_CNC_UPDATE_VERIFY_TLS", "1")

        assert _verify_update_tls() is True

    def test_update_credentials_from_environment(self, monkeypatch):
        from src.api.update import _update_credentials

        monkeypatch.setenv("ERP_CNC_UPDATE_USERNAME", "svn-user")
        monkeypatch.setenv("ERP_CNC_UPDATE_PASSWORD", "svn-pass")

        assert _update_credentials() == ("svn-user", "svn-pass")

    def test_update_credentials_from_config_file(self, monkeypatch, tmp_path):
        from src.api.update import _update_credentials

        config_path = tmp_path / "config.json"
        config_path.write_text(
            '{"update_username": "config-user", "update_password": "config-pass"}',
            encoding="utf-8",
        )
        monkeypatch.delenv("ERP_CNC_UPDATE_USERNAME", raising=False)
        monkeypatch.delenv("ERP_CNC_UPDATE_PASSWORD", raising=False)
        monkeypatch.setattr("src.api.update._get_project_root", lambda: str(tmp_path))

        assert _update_credentials() == ("config-user", "config-pass")

    def test_update_auth_header_uses_basic_auth(self, monkeypatch):
        from src.api.update import _add_update_auth_header

        monkeypatch.setenv("ERP_CNC_UPDATE_USERNAME", "svn-user")
        monkeypatch.setenv("ERP_CNC_UPDATE_PASSWORD", "svn-pass")
        request = urllib.request.Request("https://server/latest.json", method="GET")

        _add_update_auth_header(request)

        expected = base64.b64encode(b"svn-user:svn-pass").decode("ascii")
        assert request.get_header("Authorization") == f"Basic {expected}"

    def test_read_remote_json_accepts_utf8_bom(self):
        from src.api.update import _read_remote_json

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"\xef\xbb\xbf{\"version\": \"1.0.3\", \"package_url\": \"https://server/update.zip\"}"

        with patch("src.api.update._urlopen_update", return_value=FakeResponse()):
            data = _read_remote_json("https://server/latest.json")

        assert data["version"] == "1.0.3"

    async def test_check_reports_update_available(self, update_client):
        latest = {"version": "999.0.0", "package_url": "https://server/update.zip", "manifest_url": "https://server/manifest.json"}
        with patch("src.api.update._read_remote_json", return_value=latest):
            resp = await update_client.get("/api/update/check")

        body = resp.json()
        assert body["status"] == 0
        assert body["update_available"] is True
        assert body["latest_version"] == "999.0.0"
        assert body["package_url"] == "https://server/update.zip"

    async def test_check_reports_no_update_when_same_version(self, update_client):
        from version import VERSION
        latest = {"version": VERSION, "package_url": "https://server/update.zip"}
        with patch("src.api.update._read_remote_json", return_value=latest):
            resp = await update_client.get("/api/update/check")

        body = resp.json()
        assert body["status"] == 0
        assert body["update_available"] is False
        assert "no update" in body["message"].lower()

    async def test_check_failure_returns_status_1(self, update_client):
        with patch("src.api.update._read_remote_json", side_effect=RuntimeError("offline")):
            resp = await update_client.get("/api/update/check")

        body = resp.json()
        assert body["status"] == 1
        assert "offline" in body["message"]

    async def test_check_401_mentions_credentials(self, update_client):
        error = urllib.error.HTTPError("https://server/latest.json", 401, "Unauthorized", None, None)
        with patch("src.api.update._read_remote_json", side_effect=error):
            resp = await update_client.get("/api/update/check")

        body = resp.json()
        assert body["status"] == 1
        assert "requires credentials" in body["message"]
        assert "ERP_CNC_UPDATE_USERNAME" in body["message"]

    async def test_apply_latest_downloads_zip_and_spawns_update(self, update_client):
        latest = {"version": "999.0.0", "package_url": "https://server/update.zip"}
        with patch("src.api.update._read_remote_json", return_value=latest), \
             patch("src.api.update._download_remote_file", return_value=b"PK-update"), \
             patch("src.api.update._get_exe_path", return_value=r"C:\Install\erp-cnc-adapter.exe"), \
             patch("src.api.update._get_exe_dir", return_value=r"C:\Install"), \
             patch("src.api.update.os.makedirs"), \
             patch("builtins.open", MagicMock()), \
             patch("src.api.update._rotate_backups"), \
             patch("src.api.update._spawn_updater") as spawn:
            resp = await update_client.post("/api/update/apply-latest")

        body = resp.json()
        assert body["status"] == 0
        assert "999.0.0" in body["message"]
        assert spawn.call_args.args[1] == r"C:\Install\staged-update.zip"
        assert spawn.call_args.args[2] == "zip"

    async def test_apply_latest_refuses_when_no_newer_version(self, update_client):
        from version import VERSION
        latest = {"version": VERSION, "package_url": "https://server/update.zip"}
        with patch("src.api.update._read_remote_json", return_value=latest):
            resp = await update_client.post("/api/update/apply-latest")

        body = resp.json()
        assert body["status"] == 1
        assert "no update" in body["message"].lower()


# ---------------------------------------------------------------------------
# POST /api/update (upload_update)
# ---------------------------------------------------------------------------

class TestUploadUpdate:

    async def test_rejects_non_exe(self, update_client):
        resp = await update_client.post(
            "/api/update",
            files={"file": ("readme.txt", b"data", "application/octet-stream")},
        )
        body = resp.json()
        assert body["status"] == 1
        assert ".zip" in body["message"].lower()

    async def test_rejects_empty_file(self, update_client):
        resp = await update_client.post(
            "/api/update",
            files={"file": ("app.exe", b"", "application/octet-stream")},
        )
        body = resp.json()
        assert body["status"] == 1
        assert "empty" in body["message"].lower()

    async def test_accepts_uppercase_exe(self, update_client):
        with patch("src.api.update._get_exe_path", return_value=r"C:\Install\erp-cnc-adapter.exe"), \
             patch("src.api.update._get_exe_dir", return_value=r"C:\Install"), \
             patch("src.api.update.os.makedirs"), \
             patch("builtins.open", MagicMock()), \
             patch("src.api.update._rotate_backups"), \
             patch("src.api.update._spawn_updater"):
            resp = await update_client.post(
                "/api/update",
                files={"file": ("APP.EXE", b"\x00" * 100, "application/octet-stream")},
            )
            body = resp.json()
            assert body["status"] == 0

    async def test_accepts_full_zip_package(self, update_client):
        with patch("src.api.update._get_exe_path", return_value=r"C:\Install\erp-cnc-adapter.exe"), \
             patch("src.api.update._get_exe_dir", return_value=r"C:\Install"), \
             patch("src.api.update.os.makedirs"), \
             patch("builtins.open", MagicMock()), \
             patch("src.api.update._rotate_backups"), \
             patch("src.api.update._spawn_updater") as spawn:
            resp = await update_client.post(
                "/api/update",
                files={"file": ("erp-cnc-adapter-update-v1.0.2.ZIP", b"PK" + b"\x00" * 100, "application/zip")},
            )

        body = resp.json()
        assert body["status"] == 0
        assert spawn.call_args.args[1] == r"C:\Install\staged-update.zip"
        assert spawn.call_args.args[2] == "zip"


    async def test_write_oserror(self, update_client):
        with patch("src.api.update._get_exe_path", return_value=r"C:\Install\erp-cnc-adapter.exe"), \
             patch("src.api.update._get_exe_dir", return_value=r"C:\Install"), \
             patch("src.api.update.os.makedirs"), \
             patch("builtins.open", side_effect=OSError("disk full")):
            resp = await update_client.post(
                "/api/update",
                files={"file": ("app.exe", b"\x00" * 10, "application/octet-stream")},
            )
            body = resp.json()
            assert body["status"] == 1
            assert "failed" in body["message"].lower()

    async def test_spawn_failure(self, update_client):
        with patch("src.api.update._get_exe_path", return_value=r"C:\Install\erp-cnc-adapter.exe"), \
             patch("src.api.update._get_exe_dir", return_value=r"C:\Install"), \
             patch("src.api.update.os.makedirs"), \
             patch("builtins.open", MagicMock()), \
             patch("src.api.update._rotate_backups"), \
             patch("src.api.update._spawn_updater", side_effect=RuntimeError("no python")):
            resp = await update_client.post(
                "/api/update",
                files={"file": ("app.exe", b"\x00" * 10, "application/octet-stream")},
            )
            body = resp.json()
            assert body["status"] == 1
            assert "failed" in body["message"].lower()

    async def test_happy_path(self, update_client):
        with patch("src.api.update._get_exe_path", return_value=r"C:\Install\erp-cnc-adapter.exe"), \
             patch("src.api.update._get_exe_dir", return_value=r"C:\Install"), \
             patch("src.api.update.os.makedirs"), \
             patch("builtins.open", MagicMock()), \
             patch("src.api.update._rotate_backups"), \
             patch("src.api.update._spawn_updater"):
            resp = await update_client.post(
                "/api/update",
                files={"file": ("app.exe", b"\x00" * 100, "application/octet-stream")},
            )
            body = resp.json()
            assert body["status"] == 0
            assert body["version_info"] != ""

    async def test_update_does_not_touch_existing_config(self, update_client):
        with patch("src.api.update._get_exe_path", return_value=r"C:\Install\erp-cnc-adapter.exe"), \
             patch("src.api.update._get_exe_dir", return_value=r"C:\Install"), \
             patch("src.api.update.os.makedirs"), \
             patch("builtins.open", MagicMock()), \
             patch("src.api.update._rotate_backups"), \
             patch("src.api.update._spawn_updater") as spawn:
            resp = await update_client.post(
                "/api/update",
                files={"file": ("app.exe", b"\x00" * 100, "application/octet-stream")},
            )

        assert resp.json()["status"] == 0
        command_args = spawn.call_args.args
        assert r"C:\Install\config.json" not in command_args
        assert command_args[2] == "exe"

    async def test_rejects_empty_filename(self, update_client):
        """Empty string filename results in rejection (422 or status=1)."""
        resp = await update_client.post(
            "/api/update",
            files={"file": ("", b"data", "application/octet-stream")},
        )
        # FastAPI may return 422 for empty filename, or our handler returns status=1
        assert resp.status_code == 422 or resp.json().get("status") == 1


# ---------------------------------------------------------------------------
# POST /api/update/rollback
# ---------------------------------------------------------------------------

class TestRollback:

    async def test_no_backups(self, update_client):
        with patch("src.api.update._list_backups", return_value=[]):
            resp = await update_client.post("/api/update/rollback")
            body = resp.json()
            assert body["status"] == 1
            assert "no backup" in body["message"].lower()

    async def test_copy_fails(self, update_client):
        backup = BackupInfo(filename="erp-cnc-adapter.exe.bak.20260101", timestamp="20260101", size_mb=5.0)
        with patch("src.api.update._list_backups", return_value=[backup]), \
             patch("src.api.update._get_exe_path", return_value=r"C:\Install\erp-cnc-adapter.exe"), \
             patch("src.api.update._get_exe_dir", return_value=r"C:\Install"), \
             patch("src.api.update.shutil.copy2", side_effect=OSError("access denied")):
            resp = await update_client.post("/api/update/rollback")
            body = resp.json()
            assert body["status"] == 1

    async def test_spawn_fails(self, update_client):
        backup = BackupInfo(filename="erp-cnc-adapter.exe.bak.20260101", timestamp="20260101", size_mb=5.0)
        with patch("src.api.update._list_backups", return_value=[backup]), \
             patch("src.api.update._get_exe_path", return_value=r"C:\Install\erp-cnc-adapter.exe"), \
             patch("src.api.update._get_exe_dir", return_value=r"C:\Install"), \
             patch("src.api.update.shutil.copy2"), \
             patch("src.api.update._spawn_updater", side_effect=RuntimeError("no python")):
            resp = await update_client.post("/api/update/rollback")
            body = resp.json()
            assert body["status"] == 1

    async def test_happy_path(self, update_client):
        backup = BackupInfo(filename="erp-cnc-adapter.exe.bak.20260101", timestamp="20260101", size_mb=5.0)
        with patch("src.api.update._list_backups", return_value=[backup]), \
             patch("src.api.update._get_exe_path", return_value=r"C:\Install\erp-cnc-adapter.exe"), \
             patch("src.api.update._get_exe_dir", return_value=r"C:\Install"), \
             patch("src.api.update.shutil.copy2"), \
             patch("src.api.update._spawn_updater"):
            resp = await update_client.post("/api/update/rollback")
            body = resp.json()
            assert body["status"] == 0

    async def test_full_backup_rollback_uses_zip_worker(self, update_client):
        backup = BackupInfo(filename="install-backup-v1.0.1.20260729_100000.zip", timestamp="20260729_100000", size_mb=5.0)
        with patch("src.api.update._list_backups", return_value=[backup]), \
             patch("src.api.update._get_exe_path", return_value=r"C:\Install\erp-cnc-adapter.exe"), \
             patch("src.api.update._get_exe_dir", return_value=r"C:\Install"), \
             patch("src.api.update.os.path.exists", return_value=True), \
             patch("src.api.update.shutil.copy2"), \
             patch("src.api.update._spawn_updater") as spawn:
            resp = await update_client.post("/api/update/rollback")

        assert resp.json()["status"] == 0
        assert spawn.call_args.args[1] == r"C:\Install\staged-update.zip"
        assert spawn.call_args.args[2] == "restore"


# ---------------------------------------------------------------------------
# GET /api/update/backups
# ---------------------------------------------------------------------------

class TestListBackupsEndpoint:

    async def test_empty(self, update_client):
        with patch("src.api.update._list_backups", return_value=[]):
            resp = await update_client.get("/api/update/backups")
            body = resp.json()
            assert body["status"] == 0
            assert body["backups"] == []

    async def test_multiple_backups(self, update_client):
        backups = [
            BackupInfo(filename="f1.bak.ts1", timestamp="ts1", size_mb=1.0),
            BackupInfo(filename="f2.bak.ts2", timestamp="ts2", size_mb=2.0),
        ]
        with patch("src.api.update._list_backups", return_value=backups):
            resp = await update_client.get("/api/update/backups")
            body = resp.json()
            assert body["status"] == 0
            assert len(body["backups"]) == 2
