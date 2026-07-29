
import json
import zipfile

from src.update_worker import _install_zip_payload
from util_scripts.create_update_package import create_package


def test_full_package_install_removes_obsolete_files_and_preserves_local_config(tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    (install_dir / "erp-cnc-adapter.exe").write_bytes(b"old")
    (install_dir / "old_only.txt").write_text("remove me", encoding="utf-8")
    (install_dir / "config.json").write_text("local config", encoding="utf-8")
    (install_dir / "logs").mkdir()
    (install_dir / "logs" / "adapter.log").write_text("keep log", encoding="utf-8")

    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "erp-cnc-adapter.exe").write_bytes(b"new")
    (payload / "VERSION.txt").write_text("Version: 1.0.2\n", encoding="utf-8")
    (payload / "config.json").write_text("package config", encoding="utf-8")
    package = create_package(payload, "1.0.2", tmp_path / "update.zip")

    _install_zip_payload(str(package), str(install_dir), verify_manifest=True)

    assert (install_dir / "erp-cnc-adapter.exe").read_bytes() == b"new"
    assert (install_dir / "VERSION.txt").read_text(encoding="utf-8") == "Version: 1.0.2\n"
    assert not (install_dir / "old_only.txt").exists()
    assert (install_dir / "config.json").read_text(encoding="utf-8") == "local config"
    assert (install_dir / "logs" / "adapter.log").read_text(encoding="utf-8") == "keep log"


def test_full_package_install_preserves_generated_launcher_scripts(tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    (install_dir / "erp-cnc-adapter.exe").write_bytes(b"old")
    scripts_dir = install_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "launch_adapter_hidden.vbs").write_text("generated vbs", encoding="utf-8")
    (scripts_dir / "start_cnc_feedback.ps1").write_text("generated ps1", encoding="utf-8")
    (scripts_dir / "old_managed.bat").write_text("remove me", encoding="utf-8")

    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "erp-cnc-adapter.exe").write_bytes(b"new")
    (payload / "VERSION.txt").write_text("Version: 1.0.10\n", encoding="utf-8")
    package = create_package(payload, "1.0.10", tmp_path / "update.zip")

    _install_zip_payload(str(package), str(install_dir), verify_manifest=True)

    assert (scripts_dir / "launch_adapter_hidden.vbs").read_text(encoding="utf-8") == "generated vbs"
    assert (scripts_dir / "start_cnc_feedback.ps1").read_text(encoding="utf-8") == "generated ps1"
    assert not (scripts_dir / "old_managed.bat").exists()


def test_restore_zip_removes_files_not_in_backup_without_manifest(tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    (install_dir / "new_only.txt").write_text("remove me", encoding="utf-8")
    (install_dir / "config.json").write_text("local config", encoding="utf-8")
    backup_zip = tmp_path / "backup.zip"
    with zipfile.ZipFile(backup_zip, "w") as archive:
        archive.writestr("erp-cnc-adapter.exe", b"old")
        archive.writestr("VERSION.txt", "Version: 1.0.1\n")

    _install_zip_payload(str(backup_zip), str(install_dir), verify_manifest=False)

    assert (install_dir / "erp-cnc-adapter.exe").read_bytes() == b"old"
    assert not (install_dir / "new_only.txt").exists()
    assert (install_dir / "config.json").read_text(encoding="utf-8") == "local config"


def test_stop_processes_kills_adapter_pid_without_image_name(monkeypatch):
    from src import update_worker

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

        class Result:
            returncode = 0
            stdout = "SUCCESS"
            stderr = ""

        return Result()

    monkeypatch.setattr(update_worker.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(update_worker.os, "getpid", lambda: 200)
    monkeypatch.setattr(update_worker.subprocess, "run", fake_run)

    update_worker._stop_processes("erp-cnc-adapter.exe", adapter_pid=100)

    assert calls == [["taskkill", "/F", "/PID", "100"]]


def test_stop_processes_does_not_kill_current_update_worker(monkeypatch):
    from src import update_worker

    calls = []
    monkeypatch.setattr(update_worker.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(update_worker.os, "getpid", lambda: 200)
    monkeypatch.setattr(update_worker.subprocess, "run", lambda args, **kwargs: calls.append(args))

    update_worker._stop_processes("erp-cnc-adapter.exe", adapter_pid=200)

    assert calls == []


def test_stop_processes_without_pid_skips_image_name_kill(monkeypatch):
    from src import update_worker

    calls = []
    monkeypatch.setattr(update_worker.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(update_worker.subprocess, "run", lambda args, **kwargs: calls.append(args))

    update_worker._stop_processes("erp-cnc-adapter.exe", adapter_pid=None)

    assert calls == []

def test_stop_processes_kills_other_adapter_processes_from_same_exe(monkeypatch):
    from src import update_worker

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

        class Result:
            returncode = 0
            stdout = "4052\n2544\n7104\n"
            stderr = ""

        if args[0] == "taskkill":
            Result.stdout = "SUCCESS"
        return Result()

    monkeypatch.setattr(update_worker.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(update_worker.os, "getpid", lambda: 7104)
    monkeypatch.setattr(update_worker.subprocess, "run", fake_run)

    update_worker._stop_processes(
        "erp-cnc-adapter.exe",
        r"C:\Program Files (x86)\ERP-CNC Adapter\erp-cnc-adapter.exe",
        adapter_pid=4052,
    )

    assert ["taskkill", "/F", "/PID", "4052"] in calls
    assert ["taskkill", "/F", "/PID", "2544"] in calls
    assert ["taskkill", "/F", "/PID", "7104"] not in calls
