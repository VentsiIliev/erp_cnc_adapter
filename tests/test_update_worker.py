
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
    monkeypatch.setattr(update_worker, "_wait_until_exe_unlocked", lambda _path: None)
    monkeypatch.setattr(update_worker.subprocess, "run", fake_run)

    update_worker._stop_processes(
        "erp-cnc-adapter.exe",
        r"C:\Program Files (x86)\ERP-CNC Adapter\erp-cnc-adapter.exe",
        adapter_pid=4052,
    )

    assert ["taskkill", "/F", "/PID", "4052"] in calls
    assert ["taskkill", "/F", "/PID", "2544"] in calls
    assert ["taskkill", "/F", "/PID", "7104"] not in calls

def test_wmic_process_parser_filters_exact_exe_path():
    from src.update_worker import _parse_wmic_process_lines

    output = """
ExecutablePath                                      ProcessId
C:\\Program Files (x86)\\ERP-CNC Adapter\\erp-cnc-adapter.exe  111
C:\\Users\\CNC1\\AppData\\Local\\Temp\\erp-cnc-adapter-update-worker-111.exe  222
C:\\Other\\erp-cnc-adapter.exe  333
"""

    assert _parse_wmic_process_lines(output, r"C:\Program Files (x86)\ERP-CNC Adapter\erp-cnc-adapter.exe") == [111]


def test_get_process_ids_falls_back_to_wmic_when_powershell_times_out(monkeypatch):
    from src import update_worker

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[0] == "powershell":
            raise subprocess.TimeoutExpired(args, 10)

        class Result:
            returncode = 0
            stdout = "ExecutablePath                                      ProcessId\nC:\\Install\\erp-cnc-adapter.exe  123\n"
            stderr = ""

        return Result()

    import subprocess

    monkeypatch.setattr(update_worker.os, "name", "nt")
    monkeypatch.setattr(update_worker.subprocess, "run", fake_run)

    assert update_worker._get_process_ids_for_exe_path(r"C:\Install\erp-cnc-adapter.exe") == [123]
    assert calls[0][0] == "powershell"
    assert calls[1][0] == "wmic"


def test_stop_processes_waits_for_target_exe_unlock_and_skips_worker_pid(monkeypatch, tmp_path):
    from src import update_worker

    exe_path = tmp_path / "erp-cnc-adapter.exe"
    exe_path.write_bytes(b"old")
    killed = []
    unlock_checks = []

    monkeypatch.setattr(update_worker.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(update_worker.os, "getpid", lambda: 200)
    monkeypatch.setattr(update_worker, "_get_process_ids_for_exe_path", lambda _path: [100, 200, 300])
    monkeypatch.setattr(update_worker, "_kill_process_id", lambda pid: killed.append(pid) or True)
    monkeypatch.setattr(update_worker, "_wait_until_exe_unlocked", lambda path: unlock_checks.append(path))

    update_worker._stop_processes("erp-cnc-adapter.exe", str(exe_path), adapter_pid=100)

    assert killed == [100, 300]
    assert 200 not in killed
    assert unlock_checks == [str(exe_path)]


def test_wait_until_exe_unlocked_raises_when_file_stays_locked(monkeypatch, tmp_path):
    from src import update_worker

    exe_path = tmp_path / "erp-cnc-adapter.exe"
    exe_path.write_bytes(b"old")
    times = iter([0.0, 1.0])

    monkeypatch.setattr(update_worker.time, "monotonic", lambda: next(times, 1.0))
    monkeypatch.setattr(update_worker.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(update_worker.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("locked")))

    import pytest

    with pytest.raises(RuntimeError, match="still locked"):
        update_worker._wait_until_exe_unlocked(str(exe_path), timeout_seconds=0.5)


def test_repair_start_cnc_shortcut_targets_hidden_launcher(monkeypatch, tmp_path):
    from src import update_worker

    install_dir = tmp_path / "install"
    scripts_dir = install_dir / "scripts"
    resources_dir = install_dir / "resources"
    scripts_dir.mkdir(parents=True)
    resources_dir.mkdir()
    launcher = scripts_dir / "start_cnc_hidden.vbs"
    launcher.write_text("hidden launcher", encoding="utf-8")
    (resources_dir / "logo.ico").write_bytes(b"icon")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))

        class Result:
            returncode = 0
            stdout = r"C:\Users\Public\Desktop\START-CNC.lnk"
            stderr = ""

        return Result()

    monkeypatch.setattr(update_worker.os, "name", "nt")
    monkeypatch.setattr(update_worker.subprocess, "run", fake_run)

    assert update_worker._repair_start_cnc_shortcut(str(install_dir)) is True

    args, kwargs = calls[0]
    script = args[-1]
    assert args[:4] == ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass"]
    assert "$shortcut.TargetPath = 'wscript.exe'" in script
    assert "//B //Nologo" in script
    assert str(launcher) in script
    assert "start_cnc_feedback.ps1" not in script
    assert kwargs["timeout"] == 20


def test_repair_start_cnc_shortcut_skips_when_hidden_launcher_missing(monkeypatch, tmp_path):
    from src import update_worker

    calls = []
    monkeypatch.setattr(update_worker.os, "name", "nt")
    monkeypatch.setattr(update_worker.subprocess, "run", lambda *args, **kwargs: calls.append(args))

    assert update_worker._repair_start_cnc_shortcut(str(tmp_path)) is False
    assert calls == []


def test_repair_status_indicator_task_registers_independent_logon_task(monkeypatch, tmp_path):
    from src import update_worker

    install_dir = tmp_path / "install"
    scripts_dir = install_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (install_dir / "config.json").write_text('{"task_username":"DOMAIN\\adapter"}', encoding="utf-8")
    (scripts_dir / "status_indicator.ps1").write_text("indicator", encoding="utf-8")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(update_worker.os, "name", "nt")
    monkeypatch.setattr(update_worker.subprocess, "run", fake_run)

    assert update_worker._repair_status_indicator_task(str(install_dir)) is True
    launcher = scripts_dir / "status_indicator_hidden.vbs"
    assert launcher.exists()
    assert "status_indicator.ps1" in launcher.read_text(encoding="utf-8")
    args, kwargs = calls[0]
    script = args[-1]
    assert "ERPCNCAdapterStatusIndicator" in script
    assert "New-ScheduledTaskTrigger -AtLogOn -User $taskUser" in script
    assert "Start-ScheduledTask -TaskName 'ERPCNCAdapterStatusIndicator'" in script
    assert "ERPCNCAdapterManualStart" not in script
    assert kwargs["timeout"] == 20


def test_repair_status_indicator_task_skips_when_script_missing(monkeypatch, tmp_path):
    from src import update_worker

    calls = []
    monkeypatch.setattr(update_worker.os, "name", "nt")
    monkeypatch.setattr(update_worker.subprocess, "run", lambda *args, **kwargs: calls.append(args))

    assert update_worker._repair_status_indicator_task(str(tmp_path)) is False
    assert calls == []


def test_stop_status_indicator_processes_targets_only_indicator_script(monkeypatch, tmp_path):
    from src import update_worker

    install_dir = tmp_path / "install"
    (install_dir / "scripts").mkdir(parents=True)
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))

        class Result:
            returncode = 0
            stdout = "456\n"
            stderr = ""

        return Result()

    monkeypatch.setattr(update_worker.os, "name", "nt")
    monkeypatch.setattr(update_worker.subprocess, "run", fake_run)

    update_worker._stop_status_indicator_processes(str(install_dir))

    args, kwargs = calls[0]
    script = args[-1]
    assert args[:4] == ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass"]
    assert "status_indicator.ps1" in script
    assert "Get-CimInstance Win32_Process" in script
    assert "Stop-Process -Id $_.ProcessId" in script
    assert "erp-cnc-adapter.exe" not in script
    assert kwargs["timeout"] == 10
