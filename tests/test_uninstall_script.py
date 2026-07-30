from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UNINSTALL_SCRIPT = PROJECT_ROOT / "scripts" / "uninstall.bat"
CLEANUP_SCRIPT = PROJECT_ROOT / "scripts" / "cleanup.bat"


def _uninstall_script_text() -> str:
    return UNINSTALL_SCRIPT.read_text(encoding="utf-8", errors="replace")


def _cleanup_script_text() -> str:
    return CLEANUP_SCRIPT.read_text(encoding="utf-8", errors="replace")


def test_uninstall_script_removes_all_adapter_tasks_and_shortcut():
    text = _uninstall_script_text()

    assert "ERPCNCAdapterStatusIndicator" in text
    assert "ERPCNCAdapterEdingHandoff" in text
    assert "ERPCNCAdapterManualStart" in text
    assert "ERPCNCAdapterWatchdog" in text
    assert "ERPCNCAdapter" in text
    assert "START-CNC.lnk" in text
    assert "%PUBLIC%\\Desktop\\START-CNC.lnk" in text
    assert "%USERPROFILE%\\Desktop\\START-CNC.lnk" in text


def test_uninstall_script_stops_adapter_cnc_and_launcher_processes():
    text = _uninstall_script_text()

    for process_name in (
        "erp-cnc-adapter.exe",
        "cnc4.03.exe",
        "cnc.exe",
        "CncServer.exe",
        "wscript.exe",
    ):
        assert process_name in text
    assert "taskkill /F /T /IM %%P" in text
    assert "status_indicator.ps1" in text
    assert "Get-CimInstance Win32_Process | Where-Object" in text
    assert "-Filter \"Name =" not in text
    assert "$currentPid = $PID" in text
    assert "$_.ProcessId -ne $currentPid" in text
    assert "$_.Name -ieq 'powershell.exe'" in text
    assert "$_.Name -ieq 'pwsh.exe'" in text
    assert "Stop-Process -Id $_.ProcessId" in text


def test_uninstall_script_schedules_install_folder_removal_after_exit():
    text = _uninstall_script_text()

    assert 'cd /d "%SystemRoot%"' in text
    assert "Remove-Item -LiteralPath '%INSTALL_DIR%' -Recurse -Force" in text
    assert "Start-Sleep -Seconds 3" in text
    assert "-WindowStyle Hidden" in text
    assert "exit /b 0" in text


def test_cleanup_script_stops_status_indicator_without_broken_batch_quoting():
    text = _cleanup_script_text()

    assert "ERPCNCAdapterStatusIndicator" in text
    assert "status_indicator.ps1" in text
    assert "Get-CimInstance Win32_Process | Where-Object" in text
    assert "-Filter \"Name =" not in text
    assert "$currentPid = $PID" in text
    assert "$_.ProcessId -ne $currentPid" in text
    assert "$_.Name -ieq 'powershell.exe'" in text
    assert "$_.Name -ieq 'pwsh.exe'" in text
    assert "Stop-Process -Id $_.ProcessId" in text
