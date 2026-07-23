from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESTART_SCRIPT = PROJECT_ROOT / "scripts" / "restart.bat"


def _restart_script_text() -> str:
    return RESTART_SCRIPT.read_text(encoding="utf-8", errors="replace")


def test_restart_script_resets_adapter_gui_and_cnc_server_before_starting():
    text = _restart_script_text()
    elevated_section = text[text.index('echo [%date% %time%] Restarting ERP-CNC Adapter'):]

    adapter_stop = elevated_section.index("taskkill /F /T /IM erp-cnc-adapter.exe")
    gui_stop = elevated_section.index("taskkill /F /T /IM cnc4.03.exe")
    server_stop = elevated_section.index("taskkill /F /T /IM CncServer.exe")
    adapter_start = elevated_section.index("schtasks /Run /TN ERPCNCAdapter")

    assert adapter_stop < gui_stop < server_stop < adapter_start
    assert "taskkill /F /T /IM cnc.exe" in text


def test_restart_script_delegates_non_task_launch_to_elevated_manual_task():
    text = _restart_script_text()

    handoff = text.index('if not "%ERPCNC_MANUAL_TASK%"=="1"')
    adapter_stop = text.index("taskkill /F /T /IM erp-cnc-adapter.exe")

    assert handoff < adapter_stop
    assert "schtasks /Run /TN ERPCNCAdapterManualStart" in text
    assert "Could not start elevated manual START-CNC task" in text


def test_restart_script_falls_back_to_direct_adapter_launch():
    text = _restart_script_text()

    assert "setlocal EnableDelayedExpansion" in text
    assert "if errorlevel 1" in text
    assert 'set "ADAPTER_EXE=!INSTALL_DIR!\\erp-cnc-adapter.exe"' in text
    assert 'set "HIDDEN_LAUNCHER=!INSTALL_DIR!\\scripts\\launch_adapter_hidden.vbs"' in text
    assert 'wscript.exe //B //Nologo "!HIDDEN_LAUNCHER!"' in text
    assert 'start "" /B /D "!INSTALL_DIR!" "!ADAPTER_EXE!"' in text
    assert "%ADAPTER_EXE%" not in text
    assert "pause" not in text.lower()


def test_restart_script_starts_gui_before_adapter_when_auto_gui_enabled():
    text = _restart_script_text()
    elevated_section = text[text.index('echo [%date% %time%] Restarting ERP-CNC Adapter'):]

    gui_branch = elevated_section.index("Auto GUI is enabled; starting Eding GUI before adapter")
    handoff = elevated_section.index("start_eding_handoff.ps1")
    adapter_start = elevated_section.index("schtasks /Run /TN ERPCNCAdapter")

    assert "ConvertFrom-Json" in elevated_section
    assert gui_branch < handoff < adapter_start


def test_restart_script_defers_gui_only_when_auto_gui_is_disabled():
    text = _restart_script_text()
    elevated_section = text[text.index('echo [%date% %time%] Restarting ERP-CNC Adapter'):]

    marker = elevated_section.index("manual_start_defer_gui.flag")
    adapter_start = elevated_section.index("schtasks /Run /TN ERPCNCAdapter")
    auto_gui_branch = elevated_section.index('if "!AUTO_GUI!"=="1"')
    disabled_branch = elevated_section.index(") else (")

    assert auto_gui_branch < disabled_branch < marker < adapter_start
    assert "Deferring Eding GUI launch until adapter readiness is confirmed" in text


def test_restart_script_logs_routine_output_instead_of_showing_console_messages():
    text = _restart_script_text()

    assert 'set "LOG_FILE=!LOG_DIR!\\start-cnc.log"' in text
    assert ">> \"!LOG_FILE!\"" in text
    assert "Restarting ERP-CNC Adapter... > \"!LOG_FILE!\"" in text
    assert "exit /b 1" in text
    assert "exit /b 0" in text
