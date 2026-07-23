"""Tests for Machine ID in installer — PathPage UI, worker config writing."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure QApplication exists before any widget tests
_qapp = None

def _ensure_qapp():
    global _qapp
    if _qapp is None:
        from PyQt5.QtWidgets import QApplication
        _qapp = QApplication.instance() or QApplication(sys.argv)
    return _qapp


# ---------------------------------------------------------------------------
# PathPage UI tests
# ---------------------------------------------------------------------------

class TestPathPageMachineField:
    """Verify Machine ID field exists on PathPage with correct defaults."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        _ensure_qapp()
        from src.installer.ui.pages import PathPage
        self.page = PathPage()
        yield
        self.page.deleteLater()

    def test_machine_edit_exists(self):
        assert hasattr(self.page, "machine_edit"), "PathPage must have a machine_edit field"

    def test_machine_edit_default_value(self):
        assert self.page.machine_edit.text() == "CNC1"

    def test_machine_edit_accepts_custom_value(self):
        self.page.machine_edit.setText("MILL3")
        assert self.page.machine_edit.text() == "MILL3"

    def test_machine_edit_max_width(self):
        assert self.page.machine_edit.maximumWidth() == 200

    def test_run_as_windows_account_default_enabled(self):
        assert self.page.run_as_user_check.isChecked() is True
        assert self.page.auto_start_check.isChecked() is True
        assert self.page.username_edit.isEnabled() is True
        assert self.page.username_edit.isHidden() is False
        assert self.page.password_edit.isEnabled() is True
        assert self.page.password_edit.isHidden() is False


# ---------------------------------------------------------------------------
# InstallWorker unit tests (no GUI, no subprocess)
# ---------------------------------------------------------------------------

class TestInstallWorkerInit:
    """Verify InstallWorker stores machine_number."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        _ensure_qapp()

    def test_default_machine_number(self):
        from src.installer.worker import InstallWorker
        worker = InstallWorker(r"C:\fake\path")
        assert worker.machine_number == "CNC1"

    def test_custom_machine_number(self):
        from src.installer.worker import InstallWorker
        worker = InstallWorker(r"C:\fake\path", "MILL5")
        assert worker.machine_number == "MILL5"

    def test_install_path_stored(self):
        from src.installer.worker import InstallWorker
        worker = InstallWorker(r"C:\fake\path", "CNC2")
        assert worker.install_path == Path(r"C:\fake\path")

    def test_task_credentials_default_empty(self):
        from src.installer.worker import InstallWorker
        worker = InstallWorker(r"C:\fake\path")
        assert worker.task_username == ""
        assert worker.task_password == ""

    def test_task_credentials_stored(self):
        from src.installer.worker import InstallWorker
        worker = InstallWorker(r"C:\fake\path", "CNC2", r"DOMAIN\adapter", "secret")
        assert worker.task_username == r"DOMAIN\adapter"
        assert worker.task_password == "secret"

    def test_auto_start_adapter_on_logon_stored(self):
        from src.installer.worker import InstallWorker
        worker = InstallWorker(r"C:\fake\path", "CNC2", "", "", False)
        assert worker.auto_start_adapter_on_logon is False


class TestInstallWorkerConfigWrite:
    """Verify the config.json merge logic used by the worker."""

    def test_writes_config_json_with_machine_number(self, tmp_path):
        """Creates config.json with machine_number when none exists."""
        config_path = tmp_path / "config.json"
        config_data = {}
        config_data["machine_number"] = "CNC9"
        config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

        result = json.loads(config_path.read_text(encoding="utf-8"))
        assert result["machine_number"] == "CNC9"

    def test_merges_with_existing_config_json(self, tmp_path):
        """Preserves existing keys when writing machine_number."""
        config_path = tmp_path / "config.json"
        existing = {"job_done_report_url": "http://example.com/done", "base_dir": r"\\server\share"}
        config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        # Simulate the worker's merge logic
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        config_data["machine_number"] = "MILL2"
        config_path.write_text(
            json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        result = json.loads(config_path.read_text(encoding="utf-8"))
        assert result["machine_number"] == "MILL2"
        assert result["job_done_report_url"] == "http://example.com/done"
        assert result["base_dir"] == r"\\server\share"

    def test_merges_task_username_into_config_json(self, tmp_path):
        """Persists the scheduled-task username chosen during install."""
        config_path = tmp_path / "config.json"
        existing = {"machine_number": "CNC1"}
        config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        config_data["task_username"] = r"DOMAIN\adapter"
        config_path.write_text(
            json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        result = json.loads(config_path.read_text(encoding="utf-8"))
        assert result["machine_number"] == "CNC1"
        assert result["task_username"] == r"DOMAIN\adapter"

    def test_merges_auto_start_choice_into_config_json(self, tmp_path):
        """Persists the install-time auto-start choice."""
        config_path = tmp_path / "config.json"
        existing = {"machine_number": "CNC1"}
        config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        config_data["auto_start_adapter_on_logon"] = False
        config_path.write_text(
            json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        result = json.loads(config_path.read_text(encoding="utf-8"))
        assert result["auto_start_adapter_on_logon"] is False

    def test_overwrites_existing_machine_number(self, tmp_path):
        """Replaces old machine_number value."""
        config_path = tmp_path / "config.json"
        existing = {"machine_number": "OLD1", "base_dir": r"\\server\share"}
        config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        config_data["machine_number"] = "NEW7"
        config_path.write_text(
            json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        result = json.loads(config_path.read_text(encoding="utf-8"))
        assert result["machine_number"] == "NEW7"
        assert result["base_dir"] == r"\\server\share"

    def test_handles_corrupt_existing_config(self, tmp_path):
        """Falls back to empty dict when existing config.json is invalid JSON."""
        config_path = tmp_path / "config.json"
        config_path.write_text("NOT VALID JSON {{{", encoding="utf-8")

        # Simulate the worker's error-handling merge logic
        config_data = {}
        try:
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            config_data = {}
        config_data["machine_number"] = "CNC5"
        config_path.write_text(
            json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        result = json.loads(config_path.read_text(encoding="utf-8"))
        assert result["machine_number"] == "CNC5"

    def test_post_install_warning_when_dll_missing(self):
        from src.installer.worker import InstallWorker

        warning = InstallWorker._post_install_warning({
            "dll_path": r"C:\missing\cncapi.dll",
            "ini_path": r"C:\missing\cnc.ini",
        })

        assert "CNC runtime files are unavailable" in warning
        assert "cncapi.dll" in warning
        assert "cnc.ini" in warning

    def test_post_install_warning_empty_when_runtime_files_exist(self, tmp_path):
        from src.installer.worker import InstallWorker

        dll_path = tmp_path / "cncapi.dll"
        ini_path = tmp_path / "cnc.ini"
        dll_path.write_text("dll", encoding="utf-8")
        ini_path.write_text("ini", encoding="utf-8")

        warning = InstallWorker._post_install_warning({
            "dll_path": str(dll_path),
            "ini_path": str(ini_path),
        })

        assert warning == ""



class TestInstallWorkerTaskHandling:
    """Verify installer task/process handling around reinstall and startup."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        _ensure_qapp()

    @patch("src.installer.worker.time.sleep")
    @patch("src.installer.worker.subprocess.run")
    def test_stop_existing_adapter_ends_tasks_and_kills_process(self, mock_run, _sleep):
        from src.installer.worker import InstallWorker

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        worker = InstallWorker(r"C:\fake\path")
        worker._stop_existing_adapter()

        commands = [call.args[0] for call in mock_run.call_args_list]
        assert ["schtasks", "/End", "/TN", "ERPCNCAdapter"] in commands
        assert ["schtasks", "/End", "/TN", "ERPCNCAdapterWatchdog"] in commands
        assert ["schtasks", "/End", "/TN", "ERPCNCAdapterManualStart"] in commands
        assert ["schtasks", "/End", "/TN", "ERPCNCAdapterEdingHandoff"] in commands
        assert ["taskkill", "/F", "/T", "/IM", "erp-cnc-adapter.exe"] in commands

    @patch("src.installer.worker.subprocess.run")
    def test_watchdog_defaults_to_system(self, mock_run, tmp_path):
        from src.installer.worker import InstallWorker
        import io

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        worker = InstallWorker(str(tmp_path))
        worker._create_watchdog_task(tmp_path / "watchdog.bat", io.StringIO())

        command = mock_run.call_args.args[0]
        assert "/RU" in command
        assert command[command.index("/RU") + 1] == "SYSTEM"
        assert "/RP" not in command

    @patch("src.installer.worker.subprocess.run")
    def test_watchdog_uses_configured_task_account(self, mock_run, tmp_path):
        from src.installer.worker import InstallWorker
        import io

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        worker = InstallWorker(str(tmp_path), "CNC1", r"DOMAIN\adapter", "secret")
        worker._create_watchdog_task(tmp_path / "watchdog.bat", io.StringIO())

        command = mock_run.call_args.args[0]
        assert command[command.index("/RU") + 1] == r"DOMAIN\adapter"
        assert command[command.index("/RP") + 1] == "secret"

    def test_hidden_launcher_runs_adapter_without_console(self, tmp_path):
        from src.installer.worker import InstallWorker

        worker = InstallWorker(str(tmp_path), "CNC1")
        launcher = worker._write_hidden_launcher(tmp_path / "erp-cnc-adapter.exe")
        text = launcher.read_text(encoding="utf-8")

        assert launcher.name == "launch_adapter_hidden.vbs"
        assert "WScript.Shell" in text
        assert "shell.Run" in text
        assert ", 0, False" in text
        assert "erp-cnc-adapter.exe" in text

    def test_start_cnc_hidden_launcher_runs_restart_without_console(self, tmp_path):
        from src.installer.worker import InstallWorker

        worker = InstallWorker(str(tmp_path), "CNC1")
        launcher = worker._write_start_cnc_hidden_launcher()
        shortcut_text = launcher.read_text(encoding="utf-8")
        task_launcher = tmp_path / "scripts" / "run_start_cnc_hidden.vbs"
        task_text = task_launcher.read_text(encoding="utf-8")

        assert launcher.name == "start_cnc_hidden.vbs"
        assert task_launcher.exists()
        assert "WScript.Shell" in shortcut_text
        assert "schtasks /Run /TN ERPCNCAdapterManualStart" in shortcut_text
        assert ", 0, True" in shortcut_text
        assert "MsgBox" in shortcut_text
        assert "ERPCNC_MANUAL_TASK=1" in task_text
        assert "cmd.exe /c" in task_text
        assert "restart.bat" in task_text
        assert ", 0, True" in task_text
        assert "start-cnc.log" in task_text
        assert "MsgBox" in task_text

    def test_start_cnc_feedback_script_shows_progress_and_polls_health(self, tmp_path):
        from src.installer.worker import InstallWorker

        worker = InstallWorker(str(tmp_path), "CNC1")
        worker._write_eding_handoff_script()
        script_path = worker._write_start_cnc_feedback_script()
        text = script_path.read_text(encoding="utf-8")

        assert script_path.name == "start_cnc_feedback.ps1"
        assert "START-CNC is loading" in text
        assert "config.json" in text
        assert "auto_start_eding_gui" in text
        assert "start-cnc.log" in text
        assert "adapter.log" in text
        assert "function Show-NewLines" in text
        assert "function Start-EdingGuiAfterReady" in text
        assert "function Wait-AdapterReadyAfterGui" in text
        assert "Show-NewLines $logPath" in text
        assert "Show-NewLines $adapterLogPath" in text
        assert "Starting manual START-CNC task" in text
        assert "ERPCNCAdapterEdingHandoff" in text
        assert "$maxAttempts = 3" in text
        assert "attempt {0} of {1}" in text
        assert "retrying the full start sequence" in text
        assert "did not become ready after all retry attempts" in text
        assert "Eding GUI auto-start deferred" in text
        assert "Starting Eding GUI through elevated START-CNC task" in text
        assert "schtasks /Run /TN $guiTaskName" in text
        assert "cnc4.03.exe" in text
        assert "Started Eding GUI" in text
        assert "Waiting for adapter to reconnect to Eding GUI server" in text
        assert "Adapter did not reconnect after Eding GUI launch" in text
        assert "Starting CNC Server" in text
        assert "CNC connection established" in text
        assert "schtasks /Run /TN $taskName" in text
        assert "Invoke-RestMethod -Uri $healthUrl" in text
        assert "$health.cnc.connected -eq $true" in text
        assert "Start-EdingGuiAfterReady" in text
        assert "Wait-AdapterReadyAfterGui" in text
        assert "START-CNC is ready" in text
        assert "Start-Sleep -Seconds 2" in text
        assert "Read-Host 'Press Enter to close'" in text

    def test_eding_handoff_script_stops_server_and_starts_gui(self, tmp_path):
        from src.installer.worker import InstallWorker

        worker = InstallWorker(str(tmp_path), "CNC1")
        script_path = worker._write_eding_handoff_script()
        text = script_path.read_text(encoding="utf-8")

        assert script_path.name == "start_eding_handoff.ps1"
        assert "config.json" in text
        assert "cnc4.03.exe" in text
        assert "taskkill /F /IM CncServer.exe" in text
        assert "taskkill /F /T /IM CncServer.exe" not in text
        assert "Start-Process -FilePath $guiPath" in text
        assert "Stopping adapter-started CNC Server before Eding GUI launch" in text
        assert "Eding GUI started" in text

    def test_manual_start_task_runs_hidden_restart_launcher_elevated(self, tmp_path):
        from src.installer.worker import InstallWorker

        worker = InstallWorker(str(tmp_path), "CNC1", r"DOMAIN\adapter", "")
        script = worker._build_manual_start_task_script()

        assert "ERPCNCAdapterManualStart" in script
        assert "run_start_cnc_hidden.vbs" in script
        assert "Unregister-ScheduledTask" in script
        assert "schtasks /Delete" not in script
        assert "-Execute 'wscript.exe'" in script
        assert "-LogonType Interactive" in script
        assert "-RunLevel Highest" in script

    def test_eding_handoff_task_runs_elevated(self, tmp_path):
        from src.installer.worker import InstallWorker

        worker = InstallWorker(str(tmp_path), "CNC1", r"DOMAIN\adapter", "")
        script = worker._build_eding_handoff_task_script()

        assert "ERPCNCAdapterEdingHandoff" in script
        assert "start_eding_handoff.ps1" in script
        assert "Unregister-ScheduledTask" in script
        assert "-Execute 'powershell.exe'" in script
        assert "-WindowStyle Hidden" in script
        assert "-LogonType Interactive" in script
        assert "-RunLevel Highest" in script

    def test_start_shortcut_targets_feedback_script_with_logo_icon(self, tmp_path):
        from src.installer.worker import InstallWorker

        worker = InstallWorker(str(tmp_path), "CNC1")
        script = worker._build_start_shortcut_script()

        assert "START-CNC.lnk" in script
        assert "Join-Path $env:PUBLIC 'Desktop'" in script
        assert "Join-Path $env:USERPROFILE 'Desktop'" in script
        assert "$shortcut.TargetPath = 'powershell.exe'" in script
        assert str(tmp_path / "scripts" / "start_cnc_feedback.ps1") in script
        assert str(tmp_path / "scripts" / "start_cnc_hidden.vbs") not in script
        assert str(tmp_path / "scripts" / "restart.bat") not in script
        assert str(tmp_path / "resources" / "logo.ico") in script
        assert "$shortcut.TargetPath" in script
        assert "$shortcut.Arguments" in script
        assert "$shortcut.IconLocation" in script

    def test_interactive_logon_task_uses_no_password(self, tmp_path):
        from src.installer.worker import InstallWorker

        worker = InstallWorker(str(tmp_path), "CNC1", r"DESKTOP-EMJIESP\CNC5", "secret")
        script = worker._build_interactive_logon_task_script(tmp_path / "launch_adapter_hidden.vbs")

        assert "New-ScheduledTaskTrigger -AtLogOn" in script
        assert "$trigger.Delay = 'PT90S'" in script
        assert "-Execute 'wscript.exe'" in script
        assert "launch_adapter_hidden.vbs" in script
        assert "-LogonType Interactive" in script
        assert r"DESKTOP-EMJIESP\CNC5" in script
        assert "-Password" not in script
        assert "secret" not in script

    def test_interactive_logon_task_can_be_created_disabled(self, tmp_path):
        from src.installer.worker import InstallWorker

        worker = InstallWorker(str(tmp_path), "CNC1", r"DESKTOP-EMJIESP\CNC5", "", False)
        script = worker._build_interactive_logon_task_script(tmp_path / "launch_adapter_hidden.vbs")

        assert "Disable-ScheduledTask -TaskName 'ERPCNCAdapter'" in script

    def test_installer_sets_startup_delay_in_registered_task(self, tmp_path):
        from pathlib import Path

        source = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "installer"
            / "worker.py"
        ).read_text(encoding="utf-8")

        assert "adapter_startup_delay_seconds" in source
        assert "auto_start_adapter_on_logon" in source
        assert "$startupDelay = 'PT" in source
        assert "$trigger.Delay = $startupDelay" in source
        assert "Disable-ScheduledTask -TaskName 'ERPCNCAdapter'" in source


    def test_credential_diagnostics_do_not_log_password(self, tmp_path):
        from src.installer.worker import InstallWorker
        import io

        worker = InstallWorker(str(tmp_path), "CNC1", r"DOMAIN\adapter", " secret ")
        log = io.StringIO()

        worker._write_task_credential_diagnostics(log)
        text = log.getvalue()

        assert "password_length: 8" in text
        assert "password_has_leading_or_trailing_space: True" in text
        assert " secret " not in text

    def test_startup_task_treats_stderr_as_failure(self):
        from src.installer.worker import InstallWorker

        result = MagicMock(
            returncode=0,
            stdout="",
            stderr="Register-ScheduledTask : The user name or password is incorrect.",
        )

        error = InstallWorker._scheduled_task_creation_error(result)

        assert "password is incorrect" in error

    @patch("src.installer.worker.subprocess.run")
    def test_start_adapter_uses_scheduled_task(self, mock_run, tmp_path):
        from src.installer.worker import InstallWorker
        import io

        mock_run.return_value = MagicMock(returncode=0, stdout="SUCCESS", stderr="")
        worker = InstallWorker(str(tmp_path))

        assert worker._start_adapter_task(io.StringIO()) is True
        mock_run.assert_called_once()
        assert mock_run.call_args.args[0] == ["schtasks", "/Run", "/TN", "ERPCNCAdapter"]

# ---------------------------------------------------------------------------
# Window integration (pass-through from PathPage to Worker)
# ---------------------------------------------------------------------------

class TestWindowPassesMachineNumber:
    """Verify InstallerWindow passes machine_edit value to InstallWorker."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        _ensure_qapp()

    @patch("src.installer.ui.window.InstallWorker")
    def test_start_install_passes_machine_number(self, MockWorker):
        from src.installer.ui.window import InstallerWindow

        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance

        window = InstallerWindow()
        window.path_page.path_edit.setText(r"C:\test\install")
        window.path_page.machine_edit.setText("CNC3")
        window._start_install()

        MockWorker.assert_called_once_with(
            r"C:\test\install",
            "CNC3",
            window.path_page.username_edit.text().strip(),
            "",
            True,
        )
        window.close()
        window.deleteLater()

    @patch("src.installer.ui.window.InstallWorker")
    def test_empty_machine_id_defaults_to_cnc1(self, MockWorker):
        from src.installer.ui.window import InstallerWindow

        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance

        window = InstallerWindow()
        window.path_page.path_edit.setText(r"C:\test\install")
        window.path_page.machine_edit.setText("   ")  # whitespace only
        window._start_install()

        MockWorker.assert_called_once_with(
            r"C:\test\install",
            "CNC1",
            window.path_page.username_edit.text().strip(),
            "",
            True,
        )
        window.close()
        window.deleteLater()

    @patch("src.installer.ui.window.InstallWorker")
    def test_machine_id_stripped(self, MockWorker):
        from src.installer.ui.window import InstallerWindow

        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance

        window = InstallerWindow()
        window.path_page.path_edit.setText(r"C:\test\install")
        window.path_page.machine_edit.setText("  MILL1  ")
        window.path_page.run_as_user_check.setChecked(False)
        window._start_install()

        MockWorker.assert_called_once_with(r"C:\test\install", "MILL1", "", "", True)
        window.close()
        window.deleteLater()

    @patch("src.installer.ui.window.InstallWorker")
    def test_task_credentials_passed_when_enabled(self, MockWorker):
        from src.installer.ui.window import InstallerWindow

        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance

        window = InstallerWindow()
        window.path_page.path_edit.setText(r"C:\test\install")
        window.path_page.machine_edit.setText("CNC4")
        window.path_page.run_as_user_check.setChecked(True)
        window.path_page.username_edit.setText(r"DOMAIN\adapter")
        window.path_page.password_edit.setText("secret")
        window._start_install()

        MockWorker.assert_called_once_with(
            r"C:\test\install", "CNC4", r"DOMAIN\adapter", "secret", True
        )
        window.close()
        window.deleteLater()

    @patch("src.installer.ui.window.InstallWorker")
    def test_auto_start_choice_passed_to_worker(self, MockWorker):
        from src.installer.ui.window import InstallerWindow

        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance

        window = InstallerWindow()
        window.path_page.path_edit.setText(r"C:\test\install")
        window.path_page.machine_edit.setText("CNC4")
        window.path_page.auto_start_check.setChecked(False)
        window._start_install()

        MockWorker.assert_called_once_with(
            r"C:\test\install",
            "CNC4",
            window.path_page.username_edit.text().strip(),
            "",
            False,
        )
        window.close()
        window.deleteLater()

    @patch("src.installer.ui.window.QMessageBox.warning")
    def test_finished_success_shows_warning_dialog_for_missing_cnc(self, mock_warning):
        from src.installer.ui.window import InstallerWindow

        window = InstallerWindow()
        window._on_finished(True, "Installation finished, but CNC runtime files are unavailable.")

        mock_warning.assert_called_once()
        window.close()
        window.deleteLater()
