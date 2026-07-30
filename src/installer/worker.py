"""
ERP-CNC Adapter Installer — Install Worker (QThread).
"""
import json
import os
import sys
import shutil
import subprocess
import urllib.request
import tempfile
import time
from pathlib import Path
from datetime import datetime

from PyQt5.QtCore import QThread, pyqtSignal


# ── Install Worker (QThread) ─────────────────────────────────────────────────
class InstallWorker(QThread):
    log_message = pyqtSignal(str)
    step_changed = pyqtSignal(str)
    progress_value = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)  # success, message
    DEFAULT_STARTUP_DELAY_SECONDS = 15
    MANUAL_START_TASK_NAME = "ERPCNCAdapterManualStart"
    EDING_HANDOFF_TASK_NAME = "ERPCNCAdapterEdingHandoff"
    STATUS_INDICATOR_TASK_NAME = "ERPCNCAdapterStatusIndicator"

    def __init__(
        self,
        install_path: str,
        machine_number: str = "CNC1",
        task_username: str = "",
        task_password: str = "",
        auto_start_adapter_on_logon: bool = True,
    ):
        super().__init__()
        self.install_path = Path(install_path)
        self.machine_number = machine_number
        self.task_username = task_username.strip()
        self.task_password = task_password
        self.auto_start_adapter_on_logon = auto_start_adapter_on_logon

    # Helper ───────────────────────────────────────────────────────────────
    @staticmethod
    def _startupinfo():
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        return si

    @staticmethod
    def _ps_quote(value: str) -> str:
        return value.replace("'", "''")

    @staticmethod
    def _log_timed(installation_log, label: str, started_at: float) -> None:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        installation_log.write(f"{label} completed in {elapsed_ms:.1f}ms\n")
        installation_log.flush()

    def _run_powershell_script(self, ps_script: str) -> subprocess.CompletedProcess:
        ps_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", delete=False, encoding="utf-8",
        )
        ps_file.write(ps_script)
        ps_file.close()
        try:
            return subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_file.name],
                capture_output=True,
                text=True,
                startupinfo=self._startupinfo(),
            )
        finally:
            os.unlink(ps_file.name)

    @staticmethod
    def _combined_step_body(ps_script: str) -> str:
        lines = [
            line for line in ps_script.splitlines()
            if not line.strip().startswith("$ErrorActionPreference")
        ]
        body = "\n".join(lines)
        return "$ErrorActionPreference = 'Stop'\n" + body + "\n$ErrorActionPreference = 'Continue'\n"

    PYTHON_VERSION = "3.12.8"
    PYTHON_URL = (
        "https://www.python.org/ftp/python/{v}/python-{v}-amd64.exe"
    )

    @staticmethod
    def _post_install_warning(config_data: dict) -> str:
        dll_path = config_data.get("dll_path", r"C:\CNC4.03\cncapi.dll")
        ini_path = config_data.get("ini_path", r"C:\CNC4.03\cnc.ini")
        missing = []
        if not Path(dll_path).exists():
            missing.append(f"CNC DLL not found: {dll_path}")
        if not Path(ini_path).exists():
            missing.append(f"CNC INI not found: {ini_path}")
        if not missing:
            return ""
        return (
            "Installation finished, but CNC runtime files are unavailable.\n"
            + "\n".join(missing)
            + "\n\nOpen the dashboard Configuration page, set the correct CNC DLL and INI paths, then apply and restart the task."
        )

    def _find_python(self) -> str | None:
        """Return path to python.exe if available, else None."""
        if not getattr(sys, "frozen", False):
            return sys.executable

        # Check PATH first
        exe = shutil.which("python") or shutil.which("python3")
        if exe:
            return exe

        # Check common install locations (both Program Files and AppData)
        username = os.environ.get("USERNAME", "")

        locations_to_check = [
            # Program Files (system-wide install)
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Python312" / "python.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Python311" / "python.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Python310" / "python.exe",
            Path(r"C:\Python312") / "python.exe",
            Path(r"C:\Python311") / "python.exe",
            Path(r"C:\Python310") / "python.exe",
            # User install (AppData)
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312" / "python.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python311" / "python.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python310" / "python.exe",
        ]

        # Add user-specific paths if username is available
        if username:
            locations_to_check.extend([
                Path(rf"C:\Users\{username}\AppData\Local\Programs\Python\Python312\python.exe"),
                Path(rf"C:\Users\{username}\AppData\Local\Programs\Python\Python311\python.exe"),
                Path(rf"C:\Users\{username}\AppData\Local\Programs\Python\Python310\python.exe"),
            ])

        for candidate in locations_to_check:
            if candidate.exists():
                return str(candidate)

        # Last resort: scan Program Files and Python directories
        for base in [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Python",
            Path(r"C:\Python"),
        ]:
            if base.exists():
                for child in sorted(base.iterdir(), reverse=True):
                    candidate = child / "python.exe"
                    if candidate.exists():
                        return str(candidate)
        return None

    def _install_python(self) -> str:
        """Download and silently install Python, return path to python.exe."""
        url = self.PYTHON_URL.format(v=self.PYTHON_VERSION)
        self.log_message.emit(f"Downloading Python {self.PYTHON_VERSION}...")
        self.log_message.emit(f"  URL: {url}")

        tmp_dir = tempfile.mkdtemp(prefix="erp_cnc_python_")
        installer_path = os.path.join(tmp_dir, "python-installer.exe")

        try:
            urllib.request.urlretrieve(url, installer_path)
        except Exception as e:
            raise RuntimeError(
                f"Failed to download Python installer: {e}\n"
                "Please install Python 3.10+ manually from https://www.python.org"
            ) from e

        self.log_message.emit("Download complete. Installing Python silently...")

        result = subprocess.run(
            [
                installer_path,
                "/quiet",
                "InstallAllUsers=1",
                "PrependPath=1",
                "Include_pip=1",
                "Include_launcher=1",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            startupinfo=self._startupinfo(),
        )

        # Clean up installer
        try:
            os.remove(installer_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass

        if result.returncode != 0:
            raise RuntimeError(
                f"Python installer exited with code {result.returncode}.\n"
                f"{result.stderr or result.stdout}\n"
                "Please install Python 3.10+ manually from https://www.python.org"
            )

        self.log_message.emit("Python installed successfully. Waiting for system to update...")

        # Wait a moment for installation to complete fully
        import time
        time.sleep(3)

        # After fresh install, Python is typically in these locations
        # Check them directly instead of relying on PATH which may not be updated yet
        default_locations = [
            rf"C:\Program Files\Python{self.PYTHON_VERSION.replace('.', '')[:2]}\python.exe",
            rf"C:\Program Files\Python312\python.exe",
            rf"C:\Users\{os.environ.get('USERNAME', 'Administrator')}\AppData\Local\Programs\Python\Python312\python.exe",
            r"C:\Python312\python.exe",
        ]

        python_found = None
        for location in default_locations:
            if os.path.exists(location):
                python_found = location
                self.log_message.emit(f"Found Python at: {location}")
                break

        if python_found:
            return python_found

        # Fallback: Refresh PATH and try to find it
        self.log_message.emit("Python not found in default locations, checking PATH...")
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            ) as key:
                sys_path = winreg.QueryValueEx(key, "Path")[0]
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                try:
                    user_path = winreg.QueryValueEx(key, "Path")[0]
                except FileNotFoundError:
                    user_path = ""
            os.environ["PATH"] = sys_path + ";" + user_path
        except Exception as e:
            self.log_message.emit(f"Warning: Could not refresh PATH from registry: {e}")

        exe = self._find_python()
        if not exe:
            raise RuntimeError(
                "Python was installed but could not be found.\n"
                "Checked locations:\n" + "\n".join(default_locations) + "\n\n"
                "Please install Python 3.10+ manually from https://www.python.org"
            )
        return exe

    def _stop_existing_adapter(self, installation_log=None) -> None:
        """Stop existing adapter tasks/processes before replacing files."""
        commands = [
            ["schtasks", "/End", "/TN", "ERPCNCAdapter"],
            ["schtasks", "/End", "/TN", "ERPCNCAdapterWatchdog"],
            ["schtasks", "/End", "/TN", self.MANUAL_START_TASK_NAME],
            ["schtasks", "/End", "/TN", self.EDING_HANDOFF_TASK_NAME],
            ["schtasks", "/End", "/TN", self.STATUS_INDICATOR_TASK_NAME],
            ["taskkill", "/F", "/T", "/IM", "erp-cnc-adapter.exe"],
        ]
        for command in commands:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                startupinfo=self._startupinfo(),
            )
            if installation_log:
                installation_log.write(
                    f"Pre-copy stop command: {' '.join(command)} -> {result.returncode}\n"
                )
                if result.stdout:
                    installation_log.write(f"STDOUT: {result.stdout}\n")
                if result.stderr:
                    installation_log.write(f"STDERR: {result.stderr}\n")
        time.sleep(2)

    def _write_watchdog_hidden_launcher(self, watchdog_path: Path, installation_log=None) -> Path:
        launcher_path = watchdog_path.parent / "watchdog_hidden.vbs"

        def vbs_quote(value: str) -> str:
            return value.replace('"', '""')

        lines = [
            'Set shell = CreateObject("WScript.Shell")',
            f'shell.CurrentDirectory = "{vbs_quote(str(watchdog_path.parent))}"',
            f'shell.Run "cmd.exe /c ""{vbs_quote(str(watchdog_path))}""", 0, False',
        ]
        launcher_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if installation_log:
            installation_log.write(f"Hidden watchdog launcher: {launcher_path}\n")
        return launcher_path

    def _build_passwordless_watchdog_task_script(self, watchdog_path: Path) -> str:
        watchdog_path = Path(watchdog_path)
        launcher_path = self._write_watchdog_hidden_launcher(watchdog_path)
        return (
            "$ErrorActionPreference = 'Stop'\n"
            "Unregister-ScheduledTask -TaskName 'ERPCNCAdapterWatchdog' -Confirm:$false -ErrorAction SilentlyContinue\n"
            f"$watchdogLauncherPath = '{self._ps_quote(str(launcher_path))}'\n"
            f"$workDir = '{self._ps_quote(str(watchdog_path.parent))}'\n"
            f"$taskUser = '{self._ps_quote(self.task_username)}'\n"
            "$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('\"' + $watchdogLauncherPath + '\"') -WorkingDirectory $workDir\n"
            "$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) "
            "-RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650)\n"
            "$principal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Highest\n"
            "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries\n"
            "Register-ScheduledTask -TaskName 'ERPCNCAdapterWatchdog' "
            "-Action $action -Trigger $trigger -Principal $principal -Settings $settings "
            "-Force -ErrorAction Stop | Out-Null\n"
        )

    def _create_passwordless_watchdog_task(self, watchdog_path: Path) -> subprocess.CompletedProcess:
        ps_script = self._build_passwordless_watchdog_task_script(watchdog_path)
        ps_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", delete=False, encoding="utf-8",
        )
        ps_file.write(ps_script)
        ps_file.close()
        try:
            return subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_file.name],
                capture_output=True,
                text=True,
                startupinfo=self._startupinfo(),
            )
        finally:
            os.unlink(ps_file.name)

    def _create_watchdog_task(self, watchdog_path: Path, installation_log) -> subprocess.CompletedProcess:
        launcher_path = self._write_watchdog_hidden_launcher(Path(watchdog_path), installation_log)
        if self.task_username and not self.task_password:
            installation_log.write(f"Watchdog Run As: {self.task_username} (interactive, no stored password)\n")
            return self._create_passwordless_watchdog_task(watchdog_path)

        command = [
            "schtasks", "/Create",
            "/TN", "ERPCNCAdapterWatchdog",
            "/TR", f'"wscript.exe" "{launcher_path}"',
            "/SC", "MINUTE",
            "/MO", "2",
            "/RL", "HIGHEST",
            "/F",
        ]
        if self.task_username:
            command.extend(["/RU", self.task_username, "/RP", self.task_password])
            installation_log.write(f"Watchdog Run As: {self.task_username}\n")
        else:
            command.extend(["/RU", "SYSTEM"])
            installation_log.write("Watchdog Run As: SYSTEM\n")

        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            startupinfo=self._startupinfo(),
        )

    def _write_status_indicator_hidden_launcher(self, installation_log=None) -> Path:
        """Create a hidden launcher for the always-on operator status indicator."""
        scripts_dir = self.install_path / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = scripts_dir / "status_indicator.ps1"
        launcher_path = scripts_dir / "status_indicator_hidden.vbs"

        def vbs_quote(value: str) -> str:
            return value.replace('"', '""')

        launcher_path.write_text(
            "Set shell = CreateObject(\"WScript.Shell\")\n"
            f"shell.CurrentDirectory = \"{vbs_quote(str(scripts_dir))}\"\n"
            f"shell.Run \"powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"\"{vbs_quote(str(script_path))}\"\"\", 0, False\n",
            encoding="utf-8",
        )
        if installation_log:
            installation_log.write(f"Hidden status indicator launcher: {launcher_path}\n")
        return launcher_path

    def _build_status_indicator_task_script(self) -> str:
        launcher_path = self._write_status_indicator_hidden_launcher()
        if self.task_username:
            user_line = f"$taskUser = '{self._ps_quote(self.task_username)}'\n"
        else:
            user_line = "$taskUser = ('{0}\\{1}' -f $env:USERDOMAIN, $env:USERNAME)\n"
        return (
            "$ErrorActionPreference = 'Stop'\n"
            f"Unregister-ScheduledTask -TaskName '{self.STATUS_INDICATOR_TASK_NAME}' -Confirm:$false -ErrorAction SilentlyContinue\n"
            f"$launcherPath = '{self._ps_quote(str(launcher_path))}'\n"
            f"$workDir = '{self._ps_quote(str(launcher_path.parent))}'\n"
            + user_line +
            "$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('//B //Nologo \"' + $launcherPath + '\"') -WorkingDirectory $workDir\n"
            "$trigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser\n"
            "$principal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Highest\n"
            "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries\n"
            f"Register-ScheduledTask -TaskName '{self.STATUS_INDICATOR_TASK_NAME}' "
            "-Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force -ErrorAction Stop | Out-Null\n"
            f"Start-ScheduledTask -TaskName '{self.STATUS_INDICATOR_TASK_NAME}' -ErrorAction SilentlyContinue\n"
        )

    def _create_status_indicator_task(self, installation_log) -> bool:
        result = self._run_powershell_script(self._build_status_indicator_task_script())
        installation_log.write("Status indicator task creation:\n")
        installation_log.write(f"Exit code: {result.returncode}\n")
        if result.stdout:
            installation_log.write(f"STDOUT:\n{result.stdout}\n")
        if result.stderr:
            installation_log.write(f"STDERR:\n{result.stderr}\n")
        return result.returncode == 0

    def _write_hidden_launcher(self, exe_path: Path, installation_log=None) -> Path:
        """Create a wscript launcher so scheduled tasks do not show a console window."""
        launcher_path = self.install_path / "scripts" / "launch_adapter_hidden.vbs"
        launcher_path.parent.mkdir(parents=True, exist_ok=True)

        def vbs_quote(value: str) -> str:
            return value.replace("\"", "\"\"")

        launcher_path.write_text(
            "Set shell = CreateObject(\"WScript.Shell\")\n"
            f"shell.CurrentDirectory = \"{vbs_quote(str(self.install_path))}\"\n"
            f"shell.Run \"\"\"{vbs_quote(str(exe_path))}\"\"\", 0, False\n",
            encoding="utf-8",
        )
        if installation_log:
            installation_log.write(f"Hidden launcher: {launcher_path}\n")
        return launcher_path

    def _write_start_cnc_hidden_launcher(self, installation_log=None) -> Path:
        """Create a hidden launcher for the manual START-CNC shortcut."""
        restart_path = self.install_path / "scripts" / "restart.bat"
        log_path = self.install_path / "logs" / "start-cnc.log"
        scripts_dir = self.install_path / "scripts"
        task_launcher_path = scripts_dir / "run_start_cnc_hidden.vbs"
        shortcut_launcher_path = scripts_dir / "start_cnc_hidden.vbs"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        def vbs_quote(value: str) -> str:
            return value.replace("\"", "\"\"")

        task_launcher_path.write_text(
            "Set shell = CreateObject(\"WScript.Shell\")\n"
            f"shell.CurrentDirectory = \"{vbs_quote(str(restart_path.parent))}\"\n"
            f"exitCode = shell.Run(\"cmd.exe /c set ERPCNC_MANUAL_TASK=1&& \"\"{vbs_quote(str(restart_path))}\"\"\", 0, True)\n"
            "If exitCode <> 0 Then\n"
            f"  MsgBox \"START-CNC failed. Check: {vbs_quote(str(log_path))}\", 16, \"START-CNC\"\n"
            "End If\n",
            encoding="utf-8",
        )
        shortcut_launcher_path.write_text(
            "Set shell = CreateObject(\"WScript.Shell\")\n"
            f"exitCode = shell.Run(\"schtasks /Run /TN {self.MANUAL_START_TASK_NAME}\", 0, True)\n"
            "If exitCode <> 0 Then\n"
            f"  MsgBox \"Could not start START-CNC task. Reinstall or run as administrator once. Check: {vbs_quote(str(log_path))}\", 16, \"START-CNC\"\n"
            "End If\n",
            encoding="utf-8",
        )
        if installation_log:
            installation_log.write(f"Hidden START-CNC task launcher: {task_launcher_path}\n")
            installation_log.write(f"Hidden START-CNC shortcut launcher: {shortcut_launcher_path}\n")
        return shortcut_launcher_path

    def _write_eding_handoff_script(self, installation_log=None) -> Path:
        """Create an elevated helper script that lets Eding GUI own CncServer startup."""
        script_path = self.install_path / "scripts" / "start_eding_handoff.ps1"
        log_path = self.install_path / "logs" / "start-cnc.log"
        script_path.parent.mkdir(parents=True, exist_ok=True)

        script_path.write_text(
            "$ErrorActionPreference = 'SilentlyContinue'\n"
            f"$installDir = '{self._ps_quote(str(self.install_path))}'\n"
            "$configPath = Join-Path $installDir 'config.json'\n"
            f"$logPath = '{self._ps_quote(str(log_path))}'\n"
            "function Add-StartLog($message) {\n"
            "  $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'\n"
            "  Add-Content -Path $logPath -Value ('[{0}] {1}' -f $stamp, $message)\n"
            "}\n"
            "function Get-EdingGuiPath {\n"
            "  $dllPath = 'C:\\CNC4.03\\cncapi.dll'\n"
            "  if (Test-Path $configPath) {\n"
            "    try {\n"
            "      $config = Get-Content -Path $configPath -Raw | ConvertFrom-Json\n"
            "      if ($config.dll_path) { $dllPath = [string]$config.dll_path }\n"
            "    } catch {}\n"
            "  }\n"
            "  $cncDir = Split-Path -Parent $dllPath\n"
            "  $candidates = @(\n"
            "    (Join-Path $cncDir 'cnc4.03.exe'),\n"
            "    (Join-Path $cncDir 'cnc.exe')\n"
            "  )\n"
            "  foreach ($candidate in $candidates) {\n"
            "    if (Test-Path $candidate) { return $candidate }\n"
            "  }\n"
            "  return $null\n"
            "}\n"
            "Add-StartLog 'Starting Eding GUI through elevated START-CNC task...'\n"
            "$guiPath = Get-EdingGuiPath\n"
            "if (-not $guiPath) {\n"
            "  Add-StartLog 'ERROR: Could not find Eding GUI next to cncapi.dll.'\n"
            "  exit 1\n"
            "}\n"
            "$runningGui = Get-Process -Name 'cnc4.03','cnc' -ErrorAction SilentlyContinue\n"
            "if ($runningGui) {\n"
            "  Add-StartLog 'Eding GUI is already running.'\n"
            "  exit 0\n"
            "}\n"
            "Add-StartLog 'Stopping adapter-started CNC Server before Eding GUI launch...'\n"
            "$killOutput = taskkill /F /IM CncServer.exe 2>&1\n"
            "foreach ($line in $killOutput) { Add-StartLog $line }\n"
            "Start-Sleep -Seconds 2\n"
            "try {\n"
            "  Start-Process -FilePath $guiPath -WorkingDirectory (Split-Path -Parent $guiPath) -ErrorAction Stop\n"
            "  Add-StartLog ('Eding GUI started: {0}' -f $guiPath)\n"
            "  exit 0\n"
            "} catch {\n"
            "  Add-StartLog ('ERROR: Failed to start Eding GUI: {0}' -f $_.Exception.Message)\n"
            "  exit 1\n"
            "}\n",
            encoding="utf-8",
        )
        if installation_log:
            installation_log.write(f"Eding GUI handoff script: {script_path}\n")
        return script_path

    def _write_start_cnc_feedback_script(self, installation_log=None) -> Path:
        """Create a visible operator progress launcher for START-CNC."""
        script_path = self.install_path / "scripts" / "start_cnc_feedback.ps1"
        log_path = self.install_path / "logs" / "start-cnc.log"
        adapter_log_path = self.install_path / "logs" / "adapter.log"
        script_path.parent.mkdir(parents=True, exist_ok=True)

        script_path.write_text(
            "$ErrorActionPreference = 'SilentlyContinue'\n"
            "$Host.UI.RawUI.WindowTitle = 'START-CNC'\n"
            f"$taskName = '{self.MANUAL_START_TASK_NAME}'\n"
            f"$guiTaskName = '{self.EDING_HANDOFF_TASK_NAME}'\n"
            f"$installDir = '{self._ps_quote(str(self.install_path))}'\n"
            "$configPath = Join-Path $installDir 'config.json'\n"
            f"$logPath = '{self._ps_quote(str(log_path))}'\n"
            f"$adapterLogPath = '{self._ps_quote(str(adapter_log_path))}'\n"
            "$healthUrl = 'http://127.0.0.1:8002/api/health'\n"
            "$timeoutSeconds = 90\n"
            "$maxAttempts = 3\n"
            "$lastStartLogLine = 0\n"
            "$lastAdapterLogLine = 0\n"
            "function Show-NewLines($path, [ref]$lastLine, $prefix, $patterns = $null) {\n"
            "  if (-not (Test-Path $path)) { return }\n"
            "  $lines = Get-Content -Path $path -ErrorAction SilentlyContinue\n"
            "  if ($null -eq $lines) { return }\n"
            "  if ($lines -is [string]) { $lines = @($lines) }\n"
            "  if ($lines.Count -lt $lastLine.Value) { $lastLine.Value = 0 }\n"
            "  for ($lineNumber = $lastLine.Value; $lineNumber -lt $lines.Count; $lineNumber++) {\n"
            "    $line = [string]$lines[$lineNumber]\n"
            "    if ($patterns) {\n"
            "      $matched = $false\n"
            "      foreach ($pattern in $patterns) {\n"
            "        if ($line -match $pattern) { $matched = $true; break }\n"
            "      }\n"
            "      if (-not $matched) { continue }\n"
            "    }\n"
            "    Write-Host ('  {0} {1}' -f $prefix, $line)\n"
            "  }\n"
            "  $lastLine.Value = $lines.Count\n"
            "}\n"
            "function Get-StartCncConfig {\n"
            "  if (-not (Test-Path $configPath)) { return $null }\n"
            "  try { return Get-Content -Path $configPath -Raw | ConvertFrom-Json } catch { return $null }\n"
            "}\n"
            "function Test-AutoStartEdingGui {\n"
            "  $config = Get-StartCncConfig\n"
            "  if ($null -eq $config) { return $false }\n"
            "  return [bool]$config.auto_start_eding_gui\n"
            "}\n"
            "function Get-EdingGuiPath {\n"
            "  $config = Get-StartCncConfig\n"
            "  $dllPath = 'C:\\CNC4.03\\cncapi.dll'\n"
            "  if ($null -ne $config -and $config.dll_path) { $dllPath = [string]$config.dll_path }\n"
            "  $cncDir = Split-Path -Parent $dllPath\n"
            "  $candidates = @(\n"
            "    (Join-Path $cncDir 'cnc4.03.exe'),\n"
            "    (Join-Path $cncDir 'cnc.exe')\n"
            "  )\n"
            "  foreach ($candidate in $candidates) {\n"
            "    if (Test-Path $candidate) { return $candidate }\n"
            "  }\n"
            "  return $null\n"
            "}\n"
            "function Start-EdingGuiAfterReady {\n"
            "  if (-not (Test-AutoStartEdingGui)) { return $true }\n"
            "  $runningGui = Get-Process -Name 'cnc4.03','cnc' -ErrorAction SilentlyContinue\n"
            "  if ($runningGui) {\n"
            "    Write-Host 'Eding GUI is already running.' -ForegroundColor Green\n"
            "    return $true\n"
            "  }\n"
            "  if (-not (Get-EdingGuiPath)) {\n"
            "    Write-Host 'Could not find Eding GUI next to cncapi.dll.' -ForegroundColor Red\n"
            "    return $false\n"
            "  }\n"
            "  Write-Host 'Starting Eding GUI through elevated START-CNC task...'\n"
            "  $taskOutput = schtasks /Run /TN $guiTaskName 2>&1\n"
            "  if ($LASTEXITCODE -ne 0) {\n"
            "    Write-Host 'Could not start elevated Eding GUI handoff task.' -ForegroundColor Red\n"
            "    Write-Host $taskOutput\n"
            "    return $false\n"
            "  }\n"
            "  Start-Sleep -Seconds 12\n"
            "  Show-NewLines $logPath ([ref]$lastStartLogLine) 'START'\n"
            "  return $true\n"
            "}\n"
            "function Wait-AdapterReadyAfterGui {\n"
            "  if (-not (Test-AutoStartEdingGui)) { return $true }\n"
            "  Write-Host 'Waiting for adapter to reconnect to Eding GUI server...'\n"
            "  $start = Get-Date\n"
            "  $stableReadyChecks = 0\n"
            "  while (((Get-Date) - $start).TotalSeconds -lt 90) {\n"
            "    Show-NewLines $logPath ([ref]$lastStartLogLine) 'START'\n"
            "    Show-NewLines $adapterLogPath ([ref]$lastAdapterLogLine) 'ADAPTER' $adapterPatterns\n"
            "    try {\n"
            "      $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2\n"
            "      $runningGui = Get-Process -Name 'cnc4.03','cnc' -ErrorAction SilentlyContinue\n"
            "      if ($health.cnc.connected -eq $true -and $runningGui) {\n"
            "        $stableReadyChecks++\n"
            "        if ($stableReadyChecks -ge 3) { return $true }\n"
            "      } else {\n"
            "        $stableReadyChecks = 0\n"
            "      }\n"
            "    } catch {}\n"
            "    Start-Sleep -Seconds 2\n"
            "  }\n"
            "  return $false\n"
            "}\n"
            "$adapterPatterns = @(\n"
            "  'Starting ERP-CNC Adapter',\n"
            "  'Starting CNC Server',\n"
            "  'CNC Server started',\n"
            "  'Auto-started CncServer',\n"
            "  'Eding GUI auto-start deferred',\n"
            "  'Started Eding GUI',\n"
            "  'Starting Eding GUI through elevated START-CNC task',\n"
            "  'Stopping adapter-started CNC Server before Eding GUI launch',\n"
            "  'Attempting CNC connection',\n"
            "  'CNC connection established',\n"
            "  'machine is ready',\n"
            "  'ERROR',\n"
            "  'WARNING',\n"
            "  'Last error',\n"
            "  'failed',\n"
            "  'timed out'\n"
            ")\n"
            "Write-Host ''\n"
            "Write-Host 'START-CNC is loading...' -ForegroundColor Cyan\n"
            "Write-Host ''\n"
            "$spinner = @('|','/','-','\\')\n"
            "$i = 0\n"
            "for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {\n"
            "  Write-Host (\"Starting manual START-CNC task... attempt {0} of {1}\" -f $attempt, $maxAttempts)\n"
            "  $taskOutput = schtasks /Run /TN $taskName 2>&1\n"
            "  if ($LASTEXITCODE -ne 0) {\n"
            "    Write-Host 'START-CNC could not start.' -ForegroundColor Red\n"
            "    Write-Host $taskOutput\n"
            "    Write-Host ''\n"
            "    Write-Host \"Check log: $logPath\"\n"
            "    Read-Host 'Press Enter to close'\n"
            "    exit 1\n"
            "  }\n"
            "  $start = Get-Date\n"
            "  while (((Get-Date) - $start).TotalSeconds -lt $timeoutSeconds) {\n"
            "    Show-NewLines $logPath ([ref]$lastStartLogLine) 'START'\n"
            "    Show-NewLines $adapterLogPath ([ref]$lastAdapterLogLine) 'ADAPTER' $adapterPatterns\n"
            "    $elapsed = [int]((Get-Date) - $start).TotalSeconds\n"
            "    $percent = [Math]::Min(100, [int](($elapsed / $timeoutSeconds) * 100))\n"
            "    $filled = [Math]::Min(20, [int]($percent / 5))\n"
            "    $bar = ('#' * $filled).PadRight(20, '.')\n"
            "    Write-Host -NoNewline (\"`r{0} Starting adapter [{1}] {2}%\" -f $spinner[$i % $spinner.Count], $bar, $percent)\n"
            "    $i++\n"
            "    try {\n"
            "      $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2\n"
            "      if ($health.cnc.connected -eq $true) {\n"
            "        Write-Host ''\n"
            "        Show-NewLines $logPath ([ref]$lastStartLogLine) 'START'\n"
            "        Show-NewLines $adapterLogPath ([ref]$lastAdapterLogLine) 'ADAPTER' $adapterPatterns\n"
            "        if (-not (Start-EdingGuiAfterReady)) {\n"
            "          Write-Host \"Check config: $configPath\"\n"
            "          Read-Host 'Press Enter to close'\n"
            "          exit 1\n"
            "        }\n"
            "        if (-not (Wait-AdapterReadyAfterGui)) {\n"
            "          Write-Host 'Adapter did not reconnect after Eding GUI launch.' -ForegroundColor Red\n"
            "          Write-Host \"Check log: $adapterLogPath\"\n"
            "          Read-Host 'Press Enter to close'\n"
            "          exit 1\n"
            "        }\n"
            "        Write-Host 'START-CNC is ready.' -ForegroundColor Green\n"
            "        Start-Sleep -Seconds 2\n"
            "        exit 0\n"
            "      }\n"
            "    } catch {}\n"
            "    Start-Sleep -Seconds 2\n"
            "  }\n"
            "  Write-Host ''\n"
            "  Show-NewLines $logPath ([ref]$lastStartLogLine) 'START'\n"
            "  Show-NewLines $adapterLogPath ([ref]$lastAdapterLogLine) 'ADAPTER' $adapterPatterns\n"
            "  if ($attempt -lt $maxAttempts) {\n"
            "    Write-Host 'START-CNC is not ready yet; retrying the full start sequence...' -ForegroundColor Yellow\n"
            "    Start-Sleep -Seconds 5\n"
            "  }\n"
            "}\n"
            "Write-Host ''\n"
            "Write-Host 'START-CNC did not become ready after all retry attempts.' -ForegroundColor Red\n"
            "Write-Host \"Check log: $logPath\"\n"
            "Read-Host 'Press Enter to close'\n"
            "exit 1\n",
            encoding="utf-8",
        )
        if installation_log:
            installation_log.write(f"START-CNC feedback script: {script_path}\n")
        return script_path

    def _build_manual_start_task_script(self) -> str:
        launcher_path = self.install_path / "scripts" / "run_start_cnc_hidden.vbs"
        script = (
            "$ErrorActionPreference = 'Stop'\n"
            f"Unregister-ScheduledTask -TaskName '{self.MANUAL_START_TASK_NAME}' -Confirm:$false -ErrorAction SilentlyContinue\n"
            f"$launcherPath = '{self._ps_quote(str(launcher_path))}'\n"
            f"$workDir = '{self._ps_quote(str(launcher_path.parent))}'\n"
            "$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('\"' + $launcherPath + '\"') -WorkingDirectory $workDir\n"
            "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries\n"
        )
        if self.task_username:
            script += (
                f"$taskUser = '{self._ps_quote(self.task_username)}'\n"
                "$principal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Highest\n"
            )
        else:
            script += "$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest\n"
        script += (
            f"Register-ScheduledTask -TaskName '{self.MANUAL_START_TASK_NAME}' "
            "-Action $action -Principal $principal -Settings $settings -Force | Out-Null\n"
        )
        return script

    def _create_manual_start_task(self, installation_log) -> bool:
        ps_script = self._build_manual_start_task_script()
        ps_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", delete=False, encoding="utf-8",
        )
        ps_file.write(ps_script)
        ps_file.close()
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_file.name],
                capture_output=True,
                text=True,
                startupinfo=self._startupinfo(),
            )
        finally:
            os.unlink(ps_file.name)

        installation_log.write("Manual START-CNC task creation:\n")
        installation_log.write(f"Exit code: {result.returncode}\n")
        if result.stdout:
            installation_log.write(f"STDOUT:\n{result.stdout}\n")
        if result.stderr:
            installation_log.write(f"STDERR:\n{result.stderr}\n")
        return result.returncode == 0 and not result.stderr

    def _build_eding_handoff_task_script(self) -> str:
        script_path = self.install_path / "scripts" / "start_eding_handoff.ps1"
        script = (
            "$ErrorActionPreference = 'Stop'\n"
            f"Unregister-ScheduledTask -TaskName '{self.EDING_HANDOFF_TASK_NAME}' -Confirm:$false -ErrorAction SilentlyContinue\n"
            f"$scriptPath = '{self._ps_quote(str(script_path))}'\n"
            f"$workDir = '{self._ps_quote(str(script_path.parent))}'\n"
            "$action = New-ScheduledTaskAction -Execute 'powershell.exe' "
            "-Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"' + $scriptPath + '\"') "
            "-WorkingDirectory $workDir\n"
            "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries\n"
        )
        if self.task_username:
            script += (
                f"$taskUser = '{self._ps_quote(self.task_username)}'\n"
                "$principal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Highest\n"
            )
        else:
            script += "$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest\n"
        script += (
            f"Register-ScheduledTask -TaskName '{self.EDING_HANDOFF_TASK_NAME}' "
            "-Action $action -Principal $principal -Settings $settings -Force | Out-Null\n"
        )
        return script

    def _create_eding_handoff_task(self, installation_log) -> bool:
        ps_script = self._build_eding_handoff_task_script()
        ps_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", delete=False, encoding="utf-8",
        )
        ps_file.write(ps_script)
        ps_file.close()
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_file.name],
                capture_output=True,
                text=True,
                startupinfo=self._startupinfo(),
            )
        finally:
            os.unlink(ps_file.name)

        installation_log.write("Eding GUI handoff task creation:\n")
        installation_log.write(f"Exit code: {result.returncode}\n")
        if result.stdout:
            installation_log.write(f"STDOUT:\n{result.stdout}\n")
        if result.stderr:
            installation_log.write(f"STDERR:\n{result.stderr}\n")
        return result.returncode == 0 and not result.stderr

    def _build_start_shortcut_script(self) -> str:
        launcher_path = self.install_path / "scripts" / "start_cnc_hidden.vbs"
        icon_path = self.install_path / "resources" / "logo.ico"
        return (
            "$ErrorActionPreference = 'Stop'\n"
            "$desktopCandidates = @()\n"
            "if ($env:PUBLIC) { $desktopCandidates += (Join-Path $env:PUBLIC 'Desktop') }\n"
            "if ($env:USERPROFILE) { $desktopCandidates += (Join-Path $env:USERPROFILE 'Desktop') }\n"
            "$desktop = $desktopCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1\n"
            "if (-not $desktop) { throw 'Could not find a desktop folder for shortcut creation.' }\n"
            "$shortcutPath = Join-Path $desktop 'START-CNC.lnk'\n"
            "$shell = New-Object -ComObject WScript.Shell\n"
            "$shortcut = $shell.CreateShortcut($shortcutPath)\n"
            "$shortcut.TargetPath = 'wscript.exe'\n"
            f"$shortcut.Arguments = '//B //Nologo \"{self._ps_quote(str(launcher_path))}\"'\n"
            f"$shortcut.WorkingDirectory = '{self._ps_quote(str(launcher_path.parent))}'\n"
            f"$shortcut.IconLocation = '{self._ps_quote(str(icon_path))}'\n"
            "$shortcut.Description = 'Start CNC adapter runtime'\n"
            "$shortcut.Save()\n"
            "Write-Output $shortcutPath\n"
        )

    def _create_start_shortcut(self, installation_log) -> bool:
        """Create a desktop START-CNC shortcut to the restart script."""
        ps_script = self._build_start_shortcut_script()
        ps_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", delete=False, encoding="utf-8",
        )
        ps_file.write(ps_script)
        ps_file.close()
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_file.name],
                capture_output=True,
                text=True,
                startupinfo=self._startupinfo(),
            )
        finally:
            os.unlink(ps_file.name)

        installation_log.write("Desktop shortcut creation:\n")
        installation_log.write(f"Exit code: {result.returncode}\n")
        if result.stdout:
            installation_log.write(f"STDOUT:\n{result.stdout}\n")
        if result.stderr:
            installation_log.write(f"STDERR:\n{result.stderr}\n")
        return result.returncode == 0


    def _build_operator_setup_script(self) -> str:
        def step(name: str, script: str) -> str:
            safe_name = self._ps_quote(name)
            body = self._combined_step_body(script)
            return (
                f"$stepWatch = [Diagnostics.Stopwatch]::StartNew()\n"
                f"try {{\n"
                f"{body}"
                f"  $stepWatch.Stop()\n"
                f"  Write-Output (\"ERP_STEP|{safe_name}|0|{{0}}|\" -f $stepWatch.ElapsedMilliseconds)\n"
                f"}} catch {{\n"
                f"  $stepWatch.Stop()\n"
                f"  $msg = $_.Exception.Message -replace '[\\r\\n]+', ' ' -replace '\\|', '/'\n"
                f"  Write-Output (\"ERP_STEP|{safe_name}|1|{{0}}|{{1}}\" -f $stepWatch.ElapsedMilliseconds, $msg)\n"
                f"}}\n"
            )

        return (
            "$ErrorActionPreference = 'Continue'\n"
            + step("Manual START-CNC task", self._build_manual_start_task_script())
            + step("Eding GUI handoff task", self._build_eding_handoff_task_script())
            + step("Status indicator task", self._build_status_indicator_task_script())
            + step("START-CNC desktop shortcut", self._build_start_shortcut_script())
        )

    @staticmethod
    def _parse_operator_setup_result(result: subprocess.CompletedProcess) -> dict[str, dict[str, str]]:
        steps = {}
        for line in (result.stdout or "").splitlines():
            if not line.startswith("ERP_STEP|"):
                continue
            parts = line.split("|", 4)
            if len(parts) != 5:
                continue
            _, name, status, elapsed_ms, message = parts
            steps[name] = {
                "ok": status == "0",
                "elapsed_ms": elapsed_ms,
                "message": message,
            }
        return steps

    def _create_operator_tasks_and_shortcut(self, installation_log) -> dict[str, bool] | None:
        result = self._run_powershell_script(self._build_operator_setup_script())
        installation_log.write("Operator task/shortcut combined setup:\n")
        installation_log.write(f"Exit code: {result.returncode}\n")
        if result.stdout:
            installation_log.write(f"STDOUT:\n{result.stdout}\n")
        if result.stderr:
            installation_log.write(f"STDERR:\n{result.stderr}\n")

        steps = self._parse_operator_setup_result(result)
        if not steps:
            installation_log.write("No combined setup step markers found; falling back to individual setup.\n")
            installation_log.flush()
            return None

        names = ("Manual START-CNC task", "Eding GUI handoff task", "Status indicator task", "START-CNC desktop shortcut")
        for name in names:
            step = steps.get(name, {"ok": False, "elapsed_ms": "?", "message": "missing step marker"})
            status = "OK" if step["ok"] else "FAILED"
            detail = f": {step['message']}" if step["message"] else ""
            installation_log.write(f"{name}: {status} in {step['elapsed_ms']}ms{detail}\n")
        installation_log.flush()
        return {name: bool(steps.get(name, {}).get("ok")) for name in names}

    def _build_interactive_logon_task_script(self, launcher_path: Path) -> str:
        def ps_quote(value: str) -> str:
            return value.replace("'", "''")

        startup_delay = f"PT{self.DEFAULT_STARTUP_DELAY_SECONDS}S"
        disable_task = ""
        if not self.auto_start_adapter_on_logon:
            disable_task = "Disable-ScheduledTask -TaskName 'ERPCNCAdapter' | Out-Null\n"
        return (
            "$ErrorActionPreference = 'Stop'\n"
            f"$action = New-ScheduledTaskAction "
            f"-Execute 'wscript.exe' "
            f"-Argument '\"{ps_quote(str(launcher_path))}\"' "
            f"-WorkingDirectory '{ps_quote(str(self.install_path))}'\n"
            f"$trigger = New-ScheduledTaskTrigger -AtLogOn -User '{ps_quote(self.task_username)}'\n"
            f"$trigger.Delay = '{startup_delay}'\n"
            f"$principal = New-ScheduledTaskPrincipal -UserId '{ps_quote(self.task_username)}' "
            f"-LogonType Interactive -RunLevel Highest\n"
            f"$settings = New-ScheduledTaskSettingsSet "
            f"-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
            f"-RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)\n"
            f"Register-ScheduledTask -TaskName 'ERPCNCAdapter' "
            f"-Action $action -Trigger $trigger -Principal $principal "
            f"-Settings $settings -Force -ErrorAction Stop | Out-Null\n"
            f"{disable_task}"
        )


    def _create_interactive_logon_task(self, launcher_path: Path, installation_log) -> bool:
        """Fallback for passwordless local users: run when that user logs on."""
        ps_script = self._build_interactive_logon_task_script(launcher_path)
        ps_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", delete=False, encoding="utf-8",
        )
        ps_file.write(ps_script)
        ps_file.close()
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", ps_file.name],
                capture_output=True, text=True,
                startupinfo=self._startupinfo(),
            )
        finally:
            os.unlink(ps_file.name)

        installation_log.write("Interactive logon fallback task registration:\n")
        installation_log.write(f"Exit code: {result.returncode}\n")
        if result.stdout:
            installation_log.write(f"STDOUT:\n{result.stdout}\n")
        if result.stderr:
            installation_log.write(f"STDERR:\n{result.stderr}\n")
        return self._scheduled_task_creation_error(result) == ""


    def _start_adapter_task(self, installation_log) -> bool:
        result = subprocess.run(
            ["schtasks", "/Run", "/TN", "ERPCNCAdapter"],
            capture_output=True,
            text=True,
            startupinfo=self._startupinfo(),
        )
        installation_log.write(f"schtasks /Run exit code: {result.returncode}\n")
        if result.stdout:
            installation_log.write(f"STDOUT:\n{result.stdout}\n")
        if result.stderr:
            installation_log.write(f"STDERR:\n{result.stderr}\n")
        return result.returncode == 0

    def _write_task_credential_diagnostics(self, installation_log) -> None:
        """Log non-secret credential diagnostics for scheduled task failures."""
        password = self.task_password or ""
        installation_log.write("Credential diagnostics:\n")
        installation_log.write(f"  username: {self.task_username or 'SYSTEM'}\n")
        installation_log.write(f"  username_length: {len(self.task_username)}\n")
        installation_log.write(f"  password_length: {len(password)}\n")
        installation_log.write(f"  password_blank: {not bool(password)}\n")
        installation_log.write(f"  password_has_leading_or_trailing_space: {password != password.strip()}\n")
        installation_log.write(f"  password_contains_non_ascii: {any(ord(ch) > 127 for ch in password)}\n")

    @staticmethod
    def _scheduled_task_creation_error(result) -> str:
        task_error = (result.stderr or "").strip()
        if result.returncode != 0 or task_error:
            return task_error or result.stdout or "Unknown scheduled task registration error"
        return ""

    # Main work ────────────────────────────────────────────────────────────
    def run(self):  # noqa: C901 — sequential installer steps
        installation_log = None
        try:
            # NO PYTHON NEEDED! Use Windows sc.exe command directly
            self.step_changed.emit("Preparing installation...")
            self.log_message.emit("Installing ERP-CNC Adapter (Python-free installation)")
            self.progress_value.emit(5)

            # 1 — Extract files ................................................
            self.step_changed.emit("Extracting files...")
            self.progress_value.emit(10)
            self.log_message.emit(f"Installing to: {self.install_path}")
            self.log_message.emit("Stopping existing adapter before replacing files...")
            self._stop_existing_adapter()

            self.install_path.mkdir(parents=True, exist_ok=True)
            self._extract_files()
            self.log_message.emit("\u2713 Files extracted successfully")

            # Create installation log file
            log_dir = self.install_path / "logs"
            log_dir.mkdir(exist_ok=True)
            installation_log_path = log_dir / "installation.log"
            installation_log = open(installation_log_path, "w", encoding="utf-8")
            installation_log.write(f"ERP-CNC Adapter Installation Log\n")
            installation_log.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            installation_log.write(f"Installation Path: {self.install_path}\n")
            installation_log.write("=" * 70 + "\n\n")
            installation_log.flush()

            self.log_message.emit(f"\u2713 Installation log: {installation_log_path}")

            # Write machine_number to config.json
            config_path = self.install_path / "config.json"
            config_data = {}
            if config_path.exists():
                try:
                    config_data = json.loads(config_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    config_data = {}
            config_data["machine_number"] = self.machine_number
            config_data["task_username"] = self.task_username
            config_data["auto_start_adapter_on_logon"] = self.auto_start_adapter_on_logon
            config_data.setdefault("adapter_startup_delay_seconds", self.DEFAULT_STARTUP_DELAY_SECONDS)
            config_path.write_text(
                json.dumps(config_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            self.log_message.emit(f"\u2713 Machine ID set to: {self.machine_number}")
            installation_log.write(f"Machine ID: {self.machine_number}\n")
            if self.task_username:
                self.log_message.emit(f"Task account: {self.task_username}")
                installation_log.write(f"Task account: {self.task_username}\n")
            else:
                self.log_message.emit("Task account: SYSTEM")
                installation_log.write("Task account: SYSTEM\n")
            installation_log.write(
                f"Adapter startup delay: {config_data['adapter_startup_delay_seconds']}s\n"
            )
            installation_log.write(
                f"Adapter auto-start on logon: {self.auto_start_adapter_on_logon}\n"
            )
            installation_log.flush()

            setup_start = time.perf_counter()
            self.log_message.emit("Preparing START-CNC launch scripts...")
            self._write_start_cnc_hidden_launcher(installation_log)
            self._write_eding_handoff_script(installation_log)
            self._write_start_cnc_feedback_script(installation_log)
            splash_path = self.install_path / "scripts" / "start_cnc_splash.ps1"
            if splash_path.exists():
                installation_log.write(f"START-CNC splash script: {splash_path}\n")
            self._log_timed(installation_log, "START-CNC script generation", setup_start)

            self.log_message.emit("Creating START-CNC tasks and shortcut...")
            setup_start = time.perf_counter()
            operator_setup = self._create_operator_tasks_and_shortcut(installation_log)
            if operator_setup is None:
                self.log_message.emit("Combined task setup did not report results; using fallback setup...")
                operator_setup = {
                    "Manual START-CNC task": self._create_manual_start_task(installation_log),
                    "Eding GUI handoff task": self._create_eding_handoff_task(installation_log),
                    "Status indicator task": self._create_status_indicator_task(installation_log),
                    "START-CNC desktop shortcut": self._create_start_shortcut(installation_log),
                }
            self._log_timed(installation_log, "START-CNC task/shortcut setup", setup_start)

            if operator_setup.get("Manual START-CNC task"):
                self.log_message.emit("\u2713 Manual start task created: START-CNC")
                installation_log.write("\u2713 Manual start task created: START-CNC\n")
            else:
                self.log_message.emit("\u26a0 Manual start task creation failed (shortcut may require elevation)")
                installation_log.write("\u26a0 Manual start task creation failed (shortcut may require elevation)\n")
            if operator_setup.get("Eding GUI handoff task"):
                self.log_message.emit("\u2713 Eding GUI handoff task created")
                installation_log.write("\u2713 Eding GUI handoff task created\n")
            else:
                self.log_message.emit("\u26a0 Eding GUI handoff task creation failed")
                installation_log.write("\u26a0 Eding GUI handoff task creation failed\n")
            if operator_setup.get("Status indicator task"):
                self.log_message.emit("Status indicator task created")
                installation_log.write("Status indicator task created\n")
            else:
                self.log_message.emit("Status indicator task creation failed (non-critical)")
                installation_log.write("Status indicator task creation failed (non-critical)\n")
            if operator_setup.get("START-CNC desktop shortcut"):
                self.log_message.emit("\u2713 Desktop shortcut created: START-CNC")
                installation_log.write("\u2713 Desktop shortcut created: START-CNC\n")
            else:
                self.log_message.emit("\u26a0 Desktop shortcut creation failed (non-critical)")
                installation_log.write("\u26a0 Desktop shortcut creation failed (non-critical)\n")
            installation_log.flush()

            self.progress_value.emit(40)

            # 2 — Install as Startup Task (not Windows Service) ...................
            self.step_changed.emit("Configuring auto-start...")
            self.log_message.emit("Configuring application to start on boot...")
            installation_log.write("STEP 1: Auto-Start Configuration\n")
            installation_log.write("-" * 70 + "\n")
            self.progress_value.emit(45)

            exe_path = self.install_path / "erp-cnc-adapter.exe"
            if not exe_path.exists():
                raise RuntimeError(f"EXE not found at: {exe_path}")

            installation_log.write(f"EXE Path: {exe_path}\n")

            # Remove old service if exists
            result = subprocess.run(
                ["sc", "query", "ERPCNCAdapter"],
                capture_output=True, startupinfo=self._startupinfo(),
            )
            if result.returncode == 0:
                self.log_message.emit("Removing old service installation...")
                installation_log.write("Found old service, removing...\n")

                subprocess.run(
                    ["taskkill", "/F", "/IM", "erp-cnc-adapter.exe"],
                    capture_output=True, startupinfo=self._startupinfo(),
                )
                time.sleep(2)

                subprocess.run(
                    ["sc", "delete", "ERPCNCAdapter"],
                    capture_output=True, startupinfo=self._startupinfo(),
                )
                time.sleep(2)
                installation_log.write("Old service removed\n")

            # Create scheduled task to run at startup (runs as console app, not service)
            self.log_message.emit(f"Creating startup task for: {exe_path}")
            installation_log.write(f"\nCreating Startup Task...\n")
            installation_log.write(f"Task Name: ERPCNCAdapter\n")
            installation_log.write(f"Executable: {exe_path}\n")

            # Delete existing task if any
            subprocess.run(
                ["schtasks", "/Delete", "/TN", "ERPCNCAdapter", "/F"],
                capture_output=True, startupinfo=self._startupinfo(),
            )

            # Create task that runs at system startup (with working directory)
            # Write PowerShell script to temp file to avoid command-line quoting
            # issues with paths containing spaces
            def ps_quote(value: str) -> str:
                return value.replace("'", "''")

            launcher_path = self._write_hidden_launcher(exe_path, installation_log)
            ps_script = (
                "$ErrorActionPreference = 'Stop'\n"
                f"$action = New-ScheduledTaskAction "
                f"-Execute 'wscript.exe' "
                f"-Argument '\"{ps_quote(str(launcher_path))}\"' "
                f"-WorkingDirectory '{ps_quote(str(self.install_path))}'\n"
                f"$startupDelay = 'PT{int(config_data['adapter_startup_delay_seconds'])}S'\n"
                f"$autoStartAdapter = ${str(self.auto_start_adapter_on_logon).lower()}\n"
                f"$settings = New-ScheduledTaskSettingsSet "
                f"-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
                f"-RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)\n"
            )
            if self.task_username:
                task_start_mode = "logon"
                ps_script += (
                    f"$taskUser = '{ps_quote(self.task_username)}'\n"
                    f"$trigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser\n"
                    f"$trigger.Delay = $startupDelay\n"
                    f"$principal = New-ScheduledTaskPrincipal -UserId $taskUser "
                    f"-LogonType Interactive -RunLevel Highest\n"
                    f"Register-ScheduledTask -TaskName 'ERPCNCAdapter' "
                    f"-Action $action -Trigger $trigger -Principal $principal "
                    f"-Settings $settings -Force -ErrorAction Stop | Out-Null\n"
                    f"if (-not $autoStartAdapter) {{ Disable-ScheduledTask -TaskName 'ERPCNCAdapter' | Out-Null }}\n"
                )
            else:
                task_start_mode = "boot"
                ps_script += (
                    f"$trigger = New-ScheduledTaskTrigger -AtStartup\n"
                    f"$trigger.Delay = $startupDelay\n"
                    f"$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' "
                    f"-LogonType ServiceAccount -RunLevel Highest\n"
                    f"Register-ScheduledTask -TaskName 'ERPCNCAdapter' "
                    f"-Action $action -Trigger $trigger -Principal $principal "
                    f"-Settings $settings -Force -ErrorAction Stop | Out-Null\n"
                    f"if (-not $autoStartAdapter) {{ Disable-ScheduledTask -TaskName 'ERPCNCAdapter' | Out-Null }}\n"
                )
            ps_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".ps1", delete=False, encoding="utf-8",
            )
            ps_file.write(ps_script)
            ps_file.close()
            try:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                     "-File", ps_file.name],
                    capture_output=True, text=True,
                    startupinfo=self._startupinfo(),
                )
            finally:
                os.unlink(ps_file.name)

            installation_log.write(f"Exit code: {result.returncode}\n")
            installation_log.write(f"STDOUT:\n{result.stdout}\n")
            if result.stderr:
                installation_log.write(f"STDERR:\n{result.stderr}\n")
            installation_log.flush()

            msg = self._scheduled_task_creation_error(result)
            if msg:
                installation_log.write("ERROR: Task creation failed!\n")
                self._write_task_credential_diagnostics(installation_log)
                if self.task_username:
                    installation_log.write(
                        "Trying interactive logon fallback task without storing a password.\n"
                    )
                    self.log_message.emit(
                        "Startup task with password failed; trying logon-only task..."
                    )
                    if self._create_interactive_logon_task(launcher_path, installation_log):
                        task_start_mode = "logon"
                        installation_log.write(
                            "Interactive logon task created; app starts when that user logs on.\n"
                        )
                        self.log_message.emit(
                            "\u2713 Logon-only startup task created for selected user"
                        )
                    else:
                        installation_log.flush()
                        raise RuntimeError(f"Startup task creation failed: {msg}\n\nCheck installation.log for details")
                else:
                    installation_log.flush()
                    raise RuntimeError(f"Startup task creation failed: {msg}\n\nCheck installation.log for details")
            verify_result = subprocess.run(
                ["schtasks", "/Query", "/TN", "ERPCNCAdapter"],
                capture_output=True, text=True,
                startupinfo=self._startupinfo(),
            )
            installation_log.write(f"Task verification exit code: {verify_result.returncode}\n")
            if verify_result.stderr:
                installation_log.write(f"Task verification STDERR:\n{verify_result.stderr}\n")
            if verify_result.returncode != 0:
                msg = verify_result.stderr or verify_result.stdout
                installation_log.write("ERROR: Task was not created.\n")
                installation_log.flush()
                raise RuntimeError(f"Startup task was not created: {msg}\n\nCheck installation.log for details")

            self.log_message.emit("\u2713 Startup task created successfully")
            installation_log.write("\u2713 Startup task created successfully\n")
            if task_start_mode == "logon":
                installation_log.write(f"Application will start when {self.task_username} logs on\n")
            else:
                installation_log.write("Application will start automatically on boot\n")
            installation_log.flush()
            self.progress_value.emit(50)

            # Create watchdog task (restarts adapter if it crashes)
            watchdog_path = self.install_path / "scripts" / "watchdog.bat"
            if watchdog_path.exists():
                self.log_message.emit("Creating watchdog task...")
                installation_log.write("\nCreating Watchdog Task...\n")

                subprocess.run(
                    ["schtasks", "/Delete", "/TN", "ERPCNCAdapterWatchdog", "/F"],
                    capture_output=True, startupinfo=self._startupinfo(),
                )

                result = self._create_watchdog_task(watchdog_path, installation_log)

                if result.returncode == 0:
                    self.log_message.emit("\u2713 Watchdog task created (checks every 2 minutes)")
                    installation_log.write("\u2713 Watchdog task created\n")
                    if not self.auto_start_adapter_on_logon:
                        subprocess.run(
                            ["schtasks", "/Change", "/TN", "ERPCNCAdapterWatchdog", "/Disable"],
                            capture_output=True, startupinfo=self._startupinfo(),
                        )
                        installation_log.write("Watchdog auto-start disabled for manual-start install\n")
                else:
                    self.log_message.emit("\u26a0 Watchdog task creation failed (non-critical)")
                    installation_log.write(f"\u26a0 Watchdog failed: {result.stderr}\n")
                    self._write_task_credential_diagnostics(installation_log)
            installation_log.flush()
            self.progress_value.emit(55)

            # 3 — Firewall .....................................................
            self.step_changed.emit("Configuring firewall...")
            self.log_message.emit("Configuring Windows Firewall...")
            installation_log.write("\nSTEP 2: Firewall Configuration\n")
            installation_log.write("-" * 70 + "\n")

            subprocess.run(
                ["netsh", "advfirewall", "firewall", "delete", "rule",
                 "name=ERP-CNC Adapter"],
                capture_output=True, startupinfo=self._startupinfo(),
            )
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule",
                 "name=ERP-CNC Adapter", "dir=in", "action=allow",
                 "protocol=TCP", "localport=8002", "enable=yes", "profile=any",
                 "description=Allow incoming connections to ERP-CNC Adapter API"],
                capture_output=True, text=True, startupinfo=self._startupinfo(),
            )
            if result.returncode == 0:
                self.log_message.emit("\u2713 Firewall rule added")
                installation_log.write("\u2713 Firewall rule added for port 8002\n")
            else:
                self.log_message.emit("\u26a0 Firewall rule failed \u2014 manual configuration may be needed")
                installation_log.write(f"\u26a0 Firewall rule failed: {result.stderr}\n")
            installation_log.flush()
            self.progress_value.emit(75)

            warning_message = self._post_install_warning(config_data)
            if warning_message:
                self.log_message.emit("\u26a0 CNC runtime files are not available yet")
                installation_log.write("\nWARNING\n")
                installation_log.write(warning_message + "\n")
                installation_log.flush()

            # 4 — Start application now ........................................
            self.step_changed.emit("Starting application...")
            self.log_message.emit("Starting ERP-CNC Adapter...")
            installation_log.write("\nSTEP 3: Starting Application\n")
            installation_log.write("-" * 70 + "\n")

            deferred_start_message = "next boot"
            if task_start_mode == "logon":
                deferred_start_message = f"when {self.task_username} logs on"
            # Start through the scheduled task so SYSTEM/user account selection is respected.
            if self.auto_start_adapter_on_logon:
                installation_log.write("Starting scheduled task: ERPCNCAdapter\n")
                try:
                    if self._start_adapter_task(installation_log):
                        self.log_message.emit("\u2713 Application start requested via scheduled task")
                        self.log_message.emit("\u2713 Access at: http://localhost:8002")
                        installation_log.write("\u2713 Scheduled task start requested successfully\n")
                    else:
                        self.log_message.emit(f"\u26a0 Could not start task now - application will start {deferred_start_message}")
                        installation_log.write(f"\u26a0 Scheduled task start failed; application will start {deferred_start_message}\n")
                except Exception as start_err:
                    self.log_message.emit(f"\u26a0 Could not start now: {start_err}")
                    self.log_message.emit(f"\u2713 Application will start {deferred_start_message}")
                    installation_log.write(f"\u26a0 Launch error: {start_err}\n")
                    installation_log.write(f"Application will start {deferred_start_message}\n")
            else:
                self.log_message.emit("\u2713 Auto-start disabled; use restart.bat to start manually")
                installation_log.write("Auto-start disabled; adapter was not started automatically after install\n")
            installation_log.write("\n" + "=" * 70 + "\n")
            installation_log.write("INSTALLATION COMPLETED SUCCESSFULLY\n")
            installation_log.write(f"Completion time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            installation_log.write("=" * 70 + "\n")
            installation_log.flush()

            self.progress_value.emit(100)
            self.finished_signal.emit(True, warning_message or "Installation completed successfully!")

        except Exception as exc:
            if installation_log:
                installation_log.write("\n" + "=" * 70 + "\n")
                installation_log.write("INSTALLATION FAILED\n")
                installation_log.write("=" * 70 + "\n")
                installation_log.write(f"Error: {str(exc)}\n")
                installation_log.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                installation_log.flush()
            self.finished_signal.emit(False, str(exc))
        finally:
            if installation_log:
                installation_log.close()

    # Extract embedded payload ─────────────────────────────────────────────
    def _extract_files(self):
        if getattr(sys, "frozen", False):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).parent

        payload = base / "payload"
        if not payload.exists():
            raise FileNotFoundError("Installation files not found!")

        self.log_message.emit("Extracting application files...")
        for item in payload.rglob("*"):
            if item.is_file():
                dest = self.install_path / item.relative_to(payload)
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(item, dest)
                except PermissionError as exc:
                    raise PermissionError(
                        f"Cannot write {dest}. Stop the running adapter or run the installer as Administrator. "
                        "If installing to Program Files, elevation is required."
                    ) from exc
        self.log_message.emit(f"\u2713 Files extracted to {self.install_path}")
