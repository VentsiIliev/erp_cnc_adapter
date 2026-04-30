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

    def __init__(
        self,
        install_path: str,
        machine_number: str = "CNC1",
        task_username: str = "",
        task_password: str = "",
    ):
        super().__init__()
        self.install_path = Path(install_path)
        self.machine_number = machine_number
        self.task_username = task_username.strip()
        self.task_password = task_password

    # Helper ───────────────────────────────────────────────────────────────
    @staticmethod
    def _startupinfo():
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        return si

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

    def _create_watchdog_task(self, watchdog_path: Path, installation_log) -> subprocess.CompletedProcess:
        command = [
            "schtasks", "/Create",
            "/TN", "ERPCNCAdapterWatchdog",
            "/TR", f'"{watchdog_path}"',
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


    def _build_interactive_logon_task_script(self, launcher_path: Path) -> str:
        def ps_quote(value: str) -> str:
            return value.replace("'", "''")

        return (
            "$ErrorActionPreference = 'Stop'\n"
            f"$action = New-ScheduledTaskAction "
            f"-Execute 'wscript.exe' "
            f"-Argument '\"{ps_quote(str(launcher_path))}\"' "
            f"-WorkingDirectory '{ps_quote(str(self.install_path))}'\n"
            f"$trigger = New-ScheduledTaskTrigger -AtLogOn -User '{ps_quote(self.task_username)}'\n"
            f"$principal = New-ScheduledTaskPrincipal -UserId '{ps_quote(self.task_username)}' "
            f"-LogonType Interactive -RunLevel Highest\n"
            f"$settings = New-ScheduledTaskSettingsSet "
            f"-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
            f"-RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)\n"
            f"Register-ScheduledTask -TaskName 'ERPCNCAdapter' "
            f"-Action $action -Trigger $trigger -Principal $principal "
            f"-Settings $settings -Force -ErrorAction Stop | Out-Null\n"
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
            task_start_mode = "boot"
            ps_script = (
                "$ErrorActionPreference = 'Stop'\n"
                f"$action = New-ScheduledTaskAction "
                f"-Execute 'wscript.exe' "
                f"-Argument '\"{ps_quote(str(launcher_path))}\"' "
                f"-WorkingDirectory '{ps_quote(str(self.install_path))}'\n"
                f"$trigger = New-ScheduledTaskTrigger -AtStartup\n"
                f"$settings = New-ScheduledTaskSettingsSet "
                f"-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
                f"-RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)\n"
            )
            if self.task_username:
                ps_script += (
                    f"$taskUser = '{ps_quote(self.task_username)}'\n"
                    f"$taskPassword = '{ps_quote(self.task_password)}'\n"
                    f"Register-ScheduledTask -TaskName 'ERPCNCAdapter' "
                    f"-Action $action -Trigger $trigger -Settings $settings "
                    f"-User $taskUser -Password $taskPassword -RunLevel Highest -Force -ErrorAction Stop | Out-Null\n"
                )
            else:
                ps_script += (
                    f"$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' "
                    f"-LogonType ServiceAccount -RunLevel Highest\n"
                    f"Register-ScheduledTask -TaskName 'ERPCNCAdapter' "
                    f"-Action $action -Trigger $trigger -Principal $principal "
                    f"-Settings $settings -Force -ErrorAction Stop | Out-Null\n"
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
                else:
                    self.log_message.emit("\u26a0 Watchdog task creation failed (non-critical)")
                    installation_log.write(f"\u26a0 Watchdog failed: {result.stderr}\n")
                    self._write_task_credential_diagnostics(installation_log)
            installation_log.flush()
            self.progress_value.emit(55)

            import time
            time.sleep(1)

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
