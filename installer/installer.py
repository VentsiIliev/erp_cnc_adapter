"""
ERP-CNC Adapter Installer — Modern PyQt5 Wizard
Self-contained installer that doesn't require external tools
"""
import os
import sys
import shutil
import subprocess
import urllib.request
import tempfile
from pathlib import Path
from datetime import datetime
import ctypes
import webbrowser
from typing import Optional

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog, QProgressBar,
    QTextEdit, QStackedWidget, QSizePolicy, QGraphicsDropShadowEffect,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt5.QtGui import QFont, QColor, QMouseEvent

VERSION = "1.0.0"

# ── PL Project Color Scheme ──────────────────────────────────────────────────
PRIMARY   = "#4261ee"
GOLD      = "#ffab00"
NAVY      = "#0D132F"
BG        = "#ffffff"
BG_CARD   = "#f9f9f9"
TEXT_BODY  = "#333333"
TEXT_MUTED = "#0D132FB3"
BORDER     = "#eeeeee"

STYLESHEET = f"""
/* ── Window ────────────────────────────────────────────────────────────── */
#InstallerWindow {{
    background: {BG};
    border-radius: 12px;
    border: 1px solid {BORDER};
}}

/* ── Custom Title Bar ─────────────────────────────────────────────────── */
#TitleBar {{
    background: {BG};
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}}
#TitleBar QLabel {{
    color: {NAVY};
    font-size: 13px;
    font-weight: 600;
}}
#CloseButton {{
    background: transparent;
    color: {TEXT_BODY};
    font-size: 18px;
    font-weight: bold;
    border: none;
    padding: 4px 12px;
    border-radius: 6px;
}}
#CloseButton:hover {{
    background: #e74c3c;
    color: white;
}}

/* ── Step Indicator ───────────────────────────────────────────────────── */
#StepDot {{
    border-radius: 6px;
    min-width: 12px; max-width: 12px;
    min-height: 12px; max-height: 12px;
}}
#StepLabel {{
    font-size: 11px;
}}

/* ── Page content ─────────────────────────────────────────────────────── */
#PageTitle {{
    color: {NAVY};
    font-size: 22px;
    font-weight: 700;
}}
#PageSubtitle {{
    color: {TEXT_MUTED};
    font-size: 13px;
}}

/* ── Buttons ──────────────────────────────────────────────────────────── */
#PrimaryButton {{
    background: {PRIMARY};
    color: white;
    font-size: 14px;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    padding: 10px 32px;
}}
#PrimaryButton:hover {{
    background: #3451d1;
}}
#PrimaryButton:disabled {{
    background: #a0b0ee;
}}

#SecondaryButton {{
    background: transparent;
    color: {TEXT_BODY};
    font-size: 14px;
    font-weight: 500;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px 32px;
}}
#SecondaryButton:hover {{
    background: {BG_CARD};
}}

#GoldButton {{
    background: {GOLD};
    color: {NAVY};
    font-size: 14px;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    padding: 10px 32px;
}}
#GoldButton:hover {{
    background: #e69d00;
}}

/* ── Path Input ───────────────────────────────────────────────────────── */
#PathInput {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    color: {TEXT_BODY};
    background: {BG};
}}
#PathInput:focus {{
    border-color: {PRIMARY};
}}

#BrowseButton {{
    background: {BG_CARD};
    color: {TEXT_BODY};
    font-size: 13px;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 16px;
}}
#BrowseButton:hover {{
    background: {BORDER};
}}

/* ── Progress Bar ─────────────────────────────────────────────────────── */
QProgressBar {{
    background: {BORDER};
    border: none;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background: {GOLD};
    border-radius: 6px;
}}

/* ── Log Area ─────────────────────────────────────────────────────────── */
#LogArea {{
    background: {BG_CARD};
    color: {TEXT_BODY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px;
    font-family: Consolas, monospace;
    font-size: 12px;
}}

/* ── Misc ─────────────────────────────────────────────────────────────── */
#DiskLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
#Checkmark {{
    color: #27ae60;
    font-size: 56px;
    font-weight: bold;
}}
#SuccessLabel {{
    color: {NAVY};
    font-size: 18px;
    font-weight: 600;
}}
#UrlLabel {{
    color: {PRIMARY};
    font-size: 14px;
}}
"""


# ── Install Worker (QThread) ─────────────────────────────────────────────────
class InstallWorker(QThread):
    log_message = pyqtSignal(str)
    step_changed = pyqtSignal(str)
    progress_value = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)  # success, message

    def __init__(self, install_path: str):
        super().__init__()
        self.install_path = Path(install_path)

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

            self.install_path.mkdir(parents=True, exist_ok=True)
            self._extract_files()
            self.log_message.emit("✓ Files extracted successfully")

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

            self.log_message.emit(f"✓ Installation log: {installation_log_path}")
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
                import time
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

            # Create task that runs at system startup
            result = subprocess.run(
                [
                    "schtasks", "/Create",
                    "/TN", "ERPCNCAdapter",
                    "/TR", f'"{exe_path}"',
                    "/SC", "ONSTART",
                    "/RU", "SYSTEM",
                    "/RL", "HIGHEST",
                    "/F"
                ],
                capture_output=True, text=True,
                startupinfo=self._startupinfo(),
            )

            installation_log.write(f"Exit code: {result.returncode}\n")
            installation_log.write(f"STDOUT:\n{result.stdout}\n")
            if result.stderr:
                installation_log.write(f"STDERR:\n{result.stderr}\n")
            installation_log.flush()

            if result.returncode != 0:
                msg = result.stderr or result.stdout
                installation_log.write(f"ERROR: Task creation failed!\n")
                installation_log.flush()
                raise RuntimeError(f"Startup task creation failed: {msg}\n\nCheck installation.log for details")

            self.log_message.emit("✓ Startup task created successfully")
            installation_log.write("✓ Startup task created successfully\n")
            installation_log.write("Application will start automatically on boot\n")
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
                self.log_message.emit("✓ Firewall rule added")
                installation_log.write("✓ Firewall rule added for port 8002\n")
            else:
                self.log_message.emit("⚠ Firewall rule failed — manual configuration may be needed")
                installation_log.write(f"⚠ Firewall rule failed: {result.stderr}\n")
            installation_log.flush()
            self.progress_value.emit(75)

            # 4 — Start application now ........................................
            self.step_changed.emit("Starting application...")
            self.log_message.emit("Starting ERP-CNC Adapter...")
            installation_log.write("\nSTEP 3: Starting Application\n")
            installation_log.write("-" * 70 + "\n")

            # Run the scheduled task now
            result = subprocess.run(
                ["schtasks", "/Run", "/TN", "ERPCNCAdapter"],
                capture_output=True, text=True,
                startupinfo=self._startupinfo(),
            )

            installation_log.write(f"Command: schtasks /Run /TN ERPCNCAdapter\n")
            installation_log.write(f"Exit code: {result.returncode}\n")
            installation_log.write(f"Output: {result.stdout}\n")

            if result.returncode == 0:
                self.log_message.emit("✓ Application started successfully")
                self.log_message.emit("✓ Access at: http://localhost:8002")
                installation_log.write("✓ Application started successfully\n")
            else:
                self.log_message.emit("✓ Application configured (will start on next boot)")
                installation_log.write("Application will start on next boot\n")

            installation_log.write("\n" + "=" * 70 + "\n")
            installation_log.write("INSTALLATION COMPLETED SUCCESSFULLY\n")
            installation_log.write(f"Completion time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            installation_log.write("=" * 70 + "\n")
            installation_log.flush()

            self.progress_value.emit(100)
            self.finished_signal.emit(True, "Installation completed successfully!")

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
                shutil.copy2(item, dest)
        self.log_message.emit(f"✓ Files extracted to {self.install_path}")


# ── Step Indicator ───────────────────────────────────────────────────────────
class StepIndicator(QWidget):
    LABELS = ["Welcome", "Choose Path", "Installing", "Done"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = 0
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(40, 12, 40, 12)
        layout.setAlignment(Qt.AlignCenter)

        self._dots: list = []
        self._labels: list = []

        for i, text in enumerate(self.LABELS):
            col = QVBoxLayout()
            col.setAlignment(Qt.AlignCenter)
            col.setSpacing(4)

            dot = QLabel()
            dot.setObjectName("StepDot")
            dot.setFixedSize(12, 12)
            dot.setAlignment(Qt.AlignCenter)
            self._dots.append(dot)
            dot_row = QHBoxLayout()
            dot_row.setAlignment(Qt.AlignCenter)
            dot_row.addWidget(dot)
            col.addLayout(dot_row)

            lbl = QLabel(text)
            lbl.setObjectName("StepLabel")
            lbl.setAlignment(Qt.AlignCenter)
            self._labels.append(lbl)
            col.addWidget(lbl)

            layout.addLayout(col)

            # Connector line between dots (except after last)
            if i < len(self.LABELS) - 1:
                line = QLabel()
                line.setFixedHeight(2)
                line.setMinimumWidth(40)
                line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                layout.addWidget(line, alignment=Qt.AlignVCenter)

        self._refresh()

    def set_step(self, index: int):
        self._current = index
        self._refresh()

    def _refresh(self):
        for i, (dot, lbl) in enumerate(zip(self._dots, self._labels)):
            if i <= self._current:
                dot.setStyleSheet(f"background: {PRIMARY}; border-radius: 6px;")
                lbl.setStyleSheet(f"color: {PRIMARY}; font-weight: 600;")
            else:
                dot.setStyleSheet("background: #d1d1d1; border-radius: 6px;")
                lbl.setStyleSheet("color: #d1d1d1;")


# ── Custom Title Bar ─────────────────────────────────────────────────────────
class TitleBar(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(44)
        self._parent = parent
        self._drag_pos: Optional[QPoint] = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 8, 0)

        title = QLabel(f"ERP-CNC Adapter Setup v{VERSION}")
        title.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        lay.addWidget(title)

        lay.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setObjectName("CloseButton")
        close_btn.setFixedSize(36, 30)
        close_btn.clicked.connect(self._parent.close)
        lay.addWidget(close_btn)

    # Drag support ─────────────────────────────────────────────────────────
    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.LeftButton:
            self._drag_pos = ev.globalPos() - self._parent.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev: QMouseEvent):
        if self._drag_pos and ev.buttons() & Qt.LeftButton:
            self._parent.move(ev.globalPos() - self._drag_pos)
            ev.accept()

    def mouseReleaseEvent(self, ev: QMouseEvent):
        self._drag_pos = None


# ── Wizard Pages ─────────────────────────────────────────────────────────────

class WelcomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(48, 32, 48, 24)
        lay.setSpacing(12)

        lay.addStretch(1)

        # Logo placeholder
        logo = QLabel("\u2699")
        logo.setStyleSheet(f"font-size: 48px; color: {PRIMARY};")
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)

        title = QLabel(f"ERP-CNC Adapter v{VERSION}")
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        subtitle = QLabel(
            "This wizard will install ERP-CNC Adapter as a Windows service.\n"
            "The service will start automatically on boot and listen on port 8002."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        lay.addStretch(2)


class PathPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.default_path = str(
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "ERP-CNC Adapter"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(48, 32, 48, 24)
        lay.setSpacing(16)

        title = QLabel("Choose Installation Path")
        title.setObjectName("PageTitle")
        lay.addWidget(title)

        subtitle = QLabel("Select the folder where the adapter will be installed.")
        subtitle.setObjectName("PageSubtitle")
        lay.addWidget(subtitle)

        lay.addSpacing(8)

        # Path input row
        row = QHBoxLayout()
        self.path_edit = QLineEdit(self.default_path)
        self.path_edit.setObjectName("PathInput")
        self.path_edit.setMinimumHeight(38)
        row.addWidget(self.path_edit)

        browse = QPushButton("Browse...")
        browse.setObjectName("BrowseButton")
        browse.setMinimumHeight(38)
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        lay.addLayout(row)

        # Disk space info
        self.disk_label = QLabel()
        self.disk_label.setObjectName("DiskLabel")
        lay.addWidget(self.disk_label)
        self._update_disk_info()
        self.path_edit.textChanged.connect(lambda _: self._update_disk_info())

        lay.addStretch()

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select Installation Folder",
                                                str(Path(self.path_edit.text()).parent))
        if path:
            self.path_edit.setText(path)

    def _update_disk_info(self):
        try:
            drive = Path(self.path_edit.text()).anchor or "C:\\"
            usage = shutil.disk_usage(drive)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            self.disk_label.setText(f"Disk space on {drive}   {free_gb:.1f} GB free of {total_gb:.1f} GB")
        except Exception:
            self.disk_label.setText("")


class InstallPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(48, 32, 48, 24)
        lay.setSpacing(12)

        title = QLabel("Installing...")
        title.setObjectName("PageTitle")
        lay.addWidget(title)

        self.step_label = QLabel("Preparing...")
        self.step_label.setObjectName("PageSubtitle")
        lay.addWidget(self.step_label)

        lay.addSpacing(4)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(12)
        lay.addWidget(self.progress)

        lay.addSpacing(4)

        self.log = QTextEdit()
        self.log.setObjectName("LogArea")
        self.log.setReadOnly(True)
        lay.addWidget(self.log, 1)


class CompletePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(48, 32, 48, 24)
        lay.setSpacing(12)

        lay.addStretch(1)

        check = QLabel("\u2713")
        check.setObjectName("Checkmark")
        check.setAlignment(Qt.AlignCenter)
        lay.addWidget(check)

        success = QLabel("Installation Complete")
        success.setObjectName("SuccessLabel")
        success.setAlignment(Qt.AlignCenter)
        lay.addWidget(success)

        url = QLabel("Service running at  http://localhost:8002")
        url.setObjectName("UrlLabel")
        url.setAlignment(Qt.AlignCenter)
        lay.addWidget(url)

        lay.addStretch(2)


# ── Error page (shown on failure) ────────────────────────────────────────────
class ErrorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(48, 32, 48, 24)
        lay.setSpacing(12)

        lay.addStretch(1)

        icon = QLabel("\u2717")
        icon.setStyleSheet("color: #e74c3c; font-size: 56px; font-weight: bold;")
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)

        title = QLabel("Installation Failed")
        title.setStyleSheet(f"color: {NAVY}; font-size: 18px; font-weight: 600;")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #e74c3c; font-size: 13px;")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        lay.addWidget(self.error_label)

        lay.addStretch(2)


# ── Main Installer Window ────────────────────────────────────────────────────
class InstallerWindow(QWidget):
    PAGE_WELCOME  = 0
    PAGE_PATH     = 1
    PAGE_INSTALL  = 2
    PAGE_COMPLETE = 3
    PAGE_ERROR    = 4

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(680, 560)
        self._center_on_screen()

        # Container (rounded card)
        self.container = QWidget(self)
        self.container.setObjectName("InstallerWindow")
        self.container.setGeometry(0, 0, 680, 560)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.container.setGraphicsEffect(shadow)

        root = QVBoxLayout(self.container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Title bar
        self.title_bar = TitleBar(self)
        root.addWidget(self.title_bar)

        # Separator
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        root.addWidget(sep)

        # Step indicator
        self.step_indicator = StepIndicator()
        root.addWidget(self.step_indicator)

        sep2 = QLabel()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {BORDER};")
        root.addWidget(sep2)

        # Stacked pages
        self.stack = QStackedWidget()
        self.welcome_page = WelcomePage()
        self.path_page = PathPage()
        self.install_page = InstallPage()
        self.complete_page = CompletePage()
        self.error_page = ErrorPage()

        self.stack.addWidget(self.welcome_page)    # 0
        self.stack.addWidget(self.path_page)       # 1
        self.stack.addWidget(self.install_page)    # 2
        self.stack.addWidget(self.complete_page)   # 3
        self.stack.addWidget(self.error_page)      # 4
        root.addWidget(self.stack, 1)

        # Button bar
        sep3 = QLabel()
        sep3.setFixedHeight(1)
        sep3.setStyleSheet(f"background: {BORDER};")
        root.addWidget(sep3)

        self.btn_bar = QHBoxLayout()
        self.btn_bar.setContentsMargins(48, 16, 48, 20)

        self.btn_secondary = QPushButton("Cancel")
        self.btn_secondary.setObjectName("SecondaryButton")
        self.btn_secondary.setCursor(Qt.PointingHandCursor)
        self.btn_secondary.clicked.connect(self._on_secondary)
        self.btn_bar.addWidget(self.btn_secondary)

        self.btn_bar.addStretch()

        self.btn_primary = QPushButton("Next")
        self.btn_primary.setObjectName("PrimaryButton")
        self.btn_primary.setCursor(Qt.PointingHandCursor)
        self.btn_primary.clicked.connect(self._on_primary)
        self.btn_bar.addWidget(self.btn_primary)

        self.btn_open = QPushButton("Open Browser")
        self.btn_open.setObjectName("GoldButton")
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(lambda: webbrowser.open("http://localhost:8002"))
        self.btn_open.hide()
        self.btn_bar.addWidget(self.btn_open)

        root.addLayout(self.btn_bar)

        # Start on welcome
        self._go_to(self.PAGE_WELCOME)

    # Navigation ───────────────────────────────────────────────────────────
    def _go_to(self, page: int):
        self.stack.setCurrentIndex(page)
        step = min(page, 3)
        self.step_indicator.set_step(step)

        # Update buttons per page
        if page == self.PAGE_WELCOME:
            self.btn_primary.setText("Next")
            self.btn_primary.show()
            self.btn_secondary.setText("Cancel")
            self.btn_secondary.show()
            self.btn_secondary.setEnabled(True)
            self.btn_open.hide()
        elif page == self.PAGE_PATH:
            self.btn_primary.setText("Install")
            self.btn_primary.show()
            self.btn_secondary.setText("Back")
            self.btn_secondary.show()
            self.btn_secondary.setEnabled(True)
            self.btn_open.hide()
        elif page == self.PAGE_INSTALL:
            self.btn_primary.hide()
            self.btn_secondary.setText("Cancel")
            self.btn_secondary.setEnabled(False)
            self.btn_open.hide()
        elif page == self.PAGE_COMPLETE:
            self.btn_primary.setText("Finish")
            self.btn_primary.show()
            self.btn_secondary.hide()
            self.btn_open.show()
        elif page == self.PAGE_ERROR:
            self.btn_primary.setText("Retry")
            self.btn_primary.show()
            self.btn_secondary.setText("Close")
            self.btn_secondary.show()
            self.btn_secondary.setEnabled(True)
            self.btn_open.hide()

    def _on_primary(self):
        page = self.stack.currentIndex()
        if page == self.PAGE_WELCOME:
            self._go_to(self.PAGE_PATH)
        elif page == self.PAGE_PATH:
            self._start_install()
        elif page == self.PAGE_COMPLETE:
            self.close()
        elif page == self.PAGE_ERROR:
            # Retry — go back to path page
            self._go_to(self.PAGE_PATH)

    def _on_secondary(self):
        page = self.stack.currentIndex()
        if page == self.PAGE_PATH:
            self._go_to(self.PAGE_WELCOME)
        else:
            self.close()

    # Installation ─────────────────────────────────────────────────────────
    def _start_install(self):
        self._go_to(self.PAGE_INSTALL)

        self.worker = InstallWorker(self.path_page.path_edit.text())
        self.worker.log_message.connect(self._on_log)
        self.worker.step_changed.connect(self._on_step)
        self.worker.progress_value.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_log(self, msg: str):
        self.install_page.log.append(msg)

    def _on_step(self, text: str):
        self.install_page.step_label.setText(text)

    def _on_progress(self, val: int):
        self.install_page.progress.setValue(val)

    def _on_finished(self, success: bool, message: str):
        if success:
            self._go_to(self.PAGE_COMPLETE)
        else:
            self.error_page.error_label.setText(message)
            self._go_to(self.PAGE_ERROR)

    # Helpers ──────────────────────────────────────────────────────────────
    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2 + geo.x()
            y = (geo.height() - self.height()) // 2 + geo.y()
            self.move(x, y)


# ── Entry Point ──────────────────────────────────────────────────────────────
def main():
    # Admin check
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLESHEET)

    if not is_admin:
        QMessageBox.critical(
            None, "Administrator Required",
            "This installer must be run as Administrator.\n\n"
            "Right-click the installer and select 'Run as administrator'.",
        )
        sys.exit(1)

    window = InstallerWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
