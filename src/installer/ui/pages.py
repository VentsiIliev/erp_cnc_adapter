"""
ERP-CNC Adapter Installer — Wizard Pages.
"""
import os
import shutil
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog, QProgressBar, QTextEdit,
    QCheckBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from ..constants import VERSION, PRIMARY, NAVY, _icon_path


class WelcomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(48, 32, 48, 24)
        lay.setSpacing(12)

        lay.addStretch(1)

        # Logo
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        ico = _icon_path()
        if ico:
            pixmap = QPixmap(ico).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(pixmap)
        else:
            logo.setText("\u2699")
            logo.setStyleSheet(f"font-size: 48px; color: {PRIMARY};")
        lay.addWidget(logo)

        title = QLabel(f"ERP-CNC Adapter v{VERSION}")
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        subtitle = QLabel(
            "This wizard will install ERP-CNC Adapter on your system.\n"
            "It will start automatically on boot and listen on port 8002."
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
        lay.setContentsMargins(48, 24, 48, 16)
        lay.setSpacing(10)

        title = QLabel("Choose Installation Path")
        title.setObjectName("PageTitle")
        lay.addWidget(title)

        subtitle = QLabel("Select the folder where the adapter will be installed.")
        subtitle.setObjectName("PageSubtitle")
        lay.addWidget(subtitle)

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

        # Machine ID input
        machine_label = QLabel("Machine ID")
        machine_label.setObjectName("PageSubtitle")
        lay.addWidget(machine_label)

        machine_hint = QLabel("Identifier for this CNC machine, e.g. CNC1, CNC2, MILL1")
        machine_hint.setObjectName("DiskLabel")
        lay.addWidget(machine_hint)

        self.machine_edit = QLineEdit("CNC1")
        self.machine_edit.setObjectName("PathInput")
        self.machine_edit.setMaximumWidth(200)
        self.machine_edit.setMinimumHeight(38)
        lay.addWidget(self.machine_edit)

        self.run_as_user_check = QCheckBox("Run adapter as a Windows account")
        self.run_as_user_check.setObjectName("PageSubtitle")
        self.run_as_user_check.setChecked(True)
        lay.addWidget(self.run_as_user_check)

        self.auto_start_check = QCheckBox("Start adapter automatically on Windows logon")
        self.auto_start_check.setObjectName("PageSubtitle")
        self.auto_start_check.setChecked(True)
        lay.addWidget(self.auto_start_check)

        credential_hint = QLabel(
            "Default: use the current Windows account so CNC network shares work. "
            "Untick auto-start when this machine should be started manually with the restart script."
        )
        credential_hint.setObjectName("DiskLabel")
        credential_hint.setWordWrap(True)
        lay.addWidget(credential_hint)

        self.username_edit = QLineEdit(self._default_username())
        self.username_edit.setObjectName("PathInput")
        self.username_edit.setPlaceholderText(r"DOMAIN\username or .\username")
        self.username_edit.setMinimumHeight(38)
        self.username_edit.setEnabled(True)
        lay.addWidget(self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setObjectName("PathInput")
        self.password_edit.setPlaceholderText("Windows password")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setMinimumHeight(38)
        self.password_edit.setEnabled(True)
        lay.addWidget(self.password_edit)

        self.run_as_user_check.toggled.connect(self._toggle_credentials)

        lay.addStretch()

    @staticmethod
    def _default_username() -> str:
        domain = os.environ.get("USERDOMAIN", "").strip()
        username = os.environ.get("USERNAME", "").strip()
        if domain and username:
            return rf"{domain}\{username}"
        return username

    def _toggle_credentials(self, enabled: bool):
        self.username_edit.setEnabled(enabled)
        self.username_edit.setVisible(enabled)
        self.password_edit.setEnabled(enabled)
        self.password_edit.setVisible(enabled)

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
