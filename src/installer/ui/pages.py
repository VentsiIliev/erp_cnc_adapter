"""
ERP-CNC Adapter Installer — Wizard Pages.
"""
import os
import shutil
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog, QProgressBar, QTextEdit,
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
