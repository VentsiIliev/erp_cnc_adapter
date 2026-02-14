"""
Launch the installer UI independently for development/testing.

Usage:
    python -m installer.ui.run
    — or —
    python installer/ui/run.py
"""
import sys
from pathlib import Path

# Ensure the project root is on sys.path so package imports work
# when running this file directly.
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QIcon

from installer.constants import STYLESHEET, _icon_path
from installer.ui.window import InstallerWindow


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLESHEET)

    ico = _icon_path()
    if ico:
        app.setWindowIcon(QIcon(ico))

    window = InstallerWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
