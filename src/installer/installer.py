"""
ERP-CNC Adapter Installer — Entry Point.
"""
import sys
import ctypes

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QFont, QIcon

from .constants import STYLESHEET, _icon_path
from .ui.window import InstallerWindow


def main():
    # Admin check
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLESHEET)

    ico = _icon_path()
    if ico:
        app.setWindowIcon(QIcon(ico))

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
