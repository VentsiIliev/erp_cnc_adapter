"""
ERP-CNC Adapter Installer — Main Installer Window.
"""
import webbrowser

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QGraphicsDropShadowEffect, QMessageBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from ..constants import BORDER
from ..worker import InstallWorker
from .title_bar import TitleBar
from .step_indicator import StepIndicator
from .pages import WelcomePage, PathPage, InstallPage, CompletePage, ErrorPage


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
        self.setFixedSize(680, 640)
        self._center_on_screen()

        # Container (rounded card)
        self.container = QWidget(self)
        self.container.setObjectName("InstallerWindow")
        self.container.setGeometry(0, 0, 680, 640)

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
        self.btn_bar.setContentsMargins(48, 12, 48, 16)

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

        task_username = ""
        task_password = ""
        if self.path_page.run_as_user_check.isChecked():
            task_username = self.path_page.username_edit.text().strip()
            task_password = self.path_page.password_edit.text()

        self.worker = InstallWorker(
            self.path_page.path_edit.text(),
            self.path_page.machine_edit.text().strip() or "CNC1",
            task_username,
            task_password,
        )
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
            if message and message != "Installation completed successfully!":
                QMessageBox.warning(self, "CNC Unavailable", message)
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
