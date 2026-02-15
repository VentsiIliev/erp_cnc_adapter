"""
ERP-CNC Adapter Installer — Step Indicator widget.
"""
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import Qt

from ..constants import PRIMARY


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
