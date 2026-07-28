from __future__ import annotations

import threading
from typing import Optional

from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from .client import AdapterJogClient
from .config import POSITION_ERROR_DISPLAY_THRESHOLD, THEME, JogPadTheme, resolve_jogpad_icon_path, resolve_reset_icon_path
from .widgets import (
    ArrowJogButton,
    BitmapCommandButton,
    CloseButton,
    CoordinateReadout,
    CustomStepButton,
    HomeStatusButton,
    StepModeButton,
    ZeroAxisButton,
)
from .workers import BackgroundCommandSender, CoordinatePoller, PauseHoldThread


class JogPad(QWidget):
    """
    Jog pad widget.

    Signals are supplied in addition to the editable action methods, so the
    widget can be integrated without changing its UI code.
    """

    jog_started = pyqtSignal(str, int, float)
    jog_stopped = pyqtSignal(str)
    step_requested = pyqtSignal(str, float, float)
    speed_changed = pyqtSignal(float)
    mode_changed = pyqtSignal(object)

    CONTINUOUS = None

    def __init__(
        self,
        theme: JogPadTheme = THEME,
        parent: Optional[QWidget] = None,
        adapter_url: Optional[str] = None,
        pause_hold_interval_ms: int = 0,
    ) -> None:

        super().__init__(parent)
        self.theme = theme
        self.adapter_client = AdapterJogClient(adapter_url)
        self.command_sender = BackgroundCommandSender(self)
        self.command_sender.command_succeeded.connect(self.on_command_succeeded)
        self.command_sender.command_failed.connect(self.on_command_failed)
        self.coordinate_labels: dict[str, QLabel] = {}
        self.coordinate_readouts: dict[str, CoordinateReadout] = {}
        self._position_error_count = 0
        self.coordinate_mode = "work"
        self.coordinate_mode_buttons: dict[str, QPushButton] = {}
        self.latest_positions: dict = {}
        self.position_poller = self._create_position_poller()
        self.pause_hold_interval_ms = max(0, int(pause_hold_interval_ms))
        self._pause_hold_active = False
        self.pause_hold_thread = self._create_pause_hold_thread()
        self._background_threads_started = False
        self.selected_step: Optional[float] = self.CONTINUOUS
        self._active_axis: Optional[str] = None

        self.setObjectName("jogPad")
        self.setMinimumSize(1060, 470)
        self._build_ui()
        self._connect_actions()
        self._apply_style()

    def _create_position_poller(self) -> CoordinatePoller:
        poller = CoordinatePoller(self.adapter_client, self)
        poller.positions_received.connect(self.on_positions_received)
        poller.error_received.connect(self.on_position_error)
        return poller

    def _create_pause_hold_thread(self) -> PauseHoldThread:
        thread = PauseHoldThread(self.adapter_client, self.pause_hold_interval_ms, self)
        thread.status_received.connect(self.on_pause_hold_status)
        thread.error_received.connect(self.on_pause_hold_error)
        return thread

    def start_background_threads(self) -> None:
        window = self.window()
        if window is not None and not window.isVisible():
            return
        if not self.position_poller.isRunning():
            self.position_poller = self._create_position_poller()
            self.position_poller.start()
        if self.pause_hold_interval_ms > 0 and not self.pause_hold_thread.isRunning():
            self.pause_hold_thread = self._create_pause_hold_thread()
            self.pause_hold_thread.start()
        self._background_threads_started = True

    def stop_background_threads(self) -> None:
        if self.pause_hold_thread.isRunning():
            self.pause_hold_thread.stop()
            self.pause_hold_thread.wait(1000)
        if self.position_poller.isRunning():
            self.position_poller.stop()
            self.position_poller.wait(1000)
        self._background_threads_started = False
        self._pause_hold_active = False

    def stop_pause_hold_thread(self) -> None:
        self.stop_background_threads()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 10)
        root.setSpacing(18)

        motion_row = QHBoxLayout()
        motion_row.setSpacing(26)

        xy_panel = self._build_xy_panel()
        z_panel = self._build_z_panel()

        motion_row.addWidget(xy_panel, 0, Qt.AlignTop)
        motion_row.addWidget(z_panel, 0, Qt.AlignTop)
        motion_row.addSpacing(54)
        motion_row.addWidget(self._build_coordinate_panel(), 0, Qt.AlignTop)
        motion_row.addStretch(1)
        root.addLayout(motion_row)

        root.addSpacing(6)

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 100)
        self.speed_slider.setValue(10)
        self.speed_slider.setSingleStep(1)
        self.speed_slider.setPageStep(5)
        self.speed_slider.setMaximumWidth(632)
        self.speed_slider.setToolTip("Jog speed: 10%")
        root.addWidget(self.speed_slider)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)

        self.mode_label = QLabel("Cont")
        self.mode_label.setObjectName("modeLabel")
        self.mode_label.setFixedSize(64, 28)
        self.mode_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        status_row.addWidget(self.mode_label)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setMinimumSize(520, 28)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        root.addLayout(status_row)

        root.addStretch(1)
        root.addLayout(self._build_bottom_controls())

    def _build_coordinate_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("coordinatePanel")
        panel.setFixedWidth(390)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        tab_row = QHBoxLayout()
        tab_row.setSpacing(0)
        for mode, label in (("machine", "Machine"), ("work", "Work")):
            button = QPushButton(label)
            button.setObjectName("coordinateModeTab")
            button.setCheckable(True)
            button.setChecked(mode == self.coordinate_mode)
            button.setFixedSize(82, 24)
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(lambda checked=False, selected=mode: self.set_coordinate_mode(selected))
            self.coordinate_mode_buttons[mode] = button
            tab_row.addWidget(button)
        tab_row.addStretch(1)
        layout.addLayout(tab_row)

        for axis in ("X", "Y", "Z"):
            row = QHBoxLayout()
            row.setSpacing(8)
            zero_button = ZeroAxisButton(axis, self.theme)
            readout = CoordinateReadout(axis)
            self.coordinate_labels[axis.lower()] = readout.value_label
            self.coordinate_readouts[axis.lower()] = readout
            zero_button.clicked.connect(lambda checked=False, selected=axis: self.action_zero_work_axis(selected))
            readout.clicked.connect(self.show_work_coordinate_dialog)
            row.addWidget(zero_button)
            row.addWidget(readout)
            layout.addLayout(row)

        return panel

    def _build_xy_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.addSpacing(86)
        self.y_positive_button = ArrowJogButton("up", "Y+", self.theme)
        top.addWidget(self.y_positive_button)
        top.addStretch(1)

        middle = QHBoxLayout()
        self.x_negative_button = ArrowJogButton("left", "X-", self.theme)
        self.x_positive_button = ArrowJogButton("right", "X+", self.theme)
        middle.addWidget(self.x_negative_button)
        middle.addSpacing(100)
        middle.addWidget(self.x_positive_button)

        bottom = QHBoxLayout()
        bottom.addSpacing(86)
        self.y_negative_button = ArrowJogButton("down", "Y-", self.theme)
        bottom.addWidget(self.y_negative_button)
        bottom.addStretch(1)

        layout.addLayout(top)
        layout.addLayout(middle)
        layout.addLayout(bottom)
        return panel

    def _build_z_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(88)

        self.z_positive_button = ArrowJogButton("up", "Z+", self.theme, icon_name="jog_up3.bmp")
        self.z_negative_button = ArrowJogButton("down", "Z-", self.theme, icon_name="jog_down3.bmp")

        layout.addWidget(self.z_positive_button)
        layout.addWidget(self.z_negative_button)
        return panel

    def _build_bottom_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(14)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.continuous_button = StepModeButton("cont", self.theme)
        self.step_0001_button = StepModeButton(".001", self.theme)
        self.step_001_button = StepModeButton("0.01", self.theme)
        self.step_01_button = StepModeButton("0.1", self.theme)
        self.step_1_button = StepModeButton("1", self.theme)
        self.home_button = HomeStatusButton(self.theme)
        self.reset_button = BitmapCommandButton("Reset CNC errors", resolve_reset_icon_path(), "RESET", self.theme)

        mode_buttons = (
            self.continuous_button,
            self.step_0001_button,
            self.step_001_button,
            self.step_01_button,
            self.step_1_button,
        )
        for button in mode_buttons:
            self.mode_group.addButton(button)

        self.continuous_button.setChecked(True)

        row.addWidget(self.continuous_button)
        row.addSpacerItem(QSpacerItem(86, 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))
        row.addWidget(self.step_0001_button)
        row.addWidget(self.step_001_button)
        row.addWidget(self.step_01_button)
        row.addWidget(self.step_1_button)
        row.addWidget(self.home_button)
        row.addWidget(self.reset_button)

        custom_column = QVBoxLayout()
        custom_column.setSpacing(4)

        self.custom_step_edit = QLineEdit("5.0")
        self.custom_step_edit.setFixedSize(72, 28)
        self.custom_step_edit.setToolTip("Custom step distance")
        self.custom_step_button = CustomStepButton(self.theme)

        custom_column.addWidget(self.custom_step_edit)
        custom_column.addWidget(self.custom_step_button)
        row.addLayout(custom_column)

        row.addStretch(1)

        self.close_button = CloseButton(self.theme)
        row.addWidget(self.close_button)
        return row

    def _connect_actions(self) -> None:
        # Direction buttons. Each connection points to a clearly named method.
        self.x_positive_button.pressed.connect(self.on_x_positive_pressed)
        self.x_positive_button.released.connect(self.on_x_positive_released)

        self.x_negative_button.pressed.connect(self.on_x_negative_pressed)
        self.x_negative_button.released.connect(self.on_x_negative_released)

        self.y_positive_button.pressed.connect(self.on_y_positive_pressed)
        self.y_positive_button.released.connect(self.on_y_positive_released)

        self.y_negative_button.pressed.connect(self.on_y_negative_pressed)
        self.y_negative_button.released.connect(self.on_y_negative_released)

        self.z_positive_button.pressed.connect(self.on_z_positive_pressed)
        self.z_positive_button.released.connect(self.on_z_positive_released)

        self.z_negative_button.pressed.connect(self.on_z_negative_pressed)
        self.z_negative_button.released.connect(self.on_z_negative_released)

        # Jog mode buttons.
        self.continuous_button.clicked.connect(
            lambda: self.set_jog_mode(self.CONTINUOUS, "Cont")
        )
        self.step_0001_button.clicked.connect(lambda: self.set_jog_mode(0.001, "0.001"))
        self.step_001_button.clicked.connect(lambda: self.set_jog_mode(0.01, "0.01"))
        self.step_01_button.clicked.connect(lambda: self.set_jog_mode(0.1, "0.1"))
        self.step_1_button.clicked.connect(lambda: self.set_jog_mode(1.0, "1.0"))

        self.custom_step_button.clicked.connect(self.use_custom_step)
        self.custom_step_edit.returnPressed.connect(self.use_custom_step)

        self.speed_slider.valueChanged.connect(self.on_speed_slider_changed)
        self.home_button.clicked.connect(self.action_home_all_axes)
        self.reset_button.clicked.connect(self.action_reset)
        self.close_button.clicked.connect(self.on_close_pressed)

    def _apply_style(self) -> None:
        accent = self.theme.accent_blue
        accent_pressed = self.theme.accent_pressed.name()
        accent_soft = self.theme.accent.lighter(165).name()
        accent_border_dark = self.theme.accent.darker(135).name()
        accent_border_light = self.theme.accent.lighter(140).name()
        background = self.theme.window_background

        self.setStyleSheet(
            f"""
            QWidget#jogPad {{
                background: {background};
                color: {self.theme.text_color};
                font-family: "Segoe UI";
                font-size: 12px;
            }}

            QLabel#modeLabel {{
                background: white;
                border: 1px solid #C8C8C8;
                padding-left: 3px;
            }}

            QLabel#statusLabel {{
                background: white;
                border: 1px solid #C8C8C8;
                color: #202020;
                padding-left: 8px;
                padding-right: 8px;
            }}

            QWidget#coordinatePanel {{
                background: #F1F1F1;
            }}

            QPushButton#coordinateModeTab {{
                background: #E8E8E8;
                border: 1px solid #B6B6B6;
                border-bottom: none;
                color: #111111;
                font-size: 12px;
                padding: 1px 8px;
            }}

            QPushButton#coordinateModeTab:checked {{
                background: {accent};
                border-color: {accent_border_dark};
                color: white;
            }}

            QFrame#coordinateReadout {{
                background: {accent};
                border-top: 2px solid {accent_border_dark};
                border-left: 2px solid {accent_border_dark};
                border-right: 2px solid {accent_border_light};
                border-bottom: 2px solid {accent_border_light};
            }}

            QLabel#coordinateAxis {{
                color: white;
                font-family: "Times New Roman";
                font-size: 38px;
            }}

            QLabel#coordinateValue {{
                color: white;
                font-family: "Times New Roman";
                font-size: 40px;
            }}

            QLineEdit {{
                background: white;
                border: 1px solid #D5DDE9;
                selection-background-color: {accent};
                font-size: 12px;
            }}

            QSlider::groove:horizontal {{
                height: 4px;
                background: {accent_soft};
                border: 1px solid {accent_border_light};
            }}

            QSlider::sub-page:horizontal {{
                background: {accent};
                border: none;
            }}

            QSlider::handle:horizontal {{
                width: 14px;
                margin: -8px 0;
                background: {accent};
                border: 1px solid {accent_border_dark};
            }}

            QSlider::handle:horizontal:pressed {{
                background: {accent_pressed};
            }}
            """
        )

    @property
    def speed_percent(self) -> float:
        return float(self.speed_slider.value())

    # =========================================================================
    # BUTTON-SPECIFIC ACTION METHODS
    #
    # These are intentionally separate so any individual button behavior can
    # be changed without touching the layout or painting code.
    # =========================================================================

    def on_x_positive_pressed(self) -> None:
        self._jog_pressed("X", +1)

    def on_x_positive_released(self) -> None:
        self._jog_released("X")

    def on_x_negative_pressed(self) -> None:
        self._jog_pressed("X", -1)

    def on_x_negative_released(self) -> None:
        self._jog_released("X")

    def on_y_positive_pressed(self) -> None:
        self._jog_pressed("Y", +1)

    def on_y_positive_released(self) -> None:
        self._jog_released("Y")

    def on_y_negative_pressed(self) -> None:
        self._jog_pressed("Y", -1)

    def on_y_negative_released(self) -> None:
        self._jog_released("Y")

    def on_z_positive_pressed(self) -> None:
        self._jog_pressed("Z", +1)

    def on_z_positive_released(self) -> None:
        self._jog_released("Z")

    def on_z_negative_pressed(self) -> None:
        self._jog_pressed("Z", -1)

    def on_z_negative_released(self) -> None:
        self._jog_released("Z")

    def clear_cnc_messages_on_show(self) -> None:
        def clear_messages() -> None:
            try:
                self.adapter_client.clear_cnc_messages()
            except Exception as exc:
                print(f"Adapter message clear failed: {exc}")

        threading.Thread(target=clear_messages, name="jog-pad-clear-messages", daemon=True).start()

    def on_close_pressed(self) -> None:
        self.stop_background_threads()
        self.window().hide()

    def show_work_coordinate_dialog(self, axis: str) -> None:
        if self.coordinate_mode != "work":
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"G92 {axis}")
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)

        field_row = QHBoxLayout()
        label = QLabel(f"G92{axis}")
        label.setObjectName("g92Label")
        label.setFixedWidth(62)
        value_edit = QLineEdit(self._current_coordinate_text(axis))
        value_edit.setObjectName("g92ValueEdit")
        value_edit.setFixedWidth(120)
        value_edit.selectAll()
        field_row.addWidget(label)
        field_row.addWidget(value_edit)
        layout.addLayout(field_row)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.setFixedWidth(74)
        cancel_button.setFixedWidth(74)
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        button_row.addWidget(ok_button)
        button_row.addWidget(cancel_button)
        layout.addLayout(button_row)

        if dialog.exec_() != QDialog.Accepted:
            return

        try:
            value = float(value_edit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid G92 value", "Enter a valid numeric coordinate value.")
            return

        self.action_set_work_coordinate(axis, value)

    def _current_coordinate_text(self, axis: str) -> str:
        coordinates = self.latest_positions.get("work") or {}
        value = coordinates.get(axis.lower())
        if value is None:
            return "0.000"
        return f"{float(value):.3f}"

    def on_positions_received(self, payload: dict) -> None:
        self._position_error_count = 0
        self.latest_positions = payload
        self._update_coordinate_labels()

    def on_position_error(self, message: str) -> None:
        self._position_error_count += 1
        if self._position_error_count < POSITION_ERROR_DISPLAY_THRESHOLD:
            print(f"Position read failed transiently: {message}")
            return
        self.set_status(f"Position read failed: {message}", error=True)

    def on_command_succeeded(self, label: str, message: str) -> None:
        self.set_status(f"{label}: {message or 'OK'}", error=False)

    def on_command_failed(self, label: str, message: str) -> None:
        if label.startswith("start ") and len(label) >= 7:
            failed_axis = label[6].upper()
            if self._active_axis == failed_axis:
                self._active_axis = None
            if self._pause_hold_active and self._looks_like_paused_state_error(message):
                self.set_status(f"{label}: blocked by pause hold. Press Proceed to release the hold.", error=True)
                return
        self.set_status(f"{label}: {message}", error=True)

    def set_status(self, message: str, error: bool = False) -> None:
        self.status_label.setText(message)
        color = "#B00020" if error else "#146C2E"
        self.status_label.setStyleSheet(f"color: {color};")

    def on_pause_hold_status(self, message: str) -> None:
        self._pause_hold_active = True
        self.set_status(message, error=False)

    def on_pause_hold_error(self, message: str) -> None:
        print(f"Adapter pause hold failed: {message}")
        self.set_status(f"Pause hold failed: {message}", error=True)

    @staticmethod
    def _looks_like_paused_state_error(message: str) -> bool:
        lowered = message.lower()
        return any(
            token in lowered
            for token in (
                "invalid state",
                "busy",
                "already running",
                "machine is not in the correct state",
                "drives not enabled",
                "motion are not enabled",
                "e-stop",
            )
        )


    def set_coordinate_mode(self, mode: str) -> None:
        if mode not in ("work", "machine"):
            return
        self.coordinate_mode = mode
        for button_mode, button in self.coordinate_mode_buttons.items():
            button.setChecked(button_mode == mode)
        for axis, readout in self.coordinate_readouts.items():
            readout.setToolTip(f"Set G92 {axis.upper()}" if mode == "work" else "Machine coordinates are read-only")
            readout.setCursor(Qt.PointingHandCursor if mode == "work" else Qt.ArrowCursor)
        self._update_coordinate_labels()

    def _update_coordinate_labels(self) -> None:
        coordinates = self.latest_positions.get(self.coordinate_mode) or {}
        for axis in ("x", "y", "z"):
            value = coordinates.get(axis)
            if value is None:
                self.coordinate_labels[axis].setText("---.---")
                continue
            self.coordinate_labels[axis].setText(f"{float(value):.3f}")

    def on_speed_slider_changed(self, value: int) -> None:
        self.speed_slider.setToolTip(f"Jog speed: {value}%")
        self.speed_changed.emit(float(value))
        self.action_speed_changed(float(value))

    def set_jog_mode(self, step: Optional[float], display_text: str) -> None:
        self.selected_step = step
        self.mode_label.setText(display_text)
        self.mode_changed.emit(step)
        self.action_mode_changed(step)

    def use_custom_step(self) -> None:
        try:
            step = float(self.custom_step_edit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid step", "Enter a valid numeric step value.")
            self.custom_step_edit.setFocus()
            self.custom_step_edit.selectAll()
            return

        if step <= 0:
            QMessageBox.warning(self, "Invalid step", "The step value must be greater than zero.")
            self.custom_step_edit.setFocus()
            self.custom_step_edit.selectAll()
            return

        self.mode_group.setExclusive(False)
        for button in self.mode_group.buttons():
            button.setChecked(False)
        self.mode_group.setExclusive(True)

        self.set_jog_mode(step, f"{step:g}")

    def _jog_pressed(self, axis: str, direction: int) -> None:
        if self.selected_step is self.CONTINUOUS:
            self._active_axis = axis
            self.jog_started.emit(axis, direction, self.speed_percent)
            self.action_start_continuous_jog(axis, direction, self.speed_percent)
            return

        signed_distance = float(direction) * float(self.selected_step)
        self.step_requested.emit(axis, signed_distance, self.speed_percent)
        self.action_move_relative(axis, signed_distance, self.speed_percent)

    def _jog_released(self, axis: str) -> None:
        if self.selected_step is not self.CONTINUOUS:
            return

        if self._active_axis == axis:
            self._active_axis = None
            self.jog_stopped.emit(axis)
            self.action_stop_continuous_jog(axis)

    # =========================================================================
    # ADAPTER HTTP ACTIONS
    #
    # These methods send commands to the running adapter over localhost HTTP.
    # =========================================================================

    def action_start_continuous_jog(
        self,
        axis: str,
        direction: int,
        speed_percent: float,
    ) -> None:
        """Called once when a direction button is pressed in continuous mode."""
        sign = "+" if direction > 0 else "-"
        self.command_sender.submit(
            f"start {axis}{sign}",
            lambda: self.adapter_client.start_continuous_jog(axis, direction, speed_percent),
        )

    def action_stop_continuous_jog(self, axis: str) -> None:
        """Called when a continuous-jog direction button is released."""
        self.command_sender.submit(
            f"stop {axis}",
            self.adapter_client.stop_continuous_jog,
        )

    def action_move_relative(
        self,
        axis: str,
        signed_distance: float,
        speed_percent: float,
    ) -> None:
        """Called once for every press while a fixed step mode is selected."""
        self.command_sender.submit(
            f"step {axis} {signed_distance:g}",
            lambda: self.adapter_client.move_relative(axis, signed_distance, speed_percent),
        )

    def action_zero_work_axis(self, axis: str) -> None:
        """Set the current position as work zero for one axis."""
        self.command_sender.submit(
            f"zero {axis}",
            lambda: self.adapter_client.zero_work_axis(axis),
        )

    def action_set_work_coordinate(self, axis: str, value: float) -> None:
        """Set the displayed work coordinate value for one axis."""
        self.command_sender.submit(
            f"G92 {axis}{value:g}",
            lambda: self.adapter_client.set_work_coordinate(axis, value),
        )

    def action_home_all_axes(self) -> None:
        """Run the all-axis home MDI command."""
        self.command_sender.submit(
            "home sequence",
            self.adapter_client.home_all_axes,
        )

    def action_reset(self) -> None:
        """Recover CNC from error states."""
        self.command_sender.submit(
            "reset",
            self.adapter_client.reset,
        )

    def action_speed_changed(self, speed_percent: float) -> None:
        """Called whenever the speed slider changes."""
        print(f"SPEED changed: {speed_percent:.0f}%")

    def action_mode_changed(self, step: Optional[float]) -> None:
        """Called when continuous or fixed-step mode changes."""
        if step is None:
            print("MODE changed: continuous")
        else:
            print(f"MODE changed: step={step:g}")
