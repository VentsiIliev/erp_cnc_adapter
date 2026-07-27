import json
from pathlib import Path

from src.jog_pad.jog_pad import AdapterJogClient, resolve_adapter_url


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b'{"status": 0, "message": "ok"}'




def test_reset_posts_adapter_reset_endpoint(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["data"] = request.data
        captured["method"] = request.get_method()
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = AdapterJogClient("http://127.0.0.1:8765/", timeout_seconds=1.25)
    response = client.reset()

    assert response == {"status": 0, "message": "ok"}
    assert captured == {
        "url": "http://127.0.0.1:8765/api/cnc/reset",
        "timeout": 1.25,
        "data": None,
        "method": "POST",
    }


def test_pause_job_posts_adapter_pause_endpoint(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["data"] = request.data
        captured["method"] = request.get_method()
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = AdapterJogClient("http://127.0.0.1:8765/", timeout_seconds=1.25)
    response = client.pause_job()

    assert response == {"status": 0, "message": "ok"}
    assert captured == {
        "url": "http://127.0.0.1:8765/api/cnc/job/pause",
        "timeout": 25.0,
        "data": None,
        "method": "POST",
    }

def test_get_homed_status_gets_adapter_homed_endpoint(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["method"] = request.get_method()
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = AdapterJogClient("http://127.0.0.1:8765/", timeout_seconds=1.25)
    response = client.get_homed_status()

    assert response == {"status": 0, "message": "ok"}
    assert captured == {
        "url": "http://127.0.0.1:8765/api/cnc/homed",
        "timeout": 5.0,
        "method": "GET",
    }


def test_home_all_axes_posts_adapter_home_endpoint(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["data"] = request.data
        captured["method"] = request.get_method()
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = AdapterJogClient("http://127.0.0.1:8765/", timeout_seconds=1.25)
    response = client.home_all_axes()

    assert response == {"status": 0, "message": "ok"}
    assert captured == {
        "url": "http://127.0.0.1:8765/api/cnc/home",
        "timeout": 1.25,
        "data": None,
        "method": "POST",
    }


def test_get_positions_gets_adapter_position_endpoint(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["method"] = request.get_method()
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = AdapterJogClient("http://127.0.0.1:8765/", timeout_seconds=1.25)
    response = client.get_positions()

    assert response == {"status": 0, "message": "ok"}
    assert captured == {
        "url": "http://127.0.0.1:8765/api/cnc/position",
        "timeout": 5.0,
        "method": "GET",
    }


def test_zero_work_axis_posts_adapter_payload(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["method"] = request.get_method()
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = AdapterJogClient("http://127.0.0.1:8765/", timeout_seconds=1.25)
    response = client.zero_work_axis("X")

    assert response == {"status": 0, "message": "ok"}
    assert captured == {
        "url": "http://127.0.0.1:8765/api/cnc/zero",
        "timeout": 1.25,
        "payload": {"axis": "X"},
        "method": "POST",
    }


def test_set_work_coordinate_posts_adapter_payload(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["method"] = request.get_method()
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = AdapterJogClient("http://127.0.0.1:8765/", timeout_seconds=1.25)
    response = client.set_work_coordinate("Z", -1.25)

    assert response == {"status": 0, "message": "ok"}
    assert captured == {
        "url": "http://127.0.0.1:8765/api/cnc/work-coordinate",
        "timeout": 1.25,
        "payload": {"axis": "Z", "value": -1.25},
        "method": "POST",
    }


def test_start_continuous_jog_posts_adapter_payload(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["method"] = request.get_method()
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = AdapterJogClient("http://127.0.0.1:8765/", timeout_seconds=3.5)
    response = client.start_continuous_jog("X", 1, 25)

    assert response == {"status": 0, "message": "ok"}
    assert captured == {
        "url": "http://127.0.0.1:8765/api/cnc/jog",
        "timeout": 3.5,
        "payload": {
            "axis": "X",
            "direction": 1,
            "step": 1.0,
            "velocity_factor": 0.25,
            "continuous": True,
        },
        "method": "POST",
    }


def test_move_relative_posts_step_jog_payload(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = AdapterJogClient("http://adapter.local")
    client.move_relative("Z", -0.1, 150)

    assert captured == {
        "url": "http://adapter.local/api/cnc/jog",
        "payload": {
            "axis": "Z",
            "direction": -1,
            "step": 0.1,
            "velocity_factor": 1.0,
            "continuous": False,
        },
    }


def test_stop_continuous_jog_posts_without_body(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["data"] = request.data
        captured["method"] = request.get_method()
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = AdapterJogClient("http://127.0.0.1:8000")
    client.stop_continuous_jog()

    assert captured == {
        "url": "http://127.0.0.1:8000/api/cnc/jog/stop",
        "data": None,
        "method": "POST",
    }

def test_resolve_adapter_url_prefers_explicit_url(monkeypatch):
    monkeypatch.setenv("ERP_CNC_ADAPTER_URL", "http://127.0.0.1:9000")

    assert resolve_adapter_url("http://127.0.0.1:7000/") == "http://127.0.0.1:7000"


def test_resolve_adapter_url_prefers_environment(monkeypatch):
    monkeypatch.setenv("ERP_CNC_ADAPTER_URL", "http://127.0.0.1:9000/")

    assert resolve_adapter_url() == "http://127.0.0.1:9000"


def test_resolve_adapter_url_uses_persisted_adapter_port(monkeypatch):
    monkeypatch.delenv("ERP_CNC_ADAPTER_URL", raising=False)
    monkeypatch.setattr(
        "src.core.config_persistence.load_user_config",
        lambda: {"port": 8123},
    )

    assert resolve_adapter_url() == "http://127.0.0.1:8123"

def test_resolve_icon_path_uses_project_logo(monkeypatch):
    from src.jog_pad import jog_pad

    monkeypatch.setattr(jog_pad.sys, "frozen", False, raising=False)

    assert jog_pad.resolve_icon_path().endswith(str(Path("resources") / "logo.ico"))



def test_resolve_home_icon_path_uses_original_jogpad_home_bitmap(monkeypatch):
    from src.jog_pad import jog_pad

    monkeypatch.setattr(jog_pad.sys, "frozen", False, raising=False)

    assert jog_pad.resolve_home_icon_path().endswith(str(Path("resources") / "jogpad" / "home_x.bmp"))


def test_jog_pad_uses_original_bitmap_icons():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "def resolve_jogpad_icon_path" in text
    assert '"up": "jog_up.bmp"' in text
    assert '"down": "jog_down.bmp"' in text
    assert '"left": "jog_left.bmp"' in text
    assert '"right": "jog_right.bmp"' in text
    assert 'icon_name="jog_up3.bmp"' in text
    assert 'icon_name="jog_down3.bmp"' in text
    assert '"cont": "jog_cont.bmp"' in text
    assert '".001": "jog_0_001.bmp"' in text
    assert '"0.01": "jog_0_01.bmp"' in text
    assert '"0.1": "jog_0_1.bmp"' in text
    assert '"1": "jog_1.bmp"' in text
    assert 'resolve_jogpad_icon_path("jog_user.bmp")' in text
    assert 'resolve_jogpad_icon_path("exit.bmp")' in text
    assert "painter.drawPixmap(inner.toRect(), self._pixmap)" in text

def test_jog_pad_window_is_brought_forward_on_launch():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "window.raise_()" in text
    assert "window.activateWindow()" in text

def test_jog_pad_window_hides_native_close_and_minimize_buttons():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "Qt.CustomizeWindowHint" in text
    assert "Qt.WindowTitleHint" in text
    assert "Qt.WindowCloseButtonHint" not in text
    assert "Qt.WindowMinimizeButtonHint" not in text

def test_jog_pad_window_stays_on_top():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "Qt.WindowStaysOnTopHint" in text
    assert "Qt.WindowActive" in text

def test_proceed_button_hides_pad():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert 'self.setToolTip("Proceed")' in text
    assert "def on_close_pressed" in text
    assert "self.window().hide()" in text

def test_jog_pad_displays_machine_style_coordinates():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "CoordinatePoller" in text
    assert "POSITION_POLL_INTERVAL_MS = 1000" in text
    assert "POSITION_READ_TIMEOUT_SECONDS = 5.0" in text
    assert "POSITION_ERROR_DISPLAY_THRESHOLD = 3" in text
    assert "self._build_coordinate_panel()" in text
    assert "class CoordinateReadout" in text
    assert 'for mode, label in (("machine", "Machine"), ("work", "Work"))' in text
    assert 'self.coordinate_mode = "work"' in text
    assert 'self.coordinate_labels[axis].setText(f"{float(value):.3f}")' in text


def test_jog_pad_shows_zero_axis_buttons():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "class ZeroAxisButton" in text
    assert "ZeroAxisButton(axis, self.theme)" in text
    assert 'resolve_jogpad_icon_path(f"home_{axis.lower()}.bmp")' in text
    assert "painter.drawPixmap(inner.toRect(), self._pixmap)" in text
    assert "zero_button.clicked.connect" in text
    assert "action_zero_work_axis" in text
    assert "CNC_UIOACTION_HOMESEQ" not in text
    assert "CncSendToGUI" not in text


def test_coordinate_widgets_use_configured_accent_blue():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "ACCENT_BLUE =" in text
    assert "fill = self.theme.accent_pressed if self.isDown() else self.theme.accent" in text
    assert "background: {accent};" in text
    assert "accent_soft = self.theme.accent.lighter(165).name()" in text
    assert "accent_border_dark = self.theme.accent.darker(135).name()" in text
    assert "background: {accent_soft};" in text
    assert "border-top: 2px solid {accent_border_dark};" in text
    assert "#2B56A3" not in text
    assert "#2C56A2" not in text


def test_coordinate_panel_has_extra_gap_after_jog_buttons():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "motion_row.addWidget(z_panel, 0, Qt.AlignTop)" in text
    assert "motion_row.addSpacing(54)" in text
    assert "motion_row.addWidget(self._build_coordinate_panel(), 0, Qt.AlignTop)" in text

def test_coordinate_readouts_open_g92_dialog():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "clicked = pyqtSignal(str)" in text
    assert "readout.clicked.connect(self.show_work_coordinate_dialog)" in text
    assert "def show_work_coordinate_dialog" in text
    assert 'label = QLabel(f"G92{axis}")' in text
    assert "def action_set_work_coordinate" in text
    assert "self.adapter_client.set_work_coordinate(axis, value)" in text

def test_coordinate_g92_dialog_is_work_tab_only():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert 'if self.coordinate_mode != "work":' in text
    assert "Machine coordinates are read-only" in text
    assert "self.coordinate_readouts[axis.lower()] = readout" in text

def test_jog_pad_has_home_status_button():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "class HomeStatusButton" in text
    assert "self.home_button = HomeStatusButton(self.theme)" in text
    assert "row.addWidget(self.home_button)" in text
    assert "CncGetAllAxesHomed" not in text
    assert "poller.homed_status_received.connect(self.on_homed_status_received)" in text
    assert 'payload.get("allAxesHomed")' in text
    assert "self._position_error_count = 0" in text
    assert "Position read failed transiently" in text
    assert "self.home_button.clicked.connect(self.action_home_all_axes)" in text
    assert "self.adapter_client.home_all_axes" in text
    assert "G28 X0 Y0 Z0" in text
    assert "resolve_home_icon_path" in text
    assert "QPixmap(home_icon_path)" in text
    assert "painter.drawPixmap(inner.toRect(), self._home_pixmap)" in text



def test_jog_pad_starts_and_stops_pause_hold_thread():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "class PauseHoldThread(QThread)" in text
    assert "self.client.pause_job()" in text
    assert "status_received = pyqtSignal(str)" in text
    assert "thread.status_received.connect(self.on_pause_hold_status)" in text
    assert "def on_pause_hold_status" in text
    assert "self._pause_hold_active = True" in text
    assert "--pause-hold-interval-ms" in text
    assert "self.pause_hold_thread.start()" in text
    assert "QTimer.singleShot(100, self.jog_pad.start_background_threads)" in text
    assert "def stop_background_threads" in text
    assert "self.position_poller.stop()" in text
    assert "self.pause_hold_thread.stop()" in text


def test_jog_pad_has_visible_command_status_for_failures():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "command_failed = pyqtSignal(str, str)" in text
    assert "self.command_sender.command_failed.connect(self.on_command_failed)" in text
    assert 'self.status_label = QLabel("Ready")' in text
    assert 'self.status_label.setObjectName("statusLabel")' in text
    assert "def on_command_failed" in text
    assert "Adapter jog request failed: {label}: status={status}" in text
    assert "Adapter jog request succeeded: {label}: status={status}" in text
    assert 'if label.startswith("start ")' in text
    assert "self._active_axis = None" in text
    assert "blocked by pause hold" in text
    assert "def _looks_like_paused_state_error" in text
    assert "def set_status" in text
    assert "#B00020" in text


def test_resolve_reset_icon_path_uses_project_reset_bitmap(monkeypatch):
    from src.jog_pad import jog_pad

    monkeypatch.setattr(jog_pad.sys, "frozen", False, raising=False)

    assert jog_pad.resolve_reset_icon_path().endswith(str(Path("resources") / "reset.bmp"))


def test_jog_pad_has_reset_button():
    text = Path(__file__).resolve().parent.parent.joinpath("src", "jog_pad", "jog_pad.py").read_text(encoding="utf-8")

    assert "resolve_reset_icon_path" in text
    assert "class BitmapCommandButton" in text
    assert 'self.reset_button = BitmapCommandButton("Reset CNC errors", resolve_reset_icon_path(), "RESET", self.theme)' in text
    assert "row.addWidget(self.reset_button)" in text
    assert "self.reset_button.clicked.connect(self.action_reset)" in text
    assert "def action_reset" in text
    assert "self.adapter_client.reset" in text
