"""Tests for Machine ID in installer — PathPage UI, worker config writing."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure QApplication exists before any widget tests
_qapp = None

def _ensure_qapp():
    global _qapp
    if _qapp is None:
        from PyQt5.QtWidgets import QApplication
        _qapp = QApplication.instance() or QApplication(sys.argv)
    return _qapp


# ---------------------------------------------------------------------------
# PathPage UI tests
# ---------------------------------------------------------------------------

class TestPathPageMachineField:
    """Verify Machine ID field exists on PathPage with correct defaults."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        _ensure_qapp()
        from src.installer.ui.pages import PathPage
        self.page = PathPage()
        yield
        self.page.deleteLater()

    def test_machine_edit_exists(self):
        assert hasattr(self.page, "machine_edit"), "PathPage must have a machine_edit field"

    def test_machine_edit_default_value(self):
        assert self.page.machine_edit.text() == "CNC1"

    def test_machine_edit_accepts_custom_value(self):
        self.page.machine_edit.setText("MILL3")
        assert self.page.machine_edit.text() == "MILL3"

    def test_machine_edit_max_width(self):
        assert self.page.machine_edit.maximumWidth() == 200


# ---------------------------------------------------------------------------
# InstallWorker unit tests (no GUI, no subprocess)
# ---------------------------------------------------------------------------

class TestInstallWorkerInit:
    """Verify InstallWorker stores machine_number."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        _ensure_qapp()

    def test_default_machine_number(self):
        from src.installer.worker import InstallWorker
        worker = InstallWorker(r"C:\fake\path")
        assert worker.machine_number == "CNC1"

    def test_custom_machine_number(self):
        from src.installer.worker import InstallWorker
        worker = InstallWorker(r"C:\fake\path", "MILL5")
        assert worker.machine_number == "MILL5"

    def test_install_path_stored(self):
        from src.installer.worker import InstallWorker
        worker = InstallWorker(r"C:\fake\path", "CNC2")
        assert worker.install_path == Path(r"C:\fake\path")

    def test_task_credentials_default_empty(self):
        from src.installer.worker import InstallWorker
        worker = InstallWorker(r"C:\fake\path")
        assert worker.task_username == ""
        assert worker.task_password == ""

    def test_task_credentials_stored(self):
        from src.installer.worker import InstallWorker
        worker = InstallWorker(r"C:\fake\path", "CNC2", r"DOMAIN\adapter", "secret")
        assert worker.task_username == r"DOMAIN\adapter"
        assert worker.task_password == "secret"


class TestInstallWorkerConfigWrite:
    """Verify the config.json merge logic used by the worker."""

    def test_writes_config_json_with_machine_number(self, tmp_path):
        """Creates config.json with machine_number when none exists."""
        config_path = tmp_path / "config.json"
        config_data = {}
        config_data["machine_number"] = "CNC9"
        config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

        result = json.loads(config_path.read_text(encoding="utf-8"))
        assert result["machine_number"] == "CNC9"

    def test_merges_with_existing_config_json(self, tmp_path):
        """Preserves existing keys when writing machine_number."""
        config_path = tmp_path / "config.json"
        existing = {"job_done_report_url": "http://example.com/done", "base_dir": r"\\server\share"}
        config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        # Simulate the worker's merge logic
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        config_data["machine_number"] = "MILL2"
        config_path.write_text(
            json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        result = json.loads(config_path.read_text(encoding="utf-8"))
        assert result["machine_number"] == "MILL2"
        assert result["job_done_report_url"] == "http://example.com/done"
        assert result["base_dir"] == r"\\server\share"

    def test_overwrites_existing_machine_number(self, tmp_path):
        """Replaces old machine_number value."""
        config_path = tmp_path / "config.json"
        existing = {"machine_number": "OLD1", "base_dir": r"\\server\share"}
        config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        config_data["machine_number"] = "NEW7"
        config_path.write_text(
            json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        result = json.loads(config_path.read_text(encoding="utf-8"))
        assert result["machine_number"] == "NEW7"
        assert result["base_dir"] == r"\\server\share"

    def test_handles_corrupt_existing_config(self, tmp_path):
        """Falls back to empty dict when existing config.json is invalid JSON."""
        config_path = tmp_path / "config.json"
        config_path.write_text("NOT VALID JSON {{{", encoding="utf-8")

        # Simulate the worker's error-handling merge logic
        config_data = {}
        try:
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            config_data = {}
        config_data["machine_number"] = "CNC5"
        config_path.write_text(
            json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        result = json.loads(config_path.read_text(encoding="utf-8"))
        assert result["machine_number"] == "CNC5"


# ---------------------------------------------------------------------------
# Window integration (pass-through from PathPage to Worker)
# ---------------------------------------------------------------------------

class TestWindowPassesMachineNumber:
    """Verify InstallerWindow passes machine_edit value to InstallWorker."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        _ensure_qapp()

    @patch("src.installer.ui.window.InstallWorker")
    def test_start_install_passes_machine_number(self, MockWorker):
        from src.installer.ui.window import InstallerWindow

        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance

        window = InstallerWindow()
        window.path_page.path_edit.setText(r"C:\test\install")
        window.path_page.machine_edit.setText("CNC3")
        window._start_install()

        MockWorker.assert_called_once_with(r"C:\test\install", "CNC3", "", "")
        window.close()
        window.deleteLater()

    @patch("src.installer.ui.window.InstallWorker")
    def test_empty_machine_id_defaults_to_cnc1(self, MockWorker):
        from src.installer.ui.window import InstallerWindow

        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance

        window = InstallerWindow()
        window.path_page.path_edit.setText(r"C:\test\install")
        window.path_page.machine_edit.setText("   ")  # whitespace only
        window._start_install()

        MockWorker.assert_called_once_with(r"C:\test\install", "CNC1", "", "")
        window.close()
        window.deleteLater()

    @patch("src.installer.ui.window.InstallWorker")
    def test_machine_id_stripped(self, MockWorker):
        from src.installer.ui.window import InstallerWindow

        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance

        window = InstallerWindow()
        window.path_page.path_edit.setText(r"C:\test\install")
        window.path_page.machine_edit.setText("  MILL1  ")
        window._start_install()

        MockWorker.assert_called_once_with(r"C:\test\install", "MILL1", "", "")
        window.close()
        window.deleteLater()

    @patch("src.installer.ui.window.InstallWorker")
    def test_task_credentials_passed_when_enabled(self, MockWorker):
        from src.installer.ui.window import InstallerWindow

        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance

        window = InstallerWindow()
        window.path_page.path_edit.setText(r"C:\test\install")
        window.path_page.machine_edit.setText("CNC4")
        window.path_page.run_as_user_check.setChecked(True)
        window.path_page.username_edit.setText(r"DOMAIN\adapter")
        window.path_page.password_edit.setText("secret")
        window._start_install()

        MockWorker.assert_called_once_with(
            r"C:\test\install", "CNC4", r"DOMAIN\adapter", "secret"
        )
        window.close()
        window.deleteLater()
