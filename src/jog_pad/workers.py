from __future__ import annotations

import queue
import threading
import urllib.error
from typing import Callable, Optional

from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QWidget

from .client import AdapterJogClient
from .config import POSITION_POLL_INTERVAL_MS


class BackgroundCommandSender(QObject):
    """Runs adapter HTTP calls off the Qt UI thread."""

    command_succeeded = pyqtSignal(str, str)
    command_failed = pyqtSignal(str, str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._commands: queue.Queue[Optional[tuple[str, Callable[[], dict]]]] = queue.Queue()
        self._worker = threading.Thread(target=self._run, name="jog-pad-http", daemon=True)
        self._worker.start()

    def submit(self, label: str, command: Callable[[], dict]) -> None:
        self._commands.put((label, command))

    def close(self) -> None:
        self._commands.put(None)

    def _run(self) -> None:
        while True:
            item = self._commands.get()
            if item is None:
                return

            label, command = item
            try:
                response = command()
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                message = f"HTTP {exc.code}: {details}"
                print(f"Adapter jog request failed: {label}: {message}")
                self.command_failed.emit(label, message)
            except Exception as exc:
                message = str(exc)
                print(f"Adapter jog request failed: {label}: {message}")
                self.command_failed.emit(label, message)
            else:
                status = response.get("status", "?")
                message = response.get("message", "")
                if status == 0:
                    print(f"Adapter jog request succeeded: {label}: status={status}, message={message}")
                    self.command_succeeded.emit(label, message)
                else:
                    failure_message = message or f"Adapter returned status {status}"
                    print(f"Adapter jog request failed: {label}: status={status}, message={failure_message}")
                    self.command_failed.emit(label, failure_message)

class CoordinatePoller(QThread):
    positions_received = pyqtSignal(dict)
    error_received = pyqtSignal(str)

    def __init__(self, client: AdapterJogClient, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.client = client
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        while self._running:
            try:
                self.positions_received.emit(self.client.get_positions())
            except Exception as exc:
                self.error_received.emit(str(exc))
            self.msleep(POSITION_POLL_INTERVAL_MS)


class PauseHoldThread(QThread):
    status_received = pyqtSignal(str)
    error_received = pyqtSignal(str)

    def __init__(self, client: AdapterJogClient, interval_ms: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.client = client
        self.interval_ms = max(0, int(interval_ms))
        self._running = self.interval_ms > 0

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        last_message = None
        while self._running:
            try:
                response = self.client.pause_job()
            except Exception as exc:
                self.error_received.emit(str(exc))
            else:
                status = response.get("status", 0)
                message = response.get("message", "")
                if status == 0:
                    if message.startswith("Pause hold active") and message != last_message:
                        self.status_received.emit(message)
                        last_message = message
                else:
                    self.error_received.emit(message or f"Pause hold returned status {status}")
            self.msleep(self.interval_ms)
