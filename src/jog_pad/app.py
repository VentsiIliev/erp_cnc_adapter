from __future__ import annotations

import argparse
import sys
from typing import Optional

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtWidgets import QApplication, QMainWindow

from .config import jog_pad_ipc_server_name, resolve_adapter_url, resolve_icon_path
from .pad import JogPad


class JogPadWindow(QMainWindow):
    def __init__(self, adapter_url: Optional[str] = None, pause_hold_interval_ms: int = 0) -> None:
        super().__init__()
        self.setWindowTitle("Jog Pad")
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowStaysOnTopHint)
        icon_path = resolve_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1165, 497)
        self.setMinimumSize(1060, 470)
        self.jog_pad = JogPad(adapter_url=adapter_url, pause_hold_interval_ms=pause_hold_interval_ms)
        self.setCentralWidget(self.jog_pad)
        self._background_start_scheduled = False

    def showEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().showEvent(event)
        QTimer.singleShot(0, self.jog_pad.clear_cnc_messages_on_show)
        if self._background_start_scheduled:
            return
        self._background_start_scheduled = True
        QTimer.singleShot(100, self.jog_pad.start_background_threads)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.jog_pad.stop_background_threads()
        self.jog_pad.command_sender.close()
        super().closeEvent(event)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ERP CNC Adapter jog pad")
    parser.add_argument(
        "--adapter-url",
        default=None,
        help="Base URL for the running adapter. Defaults to ERP_CNC_ADAPTER_URL or the configured adapter port.",
    )
    parser.add_argument(
        "--pause-hold-interval-ms",
        type=int,
        default=0,
        help="Milliseconds between pause requests while the jog pad is open. Use 0 to disable.",
    )
    return parser.parse_args(argv)


def _signal_existing_jog_pad(server_name: str) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(100):
        return False
    socket.write(b"show")
    socket.flush()
    socket.waitForBytesWritten(100)
    socket.disconnectFromServer()
    return True


def _install_jog_pad_ipc_server(server_name: str, window: JogPadWindow) -> Optional[QLocalServer]:
    server = QLocalServer(window)

    def on_new_connection() -> None:
        while server.hasPendingConnections():
            socket = server.nextPendingConnection()
            socket.readyRead.connect(lambda sock=socket: sock.readAll())
            window.show()
            window.setWindowState(window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
            window.raise_()
            window.activateWindow()
            QTimer.singleShot(0, window.jog_pad.clear_cnc_messages_on_show)
            window.jog_pad.start_background_threads()

    server.newConnection.connect(on_new_connection)
    if server.listen(server_name):
        return server

    QLocalServer.removeServer(server_name)
    if server.listen(server_name):
        return server
    return None


def main() -> int:
    args = _parse_args(sys.argv[1:])
    adapter_url = resolve_adapter_url(args.adapter_url)

    app = QApplication(sys.argv)
    app.setApplicationName("Jog Pad")
    app.setQuitOnLastWindowClosed(False)
    icon_path = resolve_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    app.setStyle("Fusion")

    server_name = jog_pad_ipc_server_name(adapter_url)
    if _signal_existing_jog_pad(server_name):
        return 0

    window = JogPadWindow(adapter_url=adapter_url, pause_hold_interval_ms=args.pause_hold_interval_ms)
    window._jog_pad_ipc_server = _install_jog_pad_ipc_server(server_name, window)
    window.show()
    window.setWindowState(window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
    window.raise_()
    window.activateWindow()
    return app.exec_()
