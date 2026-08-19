from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from taskmanager.infrastructure.paths import app_dir

LOCK_NAME = "taskmanager.lock"
SHOW_PAYLOAD = b"show\n"


def lock_path(directory: Path | None = None) -> Path:
    return (directory or app_dir()) / LOCK_NAME


def local_server_name(directory: Path | None = None) -> str:
    root = (directory or app_dir()).resolve()
    digest = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:16]
    return f"taskmanager-{digest}"


class InstanceGuard(QObject):
    """One process per app_dir(): lock file plus a local socket to raise the first window."""

    show_requested = Signal()

    def __init__(self, directory: Path | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._directory = Path(directory) if directory is not None else None
        self._lock = QLockFile(str(lock_path(self._directory)))
        self._lock.setStaleLockTime(30_000)
        self._server: QLocalServer | None = None

    def try_become_primary(self) -> bool:
        if not self._lock.tryLock(100):
            return False
        name = local_server_name(self._directory)
        QLocalServer.removeServer(name)
        server = QLocalServer(self)
        if not server.listen(name):
            self._lock.unlock()
            return False
        server.newConnection.connect(self._on_connection)
        self._server = server
        return True

    def notify_existing(self) -> bool:
        socket = QLocalSocket(self)
        socket.connectToServer(local_server_name(self._directory))
        if not socket.waitForConnected(1000):
            socket.deleteLater()
            return False
        socket.write(SHOW_PAYLOAD)
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        if socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            socket.waitForDisconnected(1000)
        socket.deleteLater()
        return True

    def release(self) -> None:
        if self._server is not None:
            name = self._server.serverName()
            self._server.close()
            QLocalServer.removeServer(name)
            self._server = None
        if self._lock.isLocked():
            self._lock.unlock()

    def _on_connection(self) -> None:
        if self._server is None:
            return
        socket = self._server.nextPendingConnection()
        if socket is not None:
            socket.close()
            socket.deleteLater()
        self.show_requested.emit()
