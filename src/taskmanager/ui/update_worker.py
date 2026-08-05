from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from taskmanager.services.update_service import (
    ReleaseAsset,
    UpdateCancelled,
    UpdateError,
    UpdateService,
)

logger = logging.getLogger(__name__)


class UpdateCheckWorker(QObject):
    """Fetch latest release on a worker thread."""

    succeeded = Signal(object)  # LatestRelease
    failed = Signal(str)

    def __init__(self, service: UpdateService | None = None) -> None:
        super().__init__()
        self._service = service or UpdateService()

    def run(self) -> None:
        try:
            release = self._service.fetch_latest_release()
        except UpdateError as exc:
            logger.error("Update check failed: %s", exc)
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected update check failure")
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(release)


class UpdateDownloadWorker(QObject):
    """Download a release asset with progress and cancel support."""

    progress = Signal(int, object, float)  # bytes_done, total|None, speed_bps
    succeeded = Signal(object)  # Path
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        asset: ReleaseAsset,
        dest: Path,
        service: UpdateService | None = None,
    ) -> None:
        super().__init__()
        self._asset = asset
        self._dest = Path(dest)
        self._service = service or UpdateService()
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            path = self._service.download_asset(
                self._asset,
                self._dest,
                progress_callback=self._on_progress,
                should_cancel=lambda: self._cancel,
            )
        except UpdateCancelled:
            logger.info("Update download cancelled")
            self.cancelled.emit()
            return
        except UpdateError as exc:
            logger.error("Update download failed: %s", exc)
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected update download failure")
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(path)

    def _on_progress(self, bytes_done: int, total: int | None, speed: float) -> None:
        self.progress.emit(bytes_done, total, speed)
