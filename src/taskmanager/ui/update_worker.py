from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from taskmanager.services.module_install import (
    ModuleLatestRelease,
    ModuleReleaseAsset,
    download_bytes,
    fetch_latest_module_release,
    pick_module_zip_asset,
)
from taskmanager.services.settings_service import SourceModuleConfig
from taskmanager.services.source_protocol import SourceModuleError
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


@dataclass(frozen=True)
class ModuleUpdateOffer:
    config: SourceModuleConfig
    release: ModuleLatestRelease
    asset: ModuleReleaseAsset


class ModuleUpdateCheckWorker(QObject):
    """Fetch enabled module releases and keep those newer than installed."""

    succeeded = Signal(object)  # list[ModuleUpdateOffer]
    failed = Signal(str)

    def __init__(self, modules: list[SourceModuleConfig]) -> None:
        super().__init__()
        self._modules = list(modules)

    def run(self) -> None:
        offers: list[ModuleUpdateOffer] = []
        updater = UpdateService()
        try:
            for cfg in self._modules:
                release = fetch_latest_module_release(cfg.github_repo)
                current = cfg.installed_version.strip() or "0"
                if not updater.is_newer(release.tag, current):
                    continue
                try:
                    asset = pick_module_zip_asset(release.assets)
                except SourceModuleError as exc:
                    logger.error(
                        "Module %s has a newer release but no zip: %s",
                        cfg.module_id or cfg.github_repo,
                        exc,
                    )
                    continue
                offers.append(
                    ModuleUpdateOffer(config=cfg, release=release, asset=asset)
                )
        except SourceModuleError as exc:
            logger.error("Module update check failed: %s", exc)
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected module update check failure")
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(offers)


class ModuleUpdateDownloadWorker(QObject):
    """Download module zip assets; zip write happens on the GUI thread."""

    progress = Signal(str, int, int)  # label, index, total
    succeeded = Signal(object)  # list[tuple[ModuleUpdateOffer, bytes]]
    failed = Signal(str)

    def __init__(self, offers: list[ModuleUpdateOffer]) -> None:
        super().__init__()
        self._offers = list(offers)

    def run(self) -> None:
        payloads: list[tuple[ModuleUpdateOffer, bytes]] = []
        total = len(self._offers)
        try:
            for index, offer in enumerate(self._offers, start=1):
                name = offer.config.display_name or offer.config.module_id or offer.asset.name
                self.progress.emit(f"Загрузка «{name}»…", index, total)
                data = download_bytes(offer.asset.download_url)
                payloads.append((offer, data))
        except SourceModuleError as exc:
            logger.error("Module update download failed: %s", exc)
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected module update download failure")
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(payloads)
