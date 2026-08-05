from __future__ import annotations

import json
import logging
import platform
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


GITHUB_LATEST_URL = (
    "https://api.github.com/repos/ShiragG/TaskManager/releases/latest"
)
USER_AGENT = "TaskManager-UpdateCheck"

logger = logging.getLogger(__name__)


class UpdateError(Exception):
    """Failed to check or download an update."""


class UpdateCancelled(UpdateError):
    """Download was cancelled by the user."""


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int | None = None


@dataclass(frozen=True)
class LatestRelease:
    tag: str
    version: str
    assets: list[ReleaseAsset]


ProgressCallback = Callable[[int, int | None, float], None]
CancelPredicate = Callable[[], bool]


_VERSION_RE = re.compile(
    r"^v?(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?",
    re.IGNORECASE,
)


def parse_version(tag_or_version: str) -> tuple[int, int, int]:
    """Parse ``vX.Y.Z`` / ``X.Y.Z`` into a comparable triple."""
    text = tag_or_version.strip()
    match = _VERSION_RE.match(text)
    if not match:
        raise UpdateError(f"Не удалось разобрать версию: {tag_or_version!r}")
    major = int(match.group("major"))
    minor = int(match.group("minor") or 0)
    patch = int(match.group("patch") or 0)
    return major, minor, patch


def version_is_newer(remote: str, current: str) -> bool:
    return parse_version(remote) > parse_version(current)


def asset_name_for_platform(system: str | None = None) -> str:
    name = (system or platform.system()).lower()
    if name.startswith("win"):
        return "TaskManager.exe"
    return "TaskManager"


def pick_asset(
    assets: list[ReleaseAsset], asset_name: str
) -> ReleaseAsset | None:
    for asset in assets:
        if asset.name == asset_name:
            return asset
    return None


def parse_release_payload(payload: dict[str, Any]) -> LatestRelease:
    tag = str(payload.get("tag_name") or "").strip()
    if not tag:
        raise UpdateError("В ответе GitHub нет tag_name")
    version = tag[1:] if tag.lower().startswith("v") else tag
    assets: list[ReleaseAsset] = []
    for raw in payload.get("assets") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")
        url = str(raw.get("browser_download_url") or "")
        if not name or not url:
            continue
        size_raw = raw.get("size")
        size = int(size_raw) if isinstance(size_raw, int) else None
        assets.append(ReleaseAsset(name=name, download_url=url, size=size))
    return LatestRelease(tag=tag, version=version, assets=assets)


class UpdateService:
    """Check GitHub Releases and download the platform binary (no self-replace)."""

    def __init__(
        self,
        *,
        api_url: str = GITHUB_LATEST_URL,
        opener: Any | None = None,
    ) -> None:
        self.api_url = api_url
        self._opener = opener

    def fetch_latest_release(self) -> LatestRelease:
        raw = self._http_get_json(self.api_url)
        if not isinstance(raw, dict):
            raise UpdateError("Некорректный ответ GitHub API")
        release = parse_release_payload(raw)
        logger.debug(
            "Fetched latest release tag=%s assets=%d",
            release.tag,
            len(release.assets),
        )
        return release

    def is_newer(self, remote_tag: str, current_version: str) -> bool:
        try:
            return version_is_newer(remote_tag, current_version)
        except UpdateError:
            return False

    def find_asset(
        self, release: LatestRelease, asset_name: str | None = None
    ) -> ReleaseAsset | None:
        name = asset_name or asset_name_for_platform()
        return pick_asset(release.assets, name)

    def download_asset(
        self,
        asset: ReleaseAsset,
        dest: Path,
        *,
        progress_callback: ProgressCallback | None = None,
        should_cancel: CancelPredicate | None = None,
        chunk_size: int = 64 * 1024,
    ) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            asset.download_url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
        )
        cancelled = False
        try:
            if self._opener is not None:
                response_cm = self._opener.open(request)
            else:
                response_cm = urllib.request.urlopen(request, timeout=120)
            with response_cm as resp, dest.open("wb") as out:
                total = asset.size
                if total is None:
                    length = resp.headers.get("Content-Length")
                    if length and length.isdigit():
                        total = int(length)
                bytes_done = 0
                started = time.monotonic()
                last_report = started
                while True:
                    if should_cancel is not None and should_cancel():
                        cancelled = True
                        break
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out.write(chunk)
                    bytes_done += len(chunk)
                    now = time.monotonic()
                    if progress_callback is not None and (
                        now - last_report >= 0.1 or (total and bytes_done >= total)
                    ):
                        elapsed = max(now - started, 1e-6)
                        speed = bytes_done / elapsed
                        progress_callback(bytes_done, total, speed)
                        last_report = now
        except UpdateCancelled:
            raise
        except urllib.error.URLError as exc:
            logger.exception("Update download failed")
            self._cleanup_partial(dest)
            raise UpdateError(f"Не удалось скачать обновление: {exc}") from exc
        except OSError as exc:
            logger.exception("Update save failed")
            self._cleanup_partial(dest)
            raise UpdateError(f"Не удалось сохранить файл: {exc}") from exc

        if cancelled:
            self._cleanup_partial(dest)
            logger.info("Update download cancelled, removed partial file %s", dest)
            raise UpdateCancelled("Загрузка отменена")
        logger.info("Update downloaded to %s (%s bytes)", dest, dest.stat().st_size)
        return dest

    @staticmethod
    def _cleanup_partial(dest: Path) -> None:
        try:
            if dest.is_file():
                dest.unlink()
        except OSError:
            logger.exception("Failed to remove partial update file: %s", dest)

    def _http_get_json(self, url: str) -> Any:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.github+json",
            },
        )
        try:
            if self._opener is not None:
                with self._opener.open(request) as resp:
                    body = resp.read()
            else:
                with urllib.request.urlopen(request, timeout=30) as resp:
                    body = resp.read()
        except urllib.error.HTTPError as exc:
            logger.exception("GitHub API HTTP error")
            raise UpdateError(f"GitHub API: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            logger.exception("GitHub API network error")
            raise UpdateError(f"Нет сети или GitHub недоступен: {exc}") from exc
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.exception("GitHub API JSON parse error")
            raise UpdateError("Некорректный JSON от GitHub") from exc
