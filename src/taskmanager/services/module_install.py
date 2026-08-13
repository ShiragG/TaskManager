"""Download Source module release zips from GitHub."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from taskmanager.infrastructure.github_http import (
    github_urlopen,
    wrap_github_url_error,
)
from taskmanager.services.module_loader import modules_dir
from taskmanager.services.source_protocol import SourceModuleError

logger = logging.getLogger(__name__)

USER_AGENT = "TaskManager-SourceModules"


@dataclass(frozen=True)
class ModuleReleaseAsset:
    name: str
    download_url: str
    size: int | None = None


@dataclass(frozen=True)
class ModuleLatestRelease:
    tag: str
    version: str
    assets: list[ModuleReleaseAsset]


def parse_github_repo(url: str) -> tuple[str, str]:
    """Return (owner, repo) from a GitHub URL or owner/repo string."""
    text = (url or "").strip().rstrip("/")
    if not text:
        raise SourceModuleError("Укажите URL репозитория GitHub модуля")
    if re.fullmatch(r"[\w.-]+/[\w.-]+", text):
        owner, repo = text.split("/", 1)
        return owner, repo.removesuffix(".git")
    parsed = urlparse(text)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise SourceModuleError(f"Ожидается репозиторий GitHub: {url}")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise SourceModuleError(f"Некорректный URL репозитория: {url}")
    return parts[0], parts[1].removesuffix(".git")


def github_latest_api_url(owner: str, repo: str) -> str:
    return f"https://api.github.com/repos/{owner}/{repo}/releases/latest"


def _http_json(url: str) -> dict | list:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with github_urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise SourceModuleError(
            f"GitHub API ошибка {exc.code}: {body or exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise SourceModuleError(wrap_github_url_error(exc)) from exc


def fetch_latest_module_release(github_repo: str) -> ModuleLatestRelease:
    owner, repo = parse_github_repo(github_repo)
    data = _http_json(github_latest_api_url(owner, repo))
    if not isinstance(data, dict):
        raise SourceModuleError("Неожиданный ответ GitHub Releases")
    tag = str(data.get("tag_name") or "")
    if not tag:
        raise SourceModuleError("В релизе нет tag_name")
    version = tag.lstrip("vV")
    assets: list[ModuleReleaseAsset] = []
    for raw in data.get("assets") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")
        url = str(raw.get("browser_download_url") or "")
        if not name or not url:
            continue
        size = raw.get("size")
        assets.append(
            ModuleReleaseAsset(
                name=name,
                download_url=url,
                size=int(size) if isinstance(size, int) else None,
            )
        )
    return ModuleLatestRelease(tag=tag, version=version, assets=assets)


def pick_module_zip_asset(assets: list[ModuleReleaseAsset]) -> ModuleReleaseAsset:
    zips = [a for a in assets if a.name.lower().endswith(".zip")]
    if not zips:
        raise SourceModuleError("В релизе нет zip-артефакта модуля")
    # Prefer names containing 'source' or 'plugin'
    preferred = [
        a
        for a in zips
        if any(k in a.name.lower() for k in ("source", "plugin", "razr", "module"))
    ]
    return preferred[0] if preferred else zips[0]


def download_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with github_urlopen(req, timeout=120) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise SourceModuleError(f"Скачивание не удалось ({exc.code})") from exc
    except urllib.error.URLError as exc:
        raise SourceModuleError(wrap_github_url_error(exc, download=True)) from exc


def install_module_zip(
    github_repo: str,
    *,
    module_id: str | None = None,
    base: Path | None = None,
) -> Path:
    """Download latest release zip into modules/; return path to installed zip."""
    release = fetch_latest_module_release(github_repo)
    asset = pick_module_zip_asset(release.assets)
    data = download_bytes(asset.download_url)

    # Prefer module_id from caller; else derive from asset / repo name
    dest_id = (module_id or "").strip()
    if not dest_id:
        stem = Path(asset.name).stem
        dest_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-") or "module"

    root = modules_dir(base)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / f"{dest_id}.zip"
    dest.write_bytes(data)
    logger.info(
        "Installed source module zip %s -> %s (release %s)",
        asset.name,
        dest,
        release.tag,
    )
    return dest
