"""Load Source modules from app_dir()/modules/ (zip or directory)."""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from taskmanager.infrastructure.paths import app_dir
from taskmanager.services.source_protocol import (
    SourceModule,
    SourceModuleError,
    SourceUpdateChannel,
    api_version_supported,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PluginManifest:
    id: str
    display_name: str
    version: str
    api_version: str
    entry: str  # "package.module:ClassName"
    path: Path
    update: SourceUpdateChannel = SourceUpdateChannel()


def modules_dir(base: Path | None = None) -> Path:
    return (base or app_dir()) / "modules"


def _read_manifest_from_dir(root: Path) -> dict[str, Any]:
    path = root / "plugin.json"
    if not path.is_file():
        raise SourceModuleError(f"Нет plugin.json в {root}")
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise SourceModuleError(f"Некорректный plugin.json в {root}")
    return data


def _read_manifest_from_zip(zip_path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            try:
                raw = zf.read("plugin.json")
            except KeyError as exc:
                raise SourceModuleError(
                    f"В архиве нет plugin.json: {zip_path.name}"
                ) from exc
    except zipfile.BadZipFile as exc:
        raise SourceModuleError(f"Повреждённый zip модуля: {zip_path.name}") from exc
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise SourceModuleError(f"Некорректный plugin.json в {zip_path.name}")
    return data


def _parse_update_channel(data: dict[str, Any]) -> SourceUpdateChannel:
    raw = data.get("update")
    if not isinstance(raw, dict):
        # Flat optional keys for older manifests
        return SourceUpdateChannel(
            asset_name=str(data.get("update_asset_name") or "").strip(),
            asset_pattern=str(data.get("update_asset_pattern") or "").strip(),
        )
    return SourceUpdateChannel(
        asset_name=str(raw.get("asset_name") or "").strip(),
        asset_pattern=str(raw.get("asset_pattern") or "").strip(),
    )


def parse_manifest(data: dict[str, Any], path: Path) -> PluginManifest:
    required = ("id", "display_name", "version", "api_version", "entry")
    missing = [k for k in required if not str(data.get(k, "")).strip()]
    if missing:
        raise SourceModuleError(
            f"plugin.json неполный ({path}): нет {', '.join(missing)}"
        )
    return PluginManifest(
        id=str(data["id"]).strip(),
        display_name=str(data["display_name"]).strip(),
        version=str(data["version"]).strip(),
        api_version=str(data["api_version"]).strip(),
        entry=str(data["entry"]).strip(),
        path=path,
        update=_parse_update_channel(data),
    )


def discover_module_paths(base: Path | None = None) -> list[Path]:
    root = modules_dir(base)
    if not root.is_dir():
        return []
    found: list[Path] = []
    for child in sorted(root.iterdir()):
        if child.is_file() and child.suffix.lower() == ".zip":
            found.append(child)
        elif child.is_dir() and (child / "plugin.json").is_file():
            found.append(child)
    return found


def load_manifest(path: Path) -> PluginManifest:
    if path.is_dir():
        data = _read_manifest_from_dir(path)
    elif path.is_file() and path.suffix.lower() == ".zip":
        data = _read_manifest_from_zip(path)
    else:
        raise SourceModuleError(f"Неизвестный артефакт модуля: {path}")
    return parse_manifest(data, path)


def _evict_import_caches(search_path: Path) -> None:
    """Drop stale zipimport / path finder state so zip replace reloads fresh code."""
    importlib.invalidate_caches()
    try:
        import zipimport

        cache = getattr(zipimport, "_zip_directory_cache", None)
        if isinstance(cache, dict):
            # Clear whole cache: other tmp zips with the same package name otherwise
            # shadow a newly replaced artifact via path_importer_cache.
            cache.clear()
    except Exception:
        pass
    for key in list(sys.path_importer_cache):
        key_s = str(key)
        try:
            if key_s.endswith(".zip") or ".zip/" in key_s or ".zip\\" in key_s:
                sys.path_importer_cache.pop(key, None)
            elif Path(key).resolve() == search_path.resolve():
                sys.path_importer_cache.pop(key, None)
        except OSError:
            sys.path_importer_cache.pop(key, None)


def _import_entry(entry: str, search_path: Path) -> Any:
    if ":" not in entry:
        raise SourceModuleError(f"entry должен быть module:Class — получено {entry!r}")
    module_name, class_name = entry.split(":", 1)
    module_name = module_name.strip()
    class_name = class_name.strip()
    if not module_name or not class_name:
        raise SourceModuleError(f"Некорректный entry: {entry!r}")

    path_str = str(search_path.resolve())
    # Always put this artifact first; remove afterward so other zips cannot shadow.
    while path_str in sys.path:
        sys.path.remove(path_str)
    sys.path.insert(0, path_str)
    try:
        # Evict prior loads of this module and all parent packages so a stale
        # package __path__ cannot pull submodules from an older zip.
        evict_names = {module_name, f"_tm_{module_name}_"}
        parts = module_name.split(".")
        for i in range(len(parts)):
            evict_names.add(".".join(parts[: i + 1]))
        for key in list(sys.modules):
            if key in evict_names or any(
                key.startswith(name + ".") for name in evict_names
            ):
                del sys.modules[key]
        _evict_import_caches(search_path)
        mod = importlib.import_module(module_name)
        try:
            cls = getattr(mod, class_name)
        except AttributeError as exc:
            raise SourceModuleError(
                f"В модуле {module_name} нет класса {class_name}"
            ) from exc
        return cls
    except SourceModuleError:
        raise
    except Exception as exc:
        raise SourceModuleError(
            f"Не удалось загрузить {entry}: {exc}", cause=exc
        ) from exc
    finally:
        while path_str in sys.path:
            try:
                sys.path.remove(path_str)
            except ValueError:
                break


def _validate_instance(obj: Any, manifest: PluginManifest) -> SourceModule:
    from taskmanager.services.source_protocol import SUPPORTED_API_MAJOR

    required_attrs = (
        "id",
        "display_name",
        "version",
        "api_version",
        "configure",
        "list_statuses",
        "list_priorities",
        "list_items",
        "get_item",
        "download_files",
    )
    missing = [name for name in required_attrs if not hasattr(obj, name)]
    if missing:
        raise SourceModuleError(
            f"Модуль {manifest.id}: нет методов/свойств {', '.join(missing)}"
        )
    if not api_version_supported(manifest.api_version):
        raise SourceModuleError(
            f"Модуль {manifest.id}: api_version {manifest.api_version} "
            f"не поддерживается (нужна major={SUPPORTED_API_MAJOR})"
        )
    return obj  # type: ignore[return-value]


def instantiate_module(manifest: PluginManifest) -> SourceModule:
    cls = _import_entry(manifest.entry, manifest.path)
    try:
        instance = cls()
    except Exception as exc:
        raise SourceModuleError(
            f"Не удалось создать экземпляр модуля {manifest.id}: {exc}",
            cause=exc,
        ) from exc
    return _validate_instance(instance, manifest)


def load_all_modules(base: Path | None = None) -> list[tuple[PluginManifest, SourceModule]]:
    """Discover and load modules; skip broken ones with a log warning."""
    loaded: list[tuple[PluginManifest, SourceModule]] = []
    for path in discover_module_paths(base):
        try:
            manifest = load_manifest(path)
            module = instantiate_module(manifest)
            loaded.append((manifest, module))
            logger.info(
                "Loaded source module id=%s version=%s from %s",
                manifest.id,
                manifest.version,
                path,
            )
        except SourceModuleError as exc:
            logger.warning("Skip source module at %s: %s", path, exc)
        except Exception:
            logger.exception("Unexpected error loading source module at %s", path)
    return loaded
