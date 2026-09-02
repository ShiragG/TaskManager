"""Orchestrate installed Source modules: load, credentials, list/get/download."""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass, field
from pathlib import Path

from taskmanager.domain import Task, clamp_priority
from taskmanager.infrastructure.credential_crypto import (
    CredentialCryptoError,
    decrypt_secret,
    encrypt_secret,
)
from taskmanager.infrastructure.filesystem import (
    existing_source_file_names,
    source_files_dir,
)
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.inline_images import apply_inline_images_for_task
from taskmanager.services.module_loader import (
    PluginManifest,
    instantiate_module,
    load_all_modules,
    load_manifest,
    modules_dir,
)
from taskmanager.services.module_install import install_module_zip, save_module_zip_bytes
from taskmanager.services.settings_service import Settings, SourceModuleConfig
from taskmanager.services.source_protocol import (
    SourceDraft,
    SourceListPage,
    SourceModule,
    SourceModuleError,
    SourcePriorityOption,
    SourceStatusOption,
)
from taskmanager.services.task_service import (
    CreateTaskRequest,
    ServiceError,
    TaskService,
    UpdateTaskRequest,
)

logger = logging.getLogger(__name__)


def plain_text_to_html(text: str) -> str:
    """Escape plain text and preserve line breaks for Task description HTML."""
    if not text:
        return ""
    escaped = html.escape(text, quote=False)
    return escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>\n")


@dataclass
class LoadedSource:
    config: SourceModuleConfig
    manifest: PluginManifest | None
    module: SourceModule | None
    load_error: str | None = None


@dataclass
class ModuleCatalogCache:
    statuses: list[SourceStatusOption] = field(default_factory=list)
    priorities: list[SourcePriorityOption] = field(default_factory=list)
    error: str | None = None


def _row_to_config(row: dict, *, login: str = "") -> SourceModuleConfig:
    return SourceModuleConfig(
        module_id=str(row.get("module_id") or ""),
        github_repo=str(row.get("github_repo") or ""),
        display_name=str(row.get("display_name") or ""),
        enabled=bool(row.get("enabled")),
        installed_version=str(row.get("installed_version") or ""),
        login=login,
        update_asset_name=str(row.get("update_asset_name") or ""),
        update_asset_pattern=str(row.get("update_asset_pattern") or ""),
    )


class SourceHost:
    """Host facade: discovers modules under app_dir/modules and talks to them."""

    def __init__(
        self,
        repo: SqliteRepository,
        settings: Settings,
        task_service: TaskService,
        *,
        modules_base: Path | None = None,
        pending_migration: list[SourceModuleConfig] | None = None,
    ) -> None:
        self.repo = repo
        self.settings = settings
        self.task_service = task_service
        self.modules_base = modules_base
        self._by_id: dict[str, LoadedSource] = {}
        self._pending_configs: list[SourceModuleConfig] = []
        self._catalogs: dict[str, ModuleCatalogCache] = {}
        if pending_migration:
            self._migrate_legacy_configs(pending_migration)
        self.reload()
        self.refresh_catalogs()

    def _migrate_legacy_configs(self, configs: list[SourceModuleConfig]) -> None:
        for cfg in configs:
            mid = (cfg.module_id or "").strip()
            if not mid:
                # Keep blank GitHub-only rows until install assigns an id
                if cfg.github_repo.strip():
                    self._pending_configs.append(cfg)
                continue
            existing = self.repo.get_source_module(mid)
            if existing is not None:
                continue
            self.repo.upsert_source_module(
                module_id=mid,
                github_repo=cfg.github_repo,
                display_name=cfg.display_name,
                enabled=cfg.enabled,
                installed_version=cfg.installed_version,
                update_asset_name=cfg.update_asset_name,
                update_asset_pattern=cfg.update_asset_pattern,
            )
            logger.info("Migrated source module %s from settings.json to SQLite", mid)

    def _configs_from_registry(self) -> list[SourceModuleConfig]:
        configs: list[SourceModuleConfig] = []
        for row in self.repo.list_source_modules():
            login = ""
            mid = str(row["module_id"])
            creds = self.repo.get_source_credentials(mid)
            if creds is not None:
                login = creds[0]
            configs.append(_row_to_config(row, login=login))
        configs.extend(self._pending_configs)
        return configs

    def save_module_config(self, cfg: SourceModuleConfig) -> None:
        mid = (cfg.module_id or "").strip()
        if not mid:
            # Update pending blank row by github url
            for i, pending in enumerate(self._pending_configs):
                if pending.github_repo == cfg.github_repo:
                    self._pending_configs[i] = cfg
                    break
            else:
                if cfg.github_repo.strip():
                    self._pending_configs.append(cfg)
            return
        # Drop from pending once we have an id
        self._pending_configs = [
            p
            for p in self._pending_configs
            if (p.module_id or "").strip() != mid
            and p.github_repo.strip() != cfg.github_repo.strip()
        ]
        self.repo.upsert_source_module(
            module_id=mid,
            github_repo=cfg.github_repo,
            display_name=cfg.display_name,
            enabled=cfg.enabled,
            installed_version=cfg.installed_version,
            update_asset_name=cfg.update_asset_name,
            update_asset_pattern=cfg.update_asset_pattern,
        )

    def replace_registry(self, configs: list[SourceModuleConfig]) -> None:
        """Persist UI-collected configs (upsert). Removal is via uninstall_module."""
        new_pending: list[SourceModuleConfig] = []
        for cfg in configs:
            mid = (cfg.module_id or "").strip()
            if mid:
                self.save_module_config(cfg)
            elif cfg.github_repo.strip():
                new_pending.append(cfg)
        self._pending_configs = new_pending

    def reload(self) -> None:
        self._by_id.clear()
        configs = self._configs_from_registry()
        loaded_pairs = load_all_modules(self.modules_base)
        seen_ids: set[str] = set()

        for manifest, module in loaded_pairs:
            seen_ids.add(manifest.id)
            cfg = self._config_for_manifest(manifest, configs)
            self._by_id[manifest.id] = LoadedSource(
                config=cfg, manifest=manifest, module=module
            )

        for cfg in configs:
            mid = (cfg.module_id or "").strip()
            if mid and mid not in self._by_id:
                self._by_id[mid] = LoadedSource(
                    config=cfg, manifest=None, module=None, load_error=None
                )
            elif not mid and cfg.github_repo:
                key = f"pending:{cfg.github_repo}"
                if key not in self._by_id:
                    self._by_id[key] = LoadedSource(
                        config=cfg, manifest=None, module=None
                    )

    def _config_for_manifest(
        self, manifest: PluginManifest, configs: list[SourceModuleConfig]
    ) -> SourceModuleConfig:
        for cfg in configs:
            if cfg.module_id == manifest.id:
                cfg.display_name = cfg.display_name or manifest.display_name
                cfg.installed_version = manifest.version
                if manifest.update.asset_name and not cfg.update_asset_name:
                    cfg.update_asset_name = manifest.update.asset_name
                if manifest.update.asset_pattern and not cfg.update_asset_pattern:
                    cfg.update_asset_pattern = manifest.update.asset_pattern
                # Keep registry in sync with loaded zip metadata
                self.repo.upsert_source_module(
                    module_id=cfg.module_id,
                    github_repo=cfg.github_repo,
                    display_name=cfg.display_name,
                    enabled=cfg.enabled,
                    installed_version=cfg.installed_version,
                    update_asset_name=cfg.update_asset_name,
                    update_asset_pattern=cfg.update_asset_pattern,
                )
                return cfg
        # Auto-register discovered module (disabled until user enables)
        cfg = SourceModuleConfig(
            module_id=manifest.id,
            display_name=manifest.display_name,
            installed_version=manifest.version,
            enabled=False,
            github_repo="",
            update_asset_name=manifest.update.asset_name,
            update_asset_pattern=manifest.update.asset_pattern,
        )
        self.repo.upsert_source_module(
            module_id=cfg.module_id,
            github_repo=cfg.github_repo,
            display_name=cfg.display_name,
            enabled=cfg.enabled,
            installed_version=cfg.installed_version,
            update_asset_name=cfg.update_asset_name,
            update_asset_pattern=cfg.update_asset_pattern,
        )
        return cfg

    def list_loaded(self) -> list[LoadedSource]:
        return list(self._by_id.values())

    def enabled_modules(self) -> list[LoadedSource]:
        return [
            s
            for s in self._by_id.values()
            if s.config.enabled and s.module is not None
        ]

    def enabled_modules_with_github(self) -> list[SourceModuleConfig]:
        seen: set[str] = set()
        result: list[SourceModuleConfig] = []
        for loaded in self.list_loaded():
            cfg = loaded.config
            if not cfg.enabled or not cfg.github_repo.strip():
                continue
            key = cfg.module_id or cfg.github_repo
            if key in seen:
                continue
            seen.add(key)
            result.append(cfg)
        return result

    def get(self, module_id: str) -> LoadedSource:
        try:
            return self._by_id[module_id]
        except KeyError as exc:
            raise SourceModuleError(f"Модуль «{module_id}» не найден") from exc

    def set_credentials(self, module_id: str, login: str, password: str) -> None:
        login = login.strip()
        if not login:
            raise SourceModuleError("Логин не может быть пустым")
        try:
            cipher = encrypt_secret(password)
        except CredentialCryptoError as exc:
            raise SourceModuleError(str(exc)) from exc
        self.repo.upsert_source_credentials(module_id, login, cipher)
        # Credentials changed → refresh catalogs for this module
        self.refresh_catalogs(module_ids=[module_id])

    def get_credentials(self, module_id: str) -> tuple[str, str] | None:
        row = self.repo.get_source_credentials(module_id)
        if row is None:
            return None
        login, cipher = row
        try:
            password = decrypt_secret(cipher)
        except CredentialCryptoError as exc:
            raise SourceModuleError(str(exc)) from exc
        return login, password

    def configure_module(self, module_id: str) -> SourceModule:
        loaded = self.get(module_id)
        if loaded.module is None:
            raise SourceModuleError(
                loaded.load_error or f"Модуль «{module_id}» не установлен"
            )
        if not loaded.config.enabled:
            raise SourceModuleError(f"Модуль «{module_id}» выключен в настройках")
        creds = self.get_credentials(module_id)
        if creds is None:
            raise SourceModuleError(
                f"Нет сохранённых учётных данных для модуля «{module_id}»"
            )
        login, password = creds
        try:
            loaded.module.configure(login=login, password=password)
        except SourceModuleError:
            raise
        except Exception as exc:
            raise SourceModuleError(str(exc), cause=exc) from exc
        return loaded.module

    def check_login(self, module_id: str, login: str, password: str) -> None:
        """Try login/password without persisting; refresh session catalogs on OK."""
        mid = (module_id or "").strip()
        if not mid:
            raise SourceModuleError("Модуль ещё не установлен")
        loaded = self.get(mid)
        if loaded.module is None:
            raise SourceModuleError(
                loaded.load_error or f"Модуль «{mid}» не установлен"
            )
        login = login.strip()
        if not login:
            raise SourceModuleError("Укажите логин")
        if not password:
            raise SourceModuleError("Укажите пароль")
        try:
            loaded.module.configure(login=login, password=password)
            statuses = list(loaded.module.list_statuses())
            priorities = list(loaded.module.list_priorities())
        except SourceModuleError:
            raise
        except Exception as exc:
            raise SourceModuleError(str(exc), cause=exc) from exc
        self._catalogs[mid] = ModuleCatalogCache(
            statuses=statuses, priorities=priorities, error=None
        )
        logger.debug(
            "check_login ok module=%s statuses=%s priorities=%s",
            mid,
            len(statuses),
            len(priorities),
        )

    def get_catalog(self, module_id: str) -> ModuleCatalogCache | None:
        return self._catalogs.get(module_id)

    def catalog_error(self, module_id: str) -> str | None:
        cache = self._catalogs.get(module_id)
        return cache.error if cache is not None else None

    def refresh_catalogs(self, module_ids: list[str] | None = None) -> None:
        """Fetch status/priority catalogs for enabled modules (session cache)."""
        targets = module_ids
        if targets is None:
            targets = [
                s.config.module_id
                for s in self.enabled_modules()
                if s.config.module_id
            ]
        for module_id in targets:
            mid = (module_id or "").strip()
            if not mid:
                continue
            try:
                loaded = self.get(mid)
            except SourceModuleError as exc:
                self._catalogs[mid] = ModuleCatalogCache(error=str(exc))
                continue
            if loaded.module is None or not loaded.config.enabled:
                self._catalogs.pop(mid, None)
                continue
            try:
                module = self.configure_module(mid)
                statuses = list(module.list_statuses())
                priorities = list(module.list_priorities())
                self._catalogs[mid] = ModuleCatalogCache(
                    statuses=statuses, priorities=priorities, error=None
                )
                logger.debug(
                    "catalogs refreshed module=%s statuses=%s priorities=%s",
                    mid,
                    len(statuses),
                    len(priorities),
                )
            except SourceModuleError as exc:
                logger.warning("catalog refresh failed module=%s: %s", mid, exc)
                self._catalogs[mid] = ModuleCatalogCache(error=str(exc))
            except Exception as exc:
                logger.exception("catalog refresh failed module=%s", mid)
                self._catalogs[mid] = ModuleCatalogCache(error=str(exc))

    def list_items(
        self,
        module_id: str,
        page: int = 1,
        status_filters: list[str] | None = None,
    ) -> SourceListPage:
        cache = self._catalogs.get(module_id)
        if cache is not None and cache.error:
            raise SourceModuleError(
                f"Каталог статусов недоступен: {cache.error}"
            )
        logger.debug(
            "host list_items module=%s page=%s status_filters=%s",
            module_id,
            page,
            status_filters if status_filters else [],
        )
        module = self.configure_module(module_id)
        try:
            result = module.list_items(page=page, status_filters=status_filters)
        except SourceModuleError:
            raise
        except Exception as exc:
            logger.exception("list_items failed module=%s", module_id)
            raise SourceModuleError(str(exc), cause=exc) from exc
        logger.debug(
            "host list_items module=%s -> items=%s has_more=%s",
            module_id,
            len(result.items),
            result.has_more,
        )
        return result

    def get_item(self, module_id: str, external_id: str) -> SourceDraft:
        logger.debug("host get_item module=%s external_id=%s", module_id, external_id)
        module = self.configure_module(module_id)
        try:
            draft = module.get_item(external_id)
        except SourceModuleError:
            raise
        except Exception as exc:
            logger.exception("get_item failed module=%s id=%s", module_id, external_id)
            raise SourceModuleError(str(exc), cause=exc) from exc
        logger.debug(
            "host get_item module=%s id=%s -> number=%r desc_len=%s files=%s",
            module_id,
            external_id,
            draft.number,
            len(draft.description or ""),
            len(draft.files),
        )
        return draft

    def download_files(
        self,
        module_id: str,
        external_id: str,
        dest_dir: Path,
        existing_names: list[str] | None = None,
    ) -> list[str]:
        logger.debug(
            "host download_files module=%s external_id=%s dest=%s",
            module_id,
            external_id,
            dest_dir,
        )
        module = self.configure_module(module_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            saved = module.download_files(
                external_id,
                str(dest_dir),
                existing_names=existing_names,
            )
        except SourceModuleError:
            raise
        except Exception as exc:
            logger.exception(
                "download_files failed module=%s id=%s", module_id, external_id
            )
            raise SourceModuleError(str(exc), cause=exc) from exc
        logger.debug(
            "host download_files module=%s id=%s -> saved=%s",
            module_id,
            external_id,
            len(saved),
        )
        return saved

    def install_from_github(
        self, github_repo: str, *, module_id: str | None = None, enabled: bool | None = None
    ) -> PluginManifest:
        prev_enabled, prev_github = self._install_preserve(github_repo, module_id, enabled)
        path = install_module_zip(
            github_repo, module_id=module_id, base=self.modules_base
        )
        return self._register_installed_zip(
            path,
            github_repo=github_repo,
            prev_github=prev_github,
            prev_enabled=prev_enabled,
        )

    def install_zip_bytes(
        self,
        data: bytes,
        *,
        github_repo: str,
        module_id: str | None = None,
        enabled: bool | None = None,
        asset_name: str = "",
    ) -> PluginManifest:
        prev_enabled, prev_github = self._install_preserve(github_repo, module_id, enabled)
        path = save_module_zip_bytes(
            data,
            module_id=module_id,
            asset_name=asset_name,
            base=self.modules_base,
        )
        return self._register_installed_zip(
            path,
            github_repo=github_repo,
            prev_github=prev_github,
            prev_enabled=prev_enabled,
        )

    def _install_preserve(
        self,
        github_repo: str,
        module_id: str | None,
        enabled: bool | None,
    ) -> tuple[bool, str]:
        prev_enabled = False
        prev_github = github_repo
        if module_id:
            row = self.repo.get_source_module(module_id)
            if row is not None:
                prev_enabled = bool(row["enabled"])
                prev_github = str(row["github_repo"] or github_repo)
        if enabled is not None:
            prev_enabled = enabled
        return prev_enabled, prev_github

    def _register_installed_zip(
        self,
        path: Path,
        *,
        github_repo: str,
        prev_github: str,
        prev_enabled: bool,
    ) -> PluginManifest:
        manifest = load_manifest(path)
        expected = modules_dir(self.modules_base) / f"{manifest.id}.zip"
        if path.resolve() != expected.resolve():
            if expected.exists():
                expected.unlink()
            path.replace(expected)
            path = expected
            manifest = load_manifest(path)

        self.repo.upsert_source_module(
            module_id=manifest.id,
            github_repo=prev_github or github_repo,
            display_name=manifest.display_name,
            enabled=prev_enabled,
            installed_version=manifest.version,
            update_asset_name=manifest.update.asset_name,
            update_asset_pattern=manifest.update.asset_pattern,
        )
        self._pending_configs = [
            p
            for p in self._pending_configs
            if p.github_repo.strip() not in {github_repo.strip(), prev_github.strip()}
            and (p.module_id or "").strip() != manifest.id
        ]

        self.reload()
        try:
            loaded = self.get(manifest.id)
        except SourceModuleError as exc:
            raise SourceModuleError(
                f"Модуль установлен, но не загружен: {exc}"
            ) from exc
        if loaded.module is None:
            raise SourceModuleError(
                loaded.load_error
                or f"Модуль «{manifest.id}» не найден после установки"
            )
        self.refresh_catalogs(module_ids=[manifest.id] if prev_enabled else [])
        return manifest

    def uninstall_module(self, module_id: str) -> int:
        """Remove zip, registry row, credentials; clear Task provenance. Return cleared task count."""
        mid = (module_id or "").strip()
        if not mid:
            raise SourceModuleError("Не указан ID модуля")
        linked = self.repo.count_tasks_for_source_module(mid)
        cleared = self.repo.clear_task_source_links(mid)
        self.repo.delete_source_credentials(mid)
        self.repo.delete_source_module(mid)
        zip_path = modules_dir(self.modules_base) / f"{mid}.zip"
        if zip_path.is_file():
            try:
                zip_path.unlink()
            except OSError as exc:
                logger.warning("Failed to remove module zip %s: %s", zip_path, exc)
        dir_path = modules_dir(self.modules_base) / mid
        if dir_path.is_dir():
            # Dev checkout as directory — leave on disk; only zip is the install artifact
            logger.debug("Leaving module directory in place: %s", dir_path)
        self._catalogs.pop(mid, None)
        self._pending_configs = [
            p for p in self._pending_configs if (p.module_id or "").strip() != mid
        ]
        self.reload()
        logger.info(
            "Uninstalled module %s (linked=%s cleared=%s)", mid, linked, cleared
        )
        return cleared

    def create_task_from_draft(
        self,
        *,
        project_id: int,
        module_id: str,
        draft: SourceDraft,
        create_folder: bool | None = None,
        create_notes_file: bool = False,
        by_template: bool = False,
        download_files: bool = False,
        comment: str = "",
        date_end=None,
        hidden: bool = False,
        extra_links: list[tuple[str, str]] | None = None,
        description_html: str | None = None,
        priority: int | None = None,
        number: str | None = None,
        links: list[tuple[str, str]] | None = None,
    ) -> Task:
        loaded = self.get(module_id)
        label = (
            draft.source_label
            or (loaded.manifest.display_name if loaded.manifest else module_id)
        )
        desc = (
            description_html
            if description_html is not None
            else plain_text_to_html(draft.description)
        )
        link_pairs = list(links) if links is not None else list(draft.links)
        if extra_links:
            link_pairs.extend(extra_links)
        task = self.task_service.create_task(
            CreateTaskRequest(
                project_id=project_id,
                number=(number if number is not None else draft.number),
                description=desc,
                comment=comment,
                date_end=date_end,
                priority=clamp_priority(
                    priority if priority is not None else draft.priority
                ),
                hidden=hidden,
                by_template=by_template,
                create_notes_file=create_notes_file,
                create_folder=create_folder,
                links=link_pairs,
                source_module_id=module_id,
                external_id=draft.external_id,
                source_label=label,
                source_status_id=draft.source_status_id or None,
                source_status_label=draft.source_status_label or None,
            )
        )
        task_id = task.id  # type: ignore[assignment]
        new_desc = apply_inline_images_for_task(self.task_service, task_id, desc)
        new_comment = apply_inline_images_for_task(self.task_service, task_id, comment)
        if new_desc != desc or new_comment != comment:
            self.task_service.update_task(
                task_id,
                UpdateTaskRequest(description=new_desc, comment=new_comment),
            )
            task = self.task_service.get_task(task_id)
        if download_files and task.has_folder:
            folder = self.task_service.task_folder_path(task.id)  # type: ignore[arg-type]
            try:
                self._download_into_source_files_dir(
                    module_id, draft.external_id, folder
                )
            except SourceModuleError as exc:
                logger.warning("File download after import failed: %s", exc)
                raise
        return task

    def refresh_task_from_source(self, task_id: int) -> Task:
        task = self.task_service.get_task(task_id)
        if not task.source_module_id or not task.external_id:
            raise ServiceError("У заявки нет привязки к источнику")
        draft = self.get_item(task.source_module_id, task.external_id)
        by_name = {lnk.name: lnk.target for lnk in task.links}
        for name, target in draft.links:
            by_name[name] = target
        ordered: list[tuple[str, str]] = []
        seen: set[str] = set()
        for name, target in draft.links:
            ordered.append((name, target))
            seen.add(name)
        for name, target in by_name.items():
            if name not in seen:
                ordered.append((name, target))

        description = apply_inline_images_for_task(
            self.task_service, task_id, plain_text_to_html(draft.description)
        )
        keep_priority = self.settings.keep_priority_on_source_refresh
        self.task_service.update_task(
            task_id,
            UpdateTaskRequest(
                description=description,
                priority=(
                    None if keep_priority else clamp_priority(draft.priority)
                ),
                links=ordered,
                source_status_id=draft.source_status_id or "",
                source_status_label=draft.source_status_label or "",
                # comment intentionally omitted
            ),
        )
        if draft.source_label:
            refreshed = self.task_service.get_task(task_id)
            refreshed.source_label = draft.source_label
            self.repo.update_task(refreshed)
        return self.task_service.get_task(task_id)

    def download_task_files(self, task_id: int, *, create_folder_if_missing: bool = True) -> list[str]:
        task = self.task_service.get_task(task_id)
        if not task.source_module_id or not task.external_id:
            raise ServiceError("У заявки нет привязки к источнику")
        if not task.has_folder:
            if not create_folder_if_missing:
                raise ServiceError("У заявки нет папки")
            self.task_service.recreate_task_folder(task_id)
            task = self.task_service.get_task(task_id)
        folder = self.task_service.task_folder_path(task_id)
        return self._download_into_source_files_dir(
            task.source_module_id,
            task.external_id,
            folder,
        )

    def _download_into_source_files_dir(
        self, module_id: str, external_id: str, task_folder: Path
    ) -> list[str]:
        dest = source_files_dir(task_folder)
        existing = existing_source_file_names(dest)
        return self.download_files(
            module_id,
            external_id,
            dest,
            existing_names=existing,
        )
