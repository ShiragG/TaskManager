"""Tests for Source module host loading (no modules → green)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.module_loader import (
    discover_module_paths,
    load_all_modules,
    load_manifest,
    modules_dir,
)
from taskmanager.services.settings_service import (
    Settings,
    SettingsStore,
    SourceModuleConfig,
)
from taskmanager.services.source_host import SourceHost, plain_text_to_html
from taskmanager.services.source_protocol import (
    SourceModuleError,
    SourcePriorityOption,
    SourceStatusOption,
    api_version_supported,
)
from taskmanager.services.task_service import CreateTaskRequest, TaskService


def test_api_version_supported():
    assert api_version_supported("1")
    assert api_version_supported("1.0")
    assert api_version_supported("1.2.3")
    assert not api_version_supported("2")
    assert not api_version_supported("0.9")


def test_modules_dir_empty(tmp_path: Path):
    assert discover_module_paths(tmp_path) == []
    assert load_all_modules(tmp_path) == []


def test_source_host_without_modules(tmp_path: Path):
    settings = Settings(work_dir=str(tmp_path / "work"))
    (tmp_path / "work").mkdir()
    repo = SqliteRepository(tmp_path / "t.db")
    service = TaskService(repo, settings)
    host = SourceHost(repo, settings, service, modules_base=tmp_path)
    assert host.enabled_modules() == []
    assert host.list_loaded() == []
    repo.close()


def test_plain_text_to_html_escapes():
    assert "&lt;b&gt;" in plain_text_to_html("<b>x</b>")
    assert "<br>" in plain_text_to_html("a\nb")


_STUB_PLUGIN = '''
class _Page:
    def __init__(self, items, page, has_more=False, total=None):
        self.items = items
        self.page = page
        self.has_more = has_more
        self.total = total

class _Draft:
    def __init__(self, **kw):
        for k,v in kw.items():
            setattr(self, k, v)

class _Status:
    def __init__(self, id, label, default_selected=False):
        self.id = id
        self.label = label
        self.default_selected = default_selected

class _Priority:
    def __init__(self, id, label, mapped_priority):
        self.id = id
        self.label = label
        self.mapped_priority = mapped_priority

class Plugin:
    id = "stub"
    display_name = "Stub"
    version = "0.0.1"
    api_version = %r

    def configure(self, *, login, password):
        self._login = login

    def list_statuses(self):
        return [_Status("10", "Assigned", True), _Status("1", "Dev", True)]

    def list_priorities(self):
        return [_Priority("5", "High", 0)]

    def list_items(self, page=1, status_filters=None):
        return _Page(items=[], page=page, has_more=False)

    def get_item(self, external_id):
        return _Draft(
            external_id=external_id,
            number=str(external_id),
            description="d",
            priority=5,
            links=[],
            files=[],
            source_label="Stub",
        )

    def download_files(self, external_id, dest_dir, existing_names=None):
        return []
'''


def _write_stub_zip(
    path: Path,
    *,
    api_version: str = "1",
    module_id: str = "stub",
    version: str = "0.0.1",
    package: str = "stub_mod",
) -> None:
    plugin = {
        "id": module_id,
        "display_name": "Stub",
        "version": version,
        "api_version": api_version,
        "entry": f"{package}.plugin:Plugin",
        "update": {"asset_name": f"{module_id}.zip", "asset_pattern": ""},
    }
    body = _STUB_PLUGIN % (api_version,)
    body = body.replace('id = "stub"', f'id = "{module_id}"')
    body = body.replace('version = "0.0.1"', f'version = "{version}"')
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("plugin.json", json.dumps(plugin))
        zf.writestr(f"{package}/__init__.py", "")
        zf.writestr(f"{package}/plugin.py", body)


def test_load_stub_module_zip(tmp_path: Path):
    mods = modules_dir(tmp_path)
    mods.mkdir(parents=True)
    zip_path = mods / "stub.zip"
    _write_stub_zip(zip_path)
    loaded = load_all_modules(tmp_path)
    assert len(loaded) == 1
    manifest, module = loaded[0]
    assert manifest.id == "stub"
    assert module.id == "stub"
    assert hasattr(module, "list_statuses")
    assert manifest.update.asset_name == "stub.zip"


def test_reject_unsupported_api_version(tmp_path: Path):
    mods = modules_dir(tmp_path)
    mods.mkdir(parents=True)
    zip_path = mods / "stub.zip"
    _write_stub_zip(zip_path, api_version="9")
    assert load_all_modules(tmp_path) == []


def test_provenance_columns_roundtrip(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "p.db")
    from taskmanager.domain import Task, TaskStatus
    from datetime import datetime

    project = repo.add_project("P")
    task = Task(
        id=None,
        project_id=project.id,  # type: ignore[arg-type]
        number="1",
        description="d",
        folder_name="1",
        status=TaskStatus.ACTIVE,
        created_at=datetime.now(),
        source_module_id="razr",
        external_id="42",
        source_label="Разработка (razr)",
    )
    task = repo.add_task(task)
    got = repo.get_task(task.id)  # type: ignore[arg-type]
    assert got is not None
    assert got.source_module_id == "razr"
    assert got.external_id == "42"
    assert got.source_label == "Разработка (razr)"
    repo.upsert_source_credentials("razr", "user", "cipher")
    assert repo.get_source_credentials("razr") == ("user", "cipher")
    repo.close()


def test_settings_to_sqlite_migration(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "work_dir": str(work),
                "source_modules": [
                    {
                        "module_id": "razr",
                        "github_repo": "https://github.com/o/r",
                        "enabled": True,
                        "display_name": "Razr",
                        "installed_version": "0.1.0",
                        "login": "u",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    store = SettingsStore(path)
    settings = store.load()
    assert not hasattr(settings, "source_modules") or "source_modules" not in settings.to_dict()
    assert len(store.pending_source_module_migration) == 1
    assert store.pending_source_module_migration[0].module_id == "razr"
    # Rewritten settings.json must not keep source_modules
    rewritten = json.loads(path.read_text(encoding="utf-8"))
    assert "source_modules" not in rewritten

    repo = SqliteRepository(tmp_path / "m.db")
    service = TaskService(repo, settings)
    host = SourceHost(
        repo,
        settings,
        service,
        modules_base=tmp_path,
        pending_migration=store.pending_source_module_migration,
    )
    row = repo.get_source_module("razr")
    assert row is not None
    assert row["enabled"] == 1
    assert row["github_repo"] == "https://github.com/o/r"
    loaded = host.get("razr")
    assert loaded.config.enabled is True
    repo.close()


def test_catalog_cache_and_import_blocked_on_error(tmp_path: Path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "c.db")
    service = TaskService(repo, settings)
    repo.upsert_source_module(
        module_id="fake",
        display_name="Fake",
        enabled=True,
        installed_version="1",
    )
    host = SourceHost(repo, settings, service, modules_base=tmp_path)

    class _BadMod:
        id = "fake"
        display_name = "Fake"
        version = "1"
        api_version = "1"

        def configure(self, *, login, password):
            return None

        def list_statuses(self):
            raise SourceModuleError("catalog down")

        def list_priorities(self):
            return []

        def list_items(self, page=1, status_filters=None):
            raise AssertionError("list_items must not run when catalog failed")

        def get_item(self, external_id):
            raise AssertionError("unused")

        def download_files(self, *a, **k):
            return []

    host._by_id["fake"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(module_id="fake", enabled=True),
            "manifest": None,
            "module": _BadMod(),
            "load_error": None,
        },
    )()
    monkeypatch.setattr(host, "get_credentials", lambda mid: ("u", "p"))
    host.refresh_catalogs(module_ids=["fake"])
    cache = host.get_catalog("fake")
    assert cache is not None
    assert cache.error is not None
    with pytest.raises(SourceModuleError, match="Каталог"):
        host.list_items("fake")
    repo.close()


def test_catalog_cache_success(tmp_path: Path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "c2.db")
    service = TaskService(repo, settings)
    host = SourceHost(repo, settings, service, modules_base=tmp_path)

    class _GoodMod:
        id = "good"
        display_name = "Good"
        version = "1"
        api_version = "1"

        def configure(self, *, login, password):
            return None

        def list_statuses(self):
            return [SourceStatusOption("10", "A", True)]

        def list_priorities(self):
            return [SourcePriorityOption("5", "High", 0)]

        def list_items(self, page=1, status_filters=None):
            from taskmanager.services.source_protocol import SourceListPage

            return SourceListPage(items=[], page=page)

        def get_item(self, external_id):
            raise AssertionError("unused")

        def download_files(self, *a, **k):
            return []

    host._by_id["good"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(module_id="good", enabled=True),
            "manifest": None,
            "module": _GoodMod(),
            "load_error": None,
        },
    )()
    monkeypatch.setattr(host, "get_credentials", lambda mid: ("u", "p"))
    host.refresh_catalogs(module_ids=["good"])
    cache = host.get_catalog("good")
    assert cache is not None
    assert cache.error is None
    assert cache.statuses[0].id == "10"
    assert cache.priorities[0].mapped_priority == 0
    repo.close()


def test_empty_catalog_is_not_error(tmp_path: Path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "c3.db")
    service = TaskService(repo, settings)
    host = SourceHost(repo, settings, service, modules_base=tmp_path)

    class _EmptyMod:
        id = "empty"
        display_name = "Empty"
        version = "1"
        api_version = "1"

        def configure(self, *, login, password):
            return None

        def list_statuses(self):
            return []

        def list_priorities(self):
            return []

        def list_items(self, page=1, status_filters=None):
            from taskmanager.services.source_protocol import SourceListPage

            assert status_filters == []
            return SourceListPage(items=[], page=page)

        def get_item(self, external_id):
            raise AssertionError("unused")

        def download_files(self, *a, **k):
            return []

    host._by_id["empty"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(module_id="empty", enabled=True),
            "manifest": None,
            "module": _EmptyMod(),
            "load_error": None,
        },
    )()
    monkeypatch.setattr(host, "get_credentials", lambda mid: ("u", "p"))
    host.refresh_catalogs(module_ids=["empty"])
    cache = host.get_catalog("empty")
    assert cache is not None
    assert cache.error is None
    assert cache.statuses == []
    assert cache.priorities == []
    page = host.list_items("empty", status_filters=[])
    assert page.items == []
    repo.close()


def test_check_login_refreshes_catalog_without_persist(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "c4.db")
    service = TaskService(repo, settings)
    host = SourceHost(repo, settings, service, modules_base=tmp_path)
    calls: list[tuple[str, str]] = []

    class _ProbeMod:
        id = "probe"
        display_name = "Probe"
        version = "1"
        api_version = "1"

        def configure(self, *, login, password):
            calls.append((login, password))

        def list_statuses(self):
            return [SourceStatusOption("1", "S", True)]

        def list_priorities(self):
            return []

        def list_items(self, page=1, status_filters=None):
            raise AssertionError("unused")

        def get_item(self, external_id):
            raise AssertionError("unused")

        def download_files(self, *a, **k):
            return []

    host._by_id["probe"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(module_id="probe", enabled=False),
            "manifest": None,
            "module": _ProbeMod(),
            "load_error": None,
        },
    )()
    host.check_login("probe", "user", "secret")
    assert calls == [("user", "secret")]
    assert repo.get_source_credentials("probe") is None
    cache = host.get_catalog("probe")
    assert cache is not None
    assert cache.error is None
    assert cache.statuses[0].id == "1"
    repo.close()


def test_uninstall_clears_task_source_fields(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    mods = modules_dir(tmp_path)
    mods.mkdir(parents=True)
    zip_path = mods / "stub.zip"
    _write_stub_zip(zip_path)

    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "u.db")
    service = TaskService(repo, settings)
    repo.upsert_source_module(
        module_id="stub",
        github_repo="https://github.com/o/stub",
        display_name="Stub",
        enabled=True,
        installed_version="0.0.1",
    )
    repo.upsert_source_credentials("stub", "u", "cipher")
    host = SourceHost(repo, settings, service, modules_base=tmp_path)

    project = service.create_project("P")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,  # type: ignore[arg-type]
            number="1",
            description="d",
            create_folder=False,
            source_module_id="stub",
            external_id="99",
            source_label="Stub",
        )
    )
    cleared = host.uninstall_module("stub")
    assert cleared == 1
    assert not zip_path.exists()
    assert repo.get_source_module("stub") is None
    assert repo.get_source_credentials("stub") is None
    got = service.get_task(task.id)  # type: ignore[arg-type]
    assert got.source_module_id is None
    assert got.external_id is None
    assert got.source_label is None
    repo.close()


def test_reload_after_zip_replace(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    mods = modules_dir(tmp_path)
    mods.mkdir(parents=True)
    zip_path = mods / "stub.zip"
    _write_stub_zip(zip_path, version="0.0.1")

    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "r.db")
    service = TaskService(repo, settings)
    repo.upsert_source_module(
        module_id="stub",
        github_repo="owner/stub",
        display_name="Stub",
        enabled=True,
        installed_version="0.0.1",
    )
    host = SourceHost(repo, settings, service, modules_base=tmp_path)
    assert host.get("stub").module is not None
    assert host.get("stub").config.installed_version == "0.0.1"

    # Replace zip with newer version (same module id)
    _write_stub_zip(zip_path, version="0.0.2")
    host.reload()
    loaded = host.get("stub")
    assert loaded.module is not None
    assert loaded.module.version == "0.0.2"
    assert loaded.config.installed_version == "0.0.2"
    row = repo.get_source_module("stub")
    assert row is not None
    assert row["installed_version"] == "0.0.2"
    assert row["enabled"] == 1
    repo.close()


def test_install_persists_enabled_before_save(tmp_path: Path, monkeypatch):
    """After zip install, registry is updated immediately (enabled preserved)."""
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "i.db")
    service = TaskService(repo, settings)
    host = SourceHost(repo, settings, service, modules_base=tmp_path)

    mods = modules_dir(tmp_path)
    mods.mkdir(parents=True)
    dest = mods / "stub.zip"

    def fake_install(github_repo, *, module_id=None, base=None):
        _write_stub_zip(dest, version="1.2.3")
        return dest

    monkeypatch.setattr(
        "taskmanager.services.source_host.install_module_zip", fake_install
    )
    manifest = host.install_from_github("owner/stub", enabled=True)
    assert manifest.id == "stub"
    row = repo.get_source_module("stub")
    assert row is not None
    assert row["enabled"] == 1
    assert row["installed_version"] == "1.2.3"
    assert host.get("stub").module is not None
    repo.close()
