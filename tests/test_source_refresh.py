"""Refresh from source keeps Comment; overwrites description/priority/links."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings, SourceModuleConfig
from taskmanager.services.source_host import SourceHost
from taskmanager.services.source_protocol import (
    SourceDraft,
    SourceFileMeta,
    SourceListPage,
)
from taskmanager.services.task_service import CreateTaskRequest, TaskService


@dataclass
class _FakeModule:
    id: str = "fake"
    display_name: str = "Fake"
    version: str = "0.0.1"
    api_version: str = "1"
    draft: SourceDraft | None = None

    def configure(self, *, login: str, password: str) -> None:
        return None

    def list_statuses(self):
        return []

    def list_priorities(self):
        return []

    def list_items(self, page: int = 1, status_filters=None) -> SourceListPage:
        return SourceListPage(items=[], page=page)

    def get_item(self, external_id: str) -> SourceDraft:
        assert self.draft is not None
        return self.draft

    download_calls: int = 0

    def download_files(self, external_id, dest_dir, existing_names=None):
        self.download_calls += 1
        return []


def test_refresh_preserves_comment(tmp_path: Path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "t.db")
    service = TaskService(repo, settings)
    repo.upsert_source_module(
        module_id="fake", enabled=True, display_name="Fake"
    )
    host = SourceHost(repo, settings, service, modules_base=tmp_path)
    fake = _FakeModule(
        draft=SourceDraft(
            external_id="9",
            number="9",
            description="from source",
            priority=0,
            links=[("Razr", "https://example/9")],
            files=[],
            source_label="Fake",
            source_status_id="3",
            source_status_label="В работе",
        )
    )
    host._by_id["fake"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(module_id="fake", enabled=True, display_name="Fake"),
            "manifest": None,
            "module": fake,
            "load_error": None,
        },
    )()
    # Bypass credentials
    monkeypatch.setattr(host, "get_credentials", lambda mid: ("u", "p"))

    project = service.create_project("P")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,  # type: ignore[arg-type]
            number="9",
            description="old",
            comment="<b>keep me</b>",
            priority=10,
            create_folder=False,
            source_module_id="fake",
            external_id="9",
            source_label="Fake",
            source_status_id="10",
            source_status_label="Старое",
            links=[("Razr", "https://old"), ("Заметки", "/tmp/n")],
        )
    )
    refreshed = host.refresh_task_from_source(task.id)  # type: ignore[arg-type]
    assert refreshed.comment == "<b>keep me</b>"
    assert "from source" in refreshed.description
    assert refreshed.priority == 0
    assert refreshed.source_status_id == "3"
    assert refreshed.source_status_label == "В работе"
    assert refreshed.display_status == "В работе"
    names = {lnk.name: lnk.target for lnk in refreshed.links}
    assert names["Razr"] == "https://example/9"
    assert names["Заметки"] == "/tmp/n"
    repo.close()


def test_refresh_does_not_download_source_files(tmp_path: Path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "t.db")
    service = TaskService(repo, settings)
    repo.upsert_source_module(
        module_id="fake", enabled=True, display_name="Fake"
    )
    host = SourceHost(repo, settings, service, modules_base=tmp_path)
    fake = _FakeModule(
        draft=SourceDraft(
            external_id="9",
            number="9",
            description="from source",
            priority=0,
            files=[SourceFileMeta("1", "doc.pdf")],
            source_label="Fake",
        )
    )
    host._by_id["fake"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(module_id="fake", enabled=True, display_name="Fake"),
            "manifest": None,
            "module": fake,
            "load_error": None,
        },
    )()
    monkeypatch.setattr(host, "get_credentials", lambda mid: ("u", "p"))

    project = service.create_project("P")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,  # type: ignore[arg-type]
            number="9",
            description="old",
            create_folder=True,
            source_module_id="fake",
            external_id="9",
            source_label="Fake",
        )
    )
    host.refresh_task_from_source(task.id)  # type: ignore[arg-type]
    assert fake.download_calls == 0
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    assert not (folder / "files").exists()
    repo.close()
