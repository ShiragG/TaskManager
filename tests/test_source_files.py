"""Source files dest (`files/`), presence helper, Description «Файлы» button."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from taskmanager.infrastructure.filesystem import (
    SOURCE_FILES_DIR_NAME,
    existing_source_file_names,
    source_files_dir,
    source_files_present,
)
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings, SourceModuleConfig
from taskmanager.services.source_host import SourceHost
from taskmanager.services.source_protocol import SourceDraft, SourceListPage
from taskmanager.services.task_service import CreateTaskRequest, TaskService


def test_source_files_present_none_missing_empty_and_dotfile(tmp_path: Path):
    assert source_files_present(None) is False
    missing = tmp_path / "nope"
    assert source_files_present(missing) is False
    empty = tmp_path / "empty"
    empty.mkdir()
    assert source_files_present(empty) is False
    (empty / ".hidden").write_text("x", encoding="utf-8")
    assert source_files_present(empty) is False
    (empty / "doc.pdf").write_bytes(b"x")
    assert source_files_present(empty) is True


def test_existing_source_file_names_ignores_missing_dir(tmp_path: Path):
    dest = tmp_path / SOURCE_FILES_DIR_NAME
    assert existing_source_file_names(dest) == []
    dest.mkdir()
    (dest / "a.pdf").write_bytes(b"x")
    assert existing_source_file_names(dest) == ["a.pdf"]


@dataclass
class _DownloadProbe:
    dests: list[str] = field(default_factory=list)
    existing: list[list[str]] = field(default_factory=list)
    calls: int = 0
    id: str = "fake"
    display_name: str = "Fake"
    version: str = "0.0.1"
    api_version: str = "1"

    def configure(self, *, login: str, password: str) -> None:
        return None

    def list_statuses(self):
        return []

    def list_priorities(self):
        return []

    def list_items(self, page: int = 1, status_filters=None) -> SourceListPage:
        return SourceListPage(items=[], page=page)

    def get_item(self, external_id: str) -> SourceDraft:
        return SourceDraft(
            external_id=external_id,
            number=str(external_id),
            description="d",
            priority=5,
            source_label="Fake",
        )

    def download_files(self, external_id, dest_dir, existing_names=None):
        self.calls += 1
        self.dests.append(str(dest_dir))
        self.existing.append(list(existing_names or []))
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        saved = Path(dest_dir) / "from_source.pdf"
        saved.write_bytes(b"pdf")
        return ["from_source.pdf"]


def _host_with_probe(tmp_path: Path, monkeypatch, probe: _DownloadProbe):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "t.db")
    service = TaskService(repo, settings)
    repo.upsert_source_module(module_id="fake", enabled=True, display_name="Fake")
    host = SourceHost(repo, settings, service, modules_base=tmp_path)
    host._by_id["fake"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(
                module_id="fake", enabled=True, display_name="Fake"
            ),
            "manifest": None,
            "module": probe,
            "load_error": None,
        },
    )()
    monkeypatch.setattr(host, "get_credentials", lambda mid: ("u", "p"))
    return host, service, repo


def test_download_task_files_writes_into_files_subdir(tmp_path: Path, monkeypatch):
    probe = _DownloadProbe()
    host, service, repo = _host_with_probe(tmp_path, monkeypatch, probe)
    project = service.create_project("P")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,  # type: ignore[arg-type]
            number="12",
            create_folder=True,
            source_module_id="fake",
            external_id="12",
            source_label="Fake",
        )
    )
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    (folder / "root.pdf").write_bytes(b"root")
    files = source_files_dir(folder)
    files.mkdir()
    (files / "already.pdf").write_bytes(b"old")

    saved = host.download_task_files(task.id)  # type: ignore[arg-type]
    assert saved == ["from_source.pdf"]
    dest = Path(probe.dests[0])
    assert dest == files
    assert dest.name == SOURCE_FILES_DIR_NAME
    assert "already.pdf" in probe.existing[0]
    assert "root.pdf" not in probe.existing[0]
    assert (files / "from_source.pdf").is_file()
    assert not (folder / "from_source.pdf").exists()
    assert (folder / "root.pdf").read_bytes() == b"root"
    repo.close()


def test_import_download_writes_into_files_subdir(tmp_path: Path, monkeypatch):
    probe = _DownloadProbe()
    host, service, repo = _host_with_probe(tmp_path, monkeypatch, probe)
    project = service.create_project("P")
    draft = probe.get_item("7")
    task = host.create_task_from_draft(
        project_id=project.id,  # type: ignore[arg-type]
        module_id="fake",
        draft=draft,
        create_folder=True,
        download_files=True,
    )
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    files = source_files_dir(folder)
    assert probe.calls == 1
    assert Path(probe.dests[0]) == files
    assert (files / "from_source.pdf").is_file()
    assert not (folder / "from_source.pdf").exists()
    repo.close()


def test_description_files_button_disabled_without_dir(qtbot):
    from taskmanager.ui.dialogs import RichTextEditDialog

    dialog = RichTextEditDialog(title="Описание", show_source_files_button=True)
    qtbot.addWidget(dialog)
    assert dialog.source_files_button is not None
    assert dialog.source_files_button.text() == "Файлы"
    assert not dialog.source_files_button.isEnabled()


def test_description_files_button_disabled_empty_dir(tmp_path: Path, qtbot):
    from taskmanager.ui.dialogs import RichTextEditDialog

    files = tmp_path / SOURCE_FILES_DIR_NAME
    files.mkdir()
    dialog = RichTextEditDialog(
        title="Описание",
        show_source_files_button=True,
        source_files_dir=files,
    )
    qtbot.addWidget(dialog)
    assert dialog.source_files_button is not None
    assert not dialog.source_files_button.isEnabled()


def test_description_files_button_enabled_when_file_present(tmp_path: Path, qtbot):
    from taskmanager.ui.dialogs import RichTextEditDialog

    files = tmp_path / SOURCE_FILES_DIR_NAME
    files.mkdir()
    (files / "a.pdf").write_bytes(b"x")
    dialog = RichTextEditDialog(
        title="Описание",
        show_source_files_button=True,
        source_files_dir=files,
    )
    qtbot.addWidget(dialog)
    assert dialog.source_files_button is not None
    assert dialog.source_files_button.isEnabled()


def test_comment_has_no_files_button(qtbot):
    from taskmanager.ui.dialogs import RichTextEditDialog

    dialog = RichTextEditDialog(title="Комментарий")
    qtbot.addWidget(dialog)
    assert dialog.source_files_button is None


def test_task_dialog_description_row_gets_files_dir(tmp_path: Path, qtbot):
    from taskmanager.ui.dialogs import TaskDialog

    files = tmp_path / SOURCE_FILES_DIR_NAME
    files.mkdir()
    (files / "a.pdf").write_bytes(b"x")
    settings = Settings(work_dir=str(tmp_path / "work"))
    dialog = TaskDialog(settings, source_files_dir=files)
    qtbot.addWidget(dialog)
    assert dialog.description_row.show_source_files_button is True
    assert dialog.description_row.source_files_dir == files
    assert dialog.comment_row.show_source_files_button is False
    assert dialog.comment_row.source_files_dir is None


def test_files_button_opens_folder(tmp_path: Path, qtbot, monkeypatch):
    from taskmanager.ui.dialogs import RichTextEditDialog

    files = tmp_path / SOURCE_FILES_DIR_NAME
    files.mkdir()
    (files / "a.pdf").write_bytes(b"x")
    opened: list[str] = []
    monkeypatch.setattr(
        "taskmanager.ui.dialogs.open_target", lambda target: opened.append(target)
    )
    dialog = RichTextEditDialog(
        title="Описание",
        show_source_files_button=True,
        source_files_dir=files,
    )
    qtbot.addWidget(dialog)
    assert dialog.source_files_button is not None
    dialog.source_files_button.click()
    assert opened == [str(files)]
    assert files.is_dir()
