"""Inline images in Description/Comment: host extract, import/refresh, save."""

from __future__ import annotations

import hashlib
from pathlib import Path

from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.inline_images import (
    IMAGES_DIR_NAME,
    apply_inline_images,
    apply_inline_images_for_task,
)
from taskmanager.services.settings_service import Settings, SourceModuleConfig
from taskmanager.services.source_host import SourceHost, plain_text_to_html
from taskmanager.services.source_protocol import SourceDraft, SourceFileMeta
from taskmanager.services.task_service import CreateTaskRequest, TaskService, UpdateTaskRequest

# Valid 1x1 RGB PNG
PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63f8cfc0000003010100c9fe92ef0000000049454e44ae426082"
)
PNG_HEX = PNG_1x1.hex()
PNG_SHA256 = "b1ff9c8ea3a780bad09b346c423d2d0e46815926879b18e841d928376a946640"
assert hashlib.sha256(PNG_1x1).hexdigest() == PNG_SHA256

# Tiny JPEG (magic FFD8FF); payload only needs to sniff as JPEG
JPEG_BYTES = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb0043000806060706050807070709"
    "09080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c283729"
    "2c30313434341f27393d38323c2e333432ffc0000b080001000101011100ffc400141001"
    "00000000000000000000000000000000ffda0008000100110000003f00fbffd9"
)
JPEG_HEX = JPEG_BYTES.hex()
JPEG_SHA256 = hashlib.sha256(JPEG_BYTES).hexdigest()


def _images_dir(folder: Path) -> Path:
    return folder / IMAGES_DIR_NAME


def _image_file(folder: Path, name: str) -> Path:
    return _images_dir(folder) / name


def _host(tmp_path: Path) -> tuple[SourceHost, TaskService, SqliteRepository]:
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
            "module": None,
            "load_error": None,
        },
    )()
    return host, service, repo


def _draft(*, description: str, files: list[SourceFileMeta] | None = None) -> SourceDraft:
    return SourceDraft(
        external_id="42",
        number="42",
        description=description,
        priority=5,
        links=[],
        files=list(files) if files is not None else [SourceFileMeta("att", "doc.pdf")],
        source_label="Fake",
        source_status_id="1",
        source_status_label="Open",
    )


def test_import_hex_png_writes_hash_file_and_img(tmp_path: Path):
    host, service, repo = _host(tmp_path)
    project = service.create_project("P")
    files = [SourceFileMeta("att", "doc.pdf")]
    draft = _draft(description=f"see\n{PNG_HEX}", files=files)
    task = host.create_task_from_draft(
        project_id=project.id,  # type: ignore[arg-type]
        module_id="fake",
        draft=draft,
        create_folder=True,
        download_files=False,
    )
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    stored = _image_file(folder, f"{PNG_SHA256}.png")
    assert stored.is_file()
    assert stored.read_bytes() == PNG_1x1
    assert not (folder / f"{PNG_SHA256}.png").exists()
    assert "<img" in task.description
    assert "<a href=" in task.description
    assert "file://" in task.description
    assert PNG_HEX not in task.description.replace(" ", "")
    assert draft.files == files
    assert (folder / "doc.pdf").exists() is False
    repo.close()


def test_import_base64_png_writes_hash_file(tmp_path: Path):
    import base64

    host, service, repo = _host(tmp_path)
    project = service.create_project("P")
    dump = base64.b64encode(PNG_1x1).decode("ascii")
    task = host.create_task_from_draft(
        project_id=project.id,  # type: ignore[arg-type]
        module_id="fake",
        draft=_draft(description=dump),
        create_folder=True,
    )
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    assert _image_file(folder, f"{PNG_SHA256}.png").read_bytes() == PNG_1x1
    assert "<img" in task.description
    repo.close()


def test_import_hex_jpeg_writes_hash_file(tmp_path: Path):
    host, service, repo = _host(tmp_path)
    project = service.create_project("P")
    task = host.create_task_from_draft(
        project_id=project.id,  # type: ignore[arg-type]
        module_id="fake",
        draft=_draft(description=JPEG_HEX),
        create_folder=True,
    )
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    stored = _image_file(folder, f"{JPEG_SHA256}.jpeg")
    assert stored.is_file()
    assert stored.read_bytes() == JPEG_BYTES
    assert "<img" in task.description
    repo.close()


def test_refresh_same_picture_reuses_hash_filename(tmp_path: Path, monkeypatch):
    host, service, repo = _host(tmp_path)
    project = service.create_project("P")
    draft = _draft(description=f"v1\n{PNG_HEX}")
    task = host.create_task_from_draft(
        project_id=project.id,  # type: ignore[arg-type]
        module_id="fake",
        draft=draft,
        create_folder=True,
    )
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    first = list(_images_dir(folder).glob(f"{PNG_SHA256}.*"))
    assert len(first) == 1

    class _Mod:
        def configure(self, *, login, password):
            return None

        def get_item(self, external_id):
            return _draft(description=f"v2\n{PNG_HEX}")

        def list_statuses(self):
            return []

        def list_priorities(self):
            return []

        def list_items(self, page=1, status_filters=None):
            raise AssertionError("unused")

        def download_files(self, *a, **k):
            raise AssertionError("must not touch SourceDraft.files / download")

    host._by_id["fake"].module = _Mod()
    monkeypatch.setattr(host, "get_credentials", lambda mid: ("u", "p"))
    refreshed = host.refresh_task_from_source(task.id)  # type: ignore[arg-type]
    pngs = list(_images_dir(folder).glob(f"{PNG_SHA256}.*"))
    assert len(pngs) == 1
    assert pngs[0].name == first[0].name
    assert "v2" in refreshed.description
    assert "<img" in refreshed.description
    repo.close()


def test_import_without_folder_creates_folder_for_image(tmp_path: Path):
    host, service, repo = _host(tmp_path)
    project = service.create_project("P")
    task = host.create_task_from_draft(
        project_id=project.id,  # type: ignore[arg-type]
        module_id="fake",
        draft=_draft(description=PNG_HEX),
        create_folder=False,
    )
    reloaded = service.get_task(task.id)  # type: ignore[arg-type]
    assert reloaded.has_folder is True
    folder = service.task_folder_path(reloaded.id)  # type: ignore[arg-type]
    assert _image_file(folder, f"{PNG_SHA256}.png").is_file()
    repo.close()


def test_refresh_does_not_delete_orphan_hash_files(tmp_path: Path, monkeypatch):
    host, service, repo = _host(tmp_path)
    project = service.create_project("P")
    task = host.create_task_from_draft(
        project_id=project.id,  # type: ignore[arg-type]
        module_id="fake",
        draft=_draft(description=PNG_HEX),
        create_folder=True,
    )
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    orphan = folder / ("0" * 64 + ".png")
    orphan.write_bytes(b"leftover")

    class _Mod:
        def configure(self, *, login, password):
            return None

        def get_item(self, external_id):
            return _draft(description=PNG_HEX)

        def list_statuses(self):
            return []

        def list_priorities(self):
            return []

        def list_items(self, page=1, status_filters=None):
            raise AssertionError("unused")

        def download_files(self, *a, **k):
            return []

    host._by_id["fake"].module = _Mod()
    monkeypatch.setattr(host, "get_credentials", lambda mid: ("u", "p"))
    host.refresh_task_from_source(task.id)  # type: ignore[arg-type]
    assert orphan.is_file()
    assert orphan.read_bytes() == b"leftover"
    repo.close()


def test_existing_hex_in_sqlite_unchanged_until_refresh(tmp_path: Path, monkeypatch):
    host, service, repo = _host(tmp_path)
    project = service.create_project("P")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,  # type: ignore[arg-type]
            number="7",
            description=PNG_HEX,
            create_folder=True,
            source_module_id="fake",
            external_id="42",
            source_label="Fake",
        )
    )
    loaded = service.get_task(task.id)  # type: ignore[arg-type]
    assert PNG_HEX in loaded.description
    assert "<img" not in loaded.description
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    assert not list(folder.glob("*.png"))

    class _Mod:
        def configure(self, *, login, password):
            return None

        def get_item(self, external_id):
            return _draft(description=PNG_HEX)

        def list_statuses(self):
            return []

        def list_priorities(self):
            return []

        def list_items(self, page=1, status_filters=None):
            raise AssertionError("unused")

        def download_files(self, *a, **k):
            return []

    host._by_id["fake"].module = _Mod()
    monkeypatch.setattr(host, "get_credentials", lambda mid: ("u", "p"))
    refreshed = host.refresh_task_from_source(task.id)  # type: ignore[arg-type]
    assert "<img" in refreshed.description
    assert _image_file(folder, f"{PNG_SHA256}.png").is_file()
    repo.close()


def test_save_description_hex_dump_substitutes(tmp_path: Path):
    _, service, repo = _host(tmp_path)
    project = service.create_project("P")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,  # type: ignore[arg-type]
            number="1",
            description="old",
            create_folder=True,
        )
    )
    html = plain_text_to_html(f"note\n{PNG_HEX}")
    new_html = apply_inline_images_for_task(service, task.id, html)  # type: ignore[arg-type]
    service.update_task(task.id, UpdateTaskRequest(description=new_html))  # type: ignore[arg-type]
    got = service.get_task(task.id)  # type: ignore[arg-type]
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    assert "<img" in got.description
    assert _image_file(folder, f"{PNG_SHA256}.png").read_bytes() == PNG_1x1
    assert not (folder / f"{PNG_SHA256}.png").exists()
    repo.close()


def test_save_comment_hex_dump_substitutes(tmp_path: Path):
    _, service, repo = _host(tmp_path)
    project = service.create_project("P")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,  # type: ignore[arg-type]
            number="1",
            comment="old",
            create_folder=True,
        )
    )
    html = plain_text_to_html(PNG_HEX)
    new_html = apply_inline_images_for_task(service, task.id, html)  # type: ignore[arg-type]
    service.update_task(task.id, UpdateTaskRequest(comment=new_html))  # type: ignore[arg-type]
    got = service.get_task(task.id)  # type: ignore[arg-type]
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    assert "<img" in got.comment
    assert _image_file(folder, f"{PNG_SHA256}.png").is_file()
    repo.close()


def test_save_without_folder_creates_folder(tmp_path: Path):
    _, service, repo = _host(tmp_path)
    project = service.create_project("P")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,  # type: ignore[arg-type]
            number="1",
            description="old",
            create_folder=False,
        )
    )
    assert task.has_folder is False
    html = plain_text_to_html(PNG_HEX)
    new_html = apply_inline_images_for_task(service, task.id, html)  # type: ignore[arg-type]
    service.update_task(task.id, UpdateTaskRequest(description=new_html))  # type: ignore[arg-type]
    got = service.get_task(task.id)  # type: ignore[arg-type]
    assert got.has_folder is True
    folder = service.task_folder_path(got.id)  # type: ignore[arg-type]
    assert _image_file(folder, f"{PNG_SHA256}.png").is_file()
    repo.close()


def test_data_uri_on_save_becomes_hash_file(tmp_path: Path):
    dest = tmp_path / "folder"
    dest.mkdir()
    import base64

    uri = "data:image/png;base64," + base64.b64encode(PNG_1x1).decode("ascii")
    html = f'<p>x</p><img src="{uri}">'
    new_html, names = apply_inline_images(html, dest)
    assert names == [f"{PNG_SHA256}.png"]
    assert (dest / names[0]).read_bytes() == PNG_1x1
    assert uri not in new_html
    assert "<img" in new_html
    assert "<a href=" in new_html
    assert "file://" in new_html


def test_save_task_html_extracts_description_and_comment(tmp_path: Path, qtbot):
    from taskmanager.services.settings_service import SettingsStore
    from taskmanager.ui.main_window import MainWindow

    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work))
    store.save(settings)
    repo = SqliteRepository(tmp_path / "ui.db")
    service = TaskService(repo, settings)
    window = MainWindow(service, settings, store)
    qtbot.addWidget(window)
    project = service.create_project("P")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,  # type: ignore[arg-type]
            number="1",
            description="old",
            comment="oldc",
            create_folder=True,
        )
    )
    window._save_task_html(
        task.id,  # type: ignore[arg-type]
        description=plain_text_to_html(f"d\n{PNG_HEX}"),
    )
    got = service.get_task(task.id)  # type: ignore[arg-type]
    assert "<img" in got.description
    assert "<a href=" in got.description
    assert "file://" in got.description
    window._save_task_html(
        task.id,  # type: ignore[arg-type]
        comment=plain_text_to_html(PNG_HEX),
    )
    got = service.get_task(task.id)  # type: ignore[arg-type]
    assert "<img" in got.comment
    assert "<a href=" in got.comment
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    assert _image_file(folder, f"{PNG_SHA256}.png").is_file()
    repo.close()


def test_existing_root_hash_file_left_in_place(tmp_path: Path):
    dest = tmp_path / "folder"
    dest.mkdir()
    old = dest / f"{PNG_SHA256}.png"
    old.write_bytes(PNG_1x1)
    uri = old.resolve().as_uri()
    html = f'<p>see</p><a href="{uri}"><img src="{uri}"></a>'
    new_html, names = apply_inline_images(html, dest / IMAGES_DIR_NAME)
    assert names == []
    assert old.is_file()
    assert old.read_bytes() == PNG_1x1
    assert not (dest / IMAGES_DIR_NAME / f"{PNG_SHA256}.png").exists()
    assert uri in new_html


def test_editor_insert_image_from_path_uses_data_uri(tmp_path: Path, qtbot):
    from taskmanager.ui.dialogs import RichTextEditDialog

    png_path = tmp_path / "shot.png"
    png_path.write_bytes(PNG_1x1)
    dialog = RichTextEditDialog(title="Описание")
    qtbot.addWidget(dialog)
    assert dialog.insert_image_from_path(str(png_path))
    html = dialog.html
    assert "data:image/png;base64," in html
    assert "<img" in html


def test_editor_rejects_non_image_file(tmp_path: Path, qtbot, monkeypatch):
    from taskmanager.ui.dialogs import RichTextEditDialog

    junk = tmp_path / "x.bin"
    junk.write_bytes(b"not-an-image" * 8)
    dialog = RichTextEditDialog(title="Описание")
    qtbot.addWidget(dialog)
    monkeypatch.setattr(
        "taskmanager.ui.dialogs.QMessageBox.warning", lambda *a, **k: None
    )
    assert dialog.insert_image_from_path(str(junk)) is False
    assert "data:image" not in dialog.html


def test_editor_paste_image_inserts_img(qtbot):
    from PySide6.QtCore import QMimeData, Qt
    from PySide6.QtGui import QColor, QImage
    from taskmanager.ui.dialogs import RichTextEditDialog

    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(QColor(Qt.GlobalColor.red))
    mime = QMimeData()
    mime.setImageData(image)
    dialog = RichTextEditDialog(title="Комментарий")
    qtbot.addWidget(dialog)
    dialog.editor.insertFromMimeData(mime)
    html = dialog.html
    assert "<img" in html.lower()


def test_editor_open_does_not_extract_existing_hex(qtbot):
    from taskmanager.ui.dialogs import RichTextEditDialog

    dialog = RichTextEditDialog(title="Описание", html=PNG_HEX)
    qtbot.addWidget(dialog)
    assert PNG_HEX in dialog.html
    assert "file://" not in dialog.html


def _img_width(html: str) -> int | None:
    import re

    match = re.search(r"<img\b[^>]*\bwidth\s*=\s*[\"']?(\d+)", html, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"<img\b[^>]*\bwidth\s*:\s*(\d+)px", html, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def test_editor_insert_image_uses_preview_width(tmp_path: Path, qtbot):
    from taskmanager.ui.dialogs import DEFAULT_IMAGE_PREVIEW_WIDTH, RichTextEditDialog

    png_path = tmp_path / "shot.png"
    png_path.write_bytes(PNG_1x1)
    dialog = RichTextEditDialog(title="Описание")
    qtbot.addWidget(dialog)
    assert dialog.insert_image_from_path(str(png_path))
    width = _img_width(dialog.html)
    assert width is not None
    assert abs(width - DEFAULT_IMAGE_PREVIEW_WIDTH) <= 1


def test_editor_paste_image_uses_data_uri_not_html(qtbot):
    from PySide6.QtCore import QMimeData, Qt
    from PySide6.QtGui import QColor, QImage
    from taskmanager.ui.dialogs import DEFAULT_IMAGE_PREVIEW_WIDTH, RichTextEditDialog

    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(QColor(Qt.GlobalColor.red))
    mime = QMimeData()
    mime.setImageData(image)
    mime.setHtml("<p>clipboard-html-should-lose</p>")
    dialog = RichTextEditDialog(title="Комментарий")
    qtbot.addWidget(dialog)
    dialog.editor.insertFromMimeData(mime)
    html = dialog.html
    assert "data:image" in html
    assert "clipboard-html-should-lose" not in html
    width = _img_width(html)
    assert width is not None
    assert abs(width - DEFAULT_IMAGE_PREVIEW_WIDTH) <= 1


def test_save_pasted_image_writes_dot_images_and_file_uri(tmp_path: Path, qtbot):
    import base64

    from taskmanager.services.settings_service import SettingsStore
    from taskmanager.ui.main_window import MainWindow

    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work))
    store.save(settings)
    repo = SqliteRepository(tmp_path / "ui.db")
    service = TaskService(repo, settings)
    window = MainWindow(service, settings, store)
    qtbot.addWidget(window)
    project = service.create_project("P")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,  # type: ignore[arg-type]
            number="1",
            description="old",
            create_folder=True,
        )
    )
    uri = "data:image/png;base64," + base64.b64encode(PNG_1x1).decode("ascii")
    html = f'<p>shot</p><img src="{uri}" width="480">'
    window._save_task_html(task.id, description=html)  # type: ignore[arg-type]
    got = service.get_task(task.id)  # type: ignore[arg-type]
    folder = service.task_folder_path(task.id)  # type: ignore[arg-type]
    stored = _image_file(folder, f"{PNG_SHA256}.png")
    assert stored.is_file()
    assert stored.read_bytes() == PNG_1x1
    assert not (folder / f"{PNG_SHA256}.png").exists()
    assert "file://" in got.description
    assert "<img" in got.description
    assert uri not in got.description
    assert _img_width(got.description) == 480
    repo.close()


def test_extractor_keeps_existing_img_width(tmp_path: Path):
    import base64

    dest = tmp_path / "folder"
    dest.mkdir()
    uri = "data:image/png;base64," + base64.b64encode(PNG_1x1).decode("ascii")
    html = f'<p>x</p><img src="{uri}" width="240">'
    new_html, names = apply_inline_images(html, dest)
    assert names == [f"{PNG_SHA256}.png"]
    assert _img_width(new_html) == 240


def test_editor_image_preset_writes_width(tmp_path: Path, qtbot):
    from taskmanager.ui.dialogs import (
        DEFAULT_IMAGE_PREVIEW_WIDTH,
        SMALL_IMAGE_PREVIEW_WIDTH,
        RichTextEditDialog,
    )

    png_path = tmp_path / "shot.png"
    png_path.write_bytes(PNG_1x1)
    dialog = RichTextEditDialog(title="Описание")
    qtbot.addWidget(dialog)
    assert dialog.insert_image_from_path(str(png_path))
    cursors = list(dialog.editor.iter_image_cursors())
    assert cursors
    dialog.editor.set_image_display_width(cursors[0], SMALL_IMAGE_PREVIEW_WIDTH)
    assert _img_width(dialog.html) == SMALL_IMAGE_PREVIEW_WIDTH
    dialog.editor.set_image_display_width(cursors[0], DEFAULT_IMAGE_PREVIEW_WIDTH)
    assert _img_width(dialog.html) == DEFAULT_IMAGE_PREVIEW_WIDTH

