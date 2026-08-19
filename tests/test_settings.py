from pathlib import Path
import json

from taskmanager.services.settings_service import Settings, SettingsStore


def test_settings_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(
        work_dir=str(tmp_path / "work"),
        template_name=".tpl",
        warning_lead_days=3,
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.work_dir == settings.work_dir
    assert loaded.template_name == ".tpl"
    assert loaded.archive_name == ".archive"
    assert loaded.warning_lead_days == 3
    assert loaded.create_notes_file is False
    assert loaded.create_task_folder is True
    assert loaded.autonumber_on_create is False
    assert loaded.theme_mode == "system"
    assert "Белый" in loaded.colors


def test_settings_default_lead_days(tmp_path: Path):
    work = tmp_path / "w"
    work.mkdir()
    path = tmp_path / "settings.json"
    path.write_text(
        f'{{"work_dir": "{work.as_posix()}"}}',
        encoding="utf-8",
    )
    loaded = SettingsStore(path).load()
    assert loaded.warning_lead_days == 1
    assert loaded.create_notes_file is False


def test_settings_create_notes_file_true_from_json_preserved(tmp_path: Path):
    work = tmp_path / "w"
    work.mkdir()
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"work_dir": str(work), "create_notes_file": True}),
        encoding="utf-8",
    )
    loaded = SettingsStore(path).load()
    assert loaded.create_notes_file is True


def test_settings_create_notes_file_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(work_dir=str(tmp_path / "work"), create_notes_file=False)
    store.save(settings)
    loaded = store.load()
    assert loaded.create_notes_file is False


def test_settings_drops_legacy_source_modules(tmp_path: Path):
    work = tmp_path / "w"
    work.mkdir()
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "work_dir": str(work),
                "source_modules": [
                    {
                        "module_id": "razr",
                        "enabled": True,
                        "github_repo": "https://github.com/ShiragG/taskmanager-source-razr",
                        "display_name": "Разработка (razr)",
                        "login": "user",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    store = SettingsStore(path)
    loaded = store.load()
    assert "source_modules" not in loaded.to_dict()
    assert len(store.pending_source_module_migration) == 1
    assert store.pending_source_module_migration[0].module_id == "razr"
    assert store.pending_source_module_migration[0].enabled is True
    assert "password" not in store.pending_source_module_migration[0].to_dict()


def test_settings_hotkeys_roundtrip(tmp_path: Path):
    from taskmanager.services.hotkeys import validate_hotkeys

    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(
        work_dir=str(tmp_path / "work"),
        hotkeys={"focus_search": "Ctrl+K", "add_task": "Ctrl+N", "reload_current_tab": "F5"},
    )
    store.save(settings)
    loaded = SettingsStore(path).load()
    assert loaded.hotkeys["focus_search"] == "Ctrl+K"
    assert loaded.hotkeys["add_task"] == "Ctrl+N"
    assert (
        validate_hotkeys(
            {"focus_search": "Ctrl+N", "add_task": "Ctrl+N", "reload_current_tab": "F5"}
        )
        is not None
    )
    assert (
        validate_hotkeys(
            {"focus_search": "", "add_task": "Ctrl+N", "reload_current_tab": "F5"}
        )
        is not None
    )
    assert validate_hotkeys(loaded.hotkeys) is None


def test_settings_drops_unknown_keys(tmp_path: Path):
    work = tmp_path / "w"
    work.mkdir()
    path = tmp_path / "settings.json"
    path.write_text(
        f'{{"work_dir": "{work.as_posix()}", "dsn": "oracle", "far": "x"}}',
        encoding="utf-8",
    )
    loaded = SettingsStore(path).load()
    data = loaded.to_dict()
    assert "dsn" not in data
    assert "far" not in data
    assert data["work_dir"] == str(work) or data["work_dir"] == work.as_posix()


def test_event_settings_roundtrip_and_invalid_snooze(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(
        work_dir=str(tmp_path / "work"),
        event_sound_enabled=False,
        event_os_notification=False,
        event_snooze_minutes=60,
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.event_sound_enabled is False
    assert loaded.event_os_notification is False
    assert loaded.event_snooze_minutes == 60

    work = tmp_path / "w2"
    work.mkdir()
    path2 = tmp_path / "settings2.json"
    path2.write_text(
        f'{{"work_dir": "{work.as_posix()}", "event_snooze_minutes": 7}}',
        encoding="utf-8",
    )
    loaded2 = SettingsStore(path2).load()
    assert loaded2.event_snooze_minutes == 15
    assert loaded2.event_sound_enabled is True
    assert loaded2.event_os_notification is True


def test_startup_update_flags_roundtrip_and_defaults(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(
        work_dir=str(tmp_path / "work"),
        check_updates_on_startup=False,
        check_module_updates_on_startup=False,
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.check_updates_on_startup is False
    assert loaded.check_module_updates_on_startup is False

    work = tmp_path / "w2"
    work.mkdir()
    path2 = tmp_path / "settings2.json"
    path2.write_text(
        f'{{"work_dir": "{work.as_posix()}"}}',
        encoding="utf-8",
    )
    loaded2 = SettingsStore(path2).load()
    assert loaded2.check_updates_on_startup is True
    assert loaded2.check_module_updates_on_startup is True


def test_calendar_view_roundtrip_and_defaults(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(work_dir=str(tmp_path / "work"), calendar_view="week")
    store.save(settings)
    loaded = store.load()
    assert loaded.calendar_view == "week"

    work = tmp_path / "w2"
    work.mkdir()
    path2 = tmp_path / "settings2.json"
    path2.write_text(
        f'{{"work_dir": "{work.as_posix()}", "calendar_view": "nope"}}',
        encoding="utf-8",
    )
    loaded2 = SettingsStore(path2).load()
    assert loaded2.calendar_view == "compact"


def test_calendar_layout_roundtrip_and_defaults(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(
        work_dir=str(tmp_path / "work"),
        calendar_view="week",
        calendar_week_splitter=[220, 500],
        calendar_compact_splitter=[400, 120],
        calendar_day_pane_open=True,
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.calendar_week_splitter == [220, 500]
    assert loaded.calendar_compact_splitter == [400, 120]
    assert loaded.calendar_day_pane_open is True

    work = tmp_path / "w2"
    work.mkdir()
    path2 = tmp_path / "settings2.json"
    path2.write_text(
        f'{{"work_dir": "{work.as_posix()}", "calendar_week_splitter": "nope"}}',
        encoding="utf-8",
    )
    loaded2 = SettingsStore(path2).load()
    assert loaded2.calendar_week_splitter == []
    assert loaded2.calendar_compact_splitter == []
    assert loaded2.calendar_day_pane_open is False


def test_image_preview_width_roundtrip_and_defaults(tmp_path: Path):
    from taskmanager.services.settings_service import (
        DEFAULT_IMAGE_PREVIEW_WIDTH,
        IMAGE_PREVIEW_ORIGINAL,
        IMAGE_PREVIEW_SMALL,
        parse_image_preview_width,
    )

    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(
        work_dir=str(tmp_path / "work"),
        image_preview_width=IMAGE_PREVIEW_SMALL,
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.image_preview_width == 240

    work = tmp_path / "w2"
    work.mkdir()
    path2 = tmp_path / "settings2.json"
    path2.write_text(
        f'{{"work_dir": "{work.as_posix()}"}}',
        encoding="utf-8",
    )
    loaded2 = SettingsStore(path2).load()
    assert loaded2.image_preview_width == DEFAULT_IMAGE_PREVIEW_WIDTH
    assert parse_image_preview_width("nope") == DEFAULT_IMAGE_PREVIEW_WIDTH
    assert parse_image_preview_width(IMAGE_PREVIEW_ORIGINAL) == 0
    assert parse_image_preview_width(99) == DEFAULT_IMAGE_PREVIEW_WIDTH


def test_show_in_tray_roundtrip_and_default_on(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(work_dir=str(tmp_path / "work"), show_in_tray=False)
    store.save(settings)
    loaded = store.load()
    assert loaded.show_in_tray is False

    work = tmp_path / "w2"
    work.mkdir()
    path2 = tmp_path / "settings2.json"
    path2.write_text(
        f'{{"work_dir": "{work.as_posix()}"}}',
        encoding="utf-8",
    )
    loaded2 = SettingsStore(path2).load()
    assert loaded2.show_in_tray is True
