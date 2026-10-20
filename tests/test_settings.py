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


def test_keep_priority_on_source_refresh_roundtrip_and_default_off(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(
        work_dir=str(tmp_path / "work"), keep_priority_on_source_refresh=True
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.keep_priority_on_source_refresh is True

    work = tmp_path / "w2"
    work.mkdir()
    path2 = tmp_path / "settings2.json"
    path2.write_text(
        f'{{"work_dir": "{work.as_posix()}"}}',
        encoding="utf-8",
    )
    loaded2 = SettingsStore(path2).load()
    assert loaded2.keep_priority_on_source_refresh is False


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


def test_settings_load_skips_write_when_values_match(tmp_path: Path):
    work = tmp_path / "w"
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.save(Settings(work_dir=str(work)))
    store.load()
    canonical = json.loads(path.read_text(encoding="utf-8"))
    reordered = {key: canonical[key] for key in reversed(list(canonical))}
    path.write_text(
        json.dumps(reordered, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )
    before = path.read_bytes()
    if work.exists():
        work.rmdir()
    loaded = SettingsStore(path).load()
    assert loaded.to_dict() == canonical
    assert path.read_bytes() == before
    assert work.is_dir()


def test_settings_load_rewrites_missing_keys(tmp_path: Path):
    work = tmp_path / "w"
    work.mkdir()
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"work_dir": str(work)}), encoding="utf-8")
    before = path.read_bytes()
    loaded = SettingsStore(path).load()
    assert path.read_bytes() != before
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == loaded.to_dict()
    assert "template_name" in on_disk


def test_settings_load_rewrites_legacy_source_modules_key(tmp_path: Path):
    work = tmp_path / "w"
    work.mkdir()
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.save(Settings(work_dir=str(work)))
    store.load()
    canonical = json.loads(path.read_text(encoding="utf-8"))
    raw = dict(canonical)
    raw["source_modules"] = [
        {
            "module_id": "razr",
            "enabled": True,
            "github_repo": "https://github.com/ShiragG/taskmanager-source-razr",
            "display_name": "Разработка (razr)",
            "login": "user",
        }
    ]
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    before = path.read_bytes()
    loaded_store = SettingsStore(path)
    loaded = loaded_store.load()
    assert path.read_bytes() != before
    assert loaded.to_dict() == canonical
    assert "source_modules" not in json.loads(path.read_text(encoding="utf-8"))
    assert loaded_store.pending_source_module_migration[0].module_id == "razr"


def test_source_status_highlights_roundtrip(tmp_path: Path):
    from taskmanager.services.settings_service import (
        SourceStatusHighlight,
        source_status_mark_color,
    )

    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(
        work_dir=str(tmp_path / "work"),
        source_status_highlights={
            "razr": SourceStatusHighlight(
                enabled=True,
                colors={"10": "#FF0000", "3": "nope", "4": "#abc"},
                labels={"10": "  НАЗНАЧЕНО ", "x": "  ", "": "no"},
            ),
            "empty": SourceStatusHighlight(),
        },
    )
    assert settings.source_status_highlights["razr"].colors == {
        "10": "#ff0000",
        "4": "#aabbcc",
    }
    assert settings.source_status_highlights["razr"].labels == {"10": "НАЗНАЧЕНО"}
    assert "empty" not in settings.to_dict()["source_status_highlights"]
    assert (
        source_status_mark_color(settings.source_status_highlights, "razr", "10")
        == "#ff0000"
    )
    assert (
        source_status_mark_color(settings.source_status_highlights, "razr", "3")
        is None
    )
    off = SourceStatusHighlight(
        enabled=False, colors={"10": "#ff0000"}, labels={"10": "A"}
    )
    assert source_status_mark_color({"razr": off}, "razr", "10") is None
    store.save(settings)
    loaded = store.load()
    assert loaded.source_status_highlights["razr"].enabled is True
    assert loaded.source_status_highlights["razr"].colors["4"] == "#aabbcc"
    assert loaded.source_status_highlights["razr"].labels["10"] == "НАЗНАЧЕНО"
    assert "empty" not in loaded.source_status_highlights

    work = tmp_path / "w"
    work.mkdir()
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(
        json.dumps(
            {
                "work_dir": str(work),
                "source_status_highlights": {
                    "razr": {
                        "enabled": "yes",
                        "colors": {"1": "#00ff00"},
                        "labels": {"1": "Ok"},
                    },
                    "   ": {"enabled": True, "colors": {"1": "#ffffff"}},
                    "bad": ["nope"],
                },
            }
        ),
        encoding="utf-8",
    )
    parsed = SettingsStore(raw_path).load()
    assert parsed.source_status_highlights["razr"].enabled is False
    assert parsed.source_status_highlights["razr"].colors["1"] == "#00ff00"
    assert (
        source_status_mark_color(parsed.source_status_highlights, "razr", "1")
        is None
    )
    assert "   " not in parsed.source_status_highlights
    assert "bad" not in parsed.source_status_highlights


def test_last_seen_version_roundtrip_and_invalid(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(work_dir=str(tmp_path / "work"), last_seen_version="0.11.0")
    store.save(settings)
    assert store.load().last_seen_version == "0.11.0"

    work = tmp_path / "w"
    work.mkdir()
    raw = tmp_path / "raw.json"
    raw.write_text(
        json.dumps({"work_dir": str(work), "last_seen_version": 11}),
        encoding="utf-8",
    )
    assert SettingsStore(raw).load().last_seen_version == ""

    raw.write_text(
        json.dumps({"work_dir": str(work), "last_seen_version": "  0.10.8  "}),
        encoding="utf-8",
    )
    assert SettingsStore(raw).load().last_seen_version == "0.10.8"


def test_workflow_status_colors_roundtrip(tmp_path: Path):
    from taskmanager.domain import WorkflowStatus
    from taskmanager.services.settings_service import workflow_status_mark_color

    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(
        work_dir=str(tmp_path / "work"),
        highlight_workflow_statuses=True,
        workflow_status_colors={
            "in_progress": "#FF0000",
            "done": "#abc",
            "waiting": "nope",
            "archived": "#ffffff",
            "": "#000000",
        },
    )
    assert settings.highlight_workflow_statuses is True
    assert settings.workflow_status_colors == {
        "in_progress": "#ff0000",
        "done": "#aabbcc",
    }
    assert (
        workflow_status_mark_color(
            settings.highlight_workflow_statuses,
            settings.workflow_status_colors,
            WorkflowStatus.IN_PROGRESS,
        )
        == "#ff0000"
    )
    assert (
        workflow_status_mark_color(
            settings.highlight_workflow_statuses,
            settings.workflow_status_colors,
            WorkflowStatus.NEW,
        )
        is None
    )
    assert (
        workflow_status_mark_color(
            False, settings.workflow_status_colors, "in_progress"
        )
        is None
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.highlight_workflow_statuses is True
    assert loaded.workflow_status_colors == {
        "in_progress": "#ff0000",
        "done": "#aabbcc",
    }
    assert "archived" not in loaded.workflow_status_colors

    work = tmp_path / "w"
    work.mkdir()
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(
        json.dumps(
            {
                "work_dir": str(work),
                "highlight_workflow_statuses": "yes",
                "workflow_status_colors": {
                    "new": "#00ff00",
                    "nope": "#ffffff",
                    "waiting": "",
                },
            }
        ),
        encoding="utf-8",
    )
    parsed = SettingsStore(raw_path).load()
    assert parsed.highlight_workflow_statuses is False
    assert parsed.workflow_status_colors == {"new": "#00ff00"}
    assert (
        workflow_status_mark_color(
            parsed.highlight_workflow_statuses,
            parsed.workflow_status_colors,
            "new",
        )
        is None
    )
    off = Settings(
        work_dir=str(work),
        highlight_workflow_statuses=False,
        workflow_status_colors={"new": "#00ff00"},
    )
    assert off.workflow_status_colors == {"new": "#00ff00"}
    assert workflow_status_mark_color(True, off.workflow_status_colors, "new") == (
        "#00ff00"
    )
