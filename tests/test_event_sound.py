from pathlib import Path

from taskmanager.infrastructure.event_sounds import (
    first_preferred_sound_path,
    list_system_sound_files,
    parse_event_sound_path,
    sound_choice_label,
)
from taskmanager.services.settings_service import Settings, SettingsStore


def test_list_system_sound_files_only_existing_audio(tmp_path: Path):
    (tmp_path / "ding.wav").write_bytes(b"x")
    (tmp_path / "readme.txt").write_bytes(b"x")
    nested = tmp_path / "theme" / "stereo"
    nested.mkdir(parents=True)
    (nested / "bell.ogg").write_bytes(b"x")
    (nested / "note.mp3").write_bytes(b"x")
    found = list_system_sound_files(roots=[tmp_path])
    names = {path.name for path in found}
    assert names == {"ding.wav", "bell.ogg"}


def test_first_preferred_sound_picks_ding_before_bell(tmp_path: Path):
    bell = tmp_path / "bell.wav"
    ding = tmp_path / "ding.ogg"
    other = tmp_path / "click.flac"
    bell.write_bytes(b"x")
    ding.write_bytes(b"x")
    other.write_bytes(b"x")
    assert Path(first_preferred_sound_path([bell, other, ding])).name == "ding.ogg"


def test_first_preferred_sound_empty_when_nothing_matches(tmp_path: Path):
    click = tmp_path / "click.wav"
    click.write_bytes(b"x")
    assert first_preferred_sound_path([click]) == ""


def test_sound_choice_label_marks_missing(tmp_path: Path):
    missing = tmp_path / "gone.wav"
    assert sound_choice_label(missing) == "gone.wav (нет файла)"
    present = tmp_path / "here.wav"
    present.write_bytes(b"x")
    assert sound_choice_label(present) == "here.wav"


def test_parse_event_sound_path_keeps_missing_and_fills_empty(tmp_path: Path):
    missing = "/definitely/missing/ding.wav"
    assert parse_event_sound_path(missing) == missing
    ding = tmp_path / "message.oga"
    ding.write_bytes(b"x")
    assert parse_event_sound_path("", candidates=[ding]) == str(ding)
    assert parse_event_sound_path(None, candidates=[]) == ""


def test_from_dict_broken_snooze_and_path_does_not_raise():
    settings = Settings.from_dict(
        {
            "event_snooze_minutes": "nope",
            "event_sound_path": "/definitely/missing/ding.wav",
            "event_sound_enabled": 1,
        }
    )
    assert settings.event_snooze_minutes == 15
    assert settings.event_sound_path == "/definitely/missing/ding.wav"
    assert settings.event_sound_enabled is True


def test_settings_store_roundtrip_keeps_missing_sound_path(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    missing = str(tmp_path / "deleted.wav")
    settings = Settings(work_dir=str(tmp_path / "work"), event_sound_path=missing)
    store.save(settings)
    loaded = store.load()
    assert loaded.event_sound_path == missing


def test_event_sound_player_missing_path_is_silence():
    from taskmanager.ui.event_sound_player import EventSoundPlayer

    player = EventSoundPlayer()
    assert player.play("") is False
    assert player.play("/no/such/sound.wav") is False


def test_settings_dialog_marks_missing_sound_file(tmp_path: Path, qtbot):
    from taskmanager.ui.settings_dialog import SettingsDialog

    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    missing = tmp_path / "gone.wav"
    settings = Settings(work_dir=str(work), event_sound_path=str(missing))
    store.save(settings)
    dialog = SettingsDialog(settings, store)
    qtbot.addWidget(dialog)
    assert dialog.event_sound_combo.currentData() == str(missing)
    assert "нет файла" in dialog.event_sound_combo.currentText()
    assert dialog.preview_sound_btn.text() == "Прослушать"
