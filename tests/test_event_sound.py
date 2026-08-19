from pathlib import Path

from taskmanager.infrastructure.event_sounds import (
    CUSTOM_SOUND_SENTINEL,
    copy_custom_sound,
    event_ping_path,
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


def test_event_sound_player_stop_and_play_stops_previous():
    from taskmanager.ui.event_sound_player import EventSoundPlayer

    class FakeSource:
        def __init__(self) -> None:
            self.stopped = 0

        def stop(self) -> None:
            self.stopped += 1

    player = EventSoundPlayer()
    first = FakeSource()
    player._effect = first  # type: ignore[assignment]
    player.stop()
    assert first.stopped == 1

    second = FakeSource()
    player._player = second  # type: ignore[assignment]
    assert player.play("/no/such/sound.wav") is False
    assert first.stopped == 2
    assert second.stopped == 1


def test_settings_preview_button_toggles_stop(tmp_path, qtbot, monkeypatch):
    from taskmanager.ui.settings_dialog import SettingsDialog

    work = tmp_path / "work"
    work.mkdir()
    wav = tmp_path / "ding.wav"
    wav.write_bytes(b"x")
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work), event_sound_path=str(wav))
    store.save(settings)
    dialog = SettingsDialog(settings, store)
    qtbot.addWidget(dialog)
    monkeypatch.setattr(dialog._sound_player, "play", lambda path: True)
    stops: list[int] = []
    original_stop = dialog._sound_player.stop

    def spy_stop() -> None:
        stops.append(1)
        original_stop()

    monkeypatch.setattr(dialog._sound_player, "stop", spy_stop)
    dialog.preview_sound_btn.click()
    assert dialog.preview_sound_btn.text() == "Стоп"
    dialog.preview_sound_btn.click()
    assert dialog.preview_sound_btn.text() == "Прослушать"
    assert stops
    dialog.preview_sound_btn.click()
    assert dialog.preview_sound_btn.text() == "Стоп"
    dialog._on_sound_combo_changed(0)
    assert dialog.preview_sound_btn.text() == "Прослушать"
    dialog.preview_sound_btn.click()
    dialog._sound_player.finished.emit()
    assert dialog.preview_sound_btn.text() == "Прослушать"


def test_copy_custom_sound_into_app_sounds_keeps_original(tmp_path: Path):
    original = tmp_path / "Downloads" / "ping.wav"
    original.parent.mkdir()
    original.write_bytes(b"wav-bytes")
    dest_dir = tmp_path / "sounds"
    copied = copy_custom_sound(original, dest_dir=dest_dir)
    assert copied == dest_dir / "ping.wav"
    assert copied.read_bytes() == b"wav-bytes"
    assert original.is_file()
    again = copy_custom_sound(original, dest_dir=dest_dir)
    assert again.name == "ping_2.wav"
    already = copy_custom_sound(copied, dest_dir=dest_dir)
    assert already.resolve() == copied.resolve()


def test_settings_custom_sound_is_copied_and_survives_reopen(
    tmp_path: Path, qtbot, monkeypatch
):
    from taskmanager.ui.settings_dialog import SettingsDialog

    sounds_dir = str(tmp_path / "sounds")
    monkeypatch.setattr(
        "taskmanager.infrastructure.event_sounds.app_sounds_dir",
        lambda **_kwargs: sounds_dir,
    )
    original = tmp_path / "Downloads" / "bell.wav"
    original.parent.mkdir()
    original.write_bytes(b"bell-bytes")
    monkeypatch.setattr(
        "taskmanager.ui.event_sound_picker.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(original), ""),
    )
    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work))
    store.save(settings)
    dialog = SettingsDialog(settings, store)
    qtbot.addWidget(dialog)
    custom_idx = dialog.event_sound_combo.findData(CUSTOM_SOUND_SENTINEL)
    assert custom_idx >= 0
    dialog.event_sound_combo.setCurrentIndex(custom_idx)
    copied = (tmp_path / "sounds" / "bell.wav").resolve()
    assert copied.is_file()
    assert copied.read_bytes() == b"bell-bytes"
    assert original.is_file()
    assert Path(dialog.event_sound_combo.currentData()).resolve() == copied
    dialog._save()
    reopened = SettingsDialog(store.load(), store)
    qtbot.addWidget(reopened)
    assert Path(reopened.event_sound_combo.currentData()).resolve() == copied


def test_event_ping_path_uses_override_or_settings_or_silence():
    assert event_ping_path(None, "/s/ding.wav", enabled=True) == "/s/ding.wav"
    assert event_ping_path("", "/s/ding.wav", enabled=True) == "/s/ding.wav"
    assert event_ping_path("  ", "/s/ding.wav", enabled=True) == "/s/ding.wav"
    assert event_ping_path("/e/own.wav", "/s/ding.wav", enabled=True) == "/e/own.wav"
    assert event_ping_path("/e/own.wav", "/s/ding.wav", enabled=False) == ""
