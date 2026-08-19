"""Combo + preview for an Event sound file, with copy-on-custom-pick."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QWidget,
)

from taskmanager.infrastructure.event_sounds import (
    CUSTOM_SOUND_SENTINEL,
    SETTINGS_SOUND_SENTINEL,
    copy_custom_sound,
    first_preferred_sound_path,
    list_system_sound_files,
    sound_choice_label,
)
from taskmanager.ui.event_sound_player import EventSoundPlayer


class EventSoundPicker(QWidget):
    """System sounds, optional «Как в настройках», and «Свой файл…» (copied)."""

    def __init__(
        self,
        parent=None,
        *,
        selected_path: str | None = None,
        include_settings_default: bool = False,
        settings_path: str = "",
    ) -> None:
        super().__init__(parent)
        self._include_settings_default = include_settings_default
        self._settings_path = settings_path or ""
        self._picking_custom_sound = False
        self._sound_combo_index = 0
        self._previewing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.combo = QComboBox()
        self.preview_btn = QPushButton("Прослушать")
        self.preview_btn.setObjectName("secondaryButton")
        self.preview_btn.clicked.connect(self._preview)
        layout.addWidget(self.combo, stretch=1)
        layout.addWidget(self.preview_btn)

        self._player = EventSoundPlayer(self)
        self._player.finished.connect(self._on_preview_finished)
        self._fill(selected_path)
        self.combo.currentIndexChanged.connect(self._on_changed)

    @property
    def current_path(self) -> str | None:
        """Stored path. None means use the settings default (Event form)."""
        data = self.combo.currentData()
        if not data or data == CUSTOM_SOUND_SENTINEL:
            return None if self._include_settings_default else self._settings_path
        if data == SETTINGS_SOUND_SENTINEL:
            return None
        return str(data)

    def _fill(self, selected_path: str | None) -> None:
        self.combo.blockSignals(True)
        self.combo.clear()
        if self._include_settings_default:
            self.combo.addItem("Как в настройках", SETTINGS_SOUND_SENTINEL)
        paths = [str(path) for path in list_system_sound_files()]
        if selected_path and selected_path not in paths:
            paths.insert(0, selected_path)
        for path in paths:
            self.combo.addItem(sound_choice_label(path), path)
        self.combo.addItem("Свой файл…", CUSTOM_SOUND_SENTINEL)
        if selected_path:
            idx = self.combo.findData(selected_path)
            self.combo.setCurrentIndex(idx if idx >= 0 else 0)
        elif self._include_settings_default:
            self.combo.setCurrentIndex(0)
        else:
            preferred = first_preferred_sound_path()
            idx = self.combo.findData(preferred) if preferred else -1
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
            elif self.combo.count() > 1:
                self.combo.setCurrentIndex(0)
        self._sound_combo_index = self.combo.currentIndex()
        self.combo.blockSignals(False)

    def _on_changed(self, index: int) -> None:
        self._stop_preview()
        if self._picking_custom_sound:
            return
        if self.combo.itemData(index) != CUSTOM_SOUND_SENTINEL:
            self._sound_combo_index = index
            return
        self._picking_custom_sound = True
        try:
            chosen, _filter = QFileDialog.getOpenFileName(
                self,
                "Звук события",
                "",
                "Звук (*.wav *.ogg *.oga *.flac);;Все файлы (*)",
            )
            if chosen:
                try:
                    copied = copy_custom_sound(chosen)
                except OSError as exc:
                    QMessageBox.warning(
                        self, "Ошибка", f"Не удалось скопировать звук:\n{exc}"
                    )
                    self._restore_index()
                    return
                self._ensure_path(str(copied))
                self._sound_combo_index = self.combo.currentIndex()
                return
            self._restore_index()
        finally:
            self._picking_custom_sound = False

    def _restore_index(self) -> None:
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(self._sound_combo_index)
        self.combo.blockSignals(False)

    def _ensure_path(self, path: str) -> None:
        idx = self.combo.findData(path)
        if idx < 0:
            insert_at = max(0, self.combo.count() - 1)
            self.combo.insertItem(insert_at, sound_choice_label(path), path)
            idx = insert_at
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(idx)
        self.combo.blockSignals(False)

    def _stop_preview(self) -> None:
        self._player.stop()
        self._previewing = False
        self.preview_btn.setText("Прослушать")

    def _on_preview_finished(self) -> None:
        self._previewing = False
        self.preview_btn.setText("Прослушать")

    def _preview(self) -> None:
        if self._previewing:
            self._stop_preview()
            return
        data = self.combo.currentData()
        if data == CUSTOM_SOUND_SENTINEL:
            return
        if data == SETTINGS_SOUND_SENTINEL or not data:
            path = self._settings_path
        else:
            path = str(data)
        if not path:
            return
        if self._player.play(path):
            self._previewing = True
            self.preview_btn.setText("Стоп")
