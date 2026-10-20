"""Read-only «Что нового» window built from user-facing markdown."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from taskmanager.services.release_notes import (
    default_minor_line,
    group_minor_lines,
    load_bundled_notes,
    markdown_for_line,
    parse_release_sections,
    should_auto_show_whats_new,
)
from taskmanager.services.settings_service import Settings, SettingsStore
from taskmanager.version import get_version

_EMPTY_NOTES = "Заметок пока нет."


class WhatsNewDialog(QDialog):
    def __init__(
        self,
        notes_text: str,
        *,
        current_version: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Что нового")
        self.setMinimumSize(520, 420)
        self._lines = group_minor_lines(parse_release_sections(notes_text))

        layout = QVBoxLayout(self)
        self._version_row = QWidget()
        row = QHBoxLayout(self._version_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Версия"))
        self.version_combo = QComboBox()
        self.version_combo.setObjectName("whatsNewVersionCombo")
        row.addWidget(self.version_combo, stretch=1)
        layout.addWidget(self._version_row)

        self.notes = QTextBrowser()
        self.notes.setObjectName("whatsNewNotes")
        self.notes.setReadOnly(True)
        self.notes.setOpenExternalLinks(False)
        layout.addWidget(self.notes, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setText("Закрыть")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if not self._lines:
            self._version_row.hide()
            self.notes.setPlainText(_EMPTY_NOTES)
            return

        self.version_combo.blockSignals(True)
        for label, _sections in self._lines:
            self.version_combo.addItem(label)
        selected = default_minor_line(self._lines, current_version)
        index = next(
            (i for i, (label, _sections) in enumerate(self._lines) if label == selected),
            0,
        )
        self.version_combo.setCurrentIndex(index)
        self.version_combo.blockSignals(False)
        self.version_combo.currentIndexChanged.connect(self._show_line)
        self._show_line(index)

    def _show_line(self, index: int) -> None:
        if index < 0 or index >= len(self._lines):
            return
        _label, sections = self._lines[index]
        self.notes.setMarkdown(markdown_for_line(sections))


def remember_seen_version(
    settings: Settings,
    store: SettingsStore,
    version: str,
) -> None:
    version = version.strip()
    if settings.last_seen_version == version:
        return
    settings.last_seen_version = version
    store.save(settings)


def show_whats_new(
    parent,
    settings: Settings,
    store: SettingsStore,
    *,
    force: bool = False,
    current_version: str | None = None,
    notes_text: str | None = None,
) -> bool:
    """Show the notes window. Auto-open only when this minor line has notes."""
    version = (current_version if current_version is not None else get_version()).strip()
    text = load_bundled_notes() if notes_text is None else notes_text
    if not force and not should_auto_show_whats_new(
        settings.last_seen_version, version, text
    ):
        return False
    dialog = WhatsNewDialog(text, current_version=version, parent=parent)
    dialog.exec()
    remember_seen_version(settings, store, version)
    return True
