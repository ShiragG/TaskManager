"""Separate scrollable dialog for Source module settings."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from taskmanager.services.settings_service import Settings, SettingsStore
from taskmanager.services.source_host import SourceHost
from taskmanager.ui.source_modules_settings import (
    HINT_TEXT,
    SourceModulesSettingsWidget,
)

CATALOG_UNAVAILABLE = "Свежий список статусов недоступен."


def status_color_rows(
    catalog: list[tuple[str, str]],
    colors: dict[str, str],
    labels: dict[str, str],
) -> list[tuple[str, str, str]]:
    """Catalog rows first, then saved ids the catalog no longer lists.

    Each row is ``(status id, label, #rrggbb or "")``. A catalog label
    replaces the saved one. An empty color means no mark.
    """
    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for status_id, label in catalog:
        sid = str(status_id).strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        text = str(label).strip() or labels.get(sid, "").strip() or sid
        rows.append((sid, text, colors.get(sid, "")))
    extras = list(dict.fromkeys([*colors, *labels]))
    for status_id in extras:
        sid = str(status_id).strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        text = labels.get(sid, "").strip() or sid
        rows.append((sid, text, colors.get(sid, "")))
    return rows


def _normalized_color(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    color = QColor(text)
    if not color.isValid():
        return ""
    return color.name()


class _StatusColorEditor(QWidget):
    def __init__(
        self,
        status_id: str,
        label: str,
        color: str,
        parent=None,
        *,
        picker_title: str = "Цвет статуса",
    ) -> None:
        super().__init__(parent)
        self.status_id = status_id
        self.label_text = label
        self._picker_title = picker_title
        self._color = _normalized_color(color)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.swatch = QPushButton()
        self.swatch.setFixedSize(28, 28)
        self.swatch.setAutoDefault(False)
        self.swatch.clicked.connect(self._pick)
        self.reset_btn = QPushButton("Сбросить")
        self.reset_btn.setObjectName("secondaryButton")
        self.reset_btn.setAutoDefault(False)
        self.reset_btn.clicked.connect(self._reset)
        layout.addWidget(self.swatch)
        layout.addWidget(self.reset_btn)
        layout.addStretch()
        self._sync_swatch()

    @property
    def color(self) -> str:
        return self._color

    def _sync_swatch(self) -> None:
        if self._color:
            self.swatch.setText("")
            self.swatch.setStyleSheet(
                "QPushButton {"
                f"background-color: {self._color};"
                "border: 1px solid #334155;"
                "border-radius: 3px;"
                "}"
            )
            self.swatch.setToolTip(self._color)
            return
        self.swatch.setText("∅")
        self.swatch.setStyleSheet(
            "QPushButton {"
            "background-color: #e2e8f0;"
            "border: 1px dashed #64748b;"
            "border-radius: 3px;"
            "color: #64748b;"
            "}"
        )
        self.swatch.setToolTip("Нет цвета")

    def _pick(self) -> None:
        initial = QColor(self._color) if self._color else QColor("#cccccc")
        if not initial.isValid():
            initial = QColor("#cccccc")
        chosen = QColorDialog.getColor(initial, self, self._picker_title)
        if not chosen.isValid():
            return
        self._color = chosen.name()
        self._sync_swatch()

    def _reset(self) -> None:
        self._color = ""
        self._sync_swatch()


class SourceStatusColorsDialog(QDialog):
    """Status label and optional color. Empty color draws no mark."""

    def __init__(
        self,
        rows: list[tuple[str, str, str]],
        *,
        catalog_unavailable: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Цвета статусов")
        self.setMinimumSize(420, 280)
        self.resize(460, 420)
        self._editors: list[_StatusColorEditor] = []

        layout = QVBoxLayout(self)
        self.notice = QLabel(CATALOG_UNAVAILABLE)
        self.notice.setObjectName("statusCatalogUnavailable")
        self.notice.setWordWrap(True)
        self.notice.setStyleSheet("color: #64748b;")
        self.notice.setVisible(catalog_unavailable)
        layout.addWidget(self.notice)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        host = QWidget()
        form = QFormLayout(host)
        for status_id, label, color in rows:
            editor = _StatusColorEditor(status_id, label, color)
            self._editors.append(editor)
            form.addRow(QLabel(label), editor)
        scroll.setWidget(host)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def collect(self) -> tuple[dict[str, str], dict[str, str]]:
        colors: dict[str, str] = {}
        labels: dict[str, str] = {}
        for editor in self._editors:
            text = editor.label_text.strip()
            if text:
                labels[editor.status_id] = text
            if editor.color:
                colors[editor.status_id] = editor.color
        return colors, labels


class SourceModulesSettingsDialog(QDialog):
    """Modules enable / install / credentials — not embedded in main Settings."""

    def __init__(
        self,
        settings: Settings,
        store: SettingsStore,
        source_host: SourceHost | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Модули источников")
        self.setMinimumSize(560, 420)
        self.resize(620, 520)
        self._settings = settings
        self._store = store
        self._source_host = source_host

        layout = QVBoxLayout(self)

        hint = QLabel(HINT_TEXT)
        hint.setObjectName("sourceModulesHint")
        hint.setWordWrap(True)
        hint.setMinimumHeight(48)
        hint.setStyleSheet("color: #64748b;")
        layout.addWidget(hint)

        self.check_module_updates_cb = QCheckBox(
            "Проверять наличие обновлений модулей при запуске"
        )
        self.check_module_updates_cb.setChecked(
            settings.check_module_updates_on_startup
        )
        layout.addWidget(self.check_module_updates_cb)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._modules_widget = SourceModulesSettingsWidget(
            source_host, scroll, settings=settings
        )
        scroll.setWidget(self._modules_widget)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        try:
            self._modules_widget.persist_credentials()
        except Exception as exc:
            QMessageBox.warning(
                self, "Модули", f"Не удалось сохранить учётные данные:\n{exc}"
            )
            return
        if self._source_host is not None:
            self._source_host.replace_registry(self._modules_widget.collect_configs())
            self._source_host.reload()
            self._source_host.refresh_catalogs()
        self._settings.check_module_updates_on_startup = (
            self.check_module_updates_cb.isChecked()
        )
        self._modules_widget.apply_status_highlights(self._settings)
        self._store.save(self._settings)
        self.accept()
