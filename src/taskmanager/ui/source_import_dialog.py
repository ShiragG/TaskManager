"""Import Source item → TaskDialog or bulk create; pick by list or number."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidgetAction,
)

from taskmanager.services.source_host import SourceHost, plain_text_to_html
from taskmanager.services.source_protocol import (
    SourceDraft,
    SourceModuleError,
    SourceStatusOption,
)

logger = logging.getLogger(__name__)

# UserRole+1: True when the Source item is already linked in this Project.
_ROLE_ALREADY_IMPORTED = Qt.ItemDataRole.UserRole + 1


class SourceImportDialog(QDialog):
    """Choose enabled module, then list or number → returns a SourceDraft.

    Bulk path emits ``bulk_import_requested`` and keeps the dialog open.
    """

    bulk_import_requested = Signal(str, list)  # module_id, external_ids

    def __init__(
        self,
        source_host: SourceHost,
        parent=None,
        *,
        project_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Импорт из источника")
        self.setMinimumSize(640, 480)
        self._host = source_host
        self._project_id = project_id
        self.draft: SourceDraft | None = None
        self.module_id: str | None = None
        self.download_files = False
        self._imported_ids: set[str] = set()
        self._status_checks: dict[str, QCheckBox] = {}
        self._status_options: list[SourceStatusOption] = []
        self._catalog_error: str | None = None
        self._page = 0
        self._has_more = False
        self._loading = False
        self._loaded_filters: list[str] | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.module_combo = QComboBox()
        for loaded in source_host.enabled_modules():
            name = (
                loaded.config.display_name
                or (loaded.manifest.display_name if loaded.manifest else loaded.config.module_id)
            )
            self.module_combo.addItem(name, loaded.config.module_id)
        self.module_combo.currentIndexChanged.connect(self._on_module_changed)
        form.addRow("Модуль", self.module_combo)

        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText("Номер элемента источника…")
        num_row = QHBoxLayout()
        num_row.addWidget(self.number_edit)
        self.fetch_btn = QPushButton("Открыть номер")
        self.fetch_btn.clicked.connect(self._fetch_by_number)
        num_row.addWidget(self.fetch_btn)
        form.addRow("По номеру", num_row)

        layout.addLayout(form)

        list_row = QHBoxLayout()
        self.status_btn = QToolButton()
        self.status_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.status_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._status_menu = QMenu(self)
        self.status_btn.setMenu(self._status_menu)
        list_row.addWidget(self.status_btn)
        self.load_btn = QPushButton("Загрузить список")
        self.load_btn.setObjectName("secondaryButton")
        self.load_btn.clicked.connect(self._load_list)
        list_row.addWidget(self.load_btn)
        layout.addLayout(list_row)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._pick_list_item)
        self.list_widget.itemChanged.connect(self._on_item_changed)
        self.list_widget.verticalScrollBar().valueChanged.connect(
            self._on_list_scroll
        )
        layout.addWidget(self.list_widget)

        action_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Выделить все")
        self.select_all_btn.setObjectName("secondaryButton")
        self.select_all_btn.clicked.connect(self._select_all_selectable)
        action_row.addWidget(self.select_all_btn)
        self.import_btn = QPushButton("Импортировать")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._bulk_import)
        action_row.addWidget(self.import_btn)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.download_cb = QCheckBox("Скачать файлы источника")
        self.download_cb.setChecked(True)
        layout.addWidget(self.download_cb)

        self.hint = QLabel(
            "Список — задачи текущего пользователя; статусы из каталога модуля. "
            "По номеру — любая доступная карточка."
        )
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #64748b;")
        layout.addWidget(self.hint)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        self.progress.setMinimumHeight(18)
        layout.addWidget(self.progress)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self._busy = False

        if self.module_combo.count() == 0:
            self.hint.setText("Нет включённых модулей — настройте их в Настройках.")
            self.status_btn.setText("Статусы ▾")
            self.status_btn.setEnabled(False)
        else:
            self._on_module_changed()

    def refresh_imported_marks(self) -> None:
        """Reload already-imported ids and update list item flags."""
        self._reload_imported_ids()
        self.list_widget.blockSignals(True)
        try:
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                external_id = item.data(Qt.ItemDataRole.UserRole)
                if external_id is None:
                    continue
                self._apply_import_state(item, str(external_id))
        finally:
            self.list_widget.blockSignals(False)
        self._sync_import_button()

    def begin_bulk_progress(self, total: int) -> None:
        """Show progress UI and lock controls for a bulk import run."""
        self._busy = True
        self._set_controls_enabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(0)
        self.progress.setFormat(f"%v / {total}")
        self.hint.setText(f"Импорт: 0 из {total}…")
        QApplication.processEvents()

    def update_bulk_progress(
        self, current: int, total: int, external_id: str = ""
    ) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(current)
        self.progress.setFormat(f"%v / {total}")
        if external_id:
            self.hint.setText(f"Импорт: {current} из {total} — {external_id}")
        else:
            self.hint.setText(f"Импорт: {current} из {total}…")
        QApplication.processEvents()

    def end_bulk_progress(self) -> None:
        self._busy = False
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self._set_controls_enabled(True)
        self._sync_import_button()
        QApplication.processEvents()

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.module_combo.setEnabled(enabled)
        self.number_edit.setEnabled(enabled)
        self.fetch_btn.setEnabled(enabled)
        self.load_btn.setEnabled(enabled)
        self.status_btn.setEnabled(enabled and not self._catalog_error)
        self.select_all_btn.setEnabled(enabled)
        self.download_cb.setEnabled(enabled)
        self.list_widget.setEnabled(enabled)
        self._buttons.setEnabled(enabled)
        if enabled:
            self._sync_import_button()
        else:
            self.import_btn.setEnabled(False)

    def reject(self) -> None:
        if self._busy:
            return
        super().reject()

    def _reload_imported_ids(self) -> None:
        module_id = self._current_module_id()
        if self._project_id is None or not module_id:
            self._imported_ids = set()
            return
        self._imported_ids = self._host.repo.list_source_external_ids(
            self._project_id, module_id
        )

    def _reset_list_pagination(self) -> None:
        self.list_widget.clear()
        self._page = 0
        self._has_more = False
        self._loading = False
        self._loaded_filters = None
        self._sync_import_button()

    def _on_module_changed(self, *_args) -> None:
        module_id = self._current_module_id()
        self._reset_list_pagination()
        self._reload_imported_ids()
        self._status_options = []
        self._catalog_error = None
        if not module_id:
            self.status_btn.setEnabled(False)
            self.status_btn.setText("Статусы ▾")
            return
        cache = self._host.get_catalog(module_id)
        if cache is None:
            # Lazy refresh if startup skipped (e.g. no creds yet)
            self._host.refresh_catalogs(module_ids=[module_id])
            cache = self._host.get_catalog(module_id)
        if cache is None:
            self._catalog_error = "Каталог статусов ещё не загружен"
        elif cache.error:
            self._catalog_error = cache.error
        else:
            self._status_options = list(cache.statuses)
        self._build_status_menu()
        self._sync_status_button_text()
        if self._catalog_error:
            self.hint.setText(f"Ошибка каталога: {self._catalog_error}")
            self.status_btn.setEnabled(False)
        elif not self._status_options:
            self.hint.setText(
                "Статусы: нет данных. Можно загрузить список без фильтра qstatus. "
                "По номеру — любая доступная карточка."
            )
            self.status_btn.setEnabled(True)
        else:
            self.hint.setText(
                "Список — задачи текущего пользователя; статусы из каталога модуля. "
                "По номеру — любая доступная карточка."
            )
            self.status_btn.setEnabled(True)

    def _build_status_menu(self) -> None:
        self._status_menu.clear()
        self._status_checks.clear()
        if not self._status_options and not self._catalog_error:
            empty = QAction("нет данных", self._status_menu)
            empty.setEnabled(False)
            self._status_menu.addAction(empty)
            return
        for opt in self._status_options:
            cb = QCheckBox(f"{opt.label} ({opt.id})")
            cb.setChecked(bool(opt.default_selected))
            cb.toggled.connect(self._on_status_filter_toggled)
            self._status_checks[opt.id] = cb
            action = QWidgetAction(self._status_menu)
            action.setDefaultWidget(cb)
            self._status_menu.addAction(action)
        if self._status_options:
            self._status_menu.addSeparator()
            select_all = QAction("Выбрать все", self._status_menu)
            select_all.triggered.connect(lambda: self._set_all_statuses(True))
            clear_all = QAction("Снять все", self._status_menu)
            clear_all.triggered.connect(lambda: self._set_all_statuses(False))
            self._status_menu.addAction(select_all)
            self._status_menu.addAction(clear_all)

    def _set_all_statuses(self, checked: bool) -> None:
        for cb in self._status_checks.values():
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
        self._on_status_filter_toggled()

    def _on_status_filter_toggled(self, *_args) -> None:
        self._sync_status_button_text()
        # Filters changed — drop loaded pages so scroll does not append mixed filters.
        if self._loaded_filters is not None and self._status_filters() != self._loaded_filters:
            self._reset_list_pagination()
            if not self._catalog_error and self._status_options:
                self.hint.setText(
                    "Список — задачи текущего пользователя; статусы из каталога модуля. "
                    "По номеру — любая доступная карточка."
                )

    def _sync_status_button_text(self, *_args) -> None:
        if self._catalog_error:
            self.status_btn.setText("Статусы: ошибка ▾")
            return
        if not self._status_options:
            self.status_btn.setText("Статусы: нет данных ▾")
            return
        selected = self._status_filters()
        if not selected:
            self.status_btn.setText("Статусы: не выбраны ▾")
            return
        if len(selected) == 1:
            sid = selected[0]
            name = next(
                (o.label for o in self._status_options if o.id == sid),
                sid,
            )
            self.status_btn.setText(f"Статусы: {name} ▾")
            return
        self.status_btn.setText(f"Статусы: выбрано {len(selected)} ▾")

    def _current_module_id(self) -> str | None:
        if self.module_combo.count() == 0:
            return None
        return self.module_combo.currentData()

    def _status_filters(self) -> list[str]:
        return [
            status_id
            for status_id, cb in self._status_checks.items()
            if cb.isChecked()
        ]

    def _load_list(self) -> None:
        """Load page 1 (replace). Used by the Загрузить список button."""
        self._fetch_list_page(page=1, append=False)

    def _on_list_scroll(self, value: int) -> None:
        bar = self.list_widget.verticalScrollBar()
        # maximum==0 means the list fits without scrolling — not a user scroll-end.
        if bar.maximum() <= 0 or value < bar.maximum():
            return
        if self._loading or not self._has_more or self._page < 1:
            return
        self._fetch_list_page(page=self._page + 1, append=True)

    def _fetch_list_page(self, *, page: int, append: bool) -> None:
        module_id = self._current_module_id()
        if not module_id:
            if not append:
                QMessageBox.information(self, "Импорт", "Нет включённых модулей")
            return
        if self._catalog_error:
            if not append:
                self.hint.setText(f"Ошибка каталога: {self._catalog_error}")
                QMessageBox.warning(
                    self,
                    "Импорт",
                    f"Не удалось загрузить каталог статусов:\n{self._catalog_error}",
                )
            return
        if self._loading:
            return
        filters = self._status_filters()
        logger.debug(
            "UI: import load list module=%s page=%s append=%s status_filters=%s",
            module_id,
            page,
            append,
            filters,
        )
        self._loading = True
        try:
            result = self._host.list_items(
                module_id, page=page, status_filters=filters
            )
        except SourceModuleError as exc:
            logger.warning("list_items failed: %s", exc)
            self._loading = False
            if not append:
                QMessageBox.warning(self, "Импорт", str(exc))
            else:
                self.hint.setText(f"Ошибка загрузки: {exc}")
            return

        if not append:
            self.list_widget.clear()
            self._reload_imported_ids()

        self.list_widget.blockSignals(True)
        try:
            for item in result.items:
                title = item.title or item.external_id
                label = f"{item.external_id}: {title}"
                if item.status:
                    label = f"[{item.status}] {label}"
                lw = QListWidgetItem(label)
                lw.setData(Qt.ItemDataRole.UserRole, item.external_id)
                self._apply_import_state(lw, item.external_id)
                self.list_widget.addItem(lw)
        finally:
            self.list_widget.blockSignals(False)

        # Stop when items empty or has_more=false (host does not invent cursors).
        self._page = result.page
        self._has_more = bool(result.has_more) and bool(result.items)
        self._loaded_filters = filters
        self._loading = False
        self._sync_import_button()

        total = self.list_widget.count()
        if total == 0:
            self.hint.setText("Нет данных")
        else:
            more = " (есть ещё страницы)" if self._has_more else ""
            self.hint.setText(f"Загружено: {total}{more}")
        logger.debug(
            "UI: import list loaded page=%s count=%s total=%s has_more=%s",
            result.page,
            len(result.items),
            total,
            self._has_more,
        )

    def _apply_import_state(self, item: QListWidgetItem, external_id: str) -> None:
        already = external_id in self._imported_ids
        item.setData(_ROLE_ALREADY_IMPORTED, already)
        flags = (
            Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEnabled
        )
        if already:
            flags = (
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setFlags(flags)
            item.setCheckState(Qt.CheckState.Checked)
        else:
            # setCheckState is required for the checkbox to appear (flags alone
            # leave Unchecked as a silent default with no indicator).
            was_checked = item.checkState() == Qt.CheckState.Checked
            item.setFlags(flags)
            item.setCheckState(
                Qt.CheckState.Checked
                if was_checked
                else Qt.CheckState.Unchecked
            )

    def _is_already_imported(self, item: QListWidgetItem) -> bool:
        return bool(item.data(_ROLE_ALREADY_IMPORTED))

    def _selectable_checked_ids(self) -> list[str]:
        ids: list[str] = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if self._is_already_imported(item):
                continue
            if item.checkState() != Qt.CheckState.Checked:
                continue
            external_id = item.data(Qt.ItemDataRole.UserRole)
            if external_id is not None:
                ids.append(str(external_id))
        return ids

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        self._sync_import_button()

    def _sync_import_button(self) -> None:
        self.import_btn.setEnabled(bool(self._selectable_checked_ids()))

    def _select_all_selectable(self) -> None:
        self.list_widget.blockSignals(True)
        try:
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if self._is_already_imported(item):
                    continue
                item.setCheckState(Qt.CheckState.Checked)
        finally:
            self.list_widget.blockSignals(False)
        self._sync_import_button()

    def _bulk_import(self) -> None:
        module_id = self._current_module_id()
        if not module_id:
            return
        candidates = self._selectable_checked_ids()
        # Skip any that became imported since load (belt and suspenders).
        importable = [eid for eid in candidates if eid not in self._imported_ids]
        skipped = len(candidates) - len(importable)
        if not importable:
            QMessageBox.information(
                self,
                "Импорт",
                "Нет выбранных элементов для импорта.",
            )
            return
        if len(importable) >= 2:
            msg = f"Импортировать {len(importable)} элементов?"
            if skipped:
                msg += f"\nПропущено уже импортированных: {skipped}."
            reply = QMessageBox.question(
                self,
                "Импорт",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.download_files = self.download_cb.isChecked()
        self.bulk_import_requested.emit(module_id, importable)

    def _pick_list_item(self, item: QListWidgetItem) -> None:
        external_id = item.data(Qt.ItemDataRole.UserRole)
        if external_id is None:
            return
        if self._is_already_imported(item) or str(external_id) in self._imported_ids:
            QMessageBox.information(
                self,
                "Импорт",
                "Этот элемент уже импортирован в текущий проект.",
            )
            return
        self._fetch(str(external_id))

    def _fetch_by_number(self) -> None:
        number = self.number_edit.text().strip()
        if not number:
            QMessageBox.warning(self, "Импорт", "Введите номер")
            return
        if number in self._imported_ids:
            QMessageBox.information(
                self,
                "Импорт",
                "Этот элемент уже импортирован в текущий проект.",
            )
            return
        self._fetch(number)

    def _fetch(self, external_id: str) -> None:
        module_id = self._current_module_id()
        if not module_id:
            return
        if external_id in self._imported_ids:
            QMessageBox.information(
                self,
                "Импорт",
                "Этот элемент уже импортирован в текущий проект.",
            )
            return
        logger.debug(
            "UI: import get_item module=%s external_id=%s",
            module_id,
            external_id,
        )
        try:
            draft = self._host.get_item(module_id, external_id)
        except SourceModuleError as exc:
            logger.warning("get_item failed: %s", exc)
            QMessageBox.warning(self, "Импорт", str(exc))
            return
        logger.debug(
            "UI: import draft ready number=%r desc_len=%s files=%s",
            draft.number,
            len(draft.description or ""),
            len(draft.files),
        )
        self.draft = draft
        self.module_id = module_id
        self.download_files = self.download_cb.isChecked()
        self.accept()


def draft_to_dialog_kwargs(draft: SourceDraft) -> dict:
    return {
        "initial_number": draft.number,
        "initial_description": plain_text_to_html(draft.description),
        "initial_priority": draft.priority,
        "initial_links": list(draft.links),
        "title": f"Импорт: {draft.number}",
    }
