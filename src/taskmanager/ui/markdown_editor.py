"""Text and Markdown editors for Task Description and Comment.

Both modes edit the same markdown. Text shows the rendered document.
Markdown shows the source. The toolbar is shared.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QBuffer,
    QEvent,
    QIODevice,
    QPoint,
    QRect,
    QSize,
    Qt,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QContextMenuEvent,
    QFont,
    QFontInfo,
    QImage,
    QImageReader,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPalette,
    QPen,
    QPolygon,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QTextFrameFormat,
    QTextImageFormat,
    QTextLength,
    QTextListFormat,
    QTextTableCellFormat,
    QTextTableFormat,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from taskmanager.domain.markdown_body import (
    _images_relative,
    _is_fenced_code_block,
    document_to_markdown,
    preview_html,
)
from taskmanager.infrastructure.filesystem import source_files_present
from taskmanager.infrastructure.platform_open import PlatformOpenError, open_target
from taskmanager.services.inline_images import sniff_image, write_markdown_image
from taskmanager.services.settings_service import (
    DEFAULT_IMAGE_PREVIEW_WIDTH,
    IMAGE_PREVIEW_MEDIUM,
    IMAGE_PREVIEW_ORIGINAL,
    IMAGE_PREVIEW_SMALL,
)
from taskmanager.services.task_service import ServiceError

_IMAGE_FILTER = "Изображения (*.png *.jpg *.jpeg *.gif *.webp)"
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
_QUOTE_MARGIN = 40
_LINK_COLOR = QColor("#0d9488")
_HEADING_LABELS = (("Обычный", 0),) + tuple(
    (f"Заголовок {level}", level) for level in range(1, 7)
)
# 1 is the largest. 6 stays only slightly larger than the editor font. All are bold.
_HEADING_SCALE = {
    1: 2.0,
    2: 20 / 13,
    3: 16 / 13,
    4: 15 / 13,
    5: 14 / 13,
    6: 13.5 / 13,
}
_TABLE_COLUMNS = 3
_TABLE_MARKDOWN = "|  |  |  |\n| --- | --- | --- |\n|  |  |  |"
_LIGHT_FILL = QColor("#e2e8f0")
_DARK_FILL = QColor("#334155")
_LIGHT_ACCENT = QColor("#0d9488")
_DARK_ACCENT = QColor("#2dd4bf")
_IMAGE_RESIZE_MIN = 40
_IMAGE_CORNER_HIT = 16

_HEADING_RE = re.compile(r"^#{1,6} ")
_TASK_RE = re.compile(r"^(\s*)([-+*])\s+\[[ xX]\]\s+")
_BULLET_RE = re.compile(r"^(\s*)([-+*])\s+")
_ORDER_RE = re.compile(r"^(\s*)\d+[.)]\s+")
_LINK_RE = re.compile(r"^\[([^\[\]]+)\]\(([^()\s]+)\)\s*$")
_FENCE_RE = re.compile(r"^```[^\n]*\n(.*)\n```$", re.DOTALL)

# Isolate toolbar buttons from the app stylesheet so checked state stays visible.
_TOOLBAR_QSS = """
QToolBar {
    background: palette(window);
    border: none;
    spacing: 4px;
    padding: 4px;
}
QToolBar QToolButton {
    background: transparent;
    color: palette(window-text);
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 4px 8px;
}
QToolBar QToolButton:hover {
    background: palette(midlight);
    border-color: palette(mid);
}
QToolBar QToolButton:pressed {
    background: palette(mid);
}
QToolBar QToolButton:checked {
    background: palette(highlight);
    color: palette(highlighted-text);
    border-color: palette(dark);
}
QToolBar QToolButton:checked:hover {
    background: palette(highlight);
}
"""


class MarkdownSourceEdit(QPlainTextEdit):
    """Markdown source. Pasting an image asks the dialog to store a file."""

    def __init__(self, on_image, parent=None) -> None:
        super().__init__(parent)
        self._on_image = on_image
        self.setPlaceholderText("Markdown…")

    def canInsertFromMimeData(self, source) -> bool:  # noqa: N802
        if _image_from_mime(source) is not None:
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:  # noqa: N802
        found = _image_from_mime(source)
        if found is not None:
            data, name = found
            self._on_image(data, name)
            return
        super().insertFromMimeData(source)


class _ImageHit:
    __slots__ = ("cursor", "view_rect", "position")

    def __init__(self, cursor: QTextCursor, view_rect: QRect, position: int) -> None:
        self.cursor = cursor
        self.view_rect = view_rect
        self.position = position


class MarkdownTextEdit(QTextEdit):
    """Rendered markdown. A click on a task box flips that task.

    Image display size lives here for the open editor only. The saved markdown
    stays ``![](.images/name)``.
    """

    def __init__(self, on_image, parent=None) -> None:
        super().__init__(parent)
        self._on_image = on_image
        self._press_pos = None
        self._applying_chrome = False
        self._drag_resize: tuple[int, int] | None = None
        self._natural_sizes: dict[str, QSize] = {}
        self._session_widths: dict[str, int] = {}
        self.image_preview_width = DEFAULT_IMAGE_PREVIEW_WIDTH
        self.setAcceptRichText(True)
        self.setMouseTracking(True)
        self.setPlaceholderText("Текст…")
        self.viewport().setMouseTracking(True)

    def canInsertFromMimeData(self, source) -> bool:  # noqa: N802
        if _image_from_mime(source) is not None:
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:  # noqa: N802
        found = _image_from_mime(source)
        if found is not None:
            data, name = found
            self._on_image(data, name)
            return
        super().insertFromMimeData(source)
        cursor = self.textCursor()
        position = cursor.position()
        anchor = cursor.anchor()
        _refresh_text_document(self)
        end = max(self.document().characterCount() - 1, 0)
        restored = self.textCursor()
        restored.setPosition(min(anchor, end))
        restored.setPosition(min(position, end), QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(restored)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if _handle_table_tab(self, event):
            return
        # Qt copies the list marker only. The checkbox is ordinary text, so a new
        # task item would otherwise have no box. An empty box leaves the list.
        if not _is_bare_enter(event) or not _cursor_in_task(self):
            super().keyPressEvent(event)
            return
        block = self.textCursor().block()
        if not _task_item_body(block).strip():
            _leave_empty_task(self, block)
            return
        _place_cursor_after_checkbox(self, block)
        previous = block.blockNumber()
        super().keyPressEvent(event)
        new_block = self.textCursor().block()
        if new_block.blockNumber() == previous or new_block.textList() is None:
            return
        if _checkbox_fragment(new_block) is None:
            _prefix_task_item(self, new_block)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._image_hit_at(pos)
            if (
                hit is not None
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier
            ):
                self._press_pos = None
                self._open_image(hit.cursor.charFormat().toImageFormat().name())
                event.accept()
                return
            if hit is not None and _near_image_corner(hit.view_rect, pos):
                self._press_pos = None
                self._drag_resize = (hit.position, hit.view_rect.left())
                event.accept()
                return
        self._press_pos = pos
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if self._drag_resize is not None:
            fragment_pos, left = self._drag_resize
            new_width = max(_IMAGE_RESIZE_MIN, pos.x() - left)
            cursor = self._cursor_for_image_at(fragment_pos)
            if cursor is not None:
                self.set_image_display_width(cursor, new_width)
            event.accept()
            return
        hit = self._image_hit_at(pos)
        if hit is not None and _near_image_corner(hit.view_rect, pos):
            self.viewport().setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif hit is not None:
            self.viewport().unsetCursor()
        elif self._checkbox_fragment_at(pos) is not None:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_resize is not None and event.button() == Qt.MouseButton.LeftButton:
            self._drag_resize = None
            event.accept()
            return
        pos = event.position().toPoint()
        if self._image_hit_at(pos) is not None:
            super().mouseReleaseEvent(event)
            return
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._press_pos is not None
            and (pos - self._press_pos).manhattanLength() <= 4
            and self.toggle_checkbox_at(pos)
        ):
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        hit = self._image_hit_at(event.pos())
        if hit is None:
            super().contextMenuEvent(event)
            return
        self._exec_menu(self._image_size_menu(hit), event.globalPos())
        event.accept()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            _apply_editor_chrome(self)
            _style_tables(self)
            self.viewport().update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setClipRect(event.rect())
        self._paint_quote_bars(painter)
        self._paint_task_boxes(painter)
        painter.end()

    def toggle_checkbox_at(self, pos) -> bool:
        fragment = self._checkbox_fragment_at(pos)
        if fragment is None:
            return False
        _flip_checkbox_fragment(self, fragment)
        return True

    def _checkbox_fragment_at(self, pos):
        block = self.cursorForPosition(pos).block()
        for candidate in (block.previous(), block, block.next()):
            if not candidate.isValid():
                continue
            fragment = _checkbox_fragment(candidate)
            if fragment is None:
                continue
            _erase, _square, hit = self._task_box_geometry(fragment)
            if hit.contains(pos):
                return fragment
        return None

    def _task_box_geometry(self, fragment):
        """Erase rect, drawn square, and a click rect wider than the square."""
        glyph = _glyph_viewport_rect(self, fragment)
        side = min(glyph.height() - 2, max(15, round(glyph.height() * 0.88)))
        side = max(side, 12)
        square = QRect(
            glyph.left() - side // 2,
            glyph.top() + max((glyph.height() - side) // 2, 0),
            side,
            side,
        )
        erase = QRect(
            square.left() - 4,
            glyph.top(),
            glyph.right() - (square.left() - 4) + 2,
            glyph.height(),
        )
        hit = square.adjusted(-6, -3, 6, 3)
        limit = glyph.right() + 4
        if hit.right() > limit:
            hit.setRight(limit)
        return erase, square, hit

    def _paint_quote_bars(self, painter: QPainter) -> None:
        accent = _accent_color(self)
        layout = self.document().documentLayout()
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        block = self.document().begin()
        while block.isValid():
            if block.blockFormat().leftMargin() >= 20:
                bounds = layout.blockBoundingRect(block)
                top = int(bounds.top()) - scroll_y
                left = int(bounds.left()) - scroll_x
                bar = QRect(left + 8, top + 1, 3, max(int(bounds.height()) - 2, 1))
                painter.fillRect(bar, accent)
            block = block.next()

    def _paint_task_boxes(self, painter: QPainter) -> None:
        border = self.palette().color(QPalette.ColorRole.Text)
        fill = self.palette().color(QPalette.ColorRole.Base)
        block = self.document().begin()
        while block.isValid():
            fragment = _checkbox_fragment(block)
            if fragment is not None:
                erase, square, _hit = self._task_box_geometry(fragment)
                painter.fillRect(erase, fill)
                _draw_task_box(
                    painter,
                    square,
                    checked=_glyph_mark(fragment.text()) == "x",
                    border=border,
                    fill=fill,
                )
            block = block.next()

    def apply_session_image_widths(self) -> None:
        """Size every image from the session, or from the preview setting."""
        for cursor in self.iter_image_cursors():
            fmt = cursor.charFormat().toImageFormat()
            key = _images_relative(fmt.name())
            if key is not None and key in self._session_widths:
                width = self._session_widths[key]
            else:
                width = self.image_preview_width
            self.set_image_display_width(cursor, width)

    def set_image_display_width(self, cursor: QTextCursor, width: int) -> None:
        fmt = cursor.charFormat()
        if not fmt.isImageFormat():
            return
        img_fmt = QTextImageFormat(fmt.toImageFormat())
        key = _images_relative(img_fmt.name())
        if key is not None:
            self._session_widths[key] = width
        natural = _natural_image_size(img_fmt, self._natural_sizes)
        if width <= 0:
            if natural.width() > 0:
                img_fmt.setWidth(natural.width())
                img_fmt.setHeight(natural.height())
            else:
                img_fmt.setWidth(0)
                img_fmt.setHeight(0)
        else:
            img_fmt.setWidth(width)
            if natural.width() > 0 and natural.height() > 0:
                img_fmt.setHeight(
                    max(1, round(width * natural.height() / natural.width()))
                )
            else:
                img_fmt.setHeight(0)
        cursor.setCharFormat(img_fmt)

    def iter_image_cursors(self) -> list[QTextCursor]:
        found: list[QTextCursor] = []
        block = self.document().firstBlock()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and fragment.charFormat().isImageFormat():
                    cursor = self._cursor_for_image_at(fragment.position())
                    if cursor is not None:
                        found.append(cursor)
                iterator += 1
            block = block.next()
        return found

    def _exec_menu(self, menu: QMenu, global_pos: QPoint) -> None:
        menu.exec(global_pos)

    def _image_size_menu(self, hit: _ImageHit) -> QMenu:
        menu = QMenu(self)
        menu.addAction(
            "Уменьшенная",
            lambda c=QTextCursor(hit.cursor): self.set_image_display_width(
                c, IMAGE_PREVIEW_SMALL
            ),
        )
        menu.addAction(
            "Средняя",
            lambda c=QTextCursor(hit.cursor): self.set_image_display_width(
                c, IMAGE_PREVIEW_MEDIUM
            ),
        )
        menu.addAction(
            "Исходная",
            lambda c=QTextCursor(hit.cursor): self.set_image_display_width(
                c, IMAGE_PREVIEW_ORIGINAL
            ),
        )
        menu.addAction(
            "Ширина…",
            lambda c=QTextCursor(hit.cursor): self._prompt_image_width(c),
        )
        return menu

    def _prompt_image_width(self, cursor: QTextCursor) -> None:
        fmt = cursor.charFormat()
        if not fmt.isImageFormat():
            return
        current = int(fmt.toImageFormat().width() or DEFAULT_IMAGE_PREVIEW_WIDTH)
        width, ok = QInputDialog.getInt(
            self,
            "Ширина",
            "Ширина (px):",
            current,
            _IMAGE_RESIZE_MIN,
            8000,
        )
        if ok:
            self.set_image_display_width(cursor, width)

    def _open_image(self, src: str) -> None:
        path = _image_file_path(src)
        if not path:
            return
        try:
            open_target(path)
        except PlatformOpenError as exc:
            QMessageBox.warning(self, "Предупреждение", str(exc))

    def _cursor_for_image_at(self, position: int) -> QTextCursor | None:
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        cursor.setPosition(position + 1, QTextCursor.MoveMode.KeepAnchor)
        if not cursor.charFormat().isImageFormat():
            return None
        return cursor

    def _image_hits(self) -> list[_ImageHit]:
        found: list[_ImageHit] = []
        doc_layout = self.document().documentLayout()
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        block = self.document().firstBlock()
        while block.isValid():
            block_rect = doc_layout.blockBoundingRect(block)
            layout = block.layout()
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                fmt = fragment.charFormat()
                if fragment.isValid() and fmt.isImageFormat() and layout is not None:
                    img_fmt = fmt.toImageFormat()
                    pos_in_block = fragment.position() - block.position()
                    line = layout.lineForTextPosition(pos_in_block)
                    if line.isValid():
                        x = line.cursorToX(pos_in_block)
                        if isinstance(x, tuple):
                            x = x[0]
                        natural = _natural_image_size(img_fmt, self._natural_sizes)
                        width = int(img_fmt.width() or natural.width() or 0)
                        height = int(img_fmt.height() or natural.height() or 0)
                        if width <= 0:
                            width = int(
                                natural.width()
                                or self.image_preview_width
                                or DEFAULT_IMAGE_PREVIEW_WIDTH
                            )
                        if height <= 0:
                            height = int(natural.height() or width)
                        view_rect = QRect(
                            int(block_rect.x() + line.x() + x) - scroll_x,
                            int(block_rect.y() + line.y()) - scroll_y,
                            width,
                            height,
                        )
                        cursor = self._cursor_for_image_at(fragment.position())
                        if cursor is not None:
                            found.append(
                                _ImageHit(cursor, view_rect, fragment.position())
                            )
                iterator += 1
            block = block.next()
        return found

    def _image_hit_at(self, view_pos: QPoint) -> _ImageHit | None:
        for hit in self._image_hits():
            if hit.view_rect.contains(view_pos):
                return hit
        return None

    def toggle_checkbox_index(self, index: int) -> bool:
        found = 0
        block = self.document().begin()
        while block.isValid():
            fragment = _checkbox_fragment(block)
            if fragment is not None:
                if found == index:
                    _flip_checkbox_fragment(self, fragment)
                    return True
                found += 1
            block = block.next()
        return False


class MarkdownEditDialog(QDialog):
    """Editable Text and Markdown views of one document."""

    def __init__(
        self,
        parent=None,
        *,
        title: str = "Текст",
        markdown: str = "",
        ensure_images_dir: Callable[[], Path] | None = None,
        images_dir: Path | None = None,
        source_files_dir: Path | None = None,
        show_source_files_button: bool = False,
        image_preview_width: int = DEFAULT_IMAGE_PREVIEW_WIDTH,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(820, 468)
        self.setStyleSheet("")
        self._ensure_images_dir = ensure_images_dir
        self._images_dir = images_dir
        self._source_files_dir = source_files_dir
        self.source_files_button: QPushButton | None = None

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.mode_combo.addItem("Текст", "text")
        self.mode_combo.addItem("Markdown", "markdown")
        self.mode_combo.currentIndexChanged.connect(self._mode_chosen)
        header.addWidget(self.mode_combo)

        toolbar = QToolBar()
        toolbar.setStyleSheet(_TOOLBAR_QSS)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.heading_combo = QComboBox()
        self.heading_combo.setToolTip("Заголовок")
        self.heading_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        for label, level in _HEADING_LABELS:
            self.heading_combo.addItem(label, level)
        self.heading_combo.currentIndexChanged.connect(self._heading_chosen)
        toolbar.addWidget(self.heading_combo)
        self.bold_action = self._add_format_action(
            toolbar,
            "Ж",
            "Жирный",
            self._toggle_bold,
            shortcut=QKeySequence.StandardKey.Bold,
        )
        self.italic_action = self._add_format_action(
            toolbar,
            "К",
            "Курсив",
            self._toggle_italic,
            shortcut=QKeySequence.StandardKey.Italic,
        )
        self.strike_action = self._add_format_action(
            toolbar, "З", "Зачёркнутый", self._toggle_strike
        )
        self.code_action = self._add_format_action(
            toolbar, "Код", "Код", self._toggle_code
        )
        self.quote_action = self._add_format_action(
            toolbar, ">", "Цитата", self._toggle_quote
        )
        self.bullet_action = self._add_format_action(
            toolbar, "•", "Маркированный список", self._toggle_bullet
        )
        self.numbered_action = self._add_format_action(
            toolbar, "1.", "Нумерованный список", self._toggle_numbered
        )
        self.todo_action = self._add_format_action(
            toolbar, "☐", "Список задач", self._toggle_todo
        )
        self.link_action = self._add_format_action(
            toolbar, "Ссылка", "Ссылка", self._insert_link, checkable=False
        )
        self.image_action = self._add_format_action(
            toolbar, "Рис.", "Вставить изображение", self._pick_image, checkable=False
        )
        self.table_action = self._add_format_action(
            toolbar, "Таблица", "Таблица", self._insert_table, checkable=False
        )
        header.addWidget(toolbar, 1)

        if show_source_files_button:
            files_button = QPushButton("Файлы")
            files_button.setToolTip("Открыть папку файлов источника")
            files_button.setEnabled(source_files_present(source_files_dir))
            files_button.clicked.connect(self._open_source_files)
            header.addWidget(files_button)
            self.source_files_button = files_button
        layout.addLayout(header)

        self.text_edit = MarkdownTextEdit(self.insert_image_bytes)
        self.text_edit.image_preview_width = image_preview_width
        self.source_edit = MarkdownSourceEdit(self.insert_image_bytes)
        self._load_text(markdown or "")
        self.stack = QStackedWidget()
        self.stack.addWidget(self.text_edit)
        self.stack.addWidget(self.source_edit)
        layout.addWidget(self.stack)

        self.text_edit.currentCharFormatChanged.connect(self._sync_format_actions)
        self.text_edit.cursorPositionChanged.connect(self._sync_format_actions)
        self.source_edit.cursorPositionChanged.connect(self._sync_format_actions)
        self._sync_format_actions()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_markdown_mode(self, source: bool) -> None:
        """Show Markdown source or the rendered Text editor."""
        showing_source = self._showing_source()
        if source:
            if not showing_source:
                self.source_edit.setPlainText(self._text_to_markdown())
            self.stack.setCurrentWidget(self.source_edit)
        else:
            if showing_source:
                self._load_text(self.source_edit.toPlainText())
            self.stack.setCurrentWidget(self.text_edit)
        self._show_mode(source)
        self._sync_format_actions()

    def _mode_chosen(self, index: int) -> None:
        data = self.mode_combo.itemData(index)
        if data is None:
            return
        self.set_markdown_mode(data == "markdown")

    def _show_mode(self, source: bool) -> None:
        index = self.mode_combo.findData("markdown" if source else "text")
        if index < 0 or self.mode_combo.currentIndex() == index:
            return
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(index)
        self.mode_combo.blockSignals(False)

    @property
    def markdown(self) -> str:
        if self._showing_source():
            return self.source_edit.toPlainText()
        return self._text_to_markdown()

    def toggle_task_checkbox(self, index: int) -> bool:
        """Flip the ``index``-th task glyph in Text, or the marker in Markdown."""
        if self._showing_source():
            from taskmanager.domain.markdown_body import toggle_task

            updated = toggle_task(self.source_edit.toPlainText(), index)
            if updated == self.source_edit.toPlainText():
                return False
            self.source_edit.setPlainText(updated)
            return True
        return self.text_edit.toggle_checkbox_index(index)

    def apply_link(self, url: str) -> None:
        """Wrap the selection as a link, or insert ``url`` when nothing is selected."""
        if self._showing_source():
            text, start, end = _source_span(self.source_edit)
            self._replace_source(*toggle_link(text, start, end, url))
            return
        cursor = self.text_edit.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n") or url
        fmt = QTextCharFormat()
        fmt.setAnchor(True)
        fmt.setAnchorHref(url)
        fmt.setForeground(_LINK_COLOR)
        cursor.insertText(selected, fmt)
        self.text_edit.setTextCursor(cursor)

    def insert_image_from_path(self, path: str) -> bool:
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось прочитать файл:\n{exc}")
            return False
        return self.insert_image_bytes(data, Path(path).name)

    def insert_image_bytes(self, data: bytes, name: str) -> bool:
        if sniff_image(data) is None:
            QMessageBox.warning(self, "Ошибка", "Неподдерживаемый формат изображения")
            return False
        if self._ensure_images_dir is None:
            QMessageBox.warning(
                self, "Ошибка", "Нельзя вставить изображение без папки заявки"
            )
            return False
        try:
            images_dir = self._ensure_images_dir()
        except (ServiceError, OSError) as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return False
        self._images_dir = images_dir
        try:
            link = write_markdown_image(images_dir, data, name)
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Неподдерживаемый формат изображения")
            return False
        self._insert_image_link(link)
        return True

    def _add_format_action(
        self,
        toolbar: QToolBar,
        label: str,
        tip: str,
        slot,
        *,
        checkable: bool = True,
        shortcut: QKeySequence.StandardKey | None = None,
    ) -> QAction:
        action = QAction(label, self)
        action.setToolTip(tip)
        action.setCheckable(checkable)
        action.triggered.connect(slot)
        if shortcut is not None:
            action.setShortcut(shortcut)
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self.addAction(action)
        toolbar.addAction(action)
        return action

    def _showing_source(self) -> bool:
        return self.stack.currentWidget() is self.source_edit

    def _load_text(self, markdown: str) -> None:
        self.text_edit.setHtml(preview_html(markdown, images_dir=self._images_dir))
        _refresh_text_document(self.text_edit)
        self.text_edit.apply_session_image_widths()
        _strip_editor_trailing_spaces(self.text_edit)
        self.text_edit.document().clearUndoRedoStacks()

    def _text_to_markdown(self) -> str:
        return document_to_markdown(self.text_edit.document())

    def _insert_image_link(self, link: str) -> None:
        if self._showing_source():
            cursor = self.source_edit.textCursor()
            cursor.insertText(link)
            self.source_edit.setTextCursor(cursor)
            return
        relative = link.removeprefix("![](").removesuffix(")")
        name = relative.split("/", 1)[-1]
        if self._images_dir is None:
            return
        path = (self._images_dir / name).resolve()
        cursor = self.text_edit.textCursor()
        src = html.escape(path.as_uri(), quote=True)
        cursor.insertHtml(f'<img src="{src}" />')
        self.text_edit.setTextCursor(cursor)
        self.text_edit.apply_session_image_widths()

    def _pick_image(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Изображение", "", _IMAGE_FILTER
        )
        if path:
            self.insert_image_from_path(path)

    def _insert_link(self) -> None:
        if self._showing_source():
            text, start, end = _source_span(self.source_edit)
            if _LINK_RE.match(text[start:end]):
                self._replace_source(*toggle_link(text, start, end, None))
                return
            url, ok = QInputDialog.getText(self, "Ссылка", "URL:")
            if not ok or not url.strip():
                return
            self._replace_source(*toggle_link(text, start, end, url.strip()))
            return
        href = _link_href(self.text_edit.textCursor())
        if href:
            self._clear_text_link()
            return
        url, ok = QInputDialog.getText(self, "Ссылка", "URL:")
        if not ok or not url.strip():
            return
        self.apply_link(url.strip())

    def _clear_text_link(self) -> None:
        cursor = self.text_edit.textCursor()
        if not cursor.hasSelection():
            fragment = _fragment_at(cursor.block(), cursor.position())
            if fragment is None:
                return
            cursor = QTextCursor(self.text_edit.document())
            cursor.setPosition(fragment.position())
            cursor.setPosition(
                fragment.position() + fragment.length(),
                QTextCursor.MoveMode.KeepAnchor,
            )
        fmt = QTextCharFormat()
        fmt.setAnchor(False)
        fmt.setAnchorHref("")
        fmt.setFontUnderline(False)
        fmt.setForeground(self.text_edit.palette().text().color())
        cursor.mergeCharFormat(fmt)

    def _heading_chosen(self, index: int) -> None:
        level = self.heading_combo.itemData(index)
        if level is None:
            return
        if self._showing_source():
            self._map_source_lines(lambda lines: _set_heading_lines(lines, int(level)))
            return
        self._apply_heading(int(level))

    def _toggle_bold(self, checked: bool) -> None:
        if self._showing_source():
            self._toggle_source_marker("**")
            return
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal)
        self.text_edit.mergeCurrentCharFormat(fmt)

    def _toggle_italic(self, checked: bool) -> None:
        if self._showing_source():
            self._toggle_source_marker("*")
            return
        fmt = QTextCharFormat()
        fmt.setFontItalic(checked)
        self.text_edit.mergeCurrentCharFormat(fmt)

    def _toggle_strike(self, checked: bool) -> None:
        if self._showing_source():
            self._toggle_source_marker("~~")
            return
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(checked)
        self.text_edit.mergeCurrentCharFormat(fmt)

    def _toggle_code(self, checked: bool) -> None:
        if self._showing_source():
            self._toggle_source_code()
            return
        fmt = QTextCharFormat()
        if checked:
            fmt.setFontFamilies(["monospace"])
            fmt.setFontFixedPitch(True)
            fmt.setBackground(_fill_color(self.text_edit))
            self.text_edit.mergeCurrentCharFormat(fmt)
            return
        family = self.text_edit.font().family() or "Sans Serif"
        fmt.setFontFamilies([family])
        fmt.setFontFixedPitch(False)
        fmt.setBackground(QBrush(Qt.BrushStyle.NoBrush))
        blocks = _selected_blocks(self.text_edit)
        if any(_is_mono_format(block.charFormat()) for block in blocks):
            for block in blocks:
                cursor = QTextCursor(block)
                block_fmt = block.blockFormat()
                block_fmt.setBackground(QBrush(Qt.BrushStyle.NoBrush))
                cursor.setBlockFormat(block_fmt)
                cursor.setBlockCharFormat(fmt)
                _select_block_text(cursor, block)
                cursor.mergeCharFormat(fmt)
            return
        self.text_edit.mergeCurrentCharFormat(fmt)

    def _toggle_quote(self, checked: bool) -> None:
        if self._showing_source():
            self._map_source_lines(_toggle_quote_lines)
            return
        if checked:
            self._remove_lists(_selected_blocks(self.text_edit))
        for block in _selected_blocks(self.text_edit):
            fmt = block.blockFormat()
            fmt.setLeftMargin(_QUOTE_MARGIN if checked else 0)
            if not checked:
                fmt.setBackground(QBrush(Qt.BrushStyle.NoBrush))
            cursor = QTextCursor(block)
            cursor.setBlockFormat(fmt)
        _apply_editor_chrome(self.text_edit)
        self._sync_format_actions()

    def _toggle_bullet(self, checked: bool) -> None:
        if self._showing_source():
            self._map_source_lines(_toggle_bullet_lines)
            return
        self._apply_list(QTextListFormat.Style.ListDisc if checked else None)

    def _toggle_numbered(self, checked: bool) -> None:
        if self._showing_source():
            self._map_source_lines(_toggle_numbered_lines)
            return
        self._apply_list(QTextListFormat.Style.ListDecimal if checked else None)

    def _toggle_todo(self, checked: bool) -> None:
        if self._showing_source():
            self._map_source_lines(_toggle_todo_lines)
            return
        blocks = _selected_blocks(self.text_edit)
        if not checked:
            _set_task_glyphs(self.text_edit, blocks, present=False)
            self._remove_lists(blocks)
            self._sync_format_actions()
            return
        _ensure_markerless_list(self.text_edit, blocks)
        _set_task_glyphs(self.text_edit, blocks, present=True)
        _restyle_task_lists(self.text_edit)
        self._sync_format_actions()

    def _insert_table(self) -> None:
        if self._showing_source():
            _insert_markdown_table(self.source_edit)
            return
        _insert_text_table(self.text_edit)

    def _apply_heading(self, level: int) -> None:
        body = self.text_edit.font()
        for block in _selected_blocks(self.text_edit):
            block_format = block.blockFormat()
            block_format.setHeadingLevel(level)
            cursor = QTextCursor(block)
            cursor.setBlockFormat(block_format)
            char_format = QTextCharFormat()
            if level:
                char_format.setFontWeight(QFont.Weight.Bold)
                _apply_font_scale(char_format, body, _HEADING_SCALE.get(level, 1))
            else:
                char_format.setFontWeight(QFont.Weight.Normal)
                _apply_font_scale(char_format, body, 1)
            _select_block_text(cursor, block)
            cursor.mergeCharFormat(char_format)
        self._sync_format_actions()

    def _apply_list(self, style: QTextListFormat.Style | None) -> None:
        blocks = _selected_blocks(self.text_edit)
        _set_task_glyphs(self.text_edit, blocks, present=False)
        if style is None:
            self._remove_lists(blocks)
        else:
            self.text_edit.textCursor().createList(style)
        self._sync_format_actions()

    def _remove_lists(self, blocks) -> None:
        cursor = self.text_edit.textCursor()
        cursor.beginEditBlock()
        for block in blocks:
            if not block.isValid():
                continue
            block_cursor = QTextCursor(block)
            text_list = block_cursor.currentList()
            if text_list is not None:
                text_list.remove(block)
        cursor.endEditBlock()

    def _toggle_source_marker(self, marker: str) -> None:
        text, start, end = _source_span(self.source_edit)
        self._replace_source(*toggle_wrapped(text, start, end, marker))

    def _toggle_source_code(self) -> None:
        text, start, end = _source_span(self.source_edit)
        selected = text[start:end]
        if "\n" in selected:
            self._replace_source(*toggle_fence(text, start, end))
            return
        self._toggle_source_marker("`")

    def _map_source_lines(self, transform) -> None:
        text, start, end = _source_span(self.source_edit)
        self._replace_source(*map_lines(text, start, end, transform))

    def _replace_source(self, text: str, start: int, end: int) -> None:
        self.source_edit.setPlainText(text)
        cursor = self.source_edit.textCursor()
        cursor.setPosition(max(0, min(start, len(text))))
        cursor.setPosition(max(0, min(end, len(text))), QTextCursor.MoveMode.KeepAnchor)
        self.source_edit.setTextCursor(cursor)
        self._sync_format_actions()

    def _sync_format_actions(self, *_args) -> None:
        if self._showing_source():
            flags = _source_format_flags(self)
        else:
            flags = _text_format_flags(self)
        for action, checked in flags:
            action.blockSignals(True)
            action.setChecked(checked)
            action.blockSignals(False)
        self._show_heading_level(_current_heading_level(self))

    def _show_heading_level(self, level: int) -> None:
        index = self.heading_combo.findData(level if 0 <= level <= 6 else -1)
        if self.heading_combo.currentIndex() == index:
            return
        self.heading_combo.blockSignals(True)
        self.heading_combo.setCurrentIndex(index)
        self.heading_combo.blockSignals(False)

    def _open_source_files(self) -> None:
        if self._source_files_dir is None:
            return
        try:
            open_target(str(self._source_files_dir))
        except PlatformOpenError as exc:
            QMessageBox.warning(self, "Файлы", str(exc))


class MarkdownEditRow(QWidget):
    """Markdown line plus «…» opening MarkdownEditDialog. Not an HTML field."""

    def __init__(
        self,
        parent=None,
        *,
        title: str = "Текст",
        markdown: str = "",
        ensure_images_dir: Callable[[], Path] | None = None,
        locate_images_dir: Callable[[], Path | None] | None = None,
        source_files_dir: Path | None = None,
        show_source_files_button: bool = False,
        image_preview_width: int = DEFAULT_IMAGE_PREVIEW_WIDTH,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self.ensure_images_dir = ensure_images_dir
        self.locate_images_dir = locate_images_dir
        self.image_preview_width = image_preview_width
        self.source_files_dir = source_files_dir
        self.show_source_files_button = show_source_files_button
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(markdown or "")
        self.edit.setPlaceholderText("Markdown…")
        button = QPushButton("…")
        button.setObjectName("secondaryButton")
        button.setFixedWidth(36)
        button.setToolTip("Редактировать")
        button.clicked.connect(self._edit)
        layout.addWidget(self.edit)
        layout.addWidget(button)

    def _edit(self) -> None:
        images_dir = None
        if self.locate_images_dir is not None:
            images_dir = self.locate_images_dir()
        dialog = MarkdownEditDialog(
            self,
            title=self._title,
            markdown=self.edit.text(),
            ensure_images_dir=self.ensure_images_dir,
            images_dir=images_dir,
            source_files_dir=self.source_files_dir,
            show_source_files_button=self.show_source_files_button,
            image_preview_width=self.image_preview_width,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.edit.setText(dialog.markdown)

    @property
    def markdown(self) -> str:
        return self.edit.text()

    @markdown.setter
    def markdown(self, value: str) -> None:
        self.edit.setText(value or "")

    @property
    def html(self) -> str:
        """Alias so existing callers read the markdown source."""
        return self.markdown

    @html.setter
    def html(self, value: str) -> None:
        self.markdown = value or ""


def toggle_wrapped(
    text: str, start: int, end: int, marker: str
) -> tuple[str, int, int]:
    """Wrap ``text[start:end]`` in ``marker``, or remove a matching pair."""
    selected = text[start:end]
    if _selection_has_marker(selected, marker):
        inner = selected[len(marker) : -len(marker)]
        return text[:start] + inner + text[end:], start, start + len(inner)
    if _outside_marker(text, start, end, marker):
        size = len(marker)
        updated = text[: start - size] + selected + text[end + size :]
        return updated, start - size, end - size
    if start == end:
        span = _enclosing_marker(text, start, marker)
        if span is not None:
            open_at, close_at = span
            inner = text[open_at + len(marker) : close_at]
            updated = text[:open_at] + inner + text[close_at + len(marker) :]
            return updated, open_at, open_at + len(inner)
    updated = text[:start] + marker + selected + marker + text[end:]
    return updated, start + len(marker), end + len(marker)


def toggle_fence(text: str, start: int, end: int) -> tuple[str, int, int]:
    """Wrap a multiline selection in a fence, or remove one."""
    selected = text[start:end]
    match = _FENCE_RE.match(selected)
    if match:
        inner = match.group(1)
        return text[:start] + inner + text[end:], start, start + len(inner)
    body = selected[:-1] if selected.endswith("\n") else selected
    wrapped = f"```\n{body}\n```"
    inner_start = start + 4
    return (
        text[:start] + wrapped + text[end:],
        inner_start,
        inner_start + len(body),
    )


def toggle_link(
    text: str, start: int, end: int, url: str | None
) -> tuple[str, int, int]:
    """Unwrap a selected link, or wrap the selection when ``url`` is given."""
    selected = text[start:end]
    match = _LINK_RE.match(selected)
    if match:
        label = match.group(1)
        return text[:start] + label + text[end:], start, start + len(label)
    if not url:
        return text, start, end
    label = selected or url
    wrapped = f"[{label}]({url})"
    return text[:start] + wrapped + text[end:], start, start + len(wrapped)


def map_lines(
    text: str,
    start: int,
    end: int,
    transform: Callable[[list[str]], list[str]],
) -> tuple[str, int, int]:
    """Apply ``transform`` to every line touched by ``[start, end]``."""
    line_start = text.rfind("\n", 0, start) + 1
    if end > start and text[end - 1 : end] == "\n":
        end -= 1
    line_end = text.find("\n", max(end, start))
    if line_end < 0:
        line_end = len(text)
    lines = text[line_start:line_end].split("\n")
    updated = "\n".join(transform(lines))
    return text[:line_start] + updated + text[line_end:], line_start, line_start + len(
        updated
    )


def _set_heading_lines(lines: list[str], level: int) -> list[str]:
    result: list[str] = []
    for line in lines:
        if not line.strip():
            result.append(line)
            continue
        body = _HEADING_RE.sub("", line, count=1) if _HEADING_RE.match(line) else line
        if level <= 0:
            result.append(body)
        else:
            result.append(f"{'#' * level} {body}")
    return result


def _heading_level_from_line(line: str) -> int:
    match = _HEADING_RE.match(line)
    if match is None:
        return 0
    return len(match.group(0).strip())


def _toggle_quote_lines(lines: list[str]) -> list[str]:
    if lines and all(_is_quote_line(line) or not line.strip() for line in lines):
        return [_unquote_line(line) for line in lines]
    return [
        line if _is_quote_line(line) else (f"> {line}" if line else ">")
        for line in lines
    ]


def _toggle_bullet_lines(lines: list[str]) -> list[str]:
    if lines and all(_is_bullet_line(line) or not line.strip() for line in lines):
        return [_strip_list_prefix(line) if line.strip() else line for line in lines]
    result: list[str] = []
    for line in lines:
        if not line.strip() or _is_bullet_line(line):
            result.append(line)
            continue
        result.append(_with_prefix(line, "- "))
    return result


def _toggle_numbered_lines(lines: list[str]) -> list[str]:
    if lines and all(_ORDER_RE.match(line) or not line.strip() for line in lines):
        return [_strip_list_prefix(line) if line.strip() else line for line in lines]
    result: list[str] = []
    number = 1
    for line in lines:
        if not line.strip():
            result.append(line)
            continue
        result.append(_with_prefix(line, f"{number}. "))
        number += 1
    return result


def _toggle_todo_lines(lines: list[str]) -> list[str]:
    if lines and all(_TASK_RE.match(line) or not line.strip() for line in lines):
        return [_strip_list_prefix(line) if line.strip() else line for line in lines]
    result: list[str] = []
    for line in lines:
        if not line.strip() or _TASK_RE.match(line):
            result.append(line)
            continue
        result.append(_with_prefix(line, "- [ ] "))
    return result


def _is_quote_line(line: str) -> bool:
    return line.startswith("> ") or line == ">"


def _unquote_line(line: str) -> str:
    if line.startswith("> "):
        return line[2:]
    if line == ">":
        return ""
    return line


def _is_bullet_line(line: str) -> bool:
    return _BULLET_RE.match(line) is not None


def _strip_list_prefix(line: str) -> str:
    for pattern in (_TASK_RE, _ORDER_RE, _BULLET_RE):
        match = pattern.match(line)
        if match is not None:
            return line[match.end() :]
    return line


def _with_prefix(line: str, prefix: str) -> str:
    indent = re.match(r"\s*", line)
    spaces = indent.group(0) if indent is not None else ""
    body = _strip_list_prefix(line).lstrip()
    return f"{spaces}{prefix}{body}"


def _selection_has_marker(selected: str, marker: str) -> bool:
    size = len(marker)
    if len(selected) < size * 2:
        return False
    if not (selected.startswith(marker) and selected.endswith(marker)):
        return False
    if _same_char(marker) and selected.startswith(marker[0] * (size + 1)):
        if selected.endswith(marker[0] * (size + 1)):
            return False
    return True


def _outside_marker(text: str, start: int, end: int, marker: str) -> bool:
    size = len(marker)
    if start < size or end + size > len(text):
        return False
    if text[start - size : start] != marker or text[end : end + size] != marker:
        return False
    if not _same_char(marker):
        return True
    edge = marker[0]
    if start - size - 1 >= 0 and text[start - size - 1] == edge:
        return False
    if end + size < len(text) and text[end + size] == edge:
        return False
    return True


def _enclosing_marker(text: str, index: int, marker: str) -> tuple[int, int] | None:
    line_start = text.rfind("\n", 0, index) + 1
    line_end = text.find("\n", index)
    if line_end < 0:
        line_end = len(text)
    local = index - line_start
    opened: int | None = None
    for pos in _marker_positions(text[line_start:line_end], marker):
        if pos < local:
            opened = None if opened is not None else pos
            continue
        if opened is not None:
            return line_start + opened, line_start + pos
        return None
    return None


def _marker_positions(segment: str, marker: str) -> list[int]:
    size = len(marker)
    positions: list[int] = []
    index = 0
    while True:
        found = segment.find(marker, index)
        if found < 0:
            return positions
        if _same_char(marker) and _part_of_longer_run(segment, found, marker):
            index = found + 1
            continue
        positions.append(found)
        index = found + size


def _part_of_longer_run(segment: str, found: int, marker: str) -> bool:
    edge = marker[0]
    size = len(marker)
    before = found > 0 and segment[found - 1] == edge
    after = found + size < len(segment) and segment[found + size] == edge
    return before or after


def _same_char(marker: str) -> bool:
    return all(char == marker[0] for char in marker)


def _is_wrapped(text: str, start: int, end: int, marker: str) -> bool:
    if start != end and (
        _selection_has_marker(text[start:end], marker)
        or _outside_marker(text, start, end, marker)
    ):
        return True
    return _enclosing_marker(text, start, marker) is not None


def _source_span(edit: QPlainTextEdit) -> tuple[str, int, int]:
    text = edit.toPlainText()
    cursor = edit.textCursor()
    return text, cursor.selectionStart(), cursor.selectionEnd()


def _source_format_flags(dialog: MarkdownEditDialog) -> list[tuple[QAction, bool]]:
    text, start, end = _source_span(dialog.source_edit)
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    line = text[line_start:line_end]
    task = _TASK_RE.match(line) is not None
    return [
        (dialog.bold_action, _is_wrapped(text, start, end, "**")),
        (dialog.italic_action, _is_wrapped(text, start, end, "*")),
        (dialog.strike_action, _is_wrapped(text, start, end, "~~")),
        (
            dialog.code_action,
            _is_wrapped(text, start, end, "`") or line.startswith("```"),
        ),
        (dialog.quote_action, line.startswith(">")),
        (dialog.bullet_action, _is_bullet_line(line) and not task),
        (dialog.numbered_action, _ORDER_RE.match(line) is not None),
        (dialog.todo_action, task),
    ]


def _text_format_flags(dialog: MarkdownEditDialog) -> list[tuple[QAction, bool]]:
    cursor = dialog.text_edit.textCursor()
    fmt = cursor.charFormat()
    block = cursor.block()
    text_list = cursor.currentList()
    style = text_list.format().style() if text_list is not None else None
    todo = _checkbox_fragment(block) is not None
    return [
        (dialog.bold_action, fmt.fontWeight() >= int(QFont.Weight.Bold)),
        (dialog.italic_action, fmt.fontItalic()),
        (dialog.strike_action, fmt.fontStrikeOut()),
        (
            dialog.code_action,
            _is_mono_format(fmt) or _is_mono_format(block.charFormat()),
        ),
        (dialog.quote_action, block.blockFormat().leftMargin() >= 20),
        (dialog.bullet_action, style == QTextListFormat.Style.ListDisc and not todo),
        (dialog.numbered_action, style == QTextListFormat.Style.ListDecimal),
        (dialog.todo_action, todo),
    ]


def _strip_editor_trailing_spaces(edit: QTextEdit) -> None:
    """Drop the single trailing space Qt inserts when HTML is loaded."""
    document = edit.document()
    positions: list[int] = []
    block = document.begin()
    while block.isValid():
        raw = block.text()
        if raw.endswith(" ") and not raw.endswith("  "):
            positions.append(block.position() + len(raw) - 1)
        block = block.next()
    if not positions:
        return
    cursor = QTextCursor(document)
    cursor.beginEditBlock()
    for pos in reversed(positions):
        cursor.setPosition(pos)
        cursor.setPosition(pos + 1, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
    cursor.endEditBlock()
    document.clearUndoRedoStacks()


def _selected_blocks(edit: QTextEdit) -> list:
    cursor = edit.textCursor()
    start = cursor.selectionStart()
    end = cursor.selectionEnd()
    if end > start:
        end -= 1
    block = edit.document().findBlock(start)
    blocks = []
    while block.isValid() and block.position() <= end:
        blocks.append(block)
        block = block.next()
    if not blocks:
        blocks.append(cursor.block())
    return blocks


def _select_block_text(cursor: QTextCursor, block) -> None:
    cursor.setPosition(block.position())
    cursor.setPosition(
        block.position() + max(block.length() - 1, 0),
        QTextCursor.MoveMode.KeepAnchor,
    )


def _is_bare_enter(event) -> bool:
    if event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
        return False
    blocked = (
        Qt.KeyboardModifier.ShiftModifier
        | Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.AltModifier
        | Qt.KeyboardModifier.MetaModifier
    )
    return not (event.modifiers() & blocked)


def _cursor_in_task(edit: QTextEdit) -> bool:
    cursor = edit.textCursor()
    if cursor.hasSelection():
        return False
    block = cursor.block()
    return block.textList() is not None and _checkbox_fragment(block) is not None


def _task_item_body(block) -> str:
    text = block.text().replace("\u2028", "").replace("\u2029", "")
    match = re.match(r"^[ \t]*[☐☑][ \t]?", text)
    if match is None:
        return text
    return text[match.end() :]


def _place_cursor_after_checkbox(edit: QTextEdit, block) -> None:
    span = _checkbox_span(block)
    if span is None:
        return
    cursor = edit.textCursor()
    if cursor.position() >= span[1]:
        return
    cursor.setPosition(span[1])
    edit.setTextCursor(cursor)


def _prefix_task_item(edit: QTextEdit, block) -> None:
    _set_task_glyphs(edit, [block], present=True)
    span = _checkbox_span(block)
    if span is None:
        return
    placed = QTextCursor(edit.document())
    placed.setPosition(span[1])
    edit.setTextCursor(placed)


def _leave_empty_task(edit: QTextEdit, block) -> None:
    cursor = QTextCursor(block)
    cursor.beginEditBlock()
    span = _checkbox_span(block)
    if span is not None:
        cursor.setPosition(span[0])
        cursor.setPosition(span[1], QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
    current = cursor.block()
    text_list = current.textList()
    if text_list is not None:
        text_list.remove(current)
    cursor.endEditBlock()
    placed = QTextCursor(current)
    placed.movePosition(QTextCursor.MoveOperation.EndOfBlock)
    edit.setTextCursor(placed)


def _set_task_glyphs(edit: QTextEdit, blocks, *, present: bool) -> None:
    for block in reversed(list(blocks)):
        if not block.isValid():
            continue
        span = _checkbox_span(block)
        if present and span is None:
            cursor = QTextCursor(block)
            cursor.setPosition(block.position())
            fmt = QTextCharFormat()
            fmt.setAnchor(True)
            fmt.setAnchorHref("tm-task:0")
            family = edit.font().family()
            if family:
                fmt.setFontFamilies([family])
            cursor.insertText("☐", fmt)
            # A colored glyph format would stick to the following item text.
            plain = QTextCharFormat()
            if family:
                plain.setFontFamilies([family])
            cursor.setCharFormat(plain)
            cursor.insertText(" ", plain)
        elif not present and span is not None:
            cursor = QTextCursor(edit.document())
            cursor.setPosition(span[0])
            cursor.setPosition(span[1], QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()


def _checkbox_span(block) -> tuple[int, int] | None:
    fragment = _checkbox_fragment(block)
    if fragment is None:
        return None
    text = fragment.text()
    match = re.match(r"^[ \t]*[☐☑][ \t]?", text)
    if match is None:
        return None
    start = fragment.position()
    end = start + match.end()
    if text[match.end() :]:
        return start, end
    iterator = block.begin()
    while not iterator.atEnd():
        current = iterator.fragment()
        iterator += 1
        if not current.isValid() or current.position() != fragment.position():
            continue
        if iterator.atEnd():
            break
        nxt = iterator.fragment()
        if nxt.isValid() and nxt.text().startswith(" "):
            end = nxt.position() + 1
        break
    return start, end


def _checkbox_fragment(block):
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid() and fragment.text().strip():
            if _glyph_mark(fragment.text()) is None:
                return None
            return fragment
        iterator += 1
    return None


def _fragment_at(block, position: int):
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid():
            start = fragment.position()
            end = start + max(fragment.length(), 1)
            if start <= position < end:
                return fragment
        iterator += 1
    return None


def _glyph_mark(text: str) -> str | None:
    stripped = text.lstrip(" \t")
    if stripped.startswith("☑"):
        return "x"
    if stripped.startswith("☐"):
        return " "
    return None


def _flip_checkbox_fragment(edit: QTextEdit, fragment) -> None:
    text = fragment.text()
    if "☐" in text:
        updated = text.replace("☐", "☑", 1)
    elif "☑" in text:
        updated = text.replace("☑", "☐", 1)
    else:
        return
    cursor = QTextCursor(edit.document())
    cursor.setPosition(fragment.position())
    cursor.setPosition(
        fragment.position() + len(text),
        QTextCursor.MoveMode.KeepAnchor,
    )
    cursor.insertText(updated, fragment.charFormat())


def _link_href(cursor: QTextCursor) -> str:
    fmt = cursor.charFormat()
    href = fmt.anchorHref() if fmt.isAnchor() else ""
    if href.startswith("tm-task:"):
        return ""
    return href


def _is_mono_format(fmt) -> bool:
    family = fmt.font().family().casefold()
    return "mono" in family or fmt.fontFixedPitch()


def _current_heading_level(dialog: MarkdownEditDialog) -> int:
    if dialog._showing_source():
        text, start, _end = _source_span(dialog.source_edit)
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", start)
        if line_end < 0:
            line_end = len(text)
        return _heading_level_from_line(text[line_start:line_end])
    return dialog.text_edit.textCursor().block().blockFormat().headingLevel()


def _apply_font_scale(fmt: QTextCharFormat, source: QFont, scale: float) -> None:
    points = source.pointSizeF()
    if points <= 0 and source.pixelSize() > 0:
        points = QFontInfo(source).pointSizeF()
    if points <= 0:
        points = 11
    fmt.clearProperty(QTextFormat.Property.FontPixelSize)
    fmt.setFontPointSize(max(1.0, points * scale))


def _refresh_text_document(edit: QTextEdit) -> None:
    """One editor font, markerless tasks, and table borders after HTML or a paste."""
    _normalize_editor_fonts(edit)
    _restyle_task_lists(edit)
    _style_tables(edit)
    _apply_editor_chrome(edit)


def _editor_family(edit: QTextEdit) -> str:
    return edit.font().family() or "Sans Serif"


def _normalized_format(
    fmt: QTextCharFormat,
    edit: QTextEdit,
    heading: int,
    *,
    force_mono: bool,
) -> QTextCharFormat:
    """Editor font and color. Headings stay larger; code stays monospace."""
    updated = QTextCharFormat(fmt)
    weight = fmt.fontWeight()
    italic = fmt.fontItalic()
    strike = fmt.fontStrikeOut()
    href = fmt.anchorHref() if fmt.isAnchor() else ""
    mono = bool(force_mono or (heading == 0 and _is_mono_format(fmt)))
    updated.clearProperty(QTextFormat.Property.FontPixelSize)
    if mono and heading == 0:
        updated.setFontFamilies(["monospace"])
        updated.setFontFixedPitch(True)
        updated.clearProperty(QTextFormat.Property.FontPointSize)
        updated.setFontWeight(weight)
    else:
        updated.setFontFamilies([_editor_family(edit)])
        updated.setFontFixedPitch(False)
        if heading:
            updated.setFontWeight(QFont.Weight.Bold)
            _apply_font_scale(updated, edit.font(), _HEADING_SCALE.get(heading, 1.0))
        else:
            updated.setFontWeight(weight)
            updated.clearProperty(QTextFormat.Property.FontPointSize)
    updated.setFontItalic(italic)
    updated.setFontStrikeOut(strike)
    if href.startswith("tm-task:"):
        updated.setForeground(QBrush(Qt.BrushStyle.NoBrush))
    elif href:
        updated.setForeground(_LINK_COLOR)
    else:
        updated.setForeground(QBrush(Qt.BrushStyle.NoBrush))
    return updated


def _format_face_matches(current: QTextCharFormat, updated: QTextCharFormat) -> bool:
    if current.fontWeight() != updated.fontWeight():
        return False
    if current.fontItalic() != updated.fontItalic():
        return False
    if current.fontStrikeOut() != updated.fontStrikeOut():
        return False
    if _font_family(current) != _font_family(updated):
        return False
    if abs(current.fontPointSize() - updated.fontPointSize()) > 0.05:
        return False
    if current.fontFixedPitch() != updated.fontFixedPitch():
        return False
    left = current.foreground()
    right = updated.foreground()
    if left.style() != right.style():
        return False
    if left.style() != Qt.BrushStyle.NoBrush and left.color() != right.color():
        return False
    return True


def _font_family(fmt: QTextCharFormat) -> str:
    families = fmt.fontFamilies()
    if families:
        return families[0].casefold()
    return fmt.font().family().casefold()


def _normalize_editor_fonts(edit: QTextEdit) -> None:
    """Drop a foreign family, size, and color. Headings 1–6 stay larger and bold."""
    pending = []
    block = edit.document().begin()
    while block.isValid():
        heading = block.blockFormat().headingLevel()
        fenced = _is_fenced_code_block(block)
        fragments = []
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            iterator += 1
            if not fragment.isValid() or not fragment.text():
                continue
            if fragment.charFormat().isImageFormat():
                continue
            fragments.append(
                (fragment.position(), fragment.length(), QTextCharFormat(fragment.charFormat()))
            )
        pending.append((block, heading, fenced, fragments))
        block = block.next()
    for block, heading, fenced, fragments in pending:
        if not block.isValid():
            continue
        for position, length, fmt in fragments:
            updated = _normalized_format(fmt, edit, heading, force_mono=fenced)
            if _format_face_matches(fmt, updated):
                continue
            cursor = QTextCursor(edit.document())
            cursor.setPosition(position)
            cursor.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
            cursor.setCharFormat(updated)
        current = block.charFormat()
        updated_block = _normalized_format(current, edit, heading, force_mono=fenced)
        if not _format_face_matches(current, updated_block):
            cursor = QTextCursor(block)
            cursor.setBlockCharFormat(updated_block)
    current = edit.currentCharFormat()
    cursor = edit.textCursor()
    heading = cursor.block().blockFormat().headingLevel() if cursor.block().isValid() else 0
    fenced = _is_fenced_code_block(cursor.block()) if cursor.block().isValid() else False
    updated_current = _normalized_format(
        current,
        edit,
        heading,
        force_mono=fenced or _is_mono_format(current),
    )
    if not _format_face_matches(current, updated_current):
        edit.setCurrentCharFormat(updated_current)


def _task_list_style() -> QTextListFormat.Style:
    return QTextListFormat.Style.ListStyleUndefined


def _ensure_markerless_list(edit: QTextEdit, blocks) -> None:
    """Put task rows in a list that draws no bullet."""
    group = None
    group_indent = None
    previous = None
    for block in blocks:
        if not block.isValid():
            continue
        existing = block.textList()
        indent = existing.format().indent() if existing is not None else 1
        if existing is not None and existing.format().style() == _task_list_style():
            group = existing
            group_indent = indent
            previous = block.blockNumber()
            continue
        if existing is not None:
            existing.remove(block)
        if (
            group is not None
            and group_indent == indent
            and previous is not None
            and block.blockNumber() == previous + 1
        ):
            group.add(block)
        else:
            fmt = QTextListFormat()
            fmt.setStyle(_task_list_style())
            fmt.setIndent(indent)
            group = QTextCursor(block).createList(fmt)
            if group is not None and group.format().indent() != indent:
                fixed = group.format()
                fixed.setIndent(indent)
                group.setFormat(fixed)
            group_indent = indent
        previous = block.blockNumber()


def _restyle_task_lists(edit: QTextEdit) -> None:
    """Task rows keep a list for Enter, without the disc that sits on the box."""
    lists = []
    block = edit.document().begin()
    while block.isValid():
        text_list = block.textList()
        if text_list is not None and all(text_list != item for item in lists):
            lists.append(text_list)
        block = block.next()
    for text_list in lists:
        blocks = [text_list.item(index) for index in range(text_list.count())]
        tasks = [item for item in blocks if _checkbox_fragment(item) is not None]
        if not tasks or len(tasks) != len(blocks):
            if tasks:
                _ensure_markerless_list(edit, tasks)
            continue
        if text_list.format().style() == _task_list_style():
            continue
        fmt = text_list.format()
        fmt.setStyle(_task_list_style())
        text_list.setFormat(fmt)


def _insert_markdown_table(edit: QPlainTextEdit) -> None:
    cursor = edit.textCursor()
    text = edit.toPlainText()
    start = cursor.selectionStart()
    end = cursor.selectionEnd()
    piece = _TABLE_MARKDOWN
    if start > 0 and text[start - 1] != "\n":
        piece = "\n" + piece
    if end < len(text) and text[end : end + 1] != "\n":
        piece += "\n"
    cursor.insertText(piece)
    edit.setTextCursor(cursor)


def _insert_text_table(edit: QTextEdit) -> None:
    fmt = QTextTableFormat()
    fmt.setBorderCollapse(True)
    fmt.setCellPadding(4)
    fmt.setCellSpacing(0)
    fmt.setHeaderRowCount(1)
    fmt.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
    table = edit.textCursor().insertTable(2, _TABLE_COLUMNS, fmt)
    _style_tables(edit)
    if table is not None:
        edit.setTextCursor(table.cellAt(0, 0).firstCursorPosition())


def _handle_table_tab(edit: QTextEdit, event) -> bool:
    if event.key() not in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
        return False
    table = edit.textCursor().currentTable()
    if table is None:
        return False
    backward = event.key() == Qt.Key.Key_Backtab or bool(
        event.modifiers() & Qt.KeyboardModifier.ShiftModifier
    )
    cell = table.cellAt(edit.textCursor())
    if not cell.isValid():
        return True
    cols = table.columns()
    last = table.rows() * cols - 1
    index = cell.row() * cols + cell.column()
    index += -1 if backward else 1
    if index < 0 or index > last:
        return True
    row, column = divmod(index, cols)
    edit.setTextCursor(table.cellAt(row, column).firstCursorPosition())
    return True


def _style_tables(edit: QTextEdit) -> None:
    if getattr(edit, "_styling_tables", False):
        return
    edit._styling_tables = True
    try:
        color = edit.palette().color(QPalette.ColorRole.Text)
        seen = []
        block = edit.document().begin()
        while block.isValid():
            table = QTextCursor(block).currentTable()
            if table is not None and all(table != item for item in seen):
                seen.append(table)
            block = block.next()
        for table in seen:
            fmt = table.format()
            fmt.setBorder(1)
            fmt.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
            fmt.setBorderBrush(color)
            fmt.setBorderCollapse(True)
            fmt.setCellSpacing(0)
            table.setFormat(fmt)
            for row in range(table.rows()):
                for column in range(table.columns()):
                    cell = table.cellAt(row, column)
                    cell_fmt = QTextTableCellFormat(cell.format())
                    cell_fmt.setBorder(1)
                    cell_fmt.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
                    cell_fmt.setBorderBrush(color)
                    cell.setFormat(cell_fmt)
    finally:
        edit._styling_tables = False


def _is_dark_base(widget) -> bool:
    base = widget.palette().color(QPalette.ColorRole.Base)
    return base.lightness() < 128


def _fill_color(widget) -> QColor:
    """Light gray on a light field, a lighter plaque on a dark field."""
    return _DARK_FILL if _is_dark_base(widget) else _LIGHT_FILL


def _accent_color(widget) -> QColor:
    return _DARK_ACCENT if _is_dark_base(widget) else _LIGHT_ACCENT


def _apply_editor_chrome(edit: QTextEdit) -> None:
    """Theme fill for code and quotes. Skips a write when the color already matches."""
    if getattr(edit, "_applying_chrome", False):
        return
    edit._applying_chrome = True
    try:
        fill = _fill_color(edit)
        block = edit.document().begin()
        while block.isValid():
            quote = block.blockFormat().leftMargin() >= 20
            fenced = _is_fenced_code_block(block) and bool(block.text().strip())
            _set_block_fill(block, fill if quote or fenced else None)
            if not fenced:
                _set_inline_code_fill(block, fill)
            block = block.next()
    finally:
        edit._applying_chrome = False


def _set_block_fill(block, color: QColor | None) -> None:
    fmt = block.blockFormat()
    if _brush_matches(fmt.background(), color):
        return
    fmt.setBackground(_brush(color))
    cursor = QTextCursor(block)
    cursor.setBlockFormat(fmt)


def _set_inline_code_fill(block, fill: QColor) -> None:
    """Snapshot fragments first: changing a format invalidates the iterator."""
    pending = []
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        iterator += 1
        if not fragment.isValid() or not fragment.text():
            continue
        fmt = fragment.charFormat()
        if fmt.isImageFormat():
            continue
        color = fill if _is_mono_format(fmt) else None
        if _brush_matches(fmt.background(), color):
            continue
        pending.append((fragment.position(), fragment.length(), fmt, color))
    for position, length, fmt, color in pending:
        cursor = QTextCursor(block)
        cursor.setPosition(position)
        cursor.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
        updated = QTextCharFormat(fmt)
        updated.setBackground(_brush(color))
        cursor.setCharFormat(updated)


def _brush(color: QColor | None) -> QBrush:
    if color is None:
        return QBrush(Qt.BrushStyle.NoBrush)
    return QBrush(color)


def _brush_matches(brush: QBrush, color: QColor | None) -> bool:
    if color is None:
        return brush.style() == Qt.BrushStyle.NoBrush
    return brush.style() != Qt.BrushStyle.NoBrush and brush.color() == color


def _glyph_viewport_rect(edit: QTextEdit, fragment) -> QRect:
    document = edit.document()
    start = QTextCursor(document)
    start.setPosition(fragment.position())
    end = QTextCursor(document)
    end.setPosition(min(fragment.position() + 1, max(document.characterCount() - 1, 0)))
    origin = edit.cursorRect(start)
    stop = edit.cursorRect(end)
    width = max(stop.left() - origin.left(), 1)
    return QRect(origin.left(), origin.top(), width, origin.height())


def _draw_task_box(
    painter: QPainter,
    square: QRect,
    *,
    checked: bool,
    border: QColor,
    fill: QColor,
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(border)
    pen.setWidthF(1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(fill)
    box = square.adjusted(0, 0, -1, -1)
    painter.drawRoundedRect(box, 2, 2)
    if checked:
        pen.setWidthF(1.8)
        painter.setPen(pen)
        painter.drawPolyline(
            QPolygon(
                [
                    QPoint(
                        box.x() + round(box.width() * 0.22),
                        box.y() + round(box.height() * 0.52),
                    ),
                    QPoint(
                        box.x() + round(box.width() * 0.42),
                        box.y() + round(box.height() * 0.74),
                    ),
                    QPoint(
                        box.x() + round(box.width() * 0.78),
                        box.y() + round(box.height() * 0.28),
                    ),
                ]
            )
        )
    painter.restore()


def _near_image_corner(view_rect: QRect, pos: QPoint) -> bool:
    handle = QRect(
        view_rect.right() - _IMAGE_CORNER_HIT,
        view_rect.bottom() - _IMAGE_CORNER_HIT,
        _IMAGE_CORNER_HIT + 8,
        _IMAGE_CORNER_HIT + 8,
    )
    return handle.contains(pos)


def _image_file_path(name: str) -> str:
    if name.startswith("file:"):
        return QUrl(name).toLocalFile()
    if name and not name.startswith("data:"):
        return name
    return ""


def _natural_image_size(
    fmt: QTextImageFormat, cache: dict[str, QSize] | None = None
) -> QSize:
    name = fmt.name()
    if cache is not None and name in cache:
        return QSize(cache[name])
    path = _image_file_path(name)
    if path:
        size = QImageReader(path).size()
        if size.isValid() and size.width() > 0:
            if cache is not None:
                cache[name] = QSize(size)
            return size
    image = QImage()
    if path:
        image = QImage(path)
    if image.isNull():
        return QSize(max(int(fmt.width()), 0), max(int(fmt.height()), 0))
    if cache is not None:
        cache[name] = image.size()
    return image.size()


def _image_from_mime(source) -> tuple[bytes, str] | None:
    if source is None:
        return None
    if source.hasUrls():
        for url in source.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() not in _IMAGE_SUFFIXES:
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if sniff_image(data) is not None:
                return data, path.name
    if source.hasImage():
        image = QImage(source.imageData())
        if image.isNull():
            return None
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            return None
        data = bytes(buffer.data())
        if sniff_image(data) is None:
            return None
        return data, "clipboard.png"
    return None
