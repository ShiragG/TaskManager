from __future__ import annotations

import base64
import logging
import re
from collections.abc import Callable
from datetime import date
from pathlib import Path

from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QDate,
    QIODevice,
    QMimeData,
    QPoint,
    QPointF,
    QRect,
    QRectF,
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
    QImage,
    QImageReader,
    QKeySequence,
    QMouseEvent,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextImageFormat,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from taskmanager.domain import (
    PRIORITY_DEFAULT,
    PRIORITY_MAX,
    PRIORITY_MIN,
    Project,
    Task,
    WORKFLOW_STATUS_LABELS,
    WorkflowStatus,
    clamp_priority,
    contrast_foreground,
    parse_workflow_status,
    priority_color_hex,
)
from taskmanager.infrastructure.filesystem import source_files_present
from taskmanager.infrastructure.platform_open import PlatformOpenError, open_target
from taskmanager.services.inline_images import sniff_image
from taskmanager.services.settings_service import (
    DEFAULT_IMAGE_PREVIEW_WIDTH,
    IMAGE_PREVIEW_SMALL,
    Settings,
)

logger = logging.getLogger(__name__)

SWATCH_SIZE = 22
SMALL_IMAGE_PREVIEW_WIDTH = IMAGE_PREVIEW_SMALL
_IMAGE_RESIZE_MIN = 40
_IMAGE_CORNER_HIT = 16
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_IMG_WIDTH_ATTR_RE = re.compile(r"\bwidth\s*=\s*[\"']?(\d+)", re.IGNORECASE)
_IMG_WIDTH_STYLE_RE = re.compile(r"width\s*:\s*(\d+)px", re.IGNORECASE)


def source_image_widths(html: str) -> list[int | None]:
    """Width of each <img> in source HTML; None if that tag has no width."""
    widths: list[int | None] = []
    for tag in _IMG_TAG_RE.findall(html or ""):
        match = _IMG_WIDTH_ATTR_RE.search(tag) or _IMG_WIDTH_STYLE_RE.search(tag)
        widths.append(int(match.group(1)) if match else None)
    return widths


class ColorSwatchButton(QToolButton):
    """Palette swatch; optional right-click removal for custom colors."""

    def __init__(
        self,
        color: str,
        *,
        tooltip: str,
        removable: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.hex_color = color
        self.removable = removable
        self.setToolTip(tooltip)
        self.setFixedSize(SWATCH_SIZE, SWATCH_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        border = "#94a3b8" if color.lower() in {"#ffffff", "#fff"} else "#334155"
        self.setStyleSheet(
            f"QToolButton {{ background-color: {color}; border: 1px solid {border}; "
            f"border-radius: 3px; }}"
            f"QToolButton:hover {{ border: 2px solid #0f766e; }}"
        )
        self._on_remove = None

    def set_remove_handler(self, handler) -> None:
        self._on_remove = handler

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if (
            event.button() == Qt.MouseButton.RightButton
            and self.removable
            and self._on_remove is not None
        ):
            self._on_remove()
            event.accept()
            return
        super().mousePressEvent(event)


class ProjectDialog(QDialog):
    def __init__(self, parent=None, *, name: str = "", title: str = "Проект") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(name)
        form.addRow("Имя", self.name_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите имя проекта")
            return
        self.accept()

    @property
    def project_name(self) -> str:
        return self.name_edit.text().strip()


# Backward-compatible alias
DirectoryDialog = ProjectDialog


def _qimage_png_bytes(image: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def _data_uri_img_html(
    data: bytes, mime: str, *, width: int = DEFAULT_IMAGE_PREVIEW_WIDTH
) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    display_width = width
    if display_width <= 0:
        image = QImage()
        image.loadFromData(data)
        display_width = image.width() if not image.isNull() else 0
    if display_width > 0:
        return f'<img src="data:{mime};base64,{b64}" width="{display_width}">'
    return f'<img src="data:{mime};base64,{b64}">'


def _image_source_path(name: str) -> str:
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
    path = _image_source_path(name)
    if path:
        size = QImageReader(path).size()
        if size.isValid() and size.width() > 0:
            if cache is not None:
                cache[name] = QSize(size)
            return size
    image = QImage()
    if name.startswith("data:"):
        comma = name.find(",")
        if comma >= 0:
            try:
                image.loadFromData(base64.b64decode(name[comma + 1 :]))
            except Exception:
                image = QImage()
    elif path:
        image = QImage(path)
    if image.isNull():
        return QSize(max(int(fmt.width()), 0), max(int(fmt.height()), 0))
    if cache is not None:
        cache[name] = image.size()
    return image.size()


def _read_preview_pixmap(name: str, _display_width: int = 0) -> tuple[QPixmap, QSize]:
    """Load original image pixels; HTML width controls on-screen size."""
    pix = QPixmap()
    path = _image_source_path(name)
    if path:
        pix = QPixmap(path)
    elif name.startswith("data:"):
        comma = name.find(",")
        if comma >= 0:
            try:
                pix.loadFromData(base64.b64decode(name[comma + 1 :]))
            except Exception:
                return QPixmap(), QSize(0, 0)
    if pix.isNull():
        return pix, QSize(0, 0)
    return pix, pix.size()


def _ancestor_main_window(widget: QWidget | None) -> QMainWindow | None:
    current = widget
    while current is not None:
        if isinstance(current, QMainWindow):
            return current
        current = current.parentWidget()
    return None


class _ImageHit:
    __slots__ = ("cursor", "view_rect", "position")

    def __init__(self, cursor: QTextCursor, view_rect: QRect, position: int) -> None:
        self.cursor = cursor
        self.view_rect = view_rect
        self.position = position


class _LinkAwareTextEdit(QTextEdit):
    """QTextEdit that opens anchors on Ctrl+click; plain click selects as usual."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._drag_resize: tuple[int, int] | None = None
        self._natural_sizes: dict[str, QSize] = {}
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.image_preview_width = DEFAULT_IMAGE_PREVIEW_WIDTH

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            pos = event.position().toPoint()
            href = self.anchorAt(pos)
            if not href:
                hit = self._image_hit_at(pos)
                if hit is not None:
                    href = hit.cursor.charFormat().toImageFormat().name()
            if href:
                self._open_href(href)
                event.accept()
                return
            logger.warning("Ctrl+click: no href or image src at %s", pos)
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._image_hit_at(event.position().toPoint())
            if hit is not None and self._near_br_corner(
                hit.view_rect, event.position().toPoint()
            ):
                self._drag_resize = (hit.position, hit.view_rect.left())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
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
        if hit is not None and self._near_br_corner(hit.view_rect, pos):
            self.viewport().setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.viewport().unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_resize is not None and event.button() == Qt.MouseButton.LeftButton:
            self._drag_resize = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _open_href(self, href: str) -> None:
        if href.startswith(("http://", "https://")):
            target = href
        else:
            target = _image_source_path(href) or href
        try:
            open_target(target)
        except PlatformOpenError as exc:
            logger.warning("Ctrl+click: failed to open %s: %s", target, exc)
            QMessageBox.warning(self, "Предупреждение", str(exc))
            return
        logger.debug("Ctrl+click: opened %s", target)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        hit = self._image_hit_at(event.pos())
        if hit is not None:
            menu = QMenu(self)
            menu.addAction(
                "Уменьшенная",
                lambda c=QTextCursor(hit.cursor): self.set_image_display_width(
                    c, SMALL_IMAGE_PREVIEW_WIDTH
                ),
            )
            menu.addAction(
                "Средняя",
                lambda c=QTextCursor(hit.cursor): self.set_image_display_width(
                    c, DEFAULT_IMAGE_PREVIEW_WIDTH
                ),
            )
            menu.addAction(
                "Исходная",
                lambda c=QTextCursor(hit.cursor): self.set_image_display_width(c, 0),
            )
            menu.addAction(
                "Ширина…",
                lambda c=QTextCursor(hit.cursor): self._prompt_image_width(c),
            )
            menu.exec(event.globalPos())
            event.accept()
            return
        super().contextMenuEvent(event)

    def insertFromMimeData(self, source: QMimeData) -> None:
        if source.hasImage():
            image = source.imageData()
            if isinstance(image, QPixmap):
                image = image.toImage()
            if isinstance(image, QImage) and not image.isNull():
                data = _qimage_png_bytes(image)
                if sniff_image(data) is not None:
                    self.textCursor().insertHtml(
                        _data_uri_img_html(
                            data, "image/png", width=self.image_preview_width
                        )
                    )
                    self.replace_preview_image_resources()
                    return
        super().insertFromMimeData(source)
        self.replace_preview_image_resources()

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

    def set_image_display_width(self, cursor: QTextCursor, width: int) -> None:
        fmt = cursor.charFormat()
        if not fmt.isImageFormat():
            return
        img_fmt = fmt.toImageFormat()
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
        self.replace_preview_image_resources()

    def apply_default_width_when_missing(
        self, source_widths: list[int | None] | None = None
    ) -> None:
        for index, cursor in enumerate(self.iter_image_cursors()):
            fmt = cursor.charFormat()
            if not fmt.isImageFormat():
                continue
            if source_widths is not None:
                if index < len(source_widths) and source_widths[index] is not None:
                    continue
            elif int(fmt.toImageFormat().width()) > 0:
                continue
            self.set_image_display_width(cursor, self.image_preview_width)

    def replace_preview_image_resources(self) -> None:
        """Keep original pixels in QTextDocument; HTML src stays original."""
        doc = self.document()
        viewport_width = self.viewport().width()
        for cursor in self.iter_image_cursors():
            fmt = cursor.charFormat()
            if not fmt.isImageFormat():
                continue
            img_fmt = fmt.toImageFormat()
            name = img_fmt.name()
            if not name:
                continue
            display_width = int(img_fmt.width())
            if display_width <= 0:
                display_width = viewport_width or DEFAULT_IMAGE_PREVIEW_WIDTH
            pixmap, natural = _read_preview_pixmap(name, display_width)
            if natural.width() > 0:
                self._natural_sizes[name] = QSize(natural)
            if pixmap.isNull():
                continue
            urls = [QUrl(name)]
            local = _image_source_path(name)
            if local:
                urls.append(QUrl.fromLocalFile(local))
            for url in urls:
                doc.addResource(QTextDocument.ResourceType.ImageResource, url, pixmap)
        count = doc.characterCount()
        if count > 0:
            doc.markContentsDirty(0, count)

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

    def _cursor_for_image_at(self, position: int) -> QTextCursor | None:
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        cursor.setPosition(position + 1, QTextCursor.MoveMode.KeepAnchor)
        if not cursor.charFormat().isImageFormat():
            return None
        return cursor

    def _image_hit_at(self, view_pos: QPoint) -> _ImageHit | None:
        doc_layout = self.document().documentLayout()
        doc_pos = QPointF(
            view_pos.x() + self.horizontalScrollBar().value(),
            view_pos.y() + self.verticalScrollBar().value(),
        )
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
                        width = img_fmt.width() or natural.width() or DEFAULT_IMAGE_PREVIEW_WIDTH
                        height = img_fmt.height() or natural.height() or width
                        rect = QRectF(
                            block_rect.x() + line.x() + x,
                            block_rect.y() + line.y(),
                            width,
                            height,
                        )
                        if rect.contains(doc_pos):
                            view_rect = QRect(
                                int(rect.x() - self.horizontalScrollBar().value()),
                                int(rect.y() - self.verticalScrollBar().value()),
                                int(rect.width()),
                                int(rect.height()),
                            )
                            cursor = self._cursor_for_image_at(fragment.position())
                            if cursor is not None:
                                return _ImageHit(cursor, view_rect, fragment.position())
                iterator += 1
            block = block.next()
        return None

    @staticmethod
    def _near_br_corner(view_rect: QRect, pos: QPoint) -> bool:
        handle = QRect(
            view_rect.right() - _IMAGE_CORNER_HIT,
            view_rect.bottom() - _IMAGE_CORNER_HIT,
            _IMAGE_CORNER_HIT + 8,
            _IMAGE_CORNER_HIT + 8,
        )
        return handle.contains(pos)


# Local toolbar QSS: do not inherit app teal toolbutton styles so checked/hover
# stay visible (native-like). Applied only on this dialog's toolbar.
_RICH_TOOLBAR_QSS = """
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


class RichTextEditDialog(QDialog):
    """Modal rich-text editor for description/comment HTML fields."""

    def __init__(
        self,
        parent=None,
        *,
        title: str = "Редактор",
        html: str = "",
        image_preview_width: int = DEFAULT_IMAGE_PREVIEW_WIDTH,
        source_files_dir: Path | None = None,
        show_source_files_button: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumSize(676, 468)
        main = _ancestor_main_window(parent)
        if main is not None:
            self.setGeometry(main.geometry())
        # Isolate dialog from app QSS so toolbar checked/hover are reliable.
        self.setStyleSheet("")
        layout = QVBoxLayout(self)
        self._source_files_dir = source_files_dir
        self.source_files_button: QPushButton | None = None

        toolbar = QToolBar()
        toolbar.setStyleSheet(_RICH_TOOLBAR_QSS)
        self.editor = _LinkAwareTextEdit()
        self.editor.setAcceptRichText(True)
        self.editor.image_preview_width = image_preview_width
        if html:
            self.editor.setHtml(html)
            self.editor.apply_default_width_when_missing(source_image_widths(html))
            self.editor.replace_preview_image_resources()

        self._act_bold = QAction("Ж", self)
        self._act_bold.setCheckable(True)
        self._act_bold.setShortcut(QKeySequence.StandardKey.Bold)
        self._act_bold.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._act_bold.triggered.connect(self._toggle_bold)
        self._act_italic = QAction("К", self)
        self._act_italic.setCheckable(True)
        self._act_italic.setShortcut(QKeySequence.StandardKey.Italic)
        self._act_italic.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._act_italic.triggered.connect(self._toggle_italic)
        self._act_underline = QAction("Ч", self)
        self._act_underline.setCheckable(True)
        self._act_underline.setShortcut(QKeySequence.StandardKey.Underline)
        self._act_underline.setShortcutContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self._act_underline.triggered.connect(self._toggle_underline)
        self._act_bullet = QAction("•", self)
        self._act_bullet.setCheckable(True)
        self._act_bullet.setToolTip("Маркированный список")
        self._act_bullet.triggered.connect(self._toggle_bullet_list)
        self._act_numbered = QAction("1.", self)
        self._act_numbered.setCheckable(True)
        self._act_numbered.setToolTip("Нумерованный список")
        self._act_numbered.triggered.connect(self._toggle_numbered_list)
        self._act_link = QAction("Ссылка", self)
        self._act_link.setCheckable(False)
        self._act_link.triggered.connect(self._insert_link)
        self._act_image = QAction("Рис.", self)
        self._act_image.setCheckable(False)
        self._act_image.setToolTip("Вставить изображение")
        self._act_image.triggered.connect(self._insert_image)
        toolbar.addAction(self._act_bold)
        toolbar.addAction(self._act_italic)
        toolbar.addAction(self._act_underline)
        toolbar.addAction(self._act_bullet)
        toolbar.addAction(self._act_numbered)
        toolbar.addAction(self._act_link)
        toolbar.addAction(self._act_image)
        self.addAction(self._act_bold)
        self.addAction(self._act_italic)
        self.addAction(self._act_underline)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(toolbar, 1)
        if show_source_files_button:
            btn = QPushButton("Файлы")
            btn.setToolTip("Открыть папку файлов источника")
            btn.setEnabled(source_files_present(source_files_dir))
            btn.clicked.connect(self._open_source_files)
            header.addWidget(btn, 0, Qt.AlignmentFlag.AlignTop)
            self.source_files_button = btn
        layout.addLayout(header)
        layout.addWidget(self.editor)

        self.editor.currentCharFormatChanged.connect(self._sync_format_actions)
        self.editor.cursorPositionChanged.connect(self._sync_format_actions)
        self._sync_format_actions()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _sync_format_actions(self, *_args) -> None:
        fmt = self.editor.currentCharFormat()
        for action, checked in (
            (self._act_bold, fmt.fontWeight() >= int(QFont.Weight.Bold)),
            (self._act_italic, fmt.fontItalic()),
            (self._act_underline, fmt.fontUnderline()),
        ):
            action.blockSignals(True)
            action.setChecked(checked)
            action.blockSignals(False)

        lst = self.editor.textCursor().currentList()
        style = lst.format().style() if lst is not None else None
        for action, checked in (
            (self._act_bullet, style == QTextListFormat.Style.ListDisc),
            (self._act_numbered, style == QTextListFormat.Style.ListDecimal),
        ):
            action.blockSignals(True)
            action.setChecked(checked)
            action.blockSignals(False)

    def _toggle_bold(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(
            QFont.Weight.Bold if checked else QFont.Weight.Normal
        )
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_italic(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(checked)
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_underline(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(checked)
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_bullet_list(self, checked: bool) -> None:
        self._apply_list_style(
            QTextListFormat.Style.ListDisc if checked else None
        )

    def _toggle_numbered_list(self, checked: bool) -> None:
        self._apply_list_style(
            QTextListFormat.Style.ListDecimal if checked else None
        )

    def _apply_list_style(self, style: QTextListFormat.Style | None) -> None:
        cursor = self.editor.textCursor()
        if style is not None:
            cursor.createList(style)
            self.editor.setTextCursor(cursor)
        else:
            self._remove_list_from_selection(cursor)
        self._sync_format_actions()

    def _remove_list_from_selection(self, cursor: QTextCursor) -> None:
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        cursor.beginEditBlock()
        block = self.editor.document().findBlock(start)
        while block.isValid() and block.position() <= end:
            block_cursor = QTextCursor(block)
            lst = block_cursor.currentList()
            if lst is not None:
                lst.remove(block)
            next_block = block.next()
            if not next_block.isValid() or next_block.position() > end:
                break
            block = next_block
        cursor.endEditBlock()

    def _insert_link(self) -> None:
        url, ok = QInputDialog.getText(self, "Ссылка", "URL:")
        if not ok or not url.strip():
            return
        cursor = self.editor.textCursor()
        selected = cursor.selectedText() or url.strip()
        fmt = QTextCharFormat()
        fmt.setAnchor(True)
        fmt.setAnchorHref(url.strip())
        fmt.setForeground(QColor("#0d9488"))
        fmt.setFontUnderline(True)
        cursor.insertText(selected, fmt)

    def _insert_image(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Изображение",
            "",
            "Изображения (*.png *.jpg *.jpeg *.gif *.webp)",
        )
        if path:
            self.insert_image_from_path(path)

    def _open_source_files(self) -> None:
        if self._source_files_dir is None:
            return
        try:
            open_target(str(self._source_files_dir))
        except PlatformOpenError as exc:
            QMessageBox.warning(self, "Файлы", str(exc))

    def insert_image_from_path(self, path: str) -> bool:
        """Insert a magic-validated image as a data URI (files are written on save)."""
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось прочитать файл:\n{exc}")
            return False
        ext = sniff_image(data)
        if ext is None:
            QMessageBox.warning(self, "Ошибка", "Неподдерживаемый формат изображения")
            return False
        mime = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
        }[ext]
        self.editor.textCursor().insertHtml(
            _data_uri_img_html(data, mime, width=self.editor.image_preview_width)
        )
        self.editor.replace_preview_image_resources()
        return True

    @property
    def html(self) -> str:
        return self.editor.toHtml()


class HtmlEditRow(QWidget):
    """Editable raw-HTML line + «…» button opening RichTextEditDialog."""

    def __init__(
        self,
        parent=None,
        *,
        title: str = "Текст",
        html: str = "",
        image_preview_width: int = DEFAULT_IMAGE_PREVIEW_WIDTH,
        source_files_dir: Path | None = None,
        show_source_files_button: bool = False,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._image_preview_width = image_preview_width
        self.source_files_dir = source_files_dir
        self.show_source_files_button = show_source_files_button
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(html or "")
        self.edit.setPlaceholderText("HTML…")
        btn = QPushButton("…")
        btn.setObjectName("secondaryButton")
        btn.setFixedWidth(36)
        btn.setToolTip("Редактировать")
        btn.clicked.connect(self._edit)
        layout.addWidget(self.edit)
        layout.addWidget(btn)

    def _edit(self) -> None:
        dialog = RichTextEditDialog(
            self,
            title=self._title,
            html=self.edit.text(),
            image_preview_width=self._image_preview_width,
            source_files_dir=self.source_files_dir,
            show_source_files_button=self.show_source_files_button,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.edit.setText(dialog.html)

    @property
    def html(self) -> str:
        return self.edit.text()

    @html.setter
    def html(self, value: str) -> None:
        self.edit.setText(value or "")


# Backward-compatible alias
HtmlPreviewRow = HtmlEditRow


class TaskDialog(QDialog):
    def __init__(
        self,
        settings: Settings,
        parent=None,
        *,
        task: Task | None = None,
        title: str = "Заявка",
        allow_template: bool = True,
        create_folder_default: bool | None = None,
        folder_validator: Callable[["TaskDialog"], str | None] | None = None,
        initial_number: str = "",
        initial_description: str = "",
        initial_priority: int | None = None,
        initial_links: list[tuple[str, str]] | None = None,
        source_linked: bool = False,
        initial_source_status: str = "",
        reminder_rows: list[tuple[int, str]] | None = None,
        on_delete_reminder: Callable[[int], bool] | None = None,
        reminder_service=None,
        on_reminders_changed: Callable[[], None] | None = None,
        source_files_dir: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(560)
        self._settings = settings
        self._task = task
        self._folder_validator = folder_validator
        self._source_linked = bool(
            source_linked or (task is not None and task.has_source)
        )
        self._on_delete_reminder = on_delete_reminder
        self._reminder_service = reminder_service
        self._on_reminders_changed = on_reminders_changed

        layout = QVBoxLayout(self)
        form = QFormLayout()

        number_value = task.number if task else initial_number
        self.number_edit = QLineEdit(number_value)
        form.addRow("Номер", self.number_edit)

        desc_value = task.description if task else initial_description
        self.description_row = HtmlEditRow(
            title="Описание",
            html=desc_value,
            image_preview_width=settings.image_preview_width,
            source_files_dir=source_files_dir,
            show_source_files_button=True,
        )
        form.addRow("Описание", self.description_row)

        self.comment_row = HtmlEditRow(
            title="Комментарий",
            html=task.comment if task else "",
            image_preview_width=settings.image_preview_width,
        )
        form.addRow("Комментарий", self.comment_row)

        self.priority_combo = QComboBox()
        for value in range(PRIORITY_MIN, PRIORITY_MAX + 1):
            self.priority_combo.addItem(str(value), value)
            bg = priority_color_hex(value)
            self.priority_combo.setItemData(
                value, QBrush(QColor(bg)), Qt.ItemDataRole.BackgroundRole
            )
            self.priority_combo.setItemData(
                value,
                QBrush(QColor(contrast_foreground(bg))),
                Qt.ItemDataRole.ForegroundRole,
            )
        if task:
            initial_priority_value = clamp_priority(task.priority)
        elif initial_priority is not None:
            initial_priority_value = clamp_priority(initial_priority)
        else:
            initial_priority_value = PRIORITY_DEFAULT
        self.priority_combo.setCurrentIndex(initial_priority_value)
        self.priority_combo.currentIndexChanged.connect(self._sync_priority_combo_color)
        self._sync_priority_combo_color()
        form.addRow("Приоритет", self.priority_combo)

        self.workflow_combo = QComboBox()
        for status, label in WORKFLOW_STATUS_LABELS.items():
            self.workflow_combo.addItem(label, status.value)
        self.source_status_edit = QLineEdit()
        self.source_status_edit.setReadOnly(True)
        if self._source_linked:
            if task and task.has_source:
                src_text = (
                    task.source_status_label or task.source_status_id or ""
                ).strip()
            else:
                src_text = (initial_source_status or "").strip()
            self.source_status_edit.setText(src_text)
            self.source_status_edit.setPlaceholderText("Нет данных из источника")
            form.addRow("Статус источника", self.source_status_edit)
            self.workflow_combo.setVisible(False)
        else:
            initial_wf = (
                task.workflow_status if task else WorkflowStatus.NEW
            )
            idx = self.workflow_combo.findData(initial_wf.value)
            self.workflow_combo.setCurrentIndex(idx if idx >= 0 else 0)
            form.addRow("Статус работы", self.workflow_combo)
            self.source_status_edit.setVisible(False)

        self.date_end_edit = QDateEdit()
        self.date_end_edit.setCalendarPopup(True)
        self.date_end_edit.setDisplayFormat("dd.MM.yyyy")
        self.has_date_end = QCheckBox("Указать срок")
        if task and task.date_end:
            self.has_date_end.setChecked(True)
            self.date_end_edit.setDate(
                QDate(task.date_end.year, task.date_end.month, task.date_end.day)
            )
        else:
            self.has_date_end.setChecked(False)
            self.date_end_edit.setDate(QDate.currentDate())
        self.date_end_edit.setEnabled(self.has_date_end.isChecked())
        self.has_date_end.toggled.connect(self.date_end_edit.setEnabled)
        date_row = QHBoxLayout()
        date_row.addWidget(self.has_date_end)
        date_row.addWidget(self.date_end_edit)
        form.addRow("Срок", date_row)

        self.hidden_cb = QCheckBox("Скрытая")
        self.hidden_cb.setChecked(bool(task and task.hidden))
        form.addRow(self.hidden_cb)

        folder_default = (
            settings.create_task_folder
            if create_folder_default is None
            else create_folder_default
        )
        self.create_folder_cb = QCheckBox("Создать папку на диске")
        self.create_folder_cb.setChecked(folder_default)
        self.template_cb = QCheckBox(
            f"Создать из шаблона («{settings.template_name}»)"
        )
        self.template_cb.setChecked(False)
        self.notes_cb = QCheckBox("Создать файл заметок (Notes.txt)")
        self.notes_cb.setChecked(settings.create_notes_file)

        if allow_template and task is None:
            form.addRow(self.create_folder_cb)
            form.addRow(self.template_cb)
            form.addRow(self.notes_cb)
            self.create_folder_cb.toggled.connect(self._sync_folder_options)
            self.template_cb.toggled.connect(self._on_template_toggled)
            self._sync_folder_options(self.create_folder_cb.isChecked())
        else:
            self.create_folder_cb.setVisible(False)
            self.template_cb.setVisible(False)
            self.notes_cb.setVisible(False)

        if task is not None:
            if task.created_at:
                created = QLabel(
                    task.created_at.strftime("%d.%m.%Y %H:%M:%S")
                )
                form.addRow("Создана", created)
            folder_state = (
                "есть (флаг)"
                if task.has_folder
                else "нет (только БД)"
            )
            hint = QLabel(
                f"Папка на диске: {task.folder_name} — {folder_state}"
            )
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #64748b;")
            form.addRow(hint)

        layout.addLayout(form)

        layout.addWidget(QLabel("Ссылки"))
        self.links_table = QTableWidget(0, 2)
        self.links_table.setHorizontalHeaderLabels(["Имя", "URL / путь"])
        self.links_table.horizontalHeader().setStretchLastSection(True)
        self.links_table.setMinimumHeight(120)
        if task and task.links:
            for link in task.links:
                self._add_link_row(link.name, link.target)
        elif initial_links:
            for name, target in initial_links:
                self._add_link_row(name, target)
        layout.addWidget(self.links_table)

        link_btns = QHBoxLayout()
        add_link = QPushButton("Добавить ссылку")
        add_link.setObjectName("secondaryButton")
        add_link.clicked.connect(lambda: self._add_link_row("", ""))
        remove_link = QPushButton("Удалить ссылку")
        remove_link.setObjectName("secondaryButton")
        remove_link.clicked.connect(self._remove_link_row)
        link_btns.addWidget(add_link)
        link_btns.addWidget(remove_link)
        link_btns.addStretch()
        layout.addLayout(link_btns)

        self.reminders_list = QListWidget()
        self.add_reminder_btn = QPushButton("Добавить событие")
        self.add_reminder_btn.setObjectName("secondaryButton")
        self.delete_reminder_btn = QPushButton("Удалить событие")
        self.delete_reminder_btn.setObjectName("secondaryButton")
        if reminder_rows is not None:
            layout.addWidget(QLabel("События"))
            self.reminders_list.setMinimumHeight(80)
            for rid, label in reminder_rows:
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, rid)
                self.reminders_list.addItem(item)
            layout.addWidget(self.reminders_list)
            rem_btns = QHBoxLayout()
            self.add_reminder_btn.clicked.connect(self._add_reminder)
            self.delete_reminder_btn.clicked.connect(self._delete_selected_reminder)
            self.reminders_list.itemDoubleClicked.connect(self._edit_reminder)
            rem_btns.addWidget(self.add_reminder_btn)
            rem_btns.addWidget(self.delete_reminder_btn)
            rem_btns.addStretch()
            layout.addLayout(rem_btns)
        else:
            self.reminders_list.hide()
            self.add_reminder_btn.hide()
            self.delete_reminder_btn.hide()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_template_toggled(self, checked: bool) -> None:
        if checked:
            self.create_folder_cb.setChecked(True)
        self._sync_folder_options(self.create_folder_cb.isChecked())

    def _sync_folder_options(self, has_folder: bool) -> None:
        self.template_cb.setEnabled(has_folder)
        self.notes_cb.setEnabled(has_folder)
        if not has_folder:
            self.template_cb.setChecked(False)
            self.notes_cb.setChecked(False)

    def _sync_priority_combo_color(self) -> None:
        color = priority_color_hex(self.priority)
        fg = contrast_foreground(color)
        self.priority_combo.setStyleSheet(
            f"QComboBox {{ background-color: {color}; color: {fg}; }}"
        )

    def _add_link_row(self, name: str, target: str) -> None:
        row = self.links_table.rowCount()
        self.links_table.insertRow(row)
        self.links_table.setItem(row, 0, QTableWidgetItem(name))
        self.links_table.setItem(row, 1, QTableWidgetItem(target))

    def _remove_link_row(self) -> None:
        row = self.links_table.currentRow()
        if row >= 0:
            self.links_table.removeRow(row)

    def _append_reminder_row(self, reminder_id: int, label: str) -> None:
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, reminder_id)
        self.reminders_list.addItem(item)

    def _add_reminder(self) -> None:
        if self._task is None or self._task.id is None or self._reminder_service is None:
            return
        from taskmanager.services.task_service import ServiceError
        from taskmanager.ui.reminders_window import (
            ReminderEditDialog,
            format_reminder_series,
        )

        edit = ReminderEditDialog(self._reminder_service, self, task=self._task)
        if edit.exec() != ReminderEditDialog.DialogCode.Accepted:
            return
        try:
            series = edit.save_to_service()
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        if series.id is None:
            return
        self._append_reminder_row(series.id, format_reminder_series(series))
        if self._on_reminders_changed is not None:
            self._on_reminders_changed()

    def _edit_reminder(self, item: QListWidgetItem) -> None:
        if self._reminder_service is None:
            return
        rid = item.data(Qt.ItemDataRole.UserRole)
        if rid is None:
            return
        from taskmanager.services.task_service import ServiceError
        from taskmanager.ui.reminders_window import (
            ReminderEditDialog,
            format_reminder_series,
        )

        try:
            series = self._reminder_service.get_reminder(int(rid))
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        edit = ReminderEditDialog(
            self._reminder_service, self, task=self._task, series=series
        )
        if edit.exec() != ReminderEditDialog.DialogCode.Accepted:
            return
        try:
            updated = edit.save_to_service()
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        if self._task is not None and updated.task_id != self._task.id:
            self.reminders_list.takeItem(self.reminders_list.row(item))
        else:
            item.setText(format_reminder_series(updated))
        if self._on_reminders_changed is not None:
            self._on_reminders_changed()

    def _delete_selected_reminder(self) -> None:
        item = self.reminders_list.currentItem()
        if item is None or self._on_delete_reminder is None:
            return
        rid = item.data(Qt.ItemDataRole.UserRole)
        if rid is None:
            return
        answer = QMessageBox.question(self, "Удаление", "Удалить событие?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self._on_delete_reminder(int(rid)):
            self.reminders_list.takeItem(self.reminders_list.row(item))

    def _accept(self) -> None:
        if not self.number_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите номер заявки")
            return
        if self._folder_validator is not None:
            error = self._folder_validator(self)
            if error:
                QMessageBox.warning(self, "Ошибка", error)
                return
        self.accept()

    @property
    def number(self) -> str:
        return self.number_edit.text().strip()

    @property
    def description(self) -> str:
        return self.description_row.html

    @property
    def comment(self) -> str:
        return self.comment_row.html

    @property
    def priority(self) -> int:
        return clamp_priority(self.priority_combo.currentData())

    @property
    def workflow_status(self) -> WorkflowStatus:
        if self._source_linked:
            if self._task is not None:
                return self._task.workflow_status
            return WorkflowStatus.NEW
        return parse_workflow_status(self.workflow_combo.currentData())

    @property
    def date_end(self) -> date | None:
        if not self.has_date_end.isChecked():
            return None
        qd = self.date_end_edit.date()
        return date(qd.year(), qd.month(), qd.day())

    @property
    def hidden(self) -> bool:
        return self.hidden_cb.isChecked()

    @property
    def by_template(self) -> bool:
        return self.template_cb.isChecked()

    @property
    def create_notes_file(self) -> bool:
        return self.notes_cb.isChecked()

    @property
    def create_folder(self) -> bool:
        if self._task is not None:
            return self._task.has_folder
        return self.create_folder_cb.isChecked()

    @property
    def links(self) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for row in range(self.links_table.rowCount()):
            name_item = self.links_table.item(row, 0)
            target_item = self.links_table.item(row, 1)
            name = name_item.text().strip() if name_item else ""
            target = target_item.text().strip() if target_item else ""
            if name and target:
                result.append((name, target))
        return result


class MissingFoldersDialog(QDialog):
    """Startup warning listing missing folders with recreate / clear actions."""

    def __init__(
        self,
        missing: list[tuple[Project, Task]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Папки не найдены")
        self.setMinimumWidth(480)
        self._missing = list(missing)
        self.recreate_ids: list[int] = []
        self.clear_ids: list[int] = []

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "У заявок с флагом папки отсутствуют каталоги на диске.\n"
                "Выберите действие для каждой или для всех:"
            )
        )
        self.list_widget = QListWidget()
        for project, task in missing:
            item = QListWidgetItem(
                f"{project.name} / {task.number} ({task.folder_name})"
            )
            item.setData(Qt.ItemDataRole.UserRole, task.id)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        row = QHBoxLayout()
        recreate_sel = QPushButton("Создать заново")
        recreate_sel.setObjectName("secondaryButton")
        recreate_sel.clicked.connect(self._recreate_selected)
        clear_sel = QPushButton("Считать без папки")
        clear_sel.setObjectName("secondaryButton")
        clear_sel.clicked.connect(self._clear_selected)
        recreate_all = QPushButton("Создать все")
        recreate_all.clicked.connect(self._recreate_all)
        clear_all = QPushButton("Все без папки")
        clear_all.setObjectName("secondaryButton")
        clear_all.clicked.connect(self._clear_all)
        row.addWidget(recreate_sel)
        row.addWidget(clear_sel)
        row.addWidget(recreate_all)
        row.addWidget(clear_all)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)

    def _selected_ids(self) -> list[int]:
        ids: list[int] = []
        for item in self.list_widget.selectedItems():
            value = item.data(Qt.ItemDataRole.UserRole)
            if value is not None:
                ids.append(int(value))
        return ids

    def _all_ids(self) -> list[int]:
        ids: list[int] = []
        for i in range(self.list_widget.count()):
            value = self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            if value is not None:
                ids.append(int(value))
        return ids

    def _recreate_selected(self) -> None:
        ids = self._selected_ids() or self._all_ids()
        self.recreate_ids = ids
        self.clear_ids = []
        self.accept()

    def _clear_selected(self) -> None:
        ids = self._selected_ids() or self._all_ids()
        self.clear_ids = ids
        self.recreate_ids = []
        self.accept()

    def _recreate_all(self) -> None:
        self.recreate_ids = self._all_ids()
        self.clear_ids = []
        self.accept()

    def _clear_all(self) -> None:
        self.clear_ids = self._all_ids()
        self.recreate_ids = []
        self.accept()


class ExcelExportDialog(QDialog):
    def __init__(
        self,
        projects: list[Project],
        parent=None,
        *,
        archive_months_by_project: dict[int, list[str]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Экспорт в Excel")
        # ~50% larger than previous 400×(implicit ~300)
        self.setMinimumWidth(600)
        self.resize(600, 450)
        self._archive_months_by_project = archive_months_by_project or {}
        self._project_items: dict[int, QTreeWidgetItem] = {}
        self._month_items: dict[int, list[QTreeWidgetItem]] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Проекты:"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        for project in projects:
            if project.id is None:
                continue
            pid = int(project.id)
            project_item = QTreeWidgetItem([project.name])
            project_item.setFlags(
                project_item.flags() | Qt.ItemFlag.ItemIsUserCheckable
            )
            project_item.setCheckState(0, Qt.CheckState.Checked)
            project_item.setData(0, Qt.ItemDataRole.UserRole, ("project", pid))
            self.tree.addTopLevelItem(project_item)
            self._project_items[pid] = project_item
            month_items: list[QTreeWidgetItem] = []
            for month in self._archive_months_by_project.get(pid, []):
                month_item = QTreeWidgetItem([month])
                month_item.setFlags(
                    month_item.flags() | Qt.ItemFlag.ItemIsUserCheckable
                )
                month_item.setCheckState(0, Qt.CheckState.Checked)
                month_item.setData(0, Qt.ItemDataRole.UserRole, ("month", pid, month))
                project_item.addChild(month_item)
                month_items.append(month_item)
            self._month_items[pid] = month_items
            # Months visible only when archive is enabled
            for child in month_items:
                child.setHidden(True)
        layout.addWidget(self.tree)

        self.hidden_cb = QCheckBox("Включить скрытые")
        self.archive_cb = QCheckBox("Включить архив")
        self.archive_cb.toggled.connect(self._on_archive_toggled)
        layout.addWidget(self.hidden_cb)
        layout.addWidget(self.archive_cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_archive_toggled(self, checked: bool) -> None:
        for month_items in self._month_items.values():
            for child in month_items:
                child.setHidden(not checked)
            if checked and month_items:
                parent = month_items[0].parent()
                if parent is not None:
                    parent.setExpanded(True)

    def _accept(self) -> None:
        if not self.selected_project_ids:
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы один проект")
            return
        self.accept()

    @property
    def selected_project_ids(self) -> list[int]:
        ids: list[int] = []
        for pid, item in self._project_items.items():
            if item.checkState(0) == Qt.CheckState.Checked:
                ids.append(pid)
        return ids

    @property
    def include_hidden(self) -> bool:
        return self.hidden_cb.isChecked()

    @property
    def include_archived(self) -> bool:
        return self.archive_cb.isChecked()

    @property
    def selected_archive_months(self) -> dict[int, list[str]]:
        """project_id → selected YYYY_MM months (only when archive enabled)."""
        if not self.include_archived:
            return {}
        result: dict[int, list[str]] = {}
        for pid in self.selected_project_ids:
            month_items = self._month_items.get(pid, [])
            result[pid] = [
                item.text(0)
                for item in month_items
                if item.checkState(0) == Qt.CheckState.Checked
            ]
        return result


def source_refresh_confirm_phrases(*, keep_priority: bool) -> tuple[str, str]:
    """Overwrite fields + preserved-note for single and bulk Refresh confirms."""
    if keep_priority:
        return (
            "описание и служебные ссылки",
            "Комментарий и приоритет не изменятся.",
        )
    return (
        "описание, приоритет и служебные ссылки",
        "Комментарий не изменится.",
    )


class BulkRefreshConfirmDialog(QDialog):
    """Consent for bulk Refresh from source, with optional source-file download."""

    def __init__(
        self, count: int, parent=None, *, keep_priority: bool = False
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Обновить все")
        layout = QVBoxLayout(self)
        fields, note = source_refresh_confirm_phrases(keep_priority=keep_priority)
        overwrite = fields[:1].upper() + fields[1:]
        label = QLabel(
            f"Будет обновлено {count} заявок из источника. "
            f"{overwrite} перезапишутся. "
            f"{note}"
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self.download_cb = QCheckBox("Скачать файлы источника")
        self.download_cb.setChecked(True)
        layout.addWidget(self.download_cb)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def download_files(self) -> bool:
        return self.download_cb.isChecked()