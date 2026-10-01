from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QContextMenuEvent, QImage, QTextCursor
from PySide6.QtWidgets import QApplication, QDialog

from taskmanager.services.inline_images import IMAGES_DIR_NAME
from taskmanager.ui.markdown_editor import MarkdownEditDialog, MarkdownTextEdit


PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63f8cfc0000003010100c9fe92ef0000000049454e44ae426082"
)


def _select_all(edit) -> None:
    cursor = edit.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    edit.setTextCursor(cursor)


def test_text_mode_is_default_and_round_trips(qtbot):
    dialog = MarkdownEditDialog(markdown="**жирный**\n\n- [ ] дело")
    qtbot.addWidget(dialog)
    assert dialog.mode_combo.currentText() == "Текст"
    assert dialog.mode_combo.currentData() == "text"
    assert "**" not in dialog.text_edit.toPlainText()
    assert "жирный" in dialog.text_edit.toPlainText()
    assert "☐" in dialog.text_edit.toPlainText()
    assert dialog.markdown == "**жирный**\n\n- [ ] дело"
    assert dialog.image_action.isEnabled()

    dialog.toggle_task_checkbox(0)
    assert dialog.markdown == "**жирный**\n\n- [x] дело"

    dialog.set_markdown_mode(True)
    assert dialog.mode_combo.currentText() == "Markdown"
    assert dialog.image_action.isEnabled()
    assert dialog.source_edit.toPlainText() == "**жирный**\n\n- [x] дело"
    dialog.source_edit.setPlainText("черновик")
    dialog.set_markdown_mode(False)
    assert dialog.mode_combo.currentText() == "Текст"
    assert dialog.markdown == "черновик"
    assert "черновик" in dialog.text_edit.toPlainText()


def test_click_on_checkbox_flips_markdown(qtbot):
    dialog = MarkdownEditDialog(markdown="- [ ] дело")
    qtbot.addWidget(dialog)
    dialog.resize(676, 468)
    dialog.show()
    edit = dialog.text_edit
    fragment = None
    block = edit.document().begin()
    while block.isValid() and fragment is None:
        iterator = block.begin()
        while not iterator.atEnd():
            current = iterator.fragment()
            if current.isValid() and "☐" in current.text():
                fragment = current
                break
            iterator += 1
        block = block.next()
    assert fragment is not None
    cursor = QTextCursor(edit.document())
    cursor.setPosition(fragment.position())
    rect = edit.cursorRect(cursor)
    qtbot.mouseClick(
        edit.viewport(),
        Qt.MouseButton.LeftButton,
        pos=rect.center(),
    )
    assert dialog.markdown == "- [x] дело"


def test_typing_in_text_mode_is_markdown(qtbot):
    dialog = MarkdownEditDialog(markdown="до")
    qtbot.addWidget(dialog)
    cursor = dialog.text_edit.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    dialog.text_edit.setTextCursor(cursor)
    dialog.text_edit.insertPlainText(" после")
    assert dialog.markdown == "до после"


def test_toolbar_in_text_mode_writes_markdown(qtbot):
    cases = (
        ("bold_action", "слово", "**слово**"),
        ("italic_action", "слово", "*слово*"),
        ("strike_action", "слово", "~~слово~~"),
        ("code_action", "слово", "`слово`"),
        ("quote_action", "слово", "> слово"),
        ("bullet_action", "слово", "- слово"),
        ("numbered_action", "слово", "1. слово"),
        ("todo_action", "слово", "- [ ] слово"),
    )
    for name, source, expected in cases:
        dialog = MarkdownEditDialog(markdown=source)
        qtbot.addWidget(dialog)
        _select_all(dialog.text_edit)
        getattr(dialog, name).trigger()
        dialog.set_markdown_mode(True)
        assert dialog.source_edit.toPlainText() == expected, name


def test_toolbar_in_markdown_mode_toggles_syntax(qtbot):
    cases = (
        ("bold_action", "слово", "**слово**"),
        ("italic_action", "слово", "*слово*"),
        ("strike_action", "слово", "~~слово~~"),
        ("code_action", "слово", "`слово`"),
        ("quote_action", "слово", "> слово"),
        ("bullet_action", "слово", "- слово"),
        ("numbered_action", "слово", "1. слово"),
        ("todo_action", "слово", "- [ ] слово"),
    )
    for name, source, expected in cases:
        dialog = MarkdownEditDialog(markdown=source)
        qtbot.addWidget(dialog)
        dialog.set_markdown_mode(True)
        _select_all(dialog.source_edit)
        action = getattr(dialog, name)
        action.trigger()
        assert dialog.source_edit.toPlainText() == expected, name
        action.trigger()
        assert dialog.source_edit.toPlainText() == source, name


def test_heading_combo_sets_level_in_both_modes(qtbot):
    labels = ["Обычный"] + [f"Заголовок {level}" for level in range(1, 7)]
    dialog = MarkdownEditDialog(markdown="слово")
    qtbot.addWidget(dialog)
    assert dialog.heading_combo.toolTip() == "Заголовок"
    assert [dialog.heading_combo.itemText(i) for i in range(dialog.heading_combo.count())] == labels

    for level in range(1, 7):
        prefix = "#" * level
        dialog = MarkdownEditDialog(markdown="слово")
        qtbot.addWidget(dialog)
        _select_all(dialog.text_edit)
        _choose_heading(dialog, level)
        assert dialog.markdown == f"{prefix} слово"
        _choose_heading(dialog, 0)
        assert dialog.markdown == "слово"

        dialog = MarkdownEditDialog(markdown="слово")
        qtbot.addWidget(dialog)
        dialog.set_markdown_mode(True)
        _select_all(dialog.source_edit)
        _choose_heading(dialog, level)
        assert dialog.source_edit.toPlainText() == f"{prefix} слово"
        _choose_heading(dialog, 0)
        assert dialog.source_edit.toPlainText() == "слово"


def test_heading_combo_follows_the_cursor(qtbot):
    dialog = MarkdownEditDialog(markdown="# Раз\n\n### Три")
    qtbot.addWidget(dialog)
    assert dialog.heading_combo.currentData() == 1
    cursor = dialog.text_edit.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
    cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
    dialog.text_edit.setTextCursor(cursor)
    assert dialog.heading_combo.currentData() == 3


def test_heading_on_pixel_font_uses_point_size(qtbot):
    from PySide6.QtGui import QFontInfo

    dialog = MarkdownEditDialog(markdown="слово")
    qtbot.addWidget(dialog)
    font = dialog.text_edit.font()
    font.setPixelSize(13)
    dialog.text_edit.setFont(font)
    assert dialog.text_edit.font().pixelSize() > 0
    body = QFontInfo(dialog.text_edit.font()).pointSizeF()
    _select_all(dialog.text_edit)
    _choose_heading(dialog, 1)
    assert dialog.markdown == "# слово"
    largest = _first_point_size(dialog.text_edit)
    assert largest >= body * 1.8
    _choose_heading(dialog, 6)
    assert dialog.markdown == "###### слово"
    smallest = _first_point_size(dialog.text_edit)
    assert body < smallest < largest
    _choose_heading(dialog, 0)
    assert dialog.markdown == "слово"


def test_enter_in_todo_continues_with_checkbox(qtbot):
    dialog = MarkdownEditDialog(markdown="- [ ] дело")
    qtbot.addWidget(dialog)
    dialog.show()
    edit = dialog.text_edit
    _end_of_block(edit, 0)
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert [line.rstrip() for line in dialog.markdown.split("\n")] == [
        "- [ ] дело",
        "- [ ]",
    ]
    assert "☐" in edit.document().begin().next().text()

    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert dialog.markdown == "- [ ] дело"
    assert edit.textCursor().block().textList() is None
    assert "☐" not in edit.textCursor().block().text()


def test_enter_splits_checked_todo_into_a_new_unchecked_item(qtbot):
    dialog = MarkdownEditDialog(markdown="- [x] дело")
    qtbot.addWidget(dialog)
    dialog.show()
    edit = dialog.text_edit
    block = edit.document().begin()
    cursor = QTextCursor(block)
    cursor.setPosition(block.position() + block.text().index("ло"))
    edit.setTextCursor(cursor)
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert dialog.markdown == "- [x] де\n- [ ] ло"


def test_enter_on_empty_todo_between_items_leaves_the_list(qtbot):
    dialog = MarkdownEditDialog(markdown="- [ ] один\n- [ ] ещё\n- [ ] три")
    qtbot.addWidget(dialog)
    dialog.show()
    edit = dialog.text_edit
    block = edit.document().begin().next()
    text = block.text()
    assert "ещё" in text
    cursor = QTextCursor(block)
    cursor.setPosition(block.position() + text.index("ещё"))
    cursor.movePosition(
        QTextCursor.MoveOperation.EndOfBlock,
        QTextCursor.MoveMode.KeepAnchor,
    )
    edit.setTextCursor(cursor)
    cursor = edit.textCursor()
    cursor.removeSelectedText()
    edit.setTextCursor(cursor)
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert edit.textCursor().block().textList() is None
    assert "☐" not in edit.textCursor().block().text()
    assert dialog.markdown == "- [ ] один\n- [ ] три"


def test_enter_in_bullet_does_not_add_a_checkbox(qtbot):
    dialog = MarkdownEditDialog(markdown="- пункт")
    qtbot.addWidget(dialog)
    dialog.show()
    edit = dialog.text_edit
    _end_of_block(edit, 0)
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert "☐" not in edit.toPlainText()
    assert [line.rstrip() for line in dialog.markdown.split("\n")] == ["- пункт", "-"]


def test_markdown_link_and_fence_toggle(qtbot):
    dialog = MarkdownEditDialog(markdown="сайт")
    qtbot.addWidget(dialog)
    dialog.set_markdown_mode(True)
    _select_all(dialog.source_edit)
    dialog.apply_link("https://example.com")
    assert dialog.source_edit.toPlainText() == "[сайт](https://example.com)"
    _select_all(dialog.source_edit)
    dialog.link_action.trigger()
    assert dialog.source_edit.toPlainText() == "сайт"

    dialog.source_edit.setPlainText("line1\nline2")
    _select_all(dialog.source_edit)
    dialog.code_action.trigger()
    assert dialog.source_edit.toPlainText() == "```\nline1\nline2\n```"
    _select_all(dialog.source_edit)
    dialog.code_action.trigger()
    assert dialog.source_edit.toPlainText() == "line1\nline2"


def test_text_mode_link_round_trips(qtbot):
    dialog = MarkdownEditDialog(markdown="сайт")
    qtbot.addWidget(dialog)
    _select_all(dialog.text_edit)
    dialog.apply_link("https://example.com")
    dialog.set_markdown_mode(True)
    assert dialog.source_edit.toPlainText() == "[сайт](https://example.com)"


def test_insert_image_writes_file_and_markdown_link(tmp_path: Path, qtbot):
    images = tmp_path / IMAGES_DIR_NAME
    png = tmp_path / "shot.png"
    png.write_bytes(PNG_1x1)
    dialog = MarkdownEditDialog(
        markdown="до",
        ensure_images_dir=lambda: images,
    )
    qtbot.addWidget(dialog)
    assert dialog.mode_combo.currentText() == "Текст"
    assert dialog.insert_image_from_path(str(png))
    assert (images / "shot.png").read_bytes() == PNG_1x1
    assert "![](.images/shot.png)" in dialog.markdown
    assert "<img" not in dialog.markdown
    assert _has_image(dialog.text_edit)

    dialog.set_markdown_mode(True)
    assert "![](.images/shot.png)" in dialog.source_edit.toPlainText()
    assert dialog.image_action.isEnabled()


def test_paste_image_uses_clipboard_name(tmp_path: Path, qtbot):
    images = tmp_path / IMAGES_DIR_NAME
    dialog = MarkdownEditDialog(ensure_images_dir=lambda: images)
    qtbot.addWidget(dialog)
    assert dialog.insert_image_bytes(PNG_1x1, "clipboard.png")
    assert (images / "clipboard.png").is_file()
    assert "![](.images/clipboard.png)" in dialog.markdown


def test_toolbar_tooltips_and_no_underline(qtbot):
    dialog = MarkdownEditDialog(markdown="текст")
    qtbot.addWidget(dialog)
    tips = {
        dialog.bold_action: "Жирный",
        dialog.italic_action: "Курсив",
        dialog.strike_action: "Зачёркнутый",
        dialog.code_action: "Код",
        dialog.quote_action: "Цитата",
        dialog.bullet_action: "Маркированный список",
        dialog.numbered_action: "Нумерованный список",
        dialog.todo_action: "Список задач",
        dialog.link_action: "Ссылка",
        dialog.image_action: "Вставить изображение",
        dialog.table_action: "Таблица",
    }
    for action, tip in tips.items():
        assert action.toolTip() == tip
    labels = {action.text() for action in tips}
    assert "Ч" not in labels
    assert "H" not in labels
    assert dialog.heading_combo.toolTip() == "Заголовок"


def test_editor_toolbar_matches_the_dialog_surface(qtbot, qapp, monkeypatch):
    def theme(_mode):
        return theme.mode

    theme.mode = "light"
    monkeypatch.setattr("taskmanager.ui.markdown_editor.resolve_theme_mode", theme)
    previous = qapp.styleSheet()
    qapp.setStyleSheet("")
    dialog = MarkdownEditDialog(markdown="текст")
    qtbot.addWidget(dialog)
    try:
        dialog._apply_toolbar_chrome()
        light = _toolbar_background(dialog.toolbar.styleSheet())
        assert "#f1f5f9" in light
        assert "#0f172a" not in light
        assert "palette(window)" not in dialog.toolbar.styleSheet()
        assert "#0f766e" not in dialog.toolbar.styleSheet()

        theme.mode = "dark"
        dialog._apply_toolbar_chrome()
        dark = _toolbar_background(dialog.toolbar.styleSheet())
        assert "#0f172a" in dark
        assert "#f1f5f9" not in dark
        assert "#0f766e" not in dialog.toolbar.styleSheet()
    finally:
        qapp.setStyleSheet(previous)


def test_editor_toolbar_follows_the_dialog_stylesheet(qtbot, qapp):
    from taskmanager.ui.stylesheet import load_stylesheet

    light_sheet, _source = load_stylesheet("app.qss")
    dark_sheet, _source = load_stylesheet("app_dark.qss")
    previous = qapp.styleSheet()
    dialog = MarkdownEditDialog(markdown="текст")
    qtbot.addWidget(dialog)
    try:
        qapp.setStyleSheet(light_sheet)
        dialog._apply_toolbar_chrome()
        assert "#f1f5f9" in _toolbar_background(dialog.toolbar.styleSheet())
        assert "#0f766e" not in dialog.toolbar.styleSheet()
        qapp.setStyleSheet(dark_sheet)
        dialog._apply_toolbar_chrome()
        assert "#0f172a" in _toolbar_background(dialog.toolbar.styleSheet())
        assert "#f1f5f9" not in _toolbar_background(dialog.toolbar.styleSheet())
        assert "#0f766e" not in dialog.toolbar.styleSheet()
    finally:
        qapp.setStyleSheet(previous)


def test_description_row_is_markdown(qtbot, tmp_path: Path):
    from taskmanager.services.settings_service import Settings
    from taskmanager.ui.dialogs import TaskDialog

    dialog = TaskDialog(Settings(work_dir=str(tmp_path)))
    qtbot.addWidget(dialog)
    assert dialog.description_row.edit.placeholderText() == "Markdown…"
    assert dialog.comment_row.edit.placeholderText() == "Markdown…"
    dialog.comment_row.html = "черновик"
    assert dialog.comment == "черновик"


def test_code_and_quote_use_theme_fill(qtbot):
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication

    from taskmanager.services.settings_service import THEME_DARK, THEME_LIGHT
    from taskmanager.ui.stylesheet import apply_stylesheet

    app = QApplication.instance()
    previous = app.styleSheet()
    try:
        apply_stylesheet(app, THEME_LIGHT)
        light = MarkdownEditDialog(markdown="до `код` после\n\n```\nline\n```\n\n> цитата")
        qtbot.addWidget(light)
        light.show()
        _assert_fill_contrast(light)

        apply_stylesheet(app, THEME_DARK)
        dark = MarkdownEditDialog(markdown="до `код` после\n\n```\nline\n```\n\n> цитата")
        qtbot.addWidget(dark)
        dark.show()
        base = dark.text_edit.palette().color(QPalette.ColorRole.Base)
        assert base.lightness() < 128
        _assert_fill_contrast(dark)
    finally:
        app.setStyleSheet(previous)


def test_quote_bar_uses_accent_color(qtbot):
    from PySide6.QtGui import QColor, QImage

    dialog = MarkdownEditDialog(markdown="> цитата")
    qtbot.addWidget(dialog)
    dialog.resize(480, 220)
    dialog.show()
    edit = dialog.text_edit
    image = QImage(edit.viewport().size(), QImage.Format.Format_ARGB32)
    edit.viewport().render(image)
    accent = QColor("#0d9488")
    hits = [
        (x, y)
        for y in range(image.height())
        for x in range(24)
        if _near(image.pixelColor(x, y), accent)
    ]
    assert hits, "quote bar should be drawn in the left margin"


def test_task_box_has_no_bullet_and_a_wide_hit_area(qtbot):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QImage, QTextListFormat

    dialog = MarkdownEditDialog(markdown="- [ ] дело\n- пункт\n\n*курсив*")
    qtbot.addWidget(dialog)
    dialog.resize(480, 240)
    dialog.show()
    edit = dialog.text_edit
    task = edit.document().begin()
    bullet = task.next()
    assert task.textList().format().style() == QTextListFormat.Style.ListStyleUndefined
    assert bullet.textList().format().style() == QTextListFormat.Style.ListDisc
    assert _fragment_uses_editor_color(edit, task)
    assert "☐" in task.text()
    assert "☐" not in bullet.text()
    assert "*" not in edit.toPlainText().splitlines()[0]

    fragment = _checkbox_fragment(edit)
    assert fragment is not None
    _erase, square, hit = edit._task_box_geometry(fragment)
    cursor = edit.textCursor()
    cursor.setPosition(fragment.position())
    glyph = edit.cursorRect(cursor)
    end = edit.textCursor()
    end.setPosition(fragment.position() + 1)
    advance = edit.cursorRect(end).left() - glyph.left()
    assert square.width() >= advance + 4
    assert hit.width() > square.width()
    assert hit.left() < square.left()

    image = QImage(edit.viewport().size(), QImage.Format.Format_ARGB32)
    edit.viewport().render(image)
    task_runs = _dark_runs(image, square.center().y(), 0, square.right() + 4)
    bullet_line = edit.cursorRect(QTextCursor(bullet))
    bullet_runs = _dark_runs(image, bullet_line.center().y(), 0, 80)
    assert task_runs
    span = task_runs[-1][1] - task_runs[0][0]
    assert span >= 14
    assert task_runs[-1][0] - task_runs[0][1] >= 6
    assert bullet_runs, "a normal list item keeps its marker"
    bullet_span = bullet_runs[0][1] - bullet_runs[0][0]
    assert bullet_span < span

    qtbot.mouseMove(edit.viewport(), hit.center())
    assert edit.viewport().cursor().shape() == Qt.CursorShape.PointingHandCursor
    qtbot.mouseMove(edit.viewport(), QPoint(hit.right() + 40, hit.center().y()))
    assert edit.viewport().cursor().shape() != Qt.CursorShape.PointingHandCursor

    qtbot.mouseClick(edit.viewport(), Qt.MouseButton.LeftButton, pos=hit.topLeft())
    assert dialog.markdown == "- [x] дело\n- пункт\n\n*курсив*"


def test_mode_combo_switches_the_same_document(qtbot):
    dialog = MarkdownEditDialog(markdown="**жирный**")
    qtbot.addWidget(dialog)
    assert dialog.mode_combo.currentText() == "Текст"
    assert list(dialog.mode_combo.itemText(i) for i in range(dialog.mode_combo.count())) == [
        "Текст",
        "Markdown",
    ]
    dialog.mode_combo.setCurrentText("Markdown")
    assert dialog.stack.currentWidget() is dialog.source_edit
    assert dialog.source_edit.toPlainText() == "**жирный**"
    dialog.mode_combo.setCurrentText("Текст")
    assert dialog.stack.currentWidget() is dialog.text_edit
    assert dialog.markdown == "**жирный**"


def test_todo_toggle_does_not_recolor_the_item(qtbot):
    from PySide6.QtGui import QTextListFormat

    dialog = MarkdownEditDialog(markdown="слово")
    qtbot.addWidget(dialog)
    _select_all(dialog.text_edit)
    dialog.todo_action.trigger()
    assert dialog.markdown == "- [ ] слово"
    task = dialog.text_edit.document().begin()
    assert task.textList().format().style() == QTextListFormat.Style.ListStyleUndefined
    assert _fragment_uses_editor_color(dialog.text_edit, task)
    assert "слово" in task.text()


def test_text_mode_uses_one_font_except_headings_and_code(qtbot):
    from PySide6.QtCore import QMimeData
    from PySide6.QtGui import QFontInfo

    source = (
        "# а\n\n## б\n\n### в\n\n#### г\n\n##### д\n\n###### е\n\n"
        "текст\n\n- пункт\n\n> цитата\n\n`код`"
    )
    dialog = MarkdownEditDialog(markdown=source)
    qtbot.addWidget(dialog)
    edit = dialog.text_edit
    body = QFontInfo(edit.font()).pointSizeF()
    family = edit.font().family().casefold()
    sizes = []
    block = edit.document().begin()
    while block.isValid():
        text = block.text().strip()
        if not text:
            block = block.next()
            continue
        point = _block_point_size(block)
        weight = _block_weight(block)
        if text in list("абвгде"):
            sizes.append(point)
            assert weight >= 700
            assert _block_family(block) == family
        elif text == "код":
            assert "mono" in _block_family(block)
        else:
            assert point == 0 or abs(point - body) < 0.2
            assert _block_family(block) == family
            assert _fragment_uses_editor_color(edit, block)
        block = block.next()
    assert len(sizes) == 6
    assert sizes[0] > sizes[-1] > body
    assert sizes == sorted(sizes, reverse=True)
    assert dialog.markdown == source

    mime = QMimeData()
    mime.setHtml(
        '<p style="font-family:Times; font-size:28pt; color:#ff0000">чужой</p>'
    )
    edit.insertFromMimeData(mime)
    pasted = _block_with_text(edit, "чужой")
    assert pasted is not None
    assert "times" not in _block_family(pasted)
    assert _block_family(pasted) == family
    pasted_size = _block_point_size(pasted)
    assert pasted_size == 0 or pasted_size < 16
    assert _fragment_uses_editor_color(edit, pasted)


def test_table_button_inserts_a_bordered_grid(qtbot):
    from PySide6.QtGui import QTextTableCellFormat

    dialog = MarkdownEditDialog(markdown="")
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.table_action.trigger()
    edit = dialog.text_edit
    table = edit.textCursor().currentTable()
    assert table is not None
    assert table.rows() == 2
    assert table.columns() == 3
    assert table.format().border() >= 1
    cell_fmt = QTextTableCellFormat(table.cellAt(0, 0).format())
    assert cell_fmt.topBorder() >= 1
    assert cell_fmt.leftBorder() >= 1
    qtbot.keyClick(edit, Qt.Key.Key_Tab)
    cell = table.cellAt(edit.textCursor())
    assert (cell.row(), cell.column()) == (0, 1)
    qtbot.keyClick(edit, Qt.Key.Key_Backtab)
    cell = table.cellAt(edit.textCursor())
    assert (cell.row(), cell.column()) == (0, 0)
    assert "| --- | --- | --- |" in dialog.markdown
    dialog.set_markdown_mode(True)
    dialog.set_markdown_mode(False)
    reloaded = _first_table(dialog.text_edit)
    assert reloaded is not None
    assert reloaded.rows() == 2 and reloaded.columns() == 3
    assert reloaded.format().border() >= 1
    reloaded_cell = QTextTableCellFormat(reloaded.cellAt(1, 2).format())
    assert reloaded_cell.topBorder() >= 1
    assert reloaded_cell.leftBorder() >= 1

    source = MarkdownEditDialog(markdown="до")
    qtbot.addWidget(source)
    source.set_markdown_mode(True)
    cursor = source.source_edit.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    source.source_edit.setTextCursor(cursor)
    source.table_action.trigger()
    text = source.source_edit.toPlainText()
    assert text.startswith("до\n")
    assert "| --- | --- | --- |" in text


def test_horizontal_rule_is_visible_and_survives_the_mode_switch(qtbot):
    source = "до\n\n---\n\nпосле"
    dialog = MarkdownEditDialog(markdown=source)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.markdown == source
    assert _horizontal_rules(dialog.text_edit)
    dialog.set_markdown_mode(True)
    assert dialog.source_edit.toPlainText() == source
    dialog.set_markdown_mode(False)
    assert dialog.markdown == source
    assert _horizontal_rules(dialog.text_edit)

    typed = MarkdownEditDialog(markdown="")
    qtbot.addWidget(typed)
    typed.show()
    _type_minus(qtbot, typed.text_edit, 3)
    assert typed.markdown == "---"
    assert _horizontal_rules(typed.text_edit)
    qtbot.keyClick(typed.text_edit, Qt.Key.Key_X)
    assert typed.markdown == "---\n\nx"

    inline = MarkdownEditDialog(markdown="аб")
    qtbot.addWidget(inline)
    inline.show()
    _end_of_block(inline.text_edit, 0)
    _type_minus(qtbot, inline.text_edit, 3)
    assert inline.markdown == "аб---"
    assert not _horizontal_rules(inline.text_edit)


def test_cell_menu_inserts_and_deletes_the_clicked_row_and_column(qtbot, monkeypatch):
    dialog = MarkdownEditDialog(markdown="")
    qtbot.addWidget(dialog)
    dialog.resize(900, 700)
    dialog.show()
    QApplication.processEvents()
    dialog.table_action.trigger()
    edit = dialog.text_edit
    table = _first_table(edit)
    assert table is not None
    edit.setTextCursor(table.cellAt(0, 0).firstCursorPosition())
    _type_minus(qtbot, edit, 3)
    assert _first_table(edit) is not None
    assert _first_table(edit).rows() == 2

    labels = _cell_menu_labels(edit, 0, 1, monkeypatch)
    assert labels[-4:] == [
        "Строка ниже",
        "Столбец справа",
        "Удалить строку",
        "Удалить столбец",
    ]

    _run_cell_action(edit, 0, 0, "Строка ниже", monkeypatch)
    table = _first_table(edit)
    assert table.rows() == 3
    assert table.cellAt(edit.textCursor()).row() == 1
    _set_cell_text(edit, 0, 0, "шапка")
    _set_cell_text(edit, 1, 0, "середина")
    _set_cell_text(edit, 2, 0, "низ")
    _set_cell_text(edit, 0, 1, "право")

    _run_cell_action(edit, 1, 0, "Удалить строку", monkeypatch)
    table = _first_table(edit)
    assert table.rows() == 2
    assert "середина" not in dialog.markdown
    assert "шапка" in dialog.markdown
    assert "низ" in dialog.markdown

    _run_cell_action(edit, 0, 0, "Столбец справа", monkeypatch)
    table = _first_table(edit)
    assert table.columns() == 4
    assert table.cellAt(edit.textCursor()).column() == 1
    assert "| --- | --- | --- | --- |" in dialog.markdown

    _run_cell_action(edit, 0, 2, "Удалить столбец", monkeypatch)
    table = _first_table(edit)
    assert table.columns() == 3
    assert "право" not in dialog.markdown
    assert "шапка" in dialog.markdown
    assert "| --- | --- | --- |" in dialog.markdown

    last = table.cellAt(table.rows() - 1, table.columns() - 1).firstCursorPosition()
    edit.setTextCursor(last)
    rows = table.rows()
    qtbot.keyClick(edit, Qt.Key.Key_Tab)
    assert _first_table(edit).rows() == rows
    assert _first_table(edit).columns() == 3


def test_mixed_task_and_bullet_stay_one_list(qtbot):
    source = "- [ ] дело\n- пункт\n\n*курсив*"
    dialog = MarkdownEditDialog(markdown=source)
    qtbot.addWidget(dialog)
    assert dialog.markdown == source
    nested = "- [ ] a\n  - [x] nested\n- bullet"
    dialog = MarkdownEditDialog(markdown=nested)
    qtbot.addWidget(dialog)
    assert dialog.markdown == nested


def _type_minus(qtbot, edit, count: int) -> None:
    for _ in range(count):
        qtbot.keyClick(edit, Qt.Key.Key_Minus)


def _toolbar_background(qss: str) -> str:
    return qss.split("QToolBar {", 1)[1].split("}", 1)[0]


def _horizontal_rules(edit) -> list:
    from PySide6.QtGui import QTextFormat

    prop = QTextFormat.Property.BlockTrailingHorizontalRulerWidth
    found = []
    block = edit.document().begin()
    while block.isValid():
        if block.blockFormat().hasProperty(prop):
            found.append(block)
        block = block.next()
    return found


def _set_cell_text(edit, row: int, column: int, text: str) -> None:
    table = _first_table(edit)
    cell = table.cellAt(row, column)
    cursor = cell.firstCursorPosition()
    cursor.setPosition(cell.lastPosition(), QTextCursor.MoveMode.KeepAnchor)
    cursor.removeSelectedText()
    cursor.insertText(text)
    edit.setTextCursor(cursor)


def _cell_menu_labels(edit, row: int, column: int, monkeypatch) -> list[str]:
    captured: dict[str, list[str]] = {}

    def fake_exec(_edit, menu, _pos):
        captured["labels"] = [action.text() for action in menu.actions() if action.text()]

    monkeypatch.setattr(MarkdownTextEdit, "_exec_menu", fake_exec)
    _open_cell_menu(edit, row, column)
    return captured["labels"]


def _run_cell_action(edit, row: int, column: int, label: str, monkeypatch) -> None:
    def fake_exec(_edit, menu, _pos):
        for action in menu.actions():
            if action.text() == label:
                action.trigger()
                return
        raise AssertionError(label)

    monkeypatch.setattr(MarkdownTextEdit, "_exec_menu", fake_exec)
    _open_cell_menu(edit, row, column)


def _open_cell_menu(edit, row: int, column: int) -> None:
    table = _first_table(edit)
    cursor = table.cellAt(row, column).firstCursorPosition()
    pos = edit.cursorRect(cursor).center()
    edit.contextMenuEvent(
        QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            pos,
            edit.viewport().mapToGlobal(pos),
        )
    )


def _select_word(edit, word: str) -> None:
    block = edit.document().begin()
    while block.isValid():
        text = block.text()
        index = text.find(word)
        if index >= 0:
            cursor = QTextCursor(edit.document())
            start = block.position() + index
            cursor.setPosition(start)
            cursor.setPosition(start + len(word), QTextCursor.MoveMode.KeepAnchor)
            edit.setTextCursor(cursor)
            return
        block = block.next()
    raise AssertionError(word)


def _anchor_point(edit, href_part: str) -> QPoint:
    block = edit.document().begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and href_part in fragment.charFormat().anchorHref():
                cursor = QTextCursor(edit.document())
                cursor.setPosition(fragment.position())
                return edit.cursorRect(cursor).center()
            iterator += 1
        block = block.next()
    raise AssertionError(href_part)


def _first_table(edit):
    block = edit.document().begin()
    while block.isValid():
        table = QTextCursor(block).currentTable()
        if table is not None:
            return table
        block = block.next()
    return None


def _fragment_uses_editor_color(edit, block) -> bool:
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        iterator += 1
        if not fragment.isValid() or not fragment.text().strip():
            continue
        brush = fragment.charFormat().foreground()
        if brush.style() == Qt.BrushStyle.NoBrush:
            continue
        if brush.color() == edit.palette().text().color():
            continue
        return False
    return True


def _block_with_text(edit, needle: str):
    block = edit.document().begin()
    while block.isValid():
        if needle in block.text():
            return block
        block = block.next()
    return None


def _block_point_size(block) -> float:
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid() and fragment.text().strip():
            return fragment.charFormat().fontPointSize()
        iterator += 1
    return 0


def _block_weight(block) -> int:
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid() and fragment.text().strip():
            return fragment.charFormat().fontWeight()
        iterator += 1
    return 0


def _block_family(block) -> str:
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid() and fragment.text().strip():
            families = fragment.charFormat().fontFamilies()
            if families:
                return families[0].casefold()
            return fragment.charFormat().font().family().casefold()
        iterator += 1
    return ""


def _choose_heading(dialog, level: int) -> None:
    dialog.heading_combo.setCurrentIndex(dialog.heading_combo.findData(level))


def _end_of_block(edit, index: int) -> None:
    block = edit.document().begin()
    for _ in range(index):
        block = block.next()
    cursor = QTextCursor(block)
    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
    edit.setTextCursor(cursor)


def _first_point_size(edit) -> float:
    block = edit.document().begin()
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid() and fragment.text().strip():
            return fragment.charFormat().fontPointSize()
        iterator += 1
    return 0


def _assert_fill_contrast(dialog) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPalette

    edit = dialog.text_edit
    base = edit.palette().color(QPalette.ColorRole.Base)
    fills = []
    block = edit.document().begin()
    while block.isValid():
        brush = block.blockFormat().background()
        if brush.style() != Qt.BrushStyle.NoBrush:
            fills.append(brush.color())
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.text() and "код" in fragment.text():
                fills.append(fragment.charFormat().background().color())
            iterator += 1
        block = block.next()
    assert fills
    for color in fills:
        if base.lightness() < 128:
            assert color.lightness() > base.lightness() + 8
        else:
            assert color.lightness() < base.lightness() - 8


def _checkbox_fragment(edit):
    block = edit.document().begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and "☐" in fragment.text():
                return fragment
            iterator += 1
        block = block.next()
    return None


def _near(color, expected) -> bool:
    return (
        abs(color.red() - expected.red()) < 12
        and abs(color.green() - expected.green()) < 12
        and abs(color.blue() - expected.blue()) < 12
    )


def _dark_runs(image, y: int, x0: int, x1: int):
    if y < 0 or y >= image.height():
        return []
    runs = []
    start = None
    for x in range(x0, min(x1, image.width())):
        dark = image.pixelColor(x, y).lightness() < 96
        if dark and start is None:
            start = x
        elif not dark and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, min(x1, image.width())))
    return runs


def test_open_sizes_every_image_from_the_preview_setting(tmp_path: Path, qtbot):
    images = _images_with(tmp_path, ("wide.png", 800, 400), ("other.png", 200, 100))
    dialog = MarkdownEditDialog(
        markdown="![](.images/wide.png)\n\n![](.images/other.png)",
        images_dir=images,
        image_preview_width=240,
    )
    qtbot.addWidget(dialog)
    assert _image_display_sizes(dialog.text_edit) == [(240, 120), (240, 120)]
    assert "width" not in dialog.markdown
    assert "![](.images/wide.png)" in dialog.markdown
    assert "![](.images/other.png)" in dialog.markdown


def test_original_preview_setting_uses_file_pixels(tmp_path: Path, qtbot):
    images = _images_with(tmp_path, ("wide.png", 640, 480))
    dialog = MarkdownEditDialog(
        markdown="![](.images/wide.png)",
        images_dir=images,
        image_preview_width=0,
    )
    qtbot.addWidget(dialog)
    assert _image_display_sizes(dialog.text_edit) == [(640, 480)]


def test_inserted_image_uses_preview_width(tmp_path: Path, qtbot):
    images = tmp_path / IMAGES_DIR_NAME
    png = tmp_path / "shot.png"
    _write_rgb_png(png, 800, 400)
    dialog = MarkdownEditDialog(
        ensure_images_dir=lambda: images,
        image_preview_width=240,
    )
    qtbot.addWidget(dialog)
    assert dialog.insert_image_from_path(str(png))
    assert _image_display_sizes(dialog.text_edit) == [(240, 120)]
    assert dialog.markdown == "![](.images/shot.png)"


def test_resized_image_lasts_until_the_editor_closes(tmp_path: Path, qtbot, monkeypatch):
    images = _images_with(tmp_path, ("wide.png", 800, 400), ("other.png", 200, 100))
    markdown = "![](.images/wide.png)\n\n![](.images/other.png)"
    dialog = _shown_editor(
        qtbot,
        markdown=markdown,
        images_dir=images,
        image_preview_width=240,
    )
    _choose_image_size(dialog.text_edit, "wide.png", "Средняя", monkeypatch)
    _choose_image_size(dialog.text_edit, "other.png", "Ширина…", monkeypatch, chosen=120)
    assert _image_display_sizes(dialog.text_edit) == [(480, 240), (120, 60)]

    dialog.set_markdown_mode(True)
    source = dialog.source_edit.toPlainText()
    assert "width" not in source
    assert "<img" not in source
    dialog.set_markdown_mode(False)
    assert _image_display_sizes(dialog.text_edit) == [(480, 240), (120, 60)]
    assert dialog.markdown == markdown

    again = MarkdownEditDialog(
        markdown=markdown,
        images_dir=images,
        image_preview_width=240,
    )
    qtbot.addWidget(again)
    assert _image_display_sizes(again.text_edit) == [(240, 120), (240, 120)]


def test_image_menu_original_restores_file_pixels(tmp_path: Path, qtbot, monkeypatch):
    images = _images_with(tmp_path, ("wide.png", 800, 400))
    dialog = _shown_editor(
        qtbot,
        markdown="![](.images/wide.png)",
        images_dir=images,
        image_preview_width=240,
    )
    _choose_image_size(dialog.text_edit, "wide.png", "Исходная", monkeypatch)
    assert _image_display_sizes(dialog.text_edit) == [(800, 400)]
    dialog.set_markdown_mode(True)
    dialog.set_markdown_mode(False)
    assert _image_display_sizes(dialog.text_edit) == [(800, 400)]
    assert "width" not in dialog.markdown


def test_corner_drag_resizes_one_image_down_to_40(tmp_path: Path, qtbot):
    images = _images_with(tmp_path, ("wide.png", 800, 400), ("other.png", 200, 100))
    dialog = _shown_editor(
        qtbot,
        markdown="![](.images/wide.png)\n\n![](.images/other.png)",
        images_dir=images,
        image_preview_width=240,
    )
    edit = dialog.text_edit
    hit = _image_hit(edit, "wide.png")
    corner = hit.view_rect.bottomRight()
    target = QPoint(hit.view_rect.left() + 10, corner.y())
    qtbot.mousePress(edit.viewport(), Qt.MouseButton.LeftButton, pos=corner)
    qtbot.mouseMove(edit.viewport(), pos=target)
    qtbot.mouseRelease(edit.viewport(), Qt.MouseButton.LeftButton, pos=target)
    assert _image_display_sizes(edit) == [(40, 20), (240, 120)]
    assert "width" not in dialog.markdown


def test_ctrl_click_opens_the_image_file(tmp_path: Path, qtbot, monkeypatch):
    images = _images_with(tmp_path, ("wide.png", 800, 400))
    dialog = _shown_editor(
        qtbot,
        markdown="- [ ] дело\n\n![](.images/wide.png)",
        images_dir=images,
        image_preview_width=240,
    )
    opened: list[str] = []
    monkeypatch.setattr(
        "taskmanager.ui.markdown_editor.open_target",
        lambda target: opened.append(target),
    )
    hit = _image_hit(dialog.text_edit, "wide.png")
    qtbot.mouseClick(
        dialog.text_edit.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        pos=hit.view_rect.center(),
    )
    assert opened == [str((images / "wide.png").resolve())]
    assert dialog.markdown.startswith("- [ ] дело")


def test_ctrl_click_opens_a_link_in_text_mode(tmp_path: Path, qtbot, monkeypatch):
    note = tmp_path / "note.txt"
    note.write_text("hi", encoding="utf-8")
    dialog = _shown_editor(
        qtbot,
        markdown=f"[сайт](https://example.com/a)\n\nфайл",
    )
    opened: list[str] = []
    monkeypatch.setattr(
        "taskmanager.ui.markdown_editor.open_target",
        lambda target: opened.append(target),
    )
    qtbot.mouseClick(
        dialog.text_edit.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        pos=_anchor_point(dialog.text_edit, "https://example.com/a"),
    )
    assert opened == ["https://example.com/a"]

    opened.clear()
    qtbot.mouseClick(
        dialog.text_edit.viewport(),
        Qt.MouseButton.LeftButton,
        pos=_anchor_point(dialog.text_edit, "https://example.com/a"),
    )
    assert opened == []

    _select_word(dialog.text_edit, "файл")
    dialog.apply_link(note.as_uri())
    qtbot.mouseClick(
        dialog.text_edit.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        pos=_anchor_point(dialog.text_edit, note.as_uri()),
    )
    assert opened == [str(note.resolve())]

    opened.clear()
    dialog.set_markdown_mode(True)
    qtbot.mouseClick(
        dialog.source_edit.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        pos=QPoint(12, 12),
    )
    assert opened == []


def test_click_on_image_does_not_toggle_a_task(tmp_path: Path, qtbot):
    images = _images_with(tmp_path, ("wide.png", 80, 60))
    dialog = _shown_editor(
        qtbot,
        markdown="- [ ] дело\n\n![](.images/wide.png)",
        images_dir=images,
        image_preview_width=240,
    )
    edit = dialog.text_edit
    fragment = _checkbox_fragment(edit)
    assert fragment is not None
    cursor = QTextCursor(edit.document())
    cursor.setPosition(fragment.position())
    qtbot.mouseClick(
        edit.viewport(),
        Qt.MouseButton.LeftButton,
        pos=edit.cursorRect(cursor).center(),
    )
    assert dialog.markdown.startswith("- [x] дело")
    hit = _image_hit(edit, "wide.png")
    qtbot.mouseClick(
        edit.viewport(),
        Qt.MouseButton.LeftButton,
        pos=hit.view_rect.center(),
    )
    assert dialog.markdown.startswith("- [x] дело")


def test_task_dialog_passes_image_preview_width(qtbot, tmp_path: Path):
    from taskmanager.services.settings_service import IMAGE_PREVIEW_SMALL, Settings
    from taskmanager.ui.dialogs import TaskDialog

    dialog = TaskDialog(
        Settings(work_dir=str(tmp_path), image_preview_width=IMAGE_PREVIEW_SMALL)
    )
    qtbot.addWidget(dialog)
    assert dialog.description_row.image_preview_width == 240
    assert dialog.comment_row.image_preview_width == 240


def test_edit_row_opens_dialog_at_preview_width(qtbot, tmp_path: Path, monkeypatch):
    from taskmanager.ui.markdown_editor import MarkdownEditRow

    images = _images_with(tmp_path, ("wide.png", 800, 400))
    row = MarkdownEditRow(
        markdown="![](.images/wide.png)",
        locate_images_dir=lambda: images,
        image_preview_width=240,
    )
    qtbot.addWidget(row)
    seen: dict[str, object] = {}

    def fake_exec(self):
        seen["sizes"] = _image_display_sizes(self.text_edit)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(MarkdownEditDialog, "exec", fake_exec)
    button = next(
        child
        for child in row.children()
        if child.__class__.__name__ == "QPushButton"
    )
    button.click()
    assert seen["sizes"] == [(240, 120)]


def _shown_editor(qtbot, **kwargs):
    dialog = MarkdownEditDialog(**kwargs)
    qtbot.addWidget(dialog)
    dialog.resize(900, 800)
    dialog.show()
    QApplication.processEvents()
    return dialog


def _images_with(tmp_path: Path, *specs: tuple[str, int, int]) -> Path:
    images = tmp_path / IMAGES_DIR_NAME
    images.mkdir()
    for name, width, height in specs:
        _write_rgb_png(images / name, width, height)
    return images


def _write_rgb_png(path: Path, width: int, height: int) -> None:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    assert image.save(str(path), "PNG")


def _image_display_sizes(edit) -> list[tuple[int, int]]:
    sizes = []
    block = edit.document().begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.charFormat().isImageFormat():
                fmt = fragment.charFormat().toImageFormat()
                sizes.append((int(fmt.width()), int(fmt.height())))
            iterator += 1
        block = block.next()
    return sizes


def _image_hit(edit, name_suffix: str):
    for hit in edit._image_hits():
        if hit.cursor.charFormat().toImageFormat().name().endswith(name_suffix):
            return hit
    raise AssertionError(f"no image hit for {name_suffix}")


def _choose_image_size(edit, name_suffix: str, label: str, monkeypatch, chosen: int = 120):
    hit = _image_hit(edit, name_suffix)

    def fake_exec(_edit, menu, _pos):
        labels = [action.text() for action in menu.actions()]
        assert labels == ["Уменьшенная", "Средняя", "Исходная", "Ширина…"]
        if label == "Ширина…":
            monkeypatch.setattr(
                "taskmanager.ui.markdown_editor.QInputDialog.getInt",
                lambda *_a, **_k: (chosen, True),
            )
        menu.actions()[labels.index(label)].trigger()

    monkeypatch.setattr(MarkdownTextEdit, "_exec_menu", fake_exec)
    global_pos = edit.viewport().mapToGlobal(hit.view_rect.center())
    edit.contextMenuEvent(
        QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            hit.view_rect.center(),
            global_pos,
        )
    )


def _has_image(edit) -> bool:
    block = edit.document().begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.charFormat().isImageFormat():
                return True
            iterator += 1
        block = block.next()
    return False
