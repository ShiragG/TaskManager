"""Markdown canon for Task Description and Comment.

Stored text is markdown. Preview HTML is produced for Qt and is not written
back. Existing HTML is converted once when a database is opened.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin

_HTML_MARKER_RE = re.compile(
    r"<(?:!DOCTYPE|html|body|p|br|div|span|b|strong|i|em|u|s|del|strike|"
    r"a|img|ul|ol|li|h[1-6]|table|blockquote|pre|code|hr)\b",
    re.IGNORECASE,
)
_TASK_LINE_RE = re.compile(
    r"^([ \t]*(?:[-+*]|\d+[.)])[ \t]+\[)([ xX])(\])",
    re.MULTILINE,
)
_CHECKBOX_INPUT_RE = re.compile(
    r"<input\b[^>]*\btask-list-item-checkbox\b[^>]*>",
    re.IGNORECASE,
)
_IMG_SRC_RE = re.compile(
    r'(<img\b[^>]*?\bsrc=")([^"]+)(")',
    re.IGNORECASE,
)
_MD_SPECIAL_RE = re.compile(r"([\\`*_\[]|])")

_engine: MarkdownIt | None = None


def looks_like_html(text: str) -> bool:
    """True when text carries tags this app used to store as HTML."""
    return bool(text and _HTML_MARKER_RE.search(text))


def render_markdown(text: str) -> str:
    """GFM HTML: tables, strikethrough, task lists, and single-newline breaks."""
    if not text:
        return ""
    return _markdown_engine().render(text)


def markdown_to_plain(text: str) -> str:
    """Search/preview text: rendered markdown with markup removed."""
    if not text:
        return ""
    from taskmanager.domain import html_to_plain

    plain = html_to_plain(render_markdown(text)).replace("\ufffc", " ")
    return " ".join(plain.split())


def markdown_to_plain_with_urls(text: str) -> str:
    """Plain text plus link URLs that are not already visible."""
    if not text:
        return ""
    from taskmanager.domain import html_to_plain_with_urls

    plain = html_to_plain_with_urls(render_markdown(text)).replace("\ufffc", " ")
    return " ".join(plain.split())


def preview_html(text: str, *, images_dir: Path | None = None) -> str:
    """View-mode HTML. Checkboxes are links, not form controls.

    ``![](.images/name)`` is rewritten to a ``file:`` URL only in this HTML.
    """
    html = render_markdown(text)
    index = 0

    def checkbox(match: re.Match[str]) -> str:
        nonlocal index
        glyph = "☑" if "checked" in match.group(0).lower() else "☐"
        link = f'<a href="tm-task:{index}">{glyph}</a>'
        index += 1
        return link

    html = _CHECKBOX_INPUT_RE.sub(checkbox, html)
    if images_dir is not None:
        html = _rewrite_image_srcs(html, images_dir)
    return html


def toggle_task(text: str, index: int) -> str:
    """Flip the ``index``-th ``- [ ]`` / ``- [x]`` marker. Unknown index is a no-op."""
    matches = list(_TASK_LINE_RE.finditer(text))
    if index < 0 or index >= len(matches):
        return text
    match = matches[index]
    mark = " " if match.group(2).lower() == "x" else "x"
    return text[: match.start(2)] + mark + text[match.end(2) :]


def html_to_markdown(html: str) -> str:
    """Convert stored HTML once. Non-HTML is returned unchanged.

    Underline is dropped. ``file://`` images under ``.images/`` become
    ``![](.images/name)``.
    """
    if not looks_like_html(html):
        return html
    from PySide6.QtGui import QTextDocument

    from taskmanager.domain import ensure_qt_app

    ensure_qt_app()
    doc = QTextDocument()
    doc.setHtml(html)
    return document_to_markdown(doc)


def document_to_markdown(doc) -> str:
    """Serialize a Qt document edited as rendered markdown."""
    from PySide6.QtGui import QTextCursor

    parts: list[str] = []
    prev_kind: str | None = None
    prev_style = None
    skip_until = -1
    code_lines: list[str] | None = None
    gap = False
    block = doc.begin()

    def flush_code() -> None:
        nonlocal code_lines, prev_kind, prev_style
        if not code_lines:
            code_lines = None
            return
        while code_lines and not code_lines[-1].strip():
            code_lines.pop()
        if code_lines:
            rendered = "```\n" + "\n".join(code_lines) + "\n```"
            _append_block(parts, "code", rendered, prev_kind, prev_style, None)
            prev_kind = "code"
            prev_style = None
        code_lines = None

    while block.isValid():
        if block.position() <= skip_until:
            block = block.next()
            continue
        cursor = QTextCursor(block)
        table = cursor.currentTable()
        if table is not None:
            flush_code()
            rendered = _table_markdown(table)
            if rendered:
                _append_block(parts, "table", rendered, prev_kind, prev_style, None)
                prev_kind = "table"
                prev_style = None
                gap = False
            last = table.cellAt(table.rows() - 1, table.columns() - 1)
            skip_until = last.lastPosition()
        elif _is_horizontal_rule(block):
            flush_code()
            rendered = _horizontal_rule_markdown(block)
            _append_block(parts, "hr", rendered, prev_kind, prev_style, None, gap=gap)
            prev_kind = "hr"
            prev_style = None
            gap = False
        elif _is_fenced_code_block(block):
            text = (
                block.text()
                .replace("\u2028", "\n")
                .replace("\u2029", "\n")
                .replace("\ufffc", "")
            )
            if code_lines is None:
                code_lines = []
            code_lines.extend(text.split("\n"))
        else:
            flush_code()
            kind, rendered, style = _block_markdown(block)
            if rendered:
                _append_block(
                    parts, kind, rendered, prev_kind, prev_style, style, gap=gap
                )
                prev_kind = kind
                prev_style = style
                gap = False
            else:
                gap = True
        block = block.next()
    flush_code()
    return "".join(parts).strip("\n")


def _append_block(
    parts: list[str],
    kind: str,
    rendered: str,
    prev_kind: str | None,
    prev_style,
    style,
    gap: bool = True,
) -> None:
    if parts:
        # Splitting a task row out of a bullet list makes two styles. They stay
        # on consecutive lines unless a blank block was really between them.
        # Other style changes keep the blank line Qt's HTML import does not.
        tight_list = kind == "list" and prev_kind == "list" and (
            style == prev_style or (_task_bullet_split(style, prev_style) and not gap)
        )
        parts.append("\n" if tight_list else "\n\n")
    parts.append(rendered)


def _task_bullet_split(style, prev_style) -> bool:
    return _is_markerless_style(style) != _is_markerless_style(prev_style)


def _is_markerless_style(style) -> bool:
    if style is None:
        return False
    from PySide6.QtGui import QTextListFormat

    return style == QTextListFormat.Style.ListStyleUndefined


def _markdown_engine() -> MarkdownIt:
    global _engine
    if _engine is None:
        engine = MarkdownIt("commonmark", {"breaks": True, "html": False})
        engine.enable("table")
        engine.enable("strikethrough")
        engine.use(tasklists_plugin)
        _engine = engine
    return _engine


def _rewrite_image_srcs(html: str, images_dir: Path) -> str:
    def repl(match: re.Match[str]) -> str:
        src = unquote(match.group(2))
        relative = src[2:] if src.startswith("./") else src
        if not relative.startswith(".images/"):
            return match.group(0)
        name = relative[len(".images/") :]
        if not name or name.startswith("/") or ".." in Path(name).parts:
            return match.group(0)
        path = (images_dir / name).resolve()
        return f"{match.group(1)}{path.as_uri()}{match.group(3)}"

    return _IMG_SRC_RE.sub(repl, html)


def _block_markdown(block) -> tuple[str, str, object]:
    from PySide6.QtGui import QTextListFormat

    text_list = block.textList()
    heading = block.blockFormat().headingLevel()
    task_mark = _leading_task_mark(block) if text_list is not None else None
    inline = _inline_markdown(
        block,
        skip_checkbox=task_mark is not None,
        ignore_bold=bool(heading),
    )
    if text_list is not None:
        fmt = text_list.format()
        style = fmt.style()
        indent = max(int(fmt.indent()) - 1, 0)
        if task_mark is not None:
            marker = f"- [{task_mark}] "
        elif style == QTextListFormat.Style.ListDecimal:
            marker = f"{text_list.itemNumber(block) + 1}. "
        else:
            marker = "- "
        body = inline.replace("\n", "\n" + "  " * indent + "  ")
        return "list", f"{'  ' * indent}{marker}{body}", style
    if not inline.strip():
        return "para", "", None
    if heading:
        return "heading", f"{'#' * heading} {inline}", None
    if block.blockFormat().leftMargin() >= 20:
        quoted = "\n".join(
            f"> {line}" if line else ">" for line in inline.split("\n")
        )
        return "quote", quoted, None
    return "para", inline, None


def _is_horizontal_rule(block) -> bool:
    """Qt stores a thematic break as an empty block with a trailing ruler."""
    from PySide6.QtGui import QTextFormat

    return block.blockFormat().hasProperty(
        QTextFormat.Property.BlockTrailingHorizontalRulerWidth
    )


def _horizontal_rule_markdown(block) -> str:
    if block.blockFormat().leftMargin() >= 20:
        return "> ---"
    return "---"


def _is_fenced_code_block(block) -> bool:
    """True for a ``<pre>`` line, not for inline ``code`` in a paragraph."""
    if block.textList() is not None:
        return False
    if block.blockFormat().headingLevel():
        return False
    if block.blockFormat().leftMargin() >= 20:
        return False
    return _is_mono(block.charFormat())


def _leading_task_mark(block) -> str | None:
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid() and fragment.text().strip():
            return _task_mark(fragment.text())
        iterator += 1
    return None


def _task_mark(text: str) -> str | None:
    stripped = text.lstrip(" \t")
    if stripped.startswith("☑"):
        return "x"
    if stripped.startswith("☐"):
        return " "
    return None


def _inline_markdown(
    block,
    *,
    skip_checkbox: bool = False,
    ignore_bold: bool = False,
) -> str:
    pieces: list[str] = []
    skipping = skip_checkbox
    clip_at = _trailing_space_clip(block)
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid():
            clipped = _clip_fragment_text(fragment, clip_at)
            if not clipped:
                iterator += 1
                continue
            text_override = None
            if skipping and clipped.strip():
                rest = _without_checkbox(clipped)
                skipping = False
                if not rest:
                    iterator += 1
                    continue
                if rest != fragment.text():
                    text_override = rest
            elif clipped != fragment.text():
                text_override = clipped
            piece = _fragment_markdown(
                fragment,
                ignore_bold=ignore_bold,
                text_override=text_override,
            )
            if piece:
                if (
                    pieces
                    and piece.startswith("![")
                    and not pieces[-1].endswith(("\n", " "))
                ):
                    pieces.append("\n")
                pieces.append(piece)
        iterator += 1
    text = "".join(pieces)
    if skip_checkbox and text.startswith(" "):
        text = text[1:]
    return text.rstrip(" ")


def _trailing_space_clip(block) -> int | None:
    """Qt stores a disposable trailing space on many blocks."""
    raw = block.text()
    if raw.endswith(" ") and not raw.endswith("  "):
        return block.position() + len(raw) - 1
    return None


def _clip_fragment_text(fragment, clip_at: int | None) -> str:
    text = fragment.text()
    if clip_at is None:
        return text
    start = fragment.position()
    end = start + len(text)
    if end <= clip_at:
        return text
    if start >= clip_at:
        return ""
    return text[: clip_at - start]


def _without_checkbox(text: str) -> str:
    if _task_mark(text) is None:
        return text
    return _drop_checkbox_prefix(text)


def _drop_checkbox_prefix(text: str) -> str:
    match = re.match(r"^[ \t]*[☐☑][ \t]?", text)
    if match is None:
        return text
    return text[match.end() :]


def _fragment_markdown(
    fragment,
    *,
    ignore_bold: bool = False,
    text_override: str | None = None,
) -> str:
    fmt = fragment.charFormat()
    if text_override is None and fmt.isImageFormat():
        return _image_markdown(fmt.toImageFormat().name())
    if text_override is None:
        text = fragment.text()
    else:
        text = text_override
    text = text.replace("\u2028", "\n").replace("\u2029", "\n").replace("\ufffc", "")
    if not text:
        return ""
    if _is_mono(fmt):
        return _wrap_code(text)
    href = fmt.anchorHref() if fmt.isAnchor() else ""
    if href.startswith("tm-task:"):
        href = ""
    from PySide6.QtGui import QFont

    bold = (not ignore_bold) and fmt.fontWeight() >= int(QFont.Weight.Bold)
    italic = fmt.fontItalic()
    strike = fmt.fontStrikeOut()
    return _wrap_styled(text, bold=bold, italic=italic, strike=strike, href=href)


def _wrap_styled(
    text: str,
    *,
    bold: bool,
    italic: bool,
    strike: bool,
    href: str,
) -> str:
    lines = [_escape_inline(line) for line in text.split("\n")]
    wrapped: list[str] = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        body = line
        if strike:
            body = f"~~{body}~~"
        if bold and italic:
            body = f"***{body}***"
        elif bold:
            body = f"**{body}**"
        elif italic:
            body = f"*{body}*"
        if href:
            body = f"[{body}]({href})"
        wrapped.append(body)
    return "\n".join(wrapped)


def _wrap_code(text: str) -> str:
    if "\n" in text or "`" in text:
        fence = "```"
        while fence in text:
            fence += "`"
        return f"{fence}\n{text}\n{fence}"
    return f"`{text}`"


def _escape_inline(text: str) -> str:
    return _MD_SPECIAL_RE.sub(r"\\\1", text)


def _is_mono(fmt) -> bool:
    family = fmt.font().family().casefold()
    return "mono" in family or fmt.fontFixedPitch()


def _image_markdown(src: str) -> str:
    relative = _images_relative(src)
    if relative:
        return f"![]({relative})"
    if not src:
        return ""
    return f"![]({src})"


def _images_relative(src: str) -> str | None:
    if not src or src.lower().startswith("data:"):
        return None
    path_str = src
    if src.lower().startswith("file:"):
        try:
            path_str = str(Path.from_uri(src))
        except (ValueError, OSError):
            return None
    normalized = path_str.replace("\\", "/")
    marker = "/.images/"
    index = normalized.lower().find(marker)
    if index >= 0:
        return normalized[index + 1 :]
    if normalized.lower().startswith(".images/"):
        return normalized
    return None


def _table_markdown(table) -> str:
    from PySide6.QtGui import QTextCursor

    rows: list[str] = []
    for row_index in range(table.rows()):
        cells: list[str] = []
        for column in range(table.columns()):
            cell = table.cellAt(row_index, column)
            cursor = cell.firstCursorPosition()
            cursor.setPosition(cell.lastPosition(), QTextCursor.MoveMode.KeepAnchor)
            text = cursor.selectedText().replace("\u2029", " ").replace("\u2028", " ")
            text = text.replace("|", "\\|").strip() or " "
            cells.append(text)
        rows.append("| " + " | ".join(cells) + " |")
    if not rows:
        return ""
    separator = "| " + " | ".join("---" for _ in range(table.columns())) + " |"
    return "\n".join([rows[0], separator, *rows[1:]])
