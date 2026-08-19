"""Extract inline image dumps from Description/Comment HTML into the task folder.

Hex/base64 dumps and ``data:`` URIs are host concerns (not SourceDraft.files).
Validated by magic bytes (PNG, JPEG, GIF, WebP); written as ``{sha256}.{ext}``
under ``.images/`` inside the task folder.
"""

from __future__ import annotations

import base64
import hashlib
import html
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from taskmanager.services.task_service import TaskService

_SEP = r"(?:\s|<br\s*/?>|&nbsp;)*"
_HEX_PAIR = r"[0-9A-Fa-f]{2}"
_B64_CHAR = r"[A-Za-z0-9+/]"

# 1x1 PNG is ~67 bytes; keep a floor so short magic-looking runs are ignored.
_MIN_IMAGE_BYTES = 24
IMAGES_DIR_NAME = ".images"

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_GIF87_MAGIC = b"GIF87a"
_GIF89_MAGIC = b"GIF89a"


def sniff_image(data: bytes) -> str | None:
    """Return ``png`` / ``jpeg`` / ``gif`` / ``webp`` from magic bytes, else None."""
    if len(data) < _MIN_IMAGE_BYTES:
        return None
    if data.startswith(_PNG_MAGIC):
        return "png"
    if data.startswith(_JPEG_MAGIC):
        return "jpeg"
    if data.startswith(_GIF87_MAGIC) or data.startswith(_GIF89_MAGIC):
        return "gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _hex_magic_re(magic: bytes) -> str:
    return _SEP.join(f"{byte:02x}" for byte in magic)


_HEX_TAIL = rf"(?:{_SEP}{_HEX_PAIR})*"

_HEX_DUMP_RE = re.compile(
    "|".join(
        (
            _hex_magic_re(_PNG_MAGIC) + _HEX_TAIL,
            _hex_magic_re(_JPEG_MAGIC) + _HEX_TAIL,
            _hex_magic_re(_GIF87_MAGIC) + _HEX_TAIL,
            _hex_magic_re(_GIF89_MAGIC) + _HEX_TAIL,
            # RIFF....WEBP
            _hex_magic_re(b"RIFF")
            + rf"(?:{_SEP}{_HEX_PAIR}){{4}}"
            + _SEP
            + _hex_magic_re(b"WEBP")
            + _HEX_TAIL,
        )
    ),
    re.IGNORECASE,
)

_B64_TAIL = rf"(?:{_SEP}{_B64_CHAR})*(?:{_SEP}={_SEP}={{0,2}})?"

_B64_DUMP_RE = re.compile(
    "|".join(
        (
            r"iVBORw0KGgo" + _B64_TAIL,  # PNG
            r"/9j/" + _B64_TAIL,  # JPEG
            r"R0lGOD" + _B64_TAIL,  # GIF
            r"UklGR" + _B64_TAIL,  # RIFF / WebP
        )
    ),
)

_IMG_DATA_RE = re.compile(
    r"(<a\b[^>]*>\s*)?<img\b[^>]*?\bsrc\s*=\s*[\"']"
    r"(data:image/(?:png|jpe?g|gif|webp);base64,[A-Za-z0-9+/=\s]+)"
    r"[\"'][^>]*/?\s*>(\s*</a>)?",
    re.IGNORECASE | re.DOTALL,
)

_RAW_DATA_RE = re.compile(
    r"data:image/(?:png|jpe?g|gif|webp);base64,([A-Za-z0-9+/=\s]+)",
    re.IGNORECASE,
)

_BARE_FILE_IMG_RE = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*[\"'](file:[^\"']+)[\"'][^>]*/?\s*>",
    re.IGNORECASE | re.DOTALL,
)


def _strip_markup_seps(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"&nbsp;", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", "", text)


def _decode_hex_dump(text: str) -> bytes | None:
    cleaned = _strip_markup_seps(text)
    if len(cleaned) % 2:
        cleaned = cleaned[:-1]
    if not cleaned or not re.fullmatch(r"[0-9A-Fa-f]+", cleaned):
        return None
    try:
        return bytes.fromhex(cleaned)
    except ValueError:
        return None


def _decode_b64_dump(text: str) -> bytes | None:
    cleaned = _strip_markup_seps(text)
    if not cleaned:
        return None
    try:
        return base64.b64decode(cleaned, validate=False)
    except Exception:
        return None


def _payload_from_data_uri(uri: str) -> bytes | None:
    comma = uri.find(",")
    if comma < 0:
        return None
    return _decode_b64_dump(uri[comma + 1 :])


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _preview_markup(
    uri: str, *, width: str | None = None, height: str | None = None
) -> str:
    escaped = html.escape(uri, quote=True)
    attrs = [f'src="{escaped}"']
    if width:
        attrs.append(f'width="{html.escape(str(width), quote=True)}"')
    if height:
        attrs.append(f'height="{html.escape(str(height), quote=True)}"')
    return f'<a href="{escaped}"><img {" ".join(attrs)}></a>'


def _write_image(dest_dir: Path, data: bytes, ext: str) -> tuple[str, str]:
    digest = hashlib.sha256(data).hexdigest()
    name = f"{digest}.{ext}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / name
    path.write_bytes(data)
    return name, _file_uri(path)


def _occupied(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    for a, b in spans:
        if start < b and end > a:
            return True
    return False


def iter_inline_image_blobs(html_text: str) -> list[tuple[int, int, bytes]]:
    """Return (start, end, image_bytes) spans to replace, left-to-right, no overlap."""
    if not html_text:
        return []
    found: list[tuple[int, int, bytes]] = []
    occupied: list[tuple[int, int]] = []

    def add(start: int, end: int, data: bytes) -> None:
        if _occupied(occupied, start, end):
            return
        if sniff_image(data) is None:
            return
        occupied.append((start, end))
        found.append((start, end, data))

    for match in _IMG_DATA_RE.finditer(html_text):
        data = _payload_from_data_uri(match.group(2))
        if data is not None:
            add(match.start(), match.end(), data)

    for match in _RAW_DATA_RE.finditer(html_text):
        data = _decode_b64_dump(match.group(1))
        if data is not None:
            add(match.start(), match.end(), data)

    for match in _HEX_DUMP_RE.finditer(html_text):
        data = _decode_hex_dump(match.group(0))
        if data is not None:
            add(match.start(), match.end(), data)

    for match in _B64_DUMP_RE.finditer(html_text):
        data = _decode_b64_dump(match.group(0))
        if data is not None:
            add(match.start(), match.end(), data)

    found.sort(key=lambda item: item[0])
    return found


_IMG_WIDTH_RE = re.compile(
    r"<img\b[^>]*?\bwidth\s*=\s*[\"']?(\d+)", re.IGNORECASE | re.DOTALL
)
_IMG_HEIGHT_RE = re.compile(
    r"<img\b[^>]*?\bheight\s*=\s*[\"']?(\d+)", re.IGNORECASE | re.DOTALL
)
_IMG_STYLE_WIDTH_RE = re.compile(
    r"<img\b[^>]*?\bstyle\s*=\s*[\"'][^\"']*?\bwidth\s*:\s*(\d+)px",
    re.IGNORECASE | re.DOTALL,
)
_IMG_STYLE_HEIGHT_RE = re.compile(
    r"<img\b[^>]*?\bstyle\s*=\s*[\"'][^\"']*?\bheight\s*:\s*(\d+)px",
    re.IGNORECASE | re.DOTALL,
)


def _img_size_attrs(markup: str) -> tuple[str | None, str | None]:
    width_match = _IMG_WIDTH_RE.search(markup) or _IMG_STYLE_WIDTH_RE.search(markup)
    height_match = _IMG_HEIGHT_RE.search(markup) or _IMG_STYLE_HEIGHT_RE.search(markup)
    width = width_match.group(1) if width_match else None
    height = height_match.group(1) if height_match else None
    return width, height


def html_has_extractable_images(html_text: str) -> bool:
    return bool(iter_inline_image_blobs(html_text))


def apply_inline_images(html_text: str, dest_dir: Path) -> tuple[str, list[str]]:
    """Write hash-named image files and substitute ``<a><img>`` previews.

    ``dest_dir`` is created if missing. Existing files with the same hash are
    overwritten. Orphan hash files are never deleted.
    """
    if not html_text:
        return html_text, []
    blobs = iter_inline_image_blobs(html_text)
    if not blobs:
        return _ensure_file_img_anchors(html_text), []

    written: list[str] = []
    pieces: list[str] = []
    last = 0
    for start, end, data in blobs:
        ext = sniff_image(data)
        if ext is None:
            continue
        name, uri = _write_image(dest_dir, data, ext)
        written.append(name)
        pieces.append(html_text[last:start])
        width, height = _img_size_attrs(html_text[start:end])
        pieces.append(_preview_markup(uri, width=width, height=height))
        last = end
    pieces.append(html_text[last:])
    return _ensure_file_img_anchors("".join(pieces)), written


def _ensure_file_img_anchors(html_text: str) -> str:
    """Wrap bare ``<img src="file://...">`` in ``<a href="file://...">``."""

    def repl(match: re.Match[str]) -> str:
        start = match.start()
        prefix = html_text[max(0, start - 160) : start]
        if re.search(r"<a\b[^>]*>\s*$", prefix, flags=re.IGNORECASE | re.DOTALL):
            return match.group(0)
        src = match.group(1)
        return f'<a href="{src}">{match.group(0)}</a>'

    return _BARE_FILE_IMG_RE.sub(repl, html_text)


def apply_inline_images_for_task(
    task_service: TaskService, task_id: int, html_text: str
) -> str:
    """Create the task folder if needed, write image files, return substituted HTML."""
    if not html_text or not html_has_extractable_images(html_text):
        return html_text
    task = task_service.get_task(task_id)
    if not task.has_folder:
        task_service.recreate_task_folder(task_id)
    dest = task_service.task_folder_path(task_id) / IMAGES_DIR_NAME
    new_html, _written = apply_inline_images(html_text, dest)
    return new_html
