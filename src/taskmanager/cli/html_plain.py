from __future__ import annotations

import hashlib
import re
from html import escape, unescape
from pathlib import Path

from taskmanager.domain import html_to_plain
from taskmanager.services.inline_images import iter_inline_image_blobs, sniff_image

_IMG_SRC_RE = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"'][^>]*/?\s*>",
    re.IGNORECASE | re.DOTALL,
)


def html_for_cli(html: str, *, images_dir: Path | None = None) -> str:
    """CLI JSON Description/Comment: hex/base64/data dumps become markers.

    Looks up ``{images_dir}/{sha256}.{ext}`` when that file already exists.
    Does not write or download files. ``file://`` ``<img>`` tags are left
    for ``html_to_cli_plain``.
    """
    if not html:
        return html
    blobs = iter_inline_image_blobs(html)
    if not blobs:
        return html
    pieces: list[str] = []
    last = 0
    for start, end, data in blobs:
        pieces.append(html[last:start])
        pieces.append(f" {escape(_blob_marker(data, images_dir))} ")
        last = end
    pieces.append(html[last:])
    return "".join(pieces)


def html_to_cli_plain(html: str, *, images_dir: Path | None = None) -> str:
    """Plain CLI preview of Description/Comment HTML.

    Inline dumps and ``<img>`` become ``[image: abs-path]`` when a file is
    already on disk, or ``[image]`` otherwise. Does not write or download
    files.
    """
    if not html:
        return ""
    replaced = html_for_cli(html, images_dir=images_dir)
    replaced = _IMG_SRC_RE.sub(_replace_img, replaced)
    plain = html_to_plain(replaced)
    return plain.replace("\ufffc", "[image]")


def _blob_marker(data: bytes, images_dir: Path | None) -> str:
    path = _existing_hashed_image(data, images_dir)
    if path is not None:
        return f"[image: {path}]"
    return "[image]"


def _existing_hashed_image(data: bytes, images_dir: Path | None) -> str | None:
    if images_dir is None:
        return None
    ext = sniff_image(data)
    if ext is None:
        return None
    candidate = images_dir / f"{hashlib.sha256(data).hexdigest()}.{ext}"
    if candidate.is_file():
        return str(candidate.resolve())
    return None


def _replace_img(match: re.Match[str]) -> str:
    src = unescape(match.group(1).strip())
    return f" {escape(_image_marker(src))} "


def _image_marker(src: str) -> str:
    path = _disk_path_from_src(src)
    if path is not None:
        return f"[image: {path}]"
    return "[image]"


def _disk_path_from_src(src: str) -> str | None:
    if not src:
        return None
    lower = src.lower()
    if lower.startswith(("data:", "http://", "https://")):
        return None
    if lower.startswith("file:"):
        try:
            return str(Path.from_uri(src).resolve())
        except (ValueError, OSError):
            return None
    path = Path(src)
    if path.is_absolute():
        return str(path.resolve())
    return None
