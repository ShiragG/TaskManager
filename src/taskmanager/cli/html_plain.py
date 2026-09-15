from __future__ import annotations

import re
from html import escape, unescape
from pathlib import Path

from taskmanager.domain import html_to_plain

_IMG_SRC_RE = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"'][^>]*/?\s*>",
    re.IGNORECASE | re.DOTALL,
)


def html_to_cli_plain(html: str) -> str:
    """Plain CLI preview of Description/Comment HTML.

    Inline ``<img>`` becomes ``[image: abs-path]`` for ``file://`` / disk
    paths, or ``[image]`` for data/http and anything without a local file.
    Does not write or download files. JSON HTML fields are left to the caller.
    """
    if not html:
        return ""
    replaced = _IMG_SRC_RE.sub(_replace_img, html)
    plain = html_to_plain(replaced)
    return plain.replace("\ufffc", "[image]")


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
