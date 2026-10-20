"""User-facing release notes, grouped by minor version line."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^##\s+(\d+)\.(\d+)\.(\d+)\s*$")
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class ReleaseSection:
    version: str
    major: int
    minor: int
    patch: int
    body: str


def parse_release_sections(text: str) -> list[ReleaseSection]:
    """Sections whose heading is ``## major.minor.patch``. Other text is ignored."""
    sections: list[ReleaseSection] = []
    current: tuple[int, int, int] | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        major, minor, patch = current
        sections.append(
            ReleaseSection(
                version=f"{major}.{minor}.{patch}",
                major=major,
                minor=minor,
                patch=patch,
                body="\n".join(buf).strip(),
            )
        )
        current = None

    for line in text.splitlines():
        match = _HEADING_RE.match(line.strip())
        if match:
            flush()
            current = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
            buf = []
            continue
        if current is not None:
            buf.append(line)
    flush()
    return sections


def minor_line_label(major: int, minor: int) -> str:
    return f"{major}.{minor}"


def parse_version(version: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.match(version.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def minor_line_for_version(version: str) -> str | None:
    parsed = parse_version(version)
    if parsed is None:
        return None
    return minor_line_label(parsed[0], parsed[1])


def group_minor_lines(
    sections: list[ReleaseSection],
) -> list[tuple[str, list[ReleaseSection]]]:
    """Newest minor line first. Within a line, newest patch first."""
    buckets: dict[tuple[int, int], list[ReleaseSection]] = {}
    for section in sections:
        key = (section.major, section.minor)
        buckets.setdefault(key, []).append(section)
    grouped: list[tuple[str, list[ReleaseSection]]] = []
    for key in sorted(buckets, reverse=True):
        patches = sorted(buckets[key], key=lambda section: section.patch, reverse=True)
        grouped.append((minor_line_label(*key), patches))
    return grouped


def markdown_for_line(sections: list[ReleaseSection]) -> str:
    """One minor line, newest patch on top, each patch under its own heading."""
    parts: list[str] = []
    ordered = sorted(
        sections,
        key=lambda section: (section.major, section.minor, section.patch),
        reverse=True,
    )
    for section in ordered:
        body = section.body.strip()
        if body:
            parts.append(f"## {section.version}\n\n{body}")
        else:
            parts.append(f"## {section.version}")
    return "\n\n".join(parts)


def line_has_notes(text: str, version: str) -> bool:
    label = minor_line_for_version(version)
    if label is None:
        return False
    return any(
        name == label for name, _sections in group_minor_lines(parse_release_sections(text))
    )


def should_auto_show_whats_new(last_seen: str, current: str, notes_text: str) -> bool:
    """Open once when the seen version differs and this minor line has notes."""
    if (last_seen or "").strip() == current.strip():
        return False
    return line_has_notes(notes_text, current)


def default_minor_line(
    lines: list[tuple[str, list[ReleaseSection]]],
    current: str,
) -> str | None:
    if not lines:
        return None
    wanted = minor_line_for_version(current)
    names = [name for name, _sections in lines]
    if wanted in names:
        return wanted
    return names[0]


def load_bundled_notes() -> str:
    from taskmanager.resources import whats_new_markdown

    path = whats_new_markdown()
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
