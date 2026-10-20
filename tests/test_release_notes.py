"""Release-note grouping and the bundled user-facing file."""

from pathlib import Path

from taskmanager.services.release_notes import (
    default_minor_line,
    group_minor_lines,
    line_has_notes,
    load_bundled_notes,
    markdown_for_line,
    parse_release_sections,
    should_auto_show_whats_new,
)
from taskmanager.version import get_version

_NOTES = """
# ignored title

## 0.10.1

- старая линейка

## 0.11.0

- база

## 0.11.3

- патч

## not-a-version

- skip
"""


def test_minor_lines_put_newest_patch_first():
    lines = group_minor_lines(parse_release_sections(_NOTES))
    assert [name for name, _sections in lines] == ["0.11", "0.10"]
    assert [section.version for section in lines[0][1]] == ["0.11.3", "0.11.0"]
    rendered = markdown_for_line(lines[0][1])
    assert rendered.index("## 0.11.3") < rendered.index("## 0.11.0")
    assert "0.10.1" not in rendered
    assert default_minor_line(lines, "0.11.2") == "0.11"
    assert default_minor_line(lines, "0.12.0") == "0.11"


def test_auto_show_only_for_unseen_version_with_notes():
    assert should_auto_show_whats_new("", "0.11.3", _NOTES) is True
    assert should_auto_show_whats_new("0.10.8", "0.11.3", _NOTES) is True
    assert should_auto_show_whats_new("0.11.3", "0.11.3", _NOTES) is False
    assert should_auto_show_whats_new(" 0.11.3 ", "0.11.3", _NOTES) is False
    assert should_auto_show_whats_new("", "0.12.0", _NOTES) is False
    assert should_auto_show_whats_new("", "beta", _NOTES) is False
    assert line_has_notes(_NOTES, "0.11.3") is True
    assert line_has_notes(_NOTES, "0.9.1") is False


def test_bundled_notes_match_current_minor_and_ship_with_the_app():
    version = get_version()
    text = load_bundled_notes()
    assert f"## {version}" in text
    assert line_has_notes(text, version) is True
    assert "src/" not in text
    assert ".py" not in text
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    spec = (root / "TaskManager.spec").read_text(encoding="utf-8")
    assert 'whats_new.md" = "taskmanager/resources/whats_new.md"' in pyproject
    assert "src/taskmanager/resources/whats_new.md" in spec
    rule = (root / ".cursor/rules/release-notes.mdc").read_text(encoding="utf-8")
    assert "alwaysApply: true" in rule
