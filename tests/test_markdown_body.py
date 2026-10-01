import os
import subprocess
import sys
from pathlib import Path

from taskmanager.domain.markdown_body import (
    html_to_markdown,
    looks_like_html,
    markdown_to_plain,
    markdown_to_plain_with_urls,
    preview_html,
    render_markdown,
    toggle_task,
)


def test_render_gfm_breaks_table_strike_and_task_list():
    html = render_markdown(
        "one\ntwo\n\n~~no~~\n\n- [ ] open\n- [x] shut\n\n| a | b |\n| --- | --- |\n| 1 | 2 |"
    )
    assert "<br" in html
    assert "<s>no</s>" in html
    assert 'type="checkbox"' in html
    assert "<table>" in html
    assert "<td>1</td>" in html


def test_plain_strips_markup_and_keeps_link_url():
    assert markdown_to_plain("**visible** word") == "visible word"
    assert (
        markdown_to_plain_with_urls("[Hello](https://example.com)")
        == "Hello https://example.com"
    )


def test_preview_checkbox_is_a_link_and_image_src_is_local():
    images = Path("/tmp/task/.images")
    html = preview_html("- [ ] todo\n\n![](.images/shot.png)", images_dir=images)
    assert "<input" not in html
    assert 'href="tm-task:0"' in html
    assert "☐" in html
    uri = images.joinpath("shot.png").resolve().as_uri()
    assert f'src="{uri}"' in html
    assert 'src=".images/shot.png"' not in html


def test_toggle_task_flips_nth_marker():
    source = "- [ ] one\n- [x] two\n- [ ] three"
    once = toggle_task(source, 0)
    assert once.splitlines()[0] == "- [x] one"
    assert once.splitlines()[1] == "- [x] two"
    back = toggle_task(once, 1)
    assert back.splitlines()[1] == "- [ ] two"
    assert toggle_task(source, 9) == source


def test_html_migration_keeps_markdown_formatting_and_drops_underline():
    html = (
        "<p>Hello <b>bold</b> <i>it</i> <u>under</u></p>"
        "<p>line<br>next</p>"
        '<p><a href="https://example.com">Hello</a></p>'
    )
    markdown = html_to_markdown(html)
    assert "**bold**" in markdown
    assert "*it*" in markdown
    assert "under" in markdown
    assert "<u>" not in markdown
    assert "line\nnext" in markdown
    assert "[Hello](https://example.com)" in markdown
    assert markdown_to_plain(markdown) == "Hello bold it under line next Hello"


def test_html_image_under_images_dir_becomes_relative_link():
    uri = Path("/tmp/task/.images/hash.png").resolve().as_uri()
    html = f'<p>see</p><a href="{uri}"><img src="{uri}"></a>'
    markdown = html_to_markdown(html)
    assert markdown.startswith("see")
    assert "![](.images/hash.png)" in markdown
    assert "file:" not in markdown
    assert "<img" not in markdown


def test_preview_round_trip_keeps_text_formatting(qapp):
    samples = (
        "**жирный** и *курсив* и ~~нет~~ и `код`",
        "**жирный**\n\n- [ ] дело",
        "# Заголовок",
        "## Второй",
        "# *курсив*",
        "> цитата с **жирным**",
        "- один\n- два\n\n1. a\n2. b",
        "- [ ] дело\n- [x] готово",
        "- [ ] a\n  - [x] nested",
        "```\nline1\nline2\n```",
        "`inline`",
        "[ссылка](https://example.com)",
        "строка\nещё",
        "| a | b |\n| --- | --- |\n| 1 | 2 |",
        "---",
        "before\n\n---\n\nafter",
        "> ---",
        "```\n---\n```",
    )
    for source in samples:
        assert html_to_markdown(preview_html(source)) == source


def test_horizontal_rule_round_trips_and_other_markers_become_dashes(qapp):
    assert html_to_markdown(preview_html("---")) == "---"
    assert html_to_markdown(preview_html("***")) == "---"
    assert html_to_markdown(preview_html("___")) == "---"
    assert html_to_markdown(preview_html("before\n\n---\n\nafter")) == (
        "before\n\n---\n\nafter"
    )
    assert html_to_markdown("<p>a</p><hr /><p>b</p>") == "a\n\n---\n\nb"
    assert html_to_markdown(preview_html("Title\n---\n")) == "## Title"
    migrated = html_to_markdown("<p><u>under</u></p><hr>")
    assert "<u>" not in migrated
    assert migrated == "under\n\n---"


def test_html_round_trip_does_not_crash_without_a_qt_app():
    """setHtml segfaults the process when pytest did not create QApplication."""
    script = (
        "from taskmanager.domain.markdown_body import html_to_markdown, preview_html\n"
        "source = '**жирный** и *курсив* и `код`'\n"
        "assert html_to_markdown(preview_html(source)) == source\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr


def test_plain_text_is_not_treated_as_html():
    assert looks_like_html("hello") is False
    assert html_to_markdown("**already**") == "**already**"
    assert html_to_markdown("see <file>") == "see <file>"
