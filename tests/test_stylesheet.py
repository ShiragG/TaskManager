from pathlib import Path

from taskmanager.ui.styles.embedded import STYLESHEETS
from taskmanager.ui.stylesheet import load_stylesheet, resolve_theme_mode


def test_embedded_matches_qss_files():
    styles_dir = Path(__file__).resolve().parents[1] / "src" / "taskmanager" / "ui" / "styles"
    for name in ("app.qss", "app_dark.qss"):
        on_disk = (styles_dir / name).read_text(encoding="utf-8")
        assert STYLESHEETS[name] == on_disk


def test_load_stylesheet_returns_nonempty(qapp):
    qss, source = load_stylesheet("app.qss")
    assert qss
    assert "QWidget" in qss
    assert source

    dark, dark_source = load_stylesheet("app_dark.qss")
    assert dark
    assert dark_source


def test_resolve_theme_mode_light_dark(qapp):
    assert resolve_theme_mode("light") == "light"
    assert resolve_theme_mode("dark") == "dark"
