from pathlib import Path

from taskmanager.version import _FALLBACK_VERSION, get_version


def test_get_version_is_nonempty():
    version = get_version()
    assert version
    assert version[0].isdigit()


def test_get_version_matches_fallback():
    assert get_version() == _FALLBACK_VERSION


def test_fallback_synced_with_pyproject():
    text = Path(__file__).resolve().parents[1].joinpath("pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert f'version = "{_FALLBACK_VERSION}"' in text
