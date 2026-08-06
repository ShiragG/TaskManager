from __future__ import annotations

from importlib import metadata

# Keep in sync with pyproject.toml [project].version for frozen/editable fallbacks.
_FALLBACK_VERSION = "0.6.2"


def get_version() -> str:
    """Return package version from metadata, with fallbacks for editable/frozen runs."""
    try:
        return metadata.version("taskmanager")
    except metadata.PackageNotFoundError:
        return _FALLBACK_VERSION
