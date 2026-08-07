from __future__ import annotations

# Canonical app version — keep in sync with pyproject.toml [project].version.
# Do not prefer importlib.metadata: a stale editable/site-packages install can
# report an older version and break update checks (e.g. missing 0.6.0→0.6.1).
_FALLBACK_VERSION = "0.6.5"


def get_version() -> str:
    """Return the application version baked into this module."""
    return _FALLBACK_VERSION
