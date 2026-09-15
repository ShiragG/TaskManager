#!/usr/bin/env python3
"""Build the GitHub Releases bootstrap executable from dist/TaskManager-onedir.

The published asset name stays TaskManager / TaskManager.exe. That file is a
onefile bootstrap: it unpacks the onedir payload beside itself, then a helper
replaces the bootstrap with the onedir loader and relaunches with the same
argv. Run on the target OS after TaskManager.spec (onedir) has been built.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    os.chdir(ROOT)
    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from taskmanager.bootstrap import (
        ONEDIR_DIST_NAME,
        PAYLOAD_ZIP_NAME,
        BootstrapError,
        render_bootstrap_spec,
        write_onedir_payload_zip,
    )

    dist = ROOT / "dist"
    onedir = dist / ONEDIR_DIST_NAME
    if not onedir.is_dir():
        print(
            f"Missing {onedir}. Build the onedir first:\n"
            "  uv run pyinstaller --noconfirm TaskManager.spec",
            file=sys.stderr,
        )
        return 1

    build = ROOT / "build"
    build.mkdir(parents=True, exist_ok=True)
    payload = build / PAYLOAD_ZIP_NAME
    try:
        write_onedir_payload_zip(onedir, payload)
    except BootstrapError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    spec_path = build / "TaskManager-bootstrap.spec"
    spec_path.write_text(
        render_bootstrap_spec(
            payload_zip=payload,
            entry=ROOT / "src" / "taskmanager" / "bootstrap_main.py",
            icon=ROOT / "src" / "taskmanager" / "resources" / "app_icon.ico",
        ),
        encoding="utf-8",
    )

    import PyInstaller.__main__

    PyInstaller.__main__.run(
        [
            "--noconfirm",
            f"--distpath={dist}",
            f"--workpath={build / 'bootstrap'}",
            str(spec_path),
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
