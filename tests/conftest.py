"""Pytest bootstrap for TaskManager.

Qt GUI tests (pytest-qt) abort without a platform plugin when DISPLAY is
unavailable — common when an agent runs pytest inside Cursor/Chromium.
"""

from __future__ import annotations

import os

# Must be set before any QApplication / pytest-qt fixture creates Qt.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
