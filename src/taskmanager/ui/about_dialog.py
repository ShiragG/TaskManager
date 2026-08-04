from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from taskmanager.version import get_version

CONTACT_EMAIL = "gulyayevsgh@mail.ru"
GITHUB_URL = "https://github.com/ShiragG/TaskManager"


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("О приложении")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)

        title = QLabel("TaskManager")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        version = QLabel(f"Версия {get_version()}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        email = QLabel(f'<a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>')
        email.setAlignment(Qt.AlignmentFlag.AlignCenter)
        email.setOpenExternalLinks(True)
        layout.addWidget(email)

        github = QLabel(f'<a href="{GITHUB_URL}">{GITHUB_URL}</a>')
        github.setAlignment(Qt.AlignmentFlag.AlignCenter)
        github.setOpenExternalLinks(True)
        layout.addWidget(github)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
