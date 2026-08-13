"""Play an Event sound file. Missing file or codec/plugin failure is silence."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect
except ImportError:  # pragma: no cover - Qt Multimedia not installed
    QAudioOutput = None  # type: ignore[misc, assignment]
    QMediaPlayer = None  # type: ignore[misc, assignment]
    QSoundEffect = None  # type: ignore[misc, assignment]


class EventSoundPlayer:
    """Play a short local file. Returns False when nothing is audible."""

    def __init__(self, parent=None) -> None:
        self._parent = parent
        self._player: QMediaPlayer | None = None
        self._output: QAudioOutput | None = None
        self._effect: QSoundEffect | None = None

    def play(self, path: str) -> bool:
        if not path:
            return False
        file_path = Path(path)
        if not file_path.is_file():
            return False
        try:
            return self._play_file(file_path)
        except Exception:
            return False

    def _play_file(self, file_path: Path) -> bool:
        url = QUrl.fromLocalFile(str(file_path.resolve()))
        if file_path.suffix.lower() == ".wav" and self._play_effect(url):
            return True
        return self._play_media(url)

    def _play_effect(self, url: QUrl) -> bool:
        if QSoundEffect is None:
            return False
        effect = QSoundEffect(self._parent)
        effect.setSource(url)
        if effect.status() == QSoundEffect.Status.Error:
            return False
        effect.play()
        self._effect = effect
        return True

    def _play_media(self, url: QUrl) -> bool:
        if QMediaPlayer is None or QAudioOutput is None:
            return False
        player = QMediaPlayer(self._parent)
        output = QAudioOutput(self._parent)
        player.setAudioOutput(output)
        player.setSource(url)
        player.play()
        self._player = player
        self._output = output
        return True
