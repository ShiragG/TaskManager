"""Play an Event sound file. Missing file or codec/plugin failure is silence."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect
except ImportError:  # pragma: no cover - Qt Multimedia not installed
    QAudioOutput = None  # type: ignore[misc, assignment]
    QMediaPlayer = None  # type: ignore[misc, assignment]
    QSoundEffect = None  # type: ignore[misc, assignment]


class EventSoundPlayer(QObject):
    """Play a short local file. Returns False when nothing is audible."""

    finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._player: QMediaPlayer | None = None
        self._output: QAudioOutput | None = None
        self._effect: QSoundEffect | None = None
        self._ignore_finished = False

    def stop(self) -> None:
        self._ignore_finished = True
        try:
            if self._effect is not None:
                self._effect.stop()
            if self._player is not None:
                self._player.stop()
        finally:
            self._ignore_finished = False

    def play(self, path: str) -> bool:
        self.stop()
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
        effect = QSoundEffect(self)
        effect.setSource(url)
        if effect.status() == QSoundEffect.Status.Error:
            return False
        effect.playingChanged.connect(self._on_effect_playing_changed)
        effect.play()
        self._effect = effect
        return True

    def _play_media(self, url: QUrl) -> bool:
        if QMediaPlayer is None or QAudioOutput is None:
            return False
        player = QMediaPlayer(self)
        output = QAudioOutput(self)
        player.setAudioOutput(output)
        player.setSource(url)
        player.mediaStatusChanged.connect(self._on_media_status)
        player.play()
        self._player = player
        self._output = output
        return True

    def _on_effect_playing_changed(self) -> None:
        if self._ignore_finished or self._effect is None:
            return
        if not self._effect.isPlaying():
            self.finished.emit()

    def _on_media_status(self, status: object) -> None:
        if self._ignore_finished or QMediaPlayer is None:
            return
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.finished.emit()
