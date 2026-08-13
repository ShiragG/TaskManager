# Event sound is a file path

An Event ping plays a user-chosen sound **file** (`event_sound_path` in settings), not `QApplication.beep()` and not an OS “system sound” event. If the path is empty, the file is missing, or Qt Multimedia cannot decode it, the ping is silent — no beep fallback and no error dialog. A missing file stays stored and is marked «нет файла» in settings.

**Status:** accepted

## Alternatives rejected

- `QApplication.beep()` — often silent on Linux.
- Playing a named OS notification sound — not portable and not a stored path.
- Replacing a deleted path with another system file — would surprise the user who picked that file.
