# Event sound is a file path

An Event ping plays a user-chosen sound **file** (`event_sound_path` in settings), not `QApplication.beep()` and not an OS “system sound” event. If the path is empty, the file is missing, or Qt Multimedia cannot decode it, the ping is silent — no beep fallback and no error dialog. A missing file stays stored and is marked «нет файла» in settings.

A file picked via «Свой файл…» is **copied** into `app_dir()/sounds/` (next to the executable; in development, CWD). Settings and Event store the copy path so the ping does not depend on a USB stick or Downloads folder. The original is left in place. Name collisions get a numeric suffix (`ding_2.wav`). System folders such as `/usr/share/sounds` are never written.

**Status:** accepted

**Status:** accepted

## Alternatives rejected

- `QApplication.beep()` — often silent on Linux.
- Playing a named OS notification sound — not portable and not a stored path.
- Replacing a deleted path with another system file — would surprise the user who picked that file.
