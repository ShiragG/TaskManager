# Source files in a `files/` subfolder

Downloaded Source files go in `{task folder}/files/`, not the task folder root (which already holds Notes.txt, template copies, and `.images/`). We do not migrate older downloads left in the root, and Refresh from source does not download or refresh those files — Import (when the download option is on) and the explicit «Скачать файлы источника…» action do.

**Status:** accepted

## Considered Options

- **Task folder root** — mixes Source files with Notes, template leftovers, and images; `existing_names` would skip a download when a same-named file already sits in the root.
- **Migrate existing root files into `files/`** — surprising for users who placed things there; old names would then block new downloads.
- **Download on Refresh from source** — would overwrite or duplicate local copies the user may have edited.

## Consequences

- A file already in the task folder root is ignored for `existing_names` and is not moved; a later manual download writes into `files/`.
- The «Файлы» button in Description opens `files/` only and stays disabled if that folder is missing or empty.
