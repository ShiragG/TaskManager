# Event text is markdown without images

Event text was HTML from the Qt rich-text editor. Description and Comment had already moved to markdown (ADR 0017) and left the calendar on that editor, so Event text stayed a widget format: underline could not round-trip, and pictures were embedded in the record. Event text is now markdown in the same column, edited with the same editor as Description and Comment, and pictures are not part of it.

An Event is not a Task body. It may have no Task and has no folder of its own, so it cannot own the `.images` directory Description uses. Embedding pictures would keep a second store inside the calendar record.

**Status:** accepted

## Alternatives rejected

- Keep HTML for Event text — the calendar would stay on Qt's serialization after Description and Comment had left it.
- Allow images the same way as Description — that needs a Task folder, and an Event may have none. Data URIs would keep the pictures inside the Event.

## Consequences

- Opening a database converts existing Event HTML once, with the same conversion as Description and Comment. Underline is dropped. Embedded images are dropped.
- The change is hard to reverse: the original HTML is gone, and a return to HTML would lose markup again.
- Lists show plain text. The Event card and the ping popup show rendered markdown, not the stored HTML.
