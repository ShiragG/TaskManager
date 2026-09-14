from __future__ import annotations

import json
import sys
from typing import Any, Mapping, Sequence


def normalize_text(value: str) -> str:
    """Rstrip each line and drop trailing empty lines; keep inner blank lines."""
    lines = [line.rstrip() for line in value.splitlines()]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def normalize_json_data(data: Any) -> Any:
    if isinstance(data, str):
        return normalize_text(data)
    if isinstance(data, Mapping):
        return {key: normalize_json_data(value) for key, value in data.items()}
    if isinstance(data, list):
        return [normalize_json_data(item) for item in data]
    return data


def emit_stdout(text: str) -> None:
    text = normalize_text(text)
    if text:
        print(text)


def emit_error(
    message: str,
    *,
    code: str,
    json_mode: bool,
    usage: str = "",
    exit_code: int = 1,
) -> int:
    if json_mode:
        print(
            json.dumps({"error": message, "code": code}, ensure_ascii=False),
            file=sys.stderr,
        )
    else:
        if usage:
            sys.stderr.write(usage if usage.endswith("\n") else usage + "\n")
        print(message, file=sys.stderr)
    return exit_code


def emit_json(data: Any) -> None:
    emit_stdout(json.dumps(normalize_json_data(data), ensure_ascii=False, indent=2))


def emit_json_value(value: Any) -> None:
    emit_stdout(json.dumps(normalize_json_data(value), ensure_ascii=False))


def format_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> str:
    str_rows = [[_cell(value) for value in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in str_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def fmt(row: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    lines = [fmt(list(headers))]
    lines.extend(fmt(row) for row in str_rows)
    return normalize_text("\n".join(lines))


def emit_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    json_mode: bool,
    json_rows: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    if json_mode:
        emit_json(list(json_rows) if json_rows is not None else [])
        return
    emit_stdout(format_table(headers, rows))


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
