from __future__ import annotations

"""Command-line interface: parse argv, print, map errors. Mutations go through TaskService."""

from taskmanager.cli.app import run_cli
from taskmanager.cli.console import attach_parent_console

__all__ = ["attach_parent_console", "run_cli"]
