"""Host ↔ Source module contract (structural; modules must not import taskmanager)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# Major API version supported by this TaskManager build.
SUPPORTED_API_MAJOR = 1


@dataclass(frozen=True)
class SourceItemSummary:
    external_id: str
    title: str
    status: str = ""
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceFileMeta:
    file_id: str
    name: str


@dataclass(frozen=True)
class SourceDraft:
    """Mapped snapshot for Import / Refresh (Comment is never included)."""

    external_id: str
    number: str
    description: str
    priority: int
    links: list[tuple[str, str]] = field(default_factory=list)
    files: list[SourceFileMeta] = field(default_factory=list)
    source_label: str = ""
    source_status_id: str = ""
    source_status_label: str = ""


@dataclass(frozen=True)
class SourceListPage:
    items: list[SourceItemSummary]
    page: int
    has_more: bool = False
    total: int | None = None


@dataclass(frozen=True)
class SourceStatusOption:
    """Catalog entry for Import status filters."""

    id: str
    label: str
    default_selected: bool = False


@dataclass(frozen=True)
class SourcePriorityOption:
    """Catalog entry; mapped_priority is already on the Task Priority scale (0..10)."""

    id: str
    label: str
    mapped_priority: int


@dataclass(frozen=True)
class SourceUpdateChannel:
    """How the host finds later release assets (github_repo is in the registry)."""

    asset_name: str = ""
    asset_pattern: str = ""


class SourceModuleError(Exception):
    """Error from a Source module suitable for UI + log (host must not crash)."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


@runtime_checkable
class SourceModule(Protocol):
    """Surface expected from a loaded plugin class instance."""

    @property
    def id(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    @property
    def version(self) -> str: ...

    @property
    def api_version(self) -> str: ...

    def configure(self, *, login: str, password: str) -> None:
        """Provide credentials; JWT is kept in module memory for the session."""
        ...

    def list_statuses(self) -> list[SourceStatusOption]: ...

    def list_priorities(self) -> list[SourcePriorityOption]: ...

    def list_items(
        self,
        page: int = 1,
        status_filters: list[str] | None = None,
    ) -> SourceListPage: ...

    def get_item(self, external_id: str) -> SourceDraft: ...

    def download_files(
        self,
        external_id: str,
        dest_dir: str,
        existing_names: list[str] | None = None,
    ) -> list[str]:
        """Download missing files into dest_dir; return saved file names."""
        ...


def parse_api_major(api_version: str) -> int:
    text = (api_version or "").strip()
    if not text:
        raise SourceModuleError("plugin.json: пустой api_version")
    major_part = text.split(".", 1)[0]
    if not major_part.isdigit():
        raise SourceModuleError(f"Некорректный api_version: {api_version!r}")
    return int(major_part)


def api_version_supported(api_version: str) -> bool:
    return parse_api_major(api_version) == SUPPORTED_API_MAJOR
