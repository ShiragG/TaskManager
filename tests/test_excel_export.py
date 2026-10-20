from datetime import date
from pathlib import Path

from taskmanager.infrastructure.filesystem import TaskFilesystem
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.excel_export import HEADERS, export_tasks_to_excel
from taskmanager.services.settings_service import Settings
from taskmanager.services.task_service import CreateTaskRequest, TaskService


def test_export_excel(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(
        work_dir=str(work),
        warning_color="#ff0000",
        highlight_warnings=True,
        warning_lead_days=1,
    )
    repo = SqliteRepository(tmp_path / "e.db")
    service = TaskService(repo, settings, TaskFilesystem(settings))
    project = service.create_project("ProjA")
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="1",
            description="[Hello](https://example.com)",
            comment="*c*",
            date_end=date(2020, 1, 1),
            color="#ffff00",
            create_folder=False,
        )
    )
    dest = tmp_path / "out.xlsx"
    path = export_tasks_to_excel(
        service, dest, project_ids=[project.id], include_hidden=False
    )
    assert path.is_file()
    from openpyxl import load_workbook

    wb = load_workbook(path)
    assert "ProjA" in wb.sheetnames
    rows = list(wb["ProjA"].iter_rows(values_only=True))
    assert list(rows[0]) == list(HEADERS)
    # Создана | Приоритет | Номер | Срок | Описание | Комментарий
    assert rows[1][2] == "1"
    assert rows[1][4] == "Hello https://example.com"
    assert rows[1][5] == "c"
    from taskmanager.domain import contrast_foreground

    deadline = wb["ProjA"].cell(row=2, column=4)
    description = wb["ProjA"].cell(row=2, column=5)
    assert "Статус" not in HEADERS
    assert description.fill.fgColor.rgb in ("00FFFF00", "FFFF00")
    assert deadline.fill.fgColor.rgb in ("00FFFF00", "FFFF00")
    assert str(deadline.font.color.rgb).upper().endswith("FF0000")
    contrast = contrast_foreground("#ffff00").lstrip("#").upper()
    for column in (1, 2, 3, 5, 6):
        rgb = str(wb["ProjA"].cell(row=2, column=column).font.color.rgb).upper()
        assert rgb.endswith(contrast)
        assert not rgb.endswith("FF0000")
    repo.close()


def test_export_excel_archive_month_filter(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "e2.db")
    service = TaskService(repo, settings, TaskFilesystem(settings))
    project = service.create_project("ProjB")
    assert project.id is not None
    active = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="A",
            description="active",
            create_folder=False,
        )
    )
    old = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="OLD",
            description="old archived",
            create_folder=False,
        )
    )
    new = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="NEW",
            description="new archived",
            create_folder=False,
        )
    )
    service.archive_task(old.id)
    service.archive_task(new.id)
    # Force distinct months in DB
    repo._conn.execute(
        "UPDATE tasks SET archive_month = ? WHERE id = ?",
        ("2025_01", old.id),
    )
    repo._conn.execute(
        "UPDATE tasks SET archive_month = ? WHERE id = ?",
        ("2026_08", new.id),
    )
    repo._conn.commit()
    months = repo.list_archive_months(project.id)
    assert months == ["2026_08", "2025_01"]

    dest = tmp_path / "filtered.xlsx"
    path = export_tasks_to_excel(
        service,
        dest,
        project_ids=[project.id],
        include_archived=True,
        archive_months_by_project={project.id: ["2026_08"]},
    )
    from openpyxl import load_workbook

    rows = list(load_workbook(path)["ProjB"].iter_rows(values_only=True))
    numbers = {r[2] for r in rows[1:]}
    assert active.number in numbers
    assert "NEW" in numbers
    assert "OLD" not in numbers
    repo.close()


def _font_rgb(cell) -> str | None:
    color = cell.font.color
    if color is None:
        return None
    try:
        rgb = color.rgb
    except Exception:
        return None
    if not isinstance(rgb, str):
        return None
    return rgb.upper()


def test_export_warning_font_only_on_deadline_without_row_color(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(
        work_dir=str(work),
        warning_color="#ff0000",
        highlight_warnings=True,
        warning_lead_days=1,
    )
    repo = SqliteRepository(tmp_path / "e3.db")
    service = TaskService(repo, settings, TaskFilesystem(settings))
    project = service.create_project("Plain")
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="1",
            description="warn",
            date_end=date(2020, 1, 1),
            create_folder=False,
        )
    )
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="2",
            description="later",
            date_end=date(2099, 1, 1),
            color="#0000ff",
            create_folder=False,
        )
    )
    path = export_tasks_to_excel(service, tmp_path / "plain.xlsx", project_ids=[project.id])
    from openpyxl import load_workbook

    from taskmanager.domain import contrast_foreground

    ws = load_workbook(path)["Plain"]
    by_number = {ws.cell(row=row, column=3).value: row for row in range(2, ws.max_row + 1)}
    warned = by_number["1"]
    later = by_number["2"]
    assert str(_font_rgb(ws.cell(row=warned, column=4))).endswith("FF0000")
    for column in (1, 2, 3, 5, 6):
        rgb = _font_rgb(ws.cell(row=warned, column=column))
        assert rgb is None or not rgb.endswith("FF0000")
    calm = contrast_foreground("#0000ff").lstrip("#").upper()
    for column in range(1, 7):
        rgb = _font_rgb(ws.cell(row=later, column=column))
        assert rgb is not None
        assert rgb.endswith(calm)
        assert not rgb.endswith("FF0000")
    repo.close()
