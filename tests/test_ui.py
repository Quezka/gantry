import os
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gantry.application.inputs import ResourceInput  # noqa: E402
from gantry.presentation import theme  # noqa: E402
from gantry.presentation.qt_app import create_application  # noqa: E402

from .conftest import SAMPLE  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return create_application(["test"])


@pytest.fixture
def window(app, services):
    from gantry.presentation.main_window import MainWindow
    w = MainWindow(services)
    w.show()
    yield w
    w.editor._saved = w.editor._project  # nothing to ask on close
    w.close()


def open_sample(window):
    window.editor.open(str(SAMPLE))
    window.plan.refresh(fit=True)
    window.show_page(window.PLAN)


def rows(window):
    tree = window.plan.tree
    out = []

    def walk(item, depth):
        out.append((depth, item.text(0)))
        for i in range(item.childCount()):
            walk(item.child(i), depth + 1)
    for i in range(tree.topLevelItemCount()):
        walk(tree.topLevelItem(i), 0)
    return out


def test_pages_wait_for_a_project(window):
    assert not window.sidebar.group.button(window.PLAN).isEnabled()
    window.show_page(window.PLAN)
    assert window.stack.currentIndex() == window.HOME
    open_sample(window)
    assert window.sidebar.group.button(window.PLAN).isEnabled()


def test_table_and_chart_show_the_same_tasks(window):
    open_sample(window)
    assert rows(window) == [(0, "Prepare"), (1, "Empty the room"), (1, "Remove old units"),
                            (0, "Fit new units"), (0, "Done")]
    assert set(window.plan.view.chart.bars) == {0, 1, 2, 3, 4}
    assert window.plan.title.text() == "Kitchen"


def test_folding_hides_rows_in_both(window):
    open_sample(window)
    window.plan.tree.topLevelItem(0).setExpanded(False)
    assert set(window.plan.view.chart.bars) == {0, 3, 4}
    assert not window.editor.dirty


def test_selecting_everything_edits_nothing(window):
    open_sample(window)
    window.plan.tree.selectAll()
    window.plan.refresh()
    assert not window.editor.dirty and not window.editor.can_undo


def test_dragging_a_bar_moves_it_and_its_followers(window):
    open_sample(window)
    plan = window.plan
    plan.view.moved.emit(3, 7)
    assert window.editor.project().tasks[3].start == date(2026, 10, 23)
    assert window.editor.can_undo
    plan.view.linked.emit(0, 4)
    assert [d.pred for d in window.editor.project().tasks[4].deps] == [0]


def test_a_circular_link_shows_a_message_instead_of_crashing(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    open_sample(window)
    seen = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: seen.append(text))
    window.plan.view.linked.emit(2, 1)  # 1 -> 2 already exists
    assert len(seen) == 1


def test_quick_add_adds_below_the_selection(window):
    open_sample(window)
    window.plan.select(3)
    window.plan.quick.setText("Clean up")
    window.plan.quick.returnPressed.emit()
    assert [t.name for t in window.editor.project().tasks][-2:] == ["Clean up", "Done"]
    assert window.plan.quick.text() == ""


def test_keyboard_indent_outdent_and_toggle_done(window):
    open_sample(window)
    window.plan.select(3)
    window.plan.indent()
    assert window.editor.project().tasks[3].depth == 1
    window.plan.outdent()
    window.plan.toggle_done()
    assert window.editor.project().tasks[3].complete == 100


def test_zoom_levels_redraw_the_chart(window):
    open_sample(window)
    widths = []
    for key in ("day", "week", "month", "quarter"):
        window.plan.set_zoom(key)
        widths.append(window.plan.view.chart.sceneRect().width())
    assert widths == sorted(widths, reverse=True)


def test_task_sheet_and_editor_open(window, app):
    from gantry.presentation.dialogs import TaskEditor, TaskSheet
    open_sample(window)
    record = window.editor.project()
    sheet = TaskSheet(record.tasks[2], record, date(2026, 10, 2))
    assert sheet.windowTitle() == "Remove old units"
    editor = TaskEditor(window.editor, record.tasks[2], record)
    assert editor.name.text() == "Remove old units" and len(editor.dep_rows) == 1
    editor.duration.setValue(7)
    assert editor.end.date().toPython() > date(2026, 10, 14)
    assert editor.to_input().duration == 7


def test_editing_a_summary_task_keeps_its_children_alone(window):
    from gantry.presentation.dialogs import TaskEditor
    open_sample(window)
    record = window.editor.project()
    dialog = TaskEditor(window.editor, record.tasks[0], record)
    assert not dialog.duration.isEnabled() and not dialog.milestone.isEnabled()
    window.editor.update_task(0, dialog.to_input())
    assert not window.editor.dirty or window.editor.project().tasks[1].duration == 2


def test_resources_and_project_pages(window):
    open_sample(window)
    window.editor.add_resource(ResourceInput("Gigi"))
    window.show_page(window.RESOURCES)
    assert window.resources.list.count() == 3
    window.show_page(window.PROJECT)
    assert window.project.name.text() == "Kitchen"
    assert not window.project.days[5].isChecked() and window.project.days[0].isChecked()
    assert window.project.holidays.count() == 1


def test_project_fields_do_not_fight_the_typist(window):
    open_sample(window)
    window.show_page(window.PROJECT)
    box = window.project.name
    box.setText("Kitchen ")  # as typed
    box.textEdited.emit("Kitchen ")
    assert box.text() == "Kitchen " and window.editor.project().name == "Kitchen "


def test_exports_are_real_files(window):
    from gantry.presentation.export import pdf_bytes, png_bytes, svg_bytes
    open_sample(window)
    record, today = window.editor.project(), date(2026, 10, 2)
    brand = window.services.branding.get()
    assert png_bytes(record, today, brand)[:8] == b"\x89PNG\r\n\x1a\n"
    assert pdf_bytes(record, today, None)[:5] == b"%PDF-"
    svg = svg_bytes(record, today, brand)
    assert b"<svg" in svg and b"Alessandrini" in svg


def test_the_school_is_in_the_sidebar_and_can_be_changed(window, services):
    assert "Alessandrini" in window.sidebar.school_name.text()
    from gantry.application.inputs import BrandingInput
    services.branding.set(BrandingInput("Other school", "Rome", None, False))
    window.sidebar.set_branding(services.branding.get())
    assert window.sidebar.school_name.text() == "Other school"
    assert not services.branding.get().on_exports


def test_both_themes_style_everything(app):
    manager = theme.manager()
    for mode in ("dark", "light"):
        manager.set_mode(mode)
        assert QApplication.instance().styleSheet()
    manager.set_mode("system")


def test_empty_state_then_first_task(window):
    window.new_project()
    assert window.plan.stack.currentIndex() == 1
    window.plan.quick.setText("First")
    window.plan.quick.returnPressed.emit()
    assert window.plan.stack.currentIndex() == 0 and rows(window) == [(0, "First")]


def _drag(window, task_id, where, dx):
    """Press on part of a bar ("body", "edge", "ring"), drag `dx` pixels, release."""
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    view = window.plan.view
    bar = view.chart.bars[task_id]
    r = bar.bar_rect()
    x = {"body": r.center().x(), "edge": r.right() - 2, "ring": r.right() + 12}[where]
    start = view.mapFromScene(QPointF(x, bar.cy))
    QTest.mouseMove(view.viewport(), start)
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, start)
    for step in range(1, 6):
        QTest.mouseMove(view.viewport(), start + QPoint(int(dx * step / 5), 0))
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, start + QPoint(int(dx), 0))
    QApplication.processEvents()


def test_real_mouse_drag_moves_a_bar(window):
    open_sample(window)
    window.plan.set_zoom("day")  # 40 px a day
    before = window.editor.project().tasks[3].start
    _drag(window, 3, "body", 160)  # four days: from a Friday to a Tuesday
    assert (window.editor.project().tasks[3].start - before).days == 4


def test_real_mouse_drag_on_the_edge_changes_the_length(window):
    open_sample(window)
    window.plan.set_zoom("day")
    before = window.editor.project().tasks[3].duration
    _drag(window, 3, "edge", 80)
    assert window.editor.project().tasks[3].duration == before + 2


def test_real_mouse_drag_from_the_ring_links_two_bars(window):
    open_sample(window)
    window.plan.set_zoom("day")
    view = window.plan.view
    target = view.chart.bars[4]
    source = view.chart.bars[3]
    dx = view.mapFromScene(QPointF(target.x0, target.cy)).x() - view.mapFromScene(
        QPointF(source.right + 12, source.cy)).x()
    dy = view.mapFromScene(QPointF(0, target.cy)).y() - view.mapFromScene(QPointF(0, source.cy)).y()
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    start = view.mapFromScene(QPointF(source.right + 12, source.cy))
    QTest.mouseMove(view.viewport(), start)
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(view.viewport(), start + QPoint(dx // 2, dy // 2))
    end = start + QPoint(dx + 4, dy)
    QTest.mouseMove(view.viewport(), end)
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, end)
    QApplication.processEvents()
    assert [d.pred for d in window.editor.project().tasks[4].deps] == [3]


def test_dragging_the_progress_triangle(window):
    open_sample(window)
    window.plan.set_zoom("day")
    bar = window.plan.view.chart.bars[3]
    r = bar.bar_rect()
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    view = window.plan.view
    start = view.mapFromScene(QPointF(r.left(), r.bottom() + 2))
    QTest.mouseMove(view.viewport(), start)
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, start)
    end = start + QPoint(int(r.width() / 2), 0)
    QTest.mouseMove(view.viewport(), end)
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, end)
    QApplication.processEvents()
    assert window.editor.project().tasks[3].complete == 50


def test_chart_and_table_follow_the_theme_after_a_selection(window):
    """Regression: refresh() used to crash once a task was selected, so nothing redrew."""
    open_sample(window)
    window.plan.select(3)
    manager = theme.manager()
    for mode, dark in (("dark", True), ("light", False)):
        manager.set_mode(mode)
        assert window.plan.view.chart.t.dark is dark
        image = window.plan.view.viewport().grab().toImage()
        pixel = image.pixelColor(image.width() - 5, image.height() - 5)
        assert (pixel.lightness() < 128) is dark
    manager.set_mode("system")


def test_a_change_after_selecting_redraws_the_table(window):
    open_sample(window)
    window.plan.select(3)
    window.editor.rename_task(3, "Fit the units")
    assert window.plan.tree.topLevelItem(1).text(0) == "Fit the units" or any(
        text == "Fit the units" for _d, text in rows(window))


def _drop(window, moving, target, where=None):
    """Drive the table's drop handler the way a drag does."""
    from PySide6.QtWidgets import QAbstractItemView
    tree = window.plan.tree
    window.plan.select(moving)
    tree.dropped.emit([moving], target[0], target[1])
    QApplication.processEvents()


def test_dropping_a_task_onto_another_makes_it_part_of_it(window):
    open_sample(window)
    _drop(window, 3, (4, None), "on")  # "Fit new units" into the milestone
    rec = {t.name: t for t in window.editor.project().tasks}
    assert rec["Fit new units"].parent == 4 and rec["Done"].summary
    assert rows(window)[-2:] == [(0, "Done"), (1, "Fit new units")]


def test_dropping_between_tasks_just_moves_the_task(window):
    open_sample(window)
    _drop(window, 4, (None, 0))  # before "Prepare"
    assert rows(window)[0] == (0, "Done")


def test_a_task_cannot_be_dropped_into_its_own_branch(window):
    open_sample(window)
    before = window.editor.project()
    _drop(window, 0, (1, None))  # "Prepare" into its own child
    assert window.editor.project() == before


def test_a_real_drag_and_drop_in_the_table(window):
    from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt as QtCore
    from PySide6.QtGui import QDropEvent
    open_sample(window)
    tree = window.plan.tree
    window.plan.select(3)
    target = tree.topLevelItem(2)  # "Done" (a milestone)
    point = tree.visualItemRect(target).center()
    from PySide6.QtWidgets import QAbstractItemView
    tree.dragMoveEvent  # the drop indicator is set by the move event Qt sends first
    tree.setState(QAbstractItemView.DraggingState)
    from PySide6.QtGui import QDragMoveEvent
    move = QDragMoveEvent(point, QtCore.MoveAction, QMimeData(), QtCore.LeftButton,
                          QtCore.NoModifier)
    tree.dragMoveEvent(move)
    drop = QDropEvent(QPointF(point), QtCore.MoveAction, QMimeData(), QtCore.LeftButton,
                      QtCore.NoModifier)
    tree.dropEvent(drop)
    QApplication.processEvents()
    assert next(t for t in window.editor.project().tasks if t.id == 3).parent == 4


def test_dragging_empty_chart_space_moves_the_view(window):
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    open_sample(window)
    window.plan.set_zoom("day")
    view = window.plan.view
    window.plan.select(3)
    bar = view.horizontalScrollBar()
    bar.setValue(400)
    empty = QPoint(view.viewport().width() // 2, view.viewport().height() - 20)
    assert not view._on_bar(empty)
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, empty)
    QTest.mouseMove(view.viewport(), empty + QPoint(-120, 0))
    QTest.mouseMove(view.viewport(), empty + QPoint(-150, 0))
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, empty + QPoint(-150, 0))
    QApplication.processEvents()
    assert bar.value() == 550  # dragged left, so the chart moved right under the cursor
    assert window.plan.selected_ids() == [3]  # a drag is not a click


def test_clicking_empty_chart_space_clears_the_selection(window):
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    open_sample(window)
    view = window.plan.view
    window.plan.select(3)
    empty = QPoint(view.viewport().width() // 2, view.viewport().height() - 20)
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier, empty)
    QApplication.processEvents()
    assert window.plan.selected_ids() == []


def test_arrows_meet_a_milestone_at_its_corner_not_its_middle(window):
    from gantry.presentation.gantt import BAR, route
    from gantry.application.types import DepKind
    open_sample(window)
    window.editor.link(3, 4)  # "Fit new units" -> the milestone "Done"
    window.plan.refresh()
    bars = window.plan.view.chart.bars
    points, head = route(DepKind.FINISH_START, bars[3], bars[4])
    assert points[-1].x() == bars[4].x0 - BAR / 2  # the diamond's left corner
    assert head.at(0).x() == points[-1].x()


def test_the_table_has_no_scroll_bar_but_lines_up_with_the_chart(window):
    open_sample(window)
    tree, view = window.plan.tree, window.plan.view
    assert tree.viewport().height() == view.viewport().height()  # same rows, same room
    bar = tree.horizontalScrollBar()
    assert "transparent" in tree.styleSheet() and bar.height() == view.horizontalScrollBar().height()


def test_the_new_person_dialog_cannot_be_resized(window):
    from gantry.presentation.dialogs import ResourceEditor
    dialog = ResourceEditor(window.editor.project())
    dialog.show()
    QApplication.processEvents()
    assert dialog.minimumSize() == dialog.maximumSize() == dialog.size()
