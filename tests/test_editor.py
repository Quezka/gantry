from datetime import date, timedelta

import pytest

from gantry.application.editor import LinkError
from gantry.application.inputs import AssignInput, DepInput, ProjectInfo, ResourceInput, TaskInput
from gantry.application.types import DepKind

from .conftest import SAMPLE, TODAY

MON = date(2026, 10, 5)


def names(editor):
    return [t.name for t in editor.project().tasks]


def add(editor, name, start=MON, length=1, **kwargs):
    return editor.add_task(TaskInput(name, start, length, **kwargs))


def test_new_project_is_empty_and_clean(editor):
    editor.new("School")
    assert editor.is_open and editor.project().empty and editor.project().name == "School"
    assert not editor.can_undo


def test_first_task_starts_today_or_the_next_working_day(editor):
    editor.new()
    id = editor.add_task(name="Hello")
    assert editor.project().tasks[0].start == TODAY and editor.project().tasks[0].id == id
    editor.set_weekdays_off([4, 5, 6])  # no work on Fridays
    other = editor.add_task(name="Later", after=id)
    assert editor.project().tasks[1].start == date(2026, 10, 5) and other == 1


def test_edits_are_undoable_and_mark_the_project_dirty(editor):
    editor.new()
    a = add(editor, "a")
    assert editor.dirty
    editor.undo()
    assert editor.project().empty
    editor.redo()
    assert names(editor) == ["a"] and a == 0


def test_typing_a_name_is_one_undo_step(editor):
    editor.new()
    a = add(editor, "a")
    editor.end_group()
    for text in ("b", "bo", "boo"):
        editor.rename_task(a, text)
    editor.undo()
    assert names(editor) == ["a"]


def test_dependencies_push_and_move_followers(editor):
    editor.new()
    a, b = add(editor, "a", length=3), add(editor, "b", length=2)
    editor.link(a, b)
    rec = {t.name: t for t in editor.project().tasks}
    assert rec["b"].start == date(2026, 10, 8)
    editor.move_task_by(a, 7)  # a week later
    rec = {t.name: t for t in editor.project().tasks}
    assert rec["a"].start == date(2026, 10, 12) and rec["b"].start == date(2026, 10, 15)


def test_linking_in_a_circle_is_refused(editor):
    editor.new()
    a, b = add(editor, "a"), add(editor, "b")
    editor.link(a, b)
    with pytest.raises(LinkError):
        editor.link(b, a)
    assert not editor.can_link(b, a)


def test_dragging_the_edge_changes_the_length(editor):
    editor.new()
    a = add(editor, "a", length=2)
    editor.resize_task_to(a, date(2026, 10, 12))
    assert editor.project().tasks[0].duration == 6
    assert editor.project().tasks[0].end == date(2026, 10, 12)


def test_progress_and_summary_progress(editor):
    editor.new()
    g = add(editor, "group")
    x = editor.add_task(TaskInput("x", MON, 1), parent=g)
    editor.add_task(TaskInput("y", MON, 1), parent=g)
    editor.set_complete(x, 100)
    assert editor.project().tasks[0].complete == 50
    editor.set_complete(g, 100)
    assert all(t.complete == 100 for t in editor.project().tasks)


def test_indent_outdent_and_order(editor):
    editor.new()
    a, b = add(editor, "a"), add(editor, "b")
    editor.indent(b)
    rec = editor.project().tasks
    assert rec[0].summary and rec[1].depth == 1 and rec[1].wbs == "1.1"
    editor.outdent(b)
    editor.move_up(b)
    assert names(editor) == ["b", "a"]


def test_folding_is_neither_undo_nor_unsaved(editor):
    editor.open(str(SAMPLE))
    editor.set_expanded(0, False)
    assert not editor.dirty and not editor.can_undo
    assert not editor.project().tasks[0].expanded


def test_duplicate_copies_the_branch_and_its_inner_links(editor):
    editor.new()
    g = add(editor, "g")
    a = editor.add_task(TaskInput("a", MON, 1), parent=g)
    b = editor.add_task(TaskInput("b", MON, 1), parent=g)
    editor.link(a, b)
    copy = editor.duplicate(g)
    rec = {t.id: t for t in editor.project().tasks}
    assert rec[copy].name == "g (copy)" and len(rec) == 6
    kids = [t for t in rec.values() if t.parent == copy]
    assert kids[1].deps[0].pred == kids[0].id


def test_update_task_validates_dependencies_and_sets_people(editor):
    editor.new()
    p = editor.add_resource(ResourceInput("Ana", rate=100))
    a, b = add(editor, "a"), add(editor, "b")
    editor.update_task(b, TaskInput("b", MON, 2, deps=(DepInput(a, DepKind.START_START, 1),),
                                    assignments=(AssignInput(p, 50),)))
    t = editor.project().tasks[1]
    assert t.deps[0].kind is DepKind.START_START and t.start == date(2026, 10, 6)
    assert t.assignments[0].load == 50 and t.cost == 100.0
    with pytest.raises(LinkError):
        editor.update_task(a, TaskInput("a", MON, 1, deps=(DepInput(b),)))


def test_milestones_have_no_length(editor):
    editor.new()
    m = add(editor, "m", milestone=True, length=5)
    assert editor.project().tasks[0].duration == 0 and m == 0


def test_overbooked_people_are_flagged(editor):
    editor.new()
    p = editor.add_resource(ResourceInput("Ana"))
    for name in ("a", "b"):
        add(editor, name, assignments=(AssignInput(p, 100),))
    r = editor.project().resources[0]
    assert r.overloaded and r.peak_load == 200
    editor.add_vacation(p, MON, MON)
    assert editor.workload(p, MON, MON).days[0][2] is True


def test_calendar_changes_move_dates(editor):
    editor.new()
    a = add(editor, "a", length=6)
    assert editor.project().tasks[0].end == date(2026, 10, 12)
    editor.add_holiday(date(2026, 10, 7))
    assert editor.project().tasks[0].end == date(2026, 10, 13)
    editor.set_weekdays_off([6])
    assert a == 0 and editor.project().off_weekdays == (6,)


def test_late_tasks_and_totals(editor):
    editor.new()
    add(editor, "old", start=date(2026, 9, 21), length=2, complete=50)
    add(editor, "fine", start=date(2026, 10, 12), length=2)
    rec = editor.project()
    assert [t.late for t in rec.tasks] == [True, False] and rec.late == 1
    assert rec.start == date(2026, 9, 21) and rec.finish == date(2026, 10, 13)


def test_save_and_open_round_trip(editor, tmp_path):
    editor.new("Round trip")
    add(editor, "a", length=3)
    path = tmp_path / "p.gan"
    editor.save(str(path))
    assert not editor.dirty
    editor.open(str(path))
    assert editor.project().name == "Round trip" and names(editor) == ["a"]


def test_saving_without_a_path_asks_for_one(editor):
    editor.new()
    from gantry.application.errors import NotFound
    with pytest.raises(NotFound):
        editor.save()


def test_opening_a_gantt_project_file_keeps_its_dates(editor):
    editor.open(str(SAMPLE))
    before = [(t.name, t.start, t.end) for t in editor.project().tasks]
    editor.rename_task(1, "Empty the room!")  # any edit re-checks every dependency
    after = [(t.name, t.start, t.end) for t in editor.project().tasks]
    assert before[2:] == after[2:]


def test_csv_lists_every_task(editor):
    editor.open(str(SAMPLE))
    lines = editor.csv().strip().splitlines()
    assert len(lines) == 6 and lines[0].startswith("ID,Name")


def test_project_info_is_kept_as_typed(editor):
    editor.new()
    editor.set_info(ProjectInfo("My project ", "Class 5A"))
    assert editor.project().name == "My project "


def test_sample_project_builds_through_use_cases(editor):
    from gantry.demo import website
    website(editor)
    rec = editor.project()
    assert len(rec.tasks) == 13 and rec.finish > rec.start and not editor.dirty
    assert TODAY - timedelta(days=30) < rec.start


def test_dropping_a_task_into_another_nests_it_with_its_branch(editor):
    editor.new()
    a, b, c = add(editor, "a"), add(editor, "b"), add(editor, "c")
    editor.indent(c)  # c under b
    editor.relocate(b, a)  # b (and c) become part of a
    rec = {t.name: t for t in editor.project().tasks}
    assert rec["b"].parent == a and rec["c"].parent == b and rec["a"].summary
    assert [t.name for t in editor.project().tasks] == ["a", "b", "c"]
    editor.undo()
    assert editor.project().tasks[1].depth == 0
    from gantry.application.errors import ApplicationError
    with pytest.raises(ApplicationError):
        editor.relocate(b, c)
