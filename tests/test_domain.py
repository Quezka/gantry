from datetime import date

from gantry.domain import Calendar, DepKind, Dependency, Project, Task, schedule, structure

MON = date(2026, 10, 5)


def project(*tasks, calendar=None):
    return Project(tasks=tuple(tasks), calendar=calendar or Calendar())


def test_ten_working_days_skip_weekends():
    cal = Calendar()
    assert cal.last_day(MON, 10) == date(2026, 10, 16)
    assert cal.end_exclusive(MON, 10) == date(2026, 10, 17)
    assert cal.last_day(MON, 0) == MON


def test_holidays_and_extra_days_change_the_count():
    cal = Calendar(holidays=frozenset({date(2026, 10, 6)}))
    assert cal.last_day(MON, 2) == date(2026, 10, 7)
    saturday = Calendar(extra_days=frozenset({date(2026, 10, 10)}))
    assert saturday.last_day(MON, 6) == date(2026, 10, 10)


def test_index_and_date_at_are_inverse_for_any_week():
    cal = Calendar(off_weekdays=frozenset({4, 5, 6}), holidays=frozenset({date(2026, 10, 7)}))
    for n in range(-30, 60):
        d = cal.date_at(n)
        assert cal.is_working(d) and cal.index(d) == n


def test_calendar_with_no_working_day_falls_back():
    assert Calendar(off_weekdays=frozenset(range(7))).per_week == 5


def test_finish_start_pushes_the_follower():
    p = schedule.normalise(project(
        Task(0, "a", MON, 3), Task(1, "b", MON, 2, deps=(Dependency(0),))))
    assert p.task(1).start == date(2026, 10, 8)


def test_lag_and_other_kinds():
    a = Task(0, "a", MON, 4)
    ss = schedule.normalise(project(a, Task(1, "b", MON, 2, deps=(
        Dependency(0, DepKind.START_START, 2),))))
    assert ss.task(1).start == date(2026, 10, 7)
    ff = schedule.normalise(project(a, Task(1, "b", MON, 2, deps=(
        Dependency(0, DepKind.FINISH_FINISH),))))
    assert Calendar().last_day(ff.task(1).start, 2) == date(2026, 10, 8)


def test_a_task_placed_late_by_hand_stays_put():
    p = schedule.normalise(project(
        Task(0, "a", MON, 1), Task(1, "b", date(2026, 10, 12), 1, deps=(Dependency(0),))))
    assert p.task(1).start == date(2026, 10, 12)


def test_summary_spans_children_and_weights_progress():
    p = schedule.roll_up(project(
        Task(0, "g", MON, 1),
        Task(1, "x", MON, 1, complete=100, parent=0),
        Task(2, "y", date(2026, 10, 7), 3, complete=0, parent=0)))
    g = p.task(0)
    assert (g.start, g.duration, g.complete) == (MON, 5, 25)


def test_moving_a_summary_moves_its_children_and_pushes_followers():
    p = project(Task(0, "g", MON, 1), Task(1, "x", MON, 2, parent=0),
                Task(2, "y", MON, 1, deps=(Dependency(0),)))
    p = schedule.normalise(p)
    moved = schedule.normalise(schedule.move_to(p, 0, date(2026, 10, 12)))
    assert moved.task(1).start == date(2026, 10, 12)
    assert moved.task(2).start == date(2026, 10, 14)


def test_cycles_and_nesting_cannot_be_linked():
    p = project(Task(0, "a", MON, 1), Task(1, "b", MON, 1, deps=(Dependency(0),)),
                Task(2, "c", MON, 1, parent=0))
    assert not schedule.can_link(p, 1, 0)
    assert not schedule.can_link(p, 0, 0)
    assert not schedule.can_link(p, 0, 2)  # a parent and its child
    assert schedule.can_link(p, 2, 1)


def test_critical_path_follows_the_longest_chain():
    p = schedule.normalise(project(
        Task(0, "a", MON, 3), Task(1, "short", MON, 1, deps=(Dependency(0),)),
        Task(2, "long", MON, 4, deps=(Dependency(0),)),
        Task(3, "end", MON, 1, deps=(Dependency(1), Dependency(2))),
        Task(4, "alone", MON, 1)))
    assert schedule.critical(p) == {0, 2, 3}


def test_structure_indent_outdent_move():
    p = project(Task(0, "a", MON), Task(1, "b", MON), Task(2, "c", MON))
    p = structure.indent(p, 1)
    assert p.task(1).parent == 0
    p = structure.indent(p, 2)  # under b? c's sibling above is a (b is a's child)
    assert p.task(2).parent == 0
    assert [t.id for t in p.tasks] == [0, 1, 2]
    p = structure.move(p, 2, -1)
    assert [t.id for t in p.tasks] == [0, 2, 1]
    p = structure.outdent(p, 2)
    assert p.task(2).parent is None and [t.id for t in p.tasks] == [0, 1, 2]


def test_deleting_a_task_drops_what_pointed_at_it():
    p = project(Task(0, "a", MON), Task(1, "b", MON, deps=(Dependency(0),)),
                Task(2, "c", MON, parent=0))
    q = p.without({0})
    assert [t.id for t in q.tasks] == [1] and q.task(1).deps == ()
