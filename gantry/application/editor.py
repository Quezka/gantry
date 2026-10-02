"""The open project and everything you can do to it, with undo and redo."""
from __future__ import annotations

import csv
import io
import uuid
from dataclasses import replace
from datetime import date, timedelta
from enum import Enum
from typing import Callable

from ..domain import (
    Allocation, DepKind, Dependency, Project, Resource, Role, Task, Vacation, schedule, structure,
)
from ..domain.calendar import Calendar
from .errors import ApplicationError, NotFound
from .inputs import ProjectInfo, ResourceInput, TaskInput
from .ports import ProjectFiles
from .records import (
    AssignmentRecord, DepRecord, ProjectRecord, ResourceRecord, RoleRecord, TaskRecord,
    VacationRecord, WorkloadRecord,
)

HISTORY = 200  # undo steps kept


class Change(Enum):
    PROJECT = "project"  # what's drawn changed
    DOCUMENT = "document"  # which file is open, or whether it's saved
    LAYOUT = "layout"  # only a branch was folded or unfolded


class LinkError(ApplicationError):
    pass


class Editor:
    def __init__(self, files: ProjectFiles, today: Callable[[], date] = date.today,
                 new_uid: Callable[[], str] | None = None):
        self._files = files
        self._today = today
        self._new_uid = new_uid or (lambda: uuid.uuid4().hex)
        self._listeners: list[Callable[[Change], None]] = []
        self._project = Project()
        self._saved: Project | None = self._project
        self._path: str | None = None
        self._undo: list[tuple[Project, str | None]] = []
        self._redo: list[Project] = []
        self._open = False

    # ---- notifications ------------------------------------------------------------------

    def subscribe(self, listener: Callable[[Change], None]):
        self._listeners.append(listener)

    def _emit(self, *changes: Change):
        for change in changes:
            for listener in list(self._listeners):
                listener(change)

    # ---- the document -------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def path(self) -> str | None:
        return self._path

    @property
    def dirty(self) -> bool:
        return self._project is not self._saved

    def today(self) -> date:
        return self._today()

    def new(self, name: str = ""):
        self._load(Project(name=name), None, saved=False)

    def open(self, path: str):
        self._load(schedule.roll_up(self._files.read(path)), str(path), saved=True)

    def _load(self, project: Project, path: str | None, saved: bool):
        self._project = project
        self._saved = project if saved else None
        self._path = path
        self._undo.clear()
        self._redo.clear()
        self._open = True
        self._emit(Change.PROJECT, Change.DOCUMENT)

    def close(self):
        self._open = False
        self._path = None
        self._project = Project()
        self._saved = self._project
        self._undo.clear()
        self._redo.clear()
        self._emit(Change.PROJECT, Change.DOCUMENT)

    def save(self, path: str | None = None):
        path = str(path or self._path or "")
        if not path:
            raise NotFound("Choose where to save the project.")
        self._files.write(path, self._files.encode(self._project))
        self._path = path
        self._saved = self._project
        self._emit(Change.DOCUMENT)

    def export(self, path: str, data: bytes):
        """Write a finished export (a picture, a CSV) as is; the project stays as it was."""
        self._files.write(str(path), data)

    def settle(self):
        """Treat what's there now as the starting point (for samples)."""
        self._undo.clear()
        self._redo.clear()
        self._saved = self._project
        self._emit(Change.DOCUMENT)

    # ---- undo ----------------------------------------------------------------------------

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self):
        if self._undo:
            self._redo.append(self._project)
            self._project, _group = self._undo.pop()
            self._emit(Change.PROJECT, Change.DOCUMENT)

    def redo(self):
        if self._redo:
            self._undo.append((self._project, None))
            self._project = self._redo.pop()
            self._emit(Change.PROJECT, Change.DOCUMENT)

    def _commit(self, project: Project, group: str | None = None):
        """Make `project` current as one undo step. Consecutive changes with the same `group`
        (e.g. typing a title) merge into one step."""
        project = schedule.normalise(project)
        if project == self._project:
            return
        if not (group and self._undo and self._undo[-1][1] == group):
            self._undo.append((self._project, group))
            del self._undo[:-HISTORY]
        self._redo.clear()
        self._project = project
        self._emit(Change.PROJECT, Change.DOCUMENT)

    def end_group(self):
        if self._undo:
            self._undo[-1] = (self._undo[-1][0], None)

    # ---- reading ------------------------------------------------------------------------

    def project(self) -> ProjectRecord:
        p, today = self._project, self._today()
        cal = p.calendar
        critical = schedule.critical(p)
        wbs: dict[int, str] = {}
        counters: dict[int | None, int] = {}
        for t in p.tasks:
            counters[t.parent] = counters.get(t.parent, 0) + 1
            head = wbs[t.parent] + "." if t.parent in wbs else ""
            wbs[t.id] = f"{head}{counters[t.parent]}"
        names = {t.id: t.name for t in p.tasks}
        who = {r.id: r.name for r in p.resources}
        successors: dict[int, list[int]] = {}
        for t in p.tasks:
            for d in t.deps:
                successors.setdefault(d.pred, []).append(t.id)
        costs: dict[int, float] = {}
        for t in reversed(p.tasks):  # children first
            if p.is_summary(t.id):
                costs[t.id] = sum(costs[c.id] for c in p.children(t.id))
            else:
                costs[t.id] = self._cost(p, t)
        records = []
        for t in p.tasks:
            end = cal.last_day(t.start, t.duration)
            summary = p.is_summary(t.id)
            records.append(TaskRecord(
                id=t.id, name=t.name, parent=t.parent, depth=p.depth(t.id), wbs=wbs[t.id],
                start=t.start, end=end, duration=t.duration, complete=t.complete, color=t.color,
                milestone=t.milestone and not summary, summary=summary,
                expanded=t.expanded, critical=t.id in critical,
                late=t.complete < 100 and end < today and not summary,
                notes=t.notes, web_link=t.web_link, cost=costs[t.id],
                cost_fixed=t.cost is not None,
                deps=tuple(DepRecord(d.pred, names.get(d.pred, "?"), d.kind, d.lag, d.strong)
                           for d in t.deps if d.pred in names),
                assignments=tuple(AssignmentRecord(a.resource, who.get(a.resource, "?"), a.load,
                                                   a.responsible)
                                  for a in p.allocations if a.task == t.id),
                successors=tuple(successors.get(t.id, ()))))
        peaks = {r.id: self._peak(p, r.id) for r in p.resources}
        roles = {r.id: r.name for r in p.roles}
        resources = tuple(
            ResourceRecord(r.id, r.name, r.role, roles.get(r.role, ""), r.email, r.phone, r.rate,
                           len({a.task for a in p.allocations if a.resource == r.id}),
                           peaks[r.id], peaks[r.id] > 100.0)
            for r in p.resources)
        tops = [t for t in p.tasks if t.parent is None]
        start = min((t.start for t in p.tasks), default=None)
        finish = max((cal.last_day(t.start, t.duration) for t in p.tasks), default=None)
        weight = sum(t.duration for t in tops)
        complete = (round(sum(t.duration * t.complete for t in tops) / weight) if weight
                    else (round(sum(t.complete for t in tops) / len(tops)) if tops else 0))
        return ProjectRecord(
            name=p.name, company=p.company, web_link=p.web_link, description=p.description,
            tasks=tuple(records), resources=resources,
            roles=tuple(RoleRecord(r.id, r.name) for r in p.roles),
            vacations=tuple(VacationRecord(v.resource, who.get(v.resource, "?"), v.start, v.end)
                            for v in p.vacations),
            off_weekdays=tuple(sorted(cal.off_weekdays)), holidays=tuple(sorted(cal.holidays)),
            start=start, finish=finish,
            duration=cal.duration_between(start, finish + timedelta(days=1)) if start else 0,
            complete=complete, cost=sum(costs[t.id] for t in tops),
            late=sum(1 for r in records if r.late), empty=not p.tasks)

    @staticmethod
    def _cost(p: Project, t: Task) -> float:
        if t.cost is not None:
            return t.cost
        total = 0.0
        for a in p.allocations:
            r = p.resource(a.resource)
            if a.task == t.id and r is not None and r.rate:
                total += r.rate * a.load / 100.0 * t.duration
        return total

    def _bookings(self, p: Project, resource: int) -> dict[date, float]:
        cal = p.calendar
        booked: dict[date, float] = {}
        for a in p.allocations:
            t = p.task(a.task)
            if a.resource != resource or t is None or p.is_summary(t.id) or t.duration <= 0:
                continue
            first = cal.index(t.start)
            for n in range(first, first + t.duration):
                day = cal.date_at(n)
                booked[day] = booked.get(day, 0.0) + a.load
        return booked

    def _peak(self, p: Project, resource: int) -> float:
        return max(self._bookings(p, resource).values(), default=0.0)

    def workload(self, resource: int, first: date, last: date) -> WorkloadRecord:
        p = self._project
        booked = self._bookings(p, resource)
        off = [(v.start, v.end) for v in p.vacations if v.resource == resource]
        days, d = [], first
        while d <= last:
            days.append((d, booked.get(d, 0.0), any(a <= d <= b for a, b in off)))
            d += timedelta(days=1)
        return WorkloadRecord(resource, tuple(days))

    def preview(self, start: date, duration: int) -> tuple[date, date]:
        """Where a task starting on `start` really starts (on a working day) and ends."""
        cal = self._project.calendar
        first = cal.next_working(start)
        return first, cal.last_day(first, duration)

    def duration_for(self, start: date, last: date) -> int:
        """How many working days it takes to get from `start` to `last`."""
        return self._project.calendar.duration_to_last(self._project.calendar.next_working(start),
                                                       last)

    def csv(self) -> str:
        record = self.project()
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["ID", "Name", "Begin date", "End date", "Duration", "Completion",
                         "Predecessors", "Resources", "Cost"])
        for t in record.tasks:
            writer.writerow([t.wbs, "  " * t.depth + t.name, t.start.isoformat(),
                             t.end.isoformat(), t.duration, t.complete,
                             ", ".join(str(d.pred) for d in t.deps),
                             ", ".join(a.name for a in t.assignments),
                             f"{t.cost:.2f}" if t.cost else ""])
        return out.getvalue()

    # ---- the project itself ----------------------------------------------------------------

    def set_info(self, info: ProjectInfo):
        self._commit(replace(self._project, name=info.name, company=info.company,
                             web_link=info.web_link, description=info.description),
                     group="info")

    def set_weekdays_off(self, days):
        cal = self._project.calendar
        self._commit(replace(self._project, calendar=Calendar(
            frozenset(days), cal.holidays, cal.extra_days)))

    def add_holiday(self, day: date):
        cal = self._project.calendar
        self._commit(replace(self._project, calendar=Calendar(
            cal.off_weekdays, cal.holidays | {day}, cal.extra_days - {day})))

    def remove_holiday(self, day: date):
        cal = self._project.calendar
        self._commit(replace(self._project, calendar=Calendar(
            cal.off_weekdays, cal.holidays - {day}, cal.extra_days)))

    def add_role(self, name: str) -> str:
        roles = self._project.roles
        used = {r.id for r in roles}
        id = next(str(i) for i in range(1000) if str(i) not in used)
        self._commit(replace(self._project, roles=roles + (Role(id, name.strip()),)))
        return id

    def remove_role(self, id: str):
        p = self._project
        self._commit(replace(
            p, roles=tuple(r for r in p.roles if r.id != id),
            resources=tuple(replace(r, role="") if r.role == id else r for r in p.resources)))

    # ---- tasks ---------------------------------------------------------------------------

    def _fresh_start(self, after: int | None) -> date:
        p = self._project
        if after is not None and p.task(after):
            return p.task(after).start
        if p.tasks:
            return min(t.start for t in p.tasks)
        return p.calendar.next_working(self._today())

    def add_task(self, input: TaskInput | None = None, after: int | None = None,
                 parent: int | None = None, name: str = "") -> int:
        """A new task, as the last child of `parent`, or right after `after` (as its sibling)."""
        p = self._project
        if after is not None and p.task(after):
            parent = p.task(after).parent
        id = p.next_task_id()
        start = input.start if input else self._fresh_start(after)
        task = Task(id, (input.name if input else name).strip() or "New task",
                    p.calendar.next_working(start), parent=parent, uid=self._new_uid())
        p = p.inserted(task, after=after)
        if parent is not None and p.task(parent):
            p = p.update(parent, expanded=True)
        self._commit(p)
        if input is not None:
            self.update_task(id, input)
        return id

    def update_task(self, id: int, input: TaskInput):
        p = self._project
        task = p.task(id)
        if task is None:
            raise NotFound("That task isn't there any more.")
        summary = p.is_summary(id)
        deps = []
        for d in input.deps:
            if d.pred == id or any(x.pred == d.pred for x in deps):
                continue
            probe = p.replace_task(replace(task, deps=()))
            if not schedule.can_link(probe, d.pred, id):
                raise LinkError("That would make the tasks wait for each other.")
            deps.append(Dependency(d.pred, d.kind, d.lag, d.strong))
        milestone = input.milestone and not summary
        changes = dict(
            name=input.name.strip() or task.name, color=input.color, notes=input.notes,
            web_link=input.web_link.strip(), cost=input.cost, deps=tuple(deps),
            milestone=milestone)
        if not summary:
            changes.update(start=p.calendar.next_working(input.start),
                           duration=0 if milestone else max(1, input.duration),
                           complete=max(0, min(100, input.complete)))
        p = p.replace_task(replace(task, **changes))
        if summary and input.start != task.start:
            p = schedule.move_to(p, id, input.start)
        allocations = tuple(a for a in p.allocations if a.task != id) + tuple(
            Allocation(id, a.resource, a.load, a.responsible)
            for a in input.assignments if p.resource(a.resource))
        self._commit(replace(p, allocations=allocations), group=f"task:{id}")

    def rename_task(self, id: int, name: str):
        if self._project.task(id) and name.strip():
            self._commit(self._project.update(id, name=name.strip()), group=f"name:{id}")

    def move_task(self, id: int, start: date):
        """Drag a bar: its start day (and everything under it) moves; followers are pushed."""
        p = self._project
        if p.task(id):
            self._commit(schedule.move_to(p, id, p.calendar.next_working(start)))

    def move_task_by(self, id: int, days: int):
        """Drag a bar by calendar days (it lands on a working day)."""
        t = self._project.task(id)
        if t and days:
            self.move_task(id, t.start + timedelta(days=days))

    def resize_task_to(self, id: int, last: date):
        """Drag a bar's right edge to the day work should end."""
        p = self._project
        t = p.task(id)
        if t and not p.is_summary(id) and not t.milestone:
            self.resize_task(id, p.calendar.duration_to_last(t.start, last))

    def resize_task(self, id: int, duration: int):
        p = self._project
        t = p.task(id)
        if t and not p.is_summary(id) and not t.milestone:
            self._commit(p.update(id, duration=max(1, duration)))

    def set_complete(self, id: int, percent: int):
        p = self._project
        percent = max(0, min(100, percent))
        if p.task(id) is None:
            return
        if p.is_summary(id):
            leaves = p.subtree(id)
            p = p.with_tasks(replace(t, complete=percent) if t.id in leaves
                             and not p.is_summary(t.id) else t for t in p.tasks)
        else:
            p = p.update(id, complete=percent)
        self._commit(p, group=f"done:{id}")

    def delete_tasks(self, ids):
        self._commit(self._project.without(set(ids)))

    def indent(self, id: int):
        if self._project.task(id):
            self._commit(structure.indent(self._project, id))

    def outdent(self, id: int):
        if self._project.task(id):
            self._commit(structure.outdent(self._project, id))

    def move_up(self, id: int):
        if self._project.task(id):
            self._commit(structure.move(self._project, id, -1))

    def move_down(self, id: int):
        if self._project.task(id):
            self._commit(structure.move(self._project, id, +1))

    def duplicate(self, id: int) -> int | None:
        p = self._project
        if p.task(id) is None:
            return None
        block = [t.id for t in p.tasks if t.id in p.subtree(id)]
        base = p.next_task_id()
        new_ids = {old: base + i for i, old in enumerate(block)}
        copies = [replace(t, uid=self._new_uid()) for t in structure.copy_subtree(p, id, new_ids)]
        copies[0] = replace(copies[0], name=copies[0].name + " (copy)")
        tasks = list(p.tasks)
        at = max(i for i, t in enumerate(tasks) if t.id in set(block)) + 1
        allocations = p.allocations + tuple(
            Allocation(new_ids[a.task], a.resource, a.load, a.responsible)
            for a in p.allocations if a.task in new_ids)
        self._commit(replace(p, tasks=tuple(tasks[:at] + copies + tasks[at:]),
                             allocations=allocations))
        return new_ids[id]

    def set_expanded(self, id: int, expanded: bool):
        """Fold or unfold a branch. Not an undo step, and not an unsaved change."""
        t = self._project.task(id)
        if t is None or t.expanded == expanded:
            return
        was_saved = not self.dirty
        self._project = self._project.update(id, expanded=expanded)
        if was_saved:
            self._saved = self._project
        else:
            self._undo = [(replace(u, tasks=tuple(
                replace(x, expanded=expanded) if x.id == id else x for x in u.tasks)), g)
                for u, g in self._undo]
        self._emit(Change.LAYOUT)

    # ---- dependencies ---------------------------------------------------------------------

    def can_link(self, pred: int, succ: int) -> bool:
        return schedule.can_link(self._project, pred, succ)

    def link(self, pred: int, succ: int, kind: DepKind = DepKind.FINISH_START, lag: int = 0):
        p = self._project
        if not schedule.can_link(p, pred, succ):
            raise LinkError("That would make the tasks wait for each other.")
        t = p.task(succ)
        deps = tuple(d for d in t.deps if d.pred != pred) + (Dependency(pred, kind, lag),)
        self._commit(p.update(succ, deps=deps))

    def unlink(self, pred: int, succ: int):
        t = self._project.task(succ)
        if t:
            self._commit(self._project.update(
                succ, deps=tuple(d for d in t.deps if d.pred != pred)))

    # ---- people ---------------------------------------------------------------------------

    def add_resource(self, input: ResourceInput) -> int:
        p = self._project
        id = p.next_resource_id()
        self._commit(replace(p, resources=p.resources + (Resource(
            id, input.name.strip() or "New person", input.role, input.email.strip(),
            input.phone.strip(), input.rate),)))
        return id

    def update_resource(self, id: int, input: ResourceInput):
        p = self._project
        r = p.resource(id)
        if r is None:
            raise NotFound("That person isn't there any more.")
        new = replace(r, name=input.name.strip() or r.name, role=input.role,
                      email=input.email.strip(), phone=input.phone.strip(), rate=input.rate)
        self._commit(replace(p, resources=tuple(new if x.id == id else x for x in p.resources)),
                     group=f"resource:{id}")

    def delete_resource(self, id: int):
        p = self._project
        self._commit(replace(
            p, resources=tuple(r for r in p.resources if r.id != id),
            allocations=tuple(a for a in p.allocations if a.resource != id),
            vacations=tuple(v for v in p.vacations if v.resource != id)))

    def assign(self, task: int, resource: int, load: float = 100.0):
        p = self._project
        if p.task(task) and p.resource(resource):
            rest = tuple(a for a in p.allocations
                         if not (a.task == task and a.resource == resource))
            self._commit(replace(p, allocations=rest + (Allocation(task, resource, load),)))

    def unassign(self, task: int, resource: int):
        p = self._project
        self._commit(replace(p, allocations=tuple(
            a for a in p.allocations if not (a.task == task and a.resource == resource))))

    def add_vacation(self, resource: int, start: date, end: date):
        p = self._project
        if p.resource(resource):
            first, last = min(start, end), max(start, end)
            self._commit(replace(p, vacations=p.vacations + (Vacation(resource, first, last),)))

    def remove_vacation(self, resource: int, start: date):
        p = self._project
        self._commit(replace(p, vacations=tuple(
            v for v in p.vacations if not (v.resource == resource and v.start == start))))
