"""The project and what's in it: a tree of tasks with dependencies, people and a calendar.

Everything is immutable; every edit makes a new `Project`, which is what gives undo for free.
`extras` carry whatever a GanttProject file holds that Gantry doesn't use, untouched, so a
file saved by Gantry still opens in GanttProject with nothing lost.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from enum import Enum
from typing import Mapping

from .calendar import Calendar


class DepKind(Enum):
    """The value is what a .gan file stores."""
    START_START = 1
    FINISH_START = 2
    FINISH_FINISH = 3
    START_FINISH = 4


@dataclass(frozen=True)
class Dependency:
    """This task can't go before `pred`, as the kind says, plus `lag` working days."""
    pred: int
    kind: DepKind = DepKind.FINISH_START
    lag: int = 0
    strong: bool = True  # GanttProject's "Strong" / "Rubber"


@dataclass(frozen=True)
class Task:
    id: int
    name: str
    start: date
    duration: int = 1  # working days; 0 for a milestone
    complete: int = 0
    parent: int | None = None
    color: str = ""
    milestone: bool = False
    expanded: bool = True
    notes: str = ""
    web_link: str = ""
    cost: float | None = None  # a fixed cost; None: worked out from the people on it
    deps: tuple[Dependency, ...] = ()
    uid: str = ""
    extras: Mapping[str, str] = field(default_factory=dict)  # attributes Gantry doesn't use
    raw: tuple[str, ...] = ()  # child elements Gantry doesn't use (XML text)


@dataclass(frozen=True)
class Resource:
    id: int
    name: str
    role: str = ""  # a role id as the file writes it
    email: str = ""
    phone: str = ""
    rate: float | None = None  # per working day
    extras: Mapping[str, str] = field(default_factory=dict)
    raw: tuple[str, ...] = ()


@dataclass(frozen=True)
class Allocation:
    task: int
    resource: int
    load: float = 100.0  # percent of the resource's day
    responsible: bool = False
    role: str = ""


@dataclass(frozen=True)
class Vacation:
    resource: int
    start: date
    end: date  # the last day off


@dataclass(frozen=True)
class Role:
    id: str
    name: str


@dataclass(frozen=True)
class Project:
    name: str = ""
    company: str = ""
    web_link: str = ""
    description: str = ""
    calendar: Calendar = field(default_factory=Calendar)
    tasks: tuple[Task, ...] = ()  # parents before their children, siblings in order
    resources: tuple[Resource, ...] = ()
    allocations: tuple[Allocation, ...] = ()
    vacations: tuple[Vacation, ...] = ()
    roles: tuple[Role, ...] = ()
    extras: Mapping[str, str] = field(default_factory=dict)  # file-level things we keep as is

    # ---- looking things up -----------------------------------------------------------

    def task(self, id: int) -> Task | None:
        return next((t for t in self.tasks if t.id == id), None)

    def children(self, id: int | None) -> list[Task]:
        return [t for t in self.tasks if t.parent == id]

    def is_summary(self, id: int) -> bool:
        return any(t.parent == id for t in self.tasks)

    def subtree(self, id: int) -> set[int]:
        """The task and everything under it."""
        found = {id}
        for t in self.tasks:  # parents come first
            if t.parent in found:
                found.add(t.id)
        return found

    def is_ancestor(self, ancestor: int, of: int) -> bool:
        by_id = {t.id: t for t in self.tasks}
        node = by_id.get(of)
        while node is not None and node.parent is not None:
            if node.parent == ancestor:
                return True
            node = by_id.get(node.parent)
        return False

    def depth(self, id: int) -> int:
        by_id = {t.id: t for t in self.tasks}
        d, node = 0, by_id.get(id)
        while node is not None and node.parent is not None:
            d += 1
            node = by_id.get(node.parent)
        return d

    def next_task_id(self) -> int:
        return max((t.id for t in self.tasks), default=-1) + 1

    def next_resource_id(self) -> int:
        return max((r.id for r in self.resources), default=-1) + 1

    def resource(self, id: int) -> Resource | None:
        return next((r for r in self.resources if r.id == id), None)

    # ---- changing things (each returns a new project) --------------------------------

    def replace_task(self, task: Task) -> "Project":
        return replace(self, tasks=tuple(task if t.id == task.id else t for t in self.tasks))

    def update(self, id: int, **changes) -> "Project":
        task = self.task(id)
        return self.replace_task(replace(task, **changes)) if task else self

    def with_tasks(self, tasks) -> "Project":
        return replace(self, tasks=tuple(tasks))

    def inserted(self, task: Task, after: int | None = None) -> "Project":
        """Add `task` as the last child of its parent, or right after the subtree of `after`."""
        tasks = list(self.tasks)
        if after is not None and any(t.id == after for t in tasks):
            keep = self.subtree(after)
            at = max(i for i, t in enumerate(tasks) if t.id in keep) + 1
        elif task.parent is not None:
            keep = self.subtree(task.parent)
            at = max(i for i, t in enumerate(tasks) if t.id in keep) + 1
        else:
            at = len(tasks)
        tasks.insert(at, task)
        return self.with_tasks(tasks)

    def without(self, ids: set[int]) -> "Project":
        """Drop tasks (and what's under them), and everything that pointed at them."""
        gone = set().union(*(self.subtree(i) for i in ids)) if ids else set()
        tasks = tuple(replace(t, deps=tuple(d for d in t.deps if d.pred not in gone))
                      for t in self.tasks if t.id not in gone)
        return replace(self, tasks=tasks,
                       allocations=tuple(a for a in self.allocations if a.task not in gone))
