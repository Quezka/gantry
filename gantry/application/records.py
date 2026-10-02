"""What the UI gets back: read-only snapshots of the project."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..domain import DepKind


@dataclass(frozen=True)
class DepRecord:
    pred: int
    pred_name: str
    kind: DepKind
    lag: int
    strong: bool


@dataclass(frozen=True)
class AssignmentRecord:
    resource: int
    name: str
    load: float
    responsible: bool


@dataclass(frozen=True)
class TaskRecord:
    id: int
    name: str
    parent: int | None
    depth: int
    wbs: str  # "2.1.3": where it sits in the tree
    start: date
    end: date  # the last day of work
    duration: int  # working days
    complete: int
    color: str
    milestone: bool
    summary: bool
    expanded: bool
    critical: bool
    late: bool  # should be finished by now, and isn't
    notes: str
    web_link: str
    cost: float
    cost_fixed: bool
    deps: tuple[DepRecord, ...]
    assignments: tuple[AssignmentRecord, ...]
    successors: tuple[int, ...]


@dataclass(frozen=True)
class ResourceRecord:
    id: int
    name: str
    role: str
    role_name: str
    email: str
    phone: str
    rate: float | None
    tasks: int
    peak_load: float  # the busiest day, in percent
    overloaded: bool


@dataclass(frozen=True)
class RoleRecord:
    id: str
    name: str


@dataclass(frozen=True)
class VacationRecord:
    resource: int
    resource_name: str
    start: date
    end: date


@dataclass(frozen=True)
class ProjectRecord:
    name: str
    company: str
    web_link: str
    description: str
    tasks: tuple[TaskRecord, ...]
    resources: tuple[ResourceRecord, ...]
    roles: tuple[RoleRecord, ...]
    vacations: tuple[VacationRecord, ...]
    off_weekdays: tuple[int, ...]
    holidays: tuple[date, ...]
    start: date | None
    finish: date | None
    duration: int  # working days from start to finish
    complete: int
    cost: float
    late: int  # how many tasks are late
    empty: bool


@dataclass(frozen=True)
class WorkloadRecord:
    resource: int
    days: tuple[tuple[date, float, bool], ...]  # (day, percent booked, on vacation)


@dataclass(frozen=True)
class BrandingRecord:
    school: str
    place: str
    logo: str | None  # a picture file; None means the built-in school emblem
    on_exports: bool  # put the school's name and emblem on exported charts
