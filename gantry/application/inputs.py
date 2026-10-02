"""What the UI sends to the use cases: plain values, no domain classes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..domain import DepKind


@dataclass(frozen=True)
class DepInput:
    pred: int
    kind: DepKind = DepKind.FINISH_START
    lag: int = 0
    strong: bool = True


@dataclass(frozen=True)
class AssignInput:
    resource: int
    load: float = 100.0
    responsible: bool = False


@dataclass(frozen=True)
class TaskInput:
    name: str
    start: date
    duration: int = 1
    complete: int = 0
    color: str = ""
    milestone: bool = False
    notes: str = ""
    web_link: str = ""
    cost: float | None = None
    deps: tuple[DepInput, ...] = ()
    assignments: tuple[AssignInput, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResourceInput:
    name: str
    role: str = ""
    email: str = ""
    phone: str = ""
    rate: float | None = None


@dataclass(frozen=True)
class ProjectInfo:
    name: str = ""
    company: str = ""
    web_link: str = ""
    description: str = ""


@dataclass(frozen=True)
class BrandingInput:
    school: str
    place: str
    logo: str | None = None
    on_exports: bool = True
