"""Reads and writes GanttProject (.gan) files.

A .gan file is XML. What Gantry understands becomes the project; everything else (the column
layout, custom columns, baselines, per-task extras…) is kept as it was and written back, so a
project that goes through Gantry still opens in GanttProject exactly as it was.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from ..application.errors import FileAccessError, FileFormatError
from ..domain import (
    Allocation, Calendar, DepKind, Dependency, Project, Resource, Role, Task, Vacation,
)

VERSION = "3.3.3309"
WEEK = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")  # the order of Python's weekday()
TASK_ATTRS = {"id", "uid", "name", "color", "meeting", "start", "duration", "complete", "expand",
              "webLink", "cost-manual-value", "cost-calculated"}
RESOURCE_ATTRS = {"id", "name", "function", "contacts", "phone"}
ROOT_KEPT = {"name", "company", "webLink"}


def _raw(element: ET.Element) -> str:
    clone = ET.fromstring(ET.tostring(element, encoding="unicode"))
    for e in clone.iter():
        e.tail = None
        if e.text is not None and not e.text.strip():
            e.text = None
    return ET.tostring(clone, encoding="unicode")


def _bool(value: str | None, default: bool = False) -> bool:
    return default if value is None else value.strip().lower() == "true"


def _int(value: str | None, default: int = 0) -> int:
    try:
        return int(float(value)) if value not in (None, "") else default
    except ValueError:
        return default


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _date(value: str | None) -> date:
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        raise FileFormatError("The file has a date that can't be read.") from None


def _kind(value: str | None) -> DepKind:
    try:
        return DepKind(int(value))
    except (TypeError, ValueError):
        return DepKind.FINISH_START


class GanFiles:
    # ---- reading ------------------------------------------------------------------------

    def read(self, path: str) -> Project:
        try:
            data = Path(path).read_bytes()
        except OSError as e:
            raise FileAccessError(f"Can't open the file: {e.strerror or e}") from None
        return self.decode(data)

    def decode(self, data: bytes) -> Project:
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            raise FileFormatError("That isn't a GanttProject file (.gan).") from None
        if root.tag != "project":
            raise FileFormatError("That isn't a GanttProject file (.gan).")
        extras: dict[str, str] = {"root": json.dumps(
            {k: v for k, v in root.attrib.items() if k not in ROOT_KEPT})}
        views = [_raw(e) for e in root.findall("view")]
        if views:
            extras["views"] = json.dumps(views)
        for tag in ("previous",):
            found = root.find(tag)
            if found is not None:
                extras[tag] = _raw(found)
        calendars = root.find("calendars")
        calendar = Calendar()
        if calendars is not None:
            extras["calendars"] = _raw(calendars)
            calendar = self._calendar(calendars)
        tasks_el = root.find("tasks")
        tasks: list[Task] = []
        successors: list[tuple[int, int, Dependency]] = []  # (pred, succ, dep)
        if tasks_el is not None:
            props = tasks_el.find("taskproperties")
            if props is not None:
                extras["taskproperties"] = _raw(props)
            extras["tasks"] = json.dumps(dict(tasks_el.attrib))
            for el in tasks_el.findall("task"):
                self._task(el, None, tasks, successors)
        by_id = {t.id: i for i, t in enumerate(tasks)}
        for pred, succ, dep in successors:
            if pred in by_id and succ in by_id:
                i = by_id[succ]
                tasks[i] = Task(**{**tasks[i].__dict__, "deps": tasks[i].deps + (dep,)})
        resources = tuple(self._resource(e) for e in root.findall("resources/resource"))
        allocations = tuple(
            Allocation(_int(a.get("task-id")), _int(a.get("resource-id")),
                       _float(a.get("load")) or 0.0, _bool(a.get("responsible")),
                       a.get("function", ""))
            for a in root.findall("allocations/allocation"))
        vacations = tuple(
            Vacation(_int(v.get("resourceid")), _date(v.get("start")), _date(v.get("end")))
            for v in root.findall("vacations/vacation"))
        roles, rolesets = [], []
        for el in root.findall("roles"):
            if el.find("role") is None:
                rolesets.append(_raw(el))
            roles += [Role(r.get("id", ""), r.get("name", "")) for r in el.findall("role")]
        if rolesets:
            extras["rolesets"] = json.dumps(rolesets)
        description = root.findtext("description") or ""
        return Project(name=root.get("name", ""), company=root.get("company", ""),
                       web_link=root.get("webLink", ""), description=description,
                       calendar=calendar, tasks=tuple(tasks), resources=resources,
                       allocations=allocations, vacations=vacations, roles=tuple(roles),
                       extras=extras)

    @staticmethod
    def _calendar(el: ET.Element) -> Calendar:
        off = frozenset()
        week = el.find("day-types/default-week")
        if week is not None:
            off = frozenset(i for i, name in enumerate(WEEK) if week.get(name) == "1")
        holidays, extra = set(), set()
        for d in el.findall("date"):
            try:
                day = date(int(d.get("year")), int(d.get("month")), int(d.get("date")))
            except (TypeError, ValueError):
                continue
            kind = d.get("type", "HOLIDAY")
            if kind == "HOLIDAY":
                holidays.add(day)
            elif kind == "WORKING_DAY":
                extra.add(day)
        return Calendar(off if week is not None else Calendar().off_weekdays,
                        frozenset(holidays), frozenset(extra))

    def _task(self, el, parent, out, successors):
        id = _int(el.get("id"))
        extras = {k: v for k, v in el.attrib.items() if k not in TASK_ATTRS}
        raw, notes = [], ""
        children = []
        for child in el:
            if child.tag == "task":
                children.append(child)
            elif child.tag == "notes":
                notes = child.text or ""
            elif child.tag == "depend":
                successors.append((id, _int(child.get("id")), Dependency(
                    id, _kind(child.get("type")), _int(child.get("difference")),
                    child.get("hardness", "Strong") != "Rubber")))
            else:
                raw.append(_raw(child))
        manual = _float(el.get("cost-manual-value"))
        cost = manual if (not _bool(el.get("cost-calculated")) and manual is not None) else None
        # `successors` holds (predecessor, successor, dep); the dep is stored on the successor
        task = Task(id=id, name=el.get("name", ""), start=_date(el.get("start")),
                    duration=max(0, _int(el.get("duration"))),
                    complete=max(0, min(100, _int(el.get("complete")))), parent=parent,
                    color=el.get("color", ""), milestone=_bool(el.get("meeting")),
                    expanded=_bool(el.get("expand"), True), notes=notes,
                    web_link=el.get("webLink", ""), cost=cost, uid=el.get("uid", ""),
                    extras=extras, raw=tuple(raw))
        out.append(task)
        for c in children:
            self._task(c, id, out, successors)

    @staticmethod
    def _resource(el: ET.Element) -> Resource:
        rate, raw = None, []
        for child in el:
            if child.tag == "rate" and child.get("name") == "standard" and rate is None:
                rate = _float(child.get("value"))
            else:
                raw.append(_raw(child))
        return Resource(_int(el.get("id")), el.get("name", ""), el.get("function", ""),
                        el.get("contacts", ""), el.get("phone", ""), rate,
                        {k: v for k, v in el.attrib.items() if k not in RESOURCE_ATTRS},
                        tuple(raw))

    # ---- writing ------------------------------------------------------------------------

    def encode(self, project: Project) -> bytes:
        x = project.extras
        attrs = json.loads(x.get("root", "{}"))
        root = ET.Element("project")
        root.set("name", project.name)
        root.set("company", project.company)
        root.set("webLink", project.web_link)
        for key in ("view-date", "view-index", "gantt-divider-location",
                    "resource-divider-location"):
            root.set(key, attrs.pop(key, {"view-date": date.today().isoformat(),
                                          "view-index": "0",
                                          "gantt-divider-location": "400",
                                          "resource-divider-location": "300"}[key]))
        root.set("version", attrs.pop("version", VERSION))
        root.set("locale", attrs.pop("locale", "en"))
        for key, value in attrs.items():
            root.set(key, value)
        ET.SubElement(root, "description").text = project.description or None
        for view in json.loads(x.get("views", "[]")):
            root.append(ET.fromstring(view))
        root.append(self._calendar_xml(project))
        tasks = ET.SubElement(root, "tasks")
        for key, value in json.loads(x.get("tasks", '{"empty-milestones": "true"}')).items():
            tasks.set(key, value)
        if "taskproperties" in x:
            tasks.append(ET.fromstring(x["taskproperties"]))
        followers: dict[int, list[Task]] = {}
        for t in project.tasks:
            for d in t.deps:
                followers.setdefault(d.pred, []).append(t)
        elements: dict[int, ET.Element] = {}
        for t in project.tasks:
            holder = elements[t.parent] if t.parent is not None else tasks
            elements[t.id] = self._task_xml(holder, t, followers.get(t.id, []))
        resources = ET.SubElement(root, "resources")
        for r in project.resources:
            el = ET.SubElement(resources, "resource", {
                "id": str(r.id), "name": r.name, "function": r.role,
                "contacts": r.email, "phone": r.phone, **r.extras})
            if r.rate is not None:
                ET.SubElement(el, "rate", {"name": "standard", "value": f"{r.rate:g}"})
            for raw in r.raw:
                el.append(ET.fromstring(raw))
        allocations = ET.SubElement(root, "allocations")
        for a in project.allocations:
            ET.SubElement(allocations, "allocation", {
                "task-id": str(a.task), "resource-id": str(a.resource),
                "function": a.role or (project.resource(a.resource).role
                                       if project.resource(a.resource) else ""),
                "responsible": str(a.responsible).lower(), "load": f"{a.load:g}"})
        vacations = ET.SubElement(root, "vacations")
        for v in project.vacations:
            ET.SubElement(vacations, "vacation", {
                "start": v.start.isoformat(), "end": v.end.isoformat(),
                "resourceid": str(v.resource)})
        root.append(ET.fromstring(x["previous"]) if "previous" in x else ET.Element("previous"))
        for raw in json.loads(x.get("rolesets", "[]")):
            root.append(ET.fromstring(raw))
        roles = ET.SubElement(root, "roles")
        for r in project.roles:
            ET.SubElement(roles, "role", {"id": r.id, "name": r.name})
        ET.indent(root, space="    ")
        return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8")

    @staticmethod
    def _task_xml(holder: ET.Element, t: Task, followers: list[Task]) -> ET.Element:
        el = ET.SubElement(holder, "task", {
            "id": str(t.id), "uid": t.uid or uuid.uuid4().hex, "name": t.name,
            "color": t.color or "#8cb6ce", "meeting": str(t.milestone).lower(),
            "start": t.start.isoformat(), "duration": str(t.duration),
            "complete": str(t.complete), "expand": str(t.expanded).lower()})
        if t.web_link:
            el.set("webLink", t.web_link)
        el.set("cost-manual-value", f"{t.cost:g}" if t.cost is not None else "0")
        el.set("cost-calculated", "false" if t.cost is not None else "true")
        for key, value in t.extras.items():
            el.set(key, value)
        if t.notes:
            ET.SubElement(el, "notes").text = t.notes
        for follower in followers:
            dep = next(d for d in follower.deps if d.pred == t.id)
            ET.SubElement(el, "depend", {
                "id": str(follower.id), "type": str(dep.kind.value),
                "difference": str(dep.lag), "hardness": "Strong" if dep.strong else "Rubber"})
        for raw in t.raw:
            el.append(ET.fromstring(raw))
        return el

    @staticmethod
    def _calendar_xml(project: Project) -> ET.Element:
        raw = project.extras.get("calendars")
        if raw:
            el = ET.fromstring(raw)
        else:
            el = ET.fromstring(
                "<calendars><day-types><day-type id=\"0\"/><day-type id=\"1\"/>"
                "<default-week id=\"1\" name=\"default\"/><only-show-weekends value=\"false\"/>"
                "<overriden-day-types/><days/></day-types></calendars>")
        cal = project.calendar
        week = el.find("day-types/default-week")
        if week is not None:
            for i, name in enumerate(WEEK):
                week.set(name, "1" if i in cal.off_weekdays else "0")
        for d in el.findall("date"):
            if d.get("type", "HOLIDAY") in ("HOLIDAY", "WORKING_DAY"):
                el.remove(d)
        for kind, days in (("HOLIDAY", cal.holidays), ("WORKING_DAY", cal.extra_days)):
            for d in sorted(days):
                ET.SubElement(el, "date", {"year": str(d.year), "month": str(d.month),
                                           "date": str(d.day), "type": kind})
        return el

    def write(self, path: str, data: bytes) -> None:
        target = Path(path)
        try:
            fd, temp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                os.replace(temp, target)
            except BaseException:
                Path(temp).unlink(missing_ok=True)
                raise
        except OSError as e:
            raise FileAccessError(f"Can't save the file: {e.strerror or e}") from None
