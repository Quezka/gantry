"""A sample project, built through the same use cases the UI uses."""
from __future__ import annotations

from datetime import date, timedelta

from .application.editor import Editor
from .application.inputs import AssignInput, ResourceInput, TaskInput
from .application.types import DepKind


def _monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


def website(editor: Editor):
    """A class project: build and launch a website, with a team of four."""
    start = _monday(editor.today()) - timedelta(days=7)
    editor.new("Class website")
    ana = editor.add_resource(ResourceInput("Ana", email="ana@example.com", rate=120))
    luca = editor.add_resource(ResourceInput("Luca", rate=100))
    sara = editor.add_resource(ResourceInput("Sara", rate=100))
    marco = editor.add_resource(ResourceInput("Marco", rate=80))

    colors = {}

    def task(name, day, length, parent=None, done=0, who=(), color="", milestone=False):
        color = color or colors.get(parent, "")
        colors[None] = ""
        id = editor.add_task(TaskInput(
            name, start + timedelta(days=day), length, done, color, milestone,
            assignments=tuple(AssignInput(r, 100) for r in who)), parent=parent)
        colors[id] = color
        return id

    plan = task("Planning", 0, 5, color="#5b5bd6")
    brief = task("Write the brief", 0, 2, plan, 100, (ana,))
    goals = task("Agree the goals", 0, 1, plan, 100, (ana, luca))
    map_ = task("Site map", 0, 2, plan, 100, (luca,))
    design = task("Design", 0, 5, color="#30a46c")
    wire = task("Wireframes", 0, 3, design, 80, (sara,))
    look = task("Colours and type", 0, 3, design, 40, (sara,))
    build = task("Build", 0, 10, color="#f5a524")
    html = task("Pages in HTML", 0, 5, build, 0, (luca, marco))
    style = task("Styling", 0, 4, build, 0, (marco,))
    forms = task("Contact form", 0, 3, build, 0, (luca,))
    test = task("Test on phones", 0, 3, color="#e5484d")
    launch = task("Launch", 0, 0, color="#e5484d", milestone=True)
    for pred, succ in ((brief, goals), (goals, map_), (map_, wire), (wire, look),
                       (look, html), (html, style), (html, forms), (style, test),
                       (forms, test), (test, launch)):
        editor.link(pred, succ)
    editor.link(map_, design, DepKind.FINISH_START)
    editor.link(design, build, DepKind.FINISH_START)
    editor.set_complete(brief, 100)
    editor.add_vacation(marco, start + timedelta(days=21), start + timedelta(days=25))
    editor.settle()
