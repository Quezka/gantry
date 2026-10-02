"""Reshaping the task tree: indent, outdent, move up and down, copy."""
from __future__ import annotations

from dataclasses import replace

from .model import Project, Task


def _order(project: Project, ids: set[int]) -> list[int]:
    return [t.id for t in project.tasks if t.id in ids]


def indent(project: Project, id: int) -> Project:
    """Make the task a child of the task just above it (at the same level)."""
    task = project.task(id)
    siblings = project.children(task.parent)
    at = [s.id for s in siblings].index(id)
    if at == 0:
        return project
    above = siblings[at - 1]
    moved = project.update(id, parent=above.id)
    # it now sits at the end of `above`'s children
    tasks = [t for t in moved.tasks if t.id not in moved.subtree(id)]
    block = [t for t in moved.tasks if t.id in moved.subtree(id)]
    keep = moved.subtree(above.id) - moved.subtree(id)
    end = max(i for i, t in enumerate(tasks) if t.id in keep) + 1
    return project.with_tasks(tasks[:end] + block + tasks[end:]).update(
        above.id, expanded=True).update(id, parent=above.id)


def outdent(project: Project, id: int) -> Project:
    """Make the task a sibling of its parent, right after it."""
    task = project.task(id)
    if task.parent is None:
        return project
    parent = project.task(task.parent)
    block_ids = project.subtree(id)
    rest = [t for t in project.tasks if t.id not in block_ids]
    block = [replace(t, parent=parent.parent) if t.id == id else t
             for t in project.tasks if t.id in block_ids]
    parent_ids = project.subtree(parent.id) - block_ids
    # later siblings under the same parent stay inside it
    end = max(i for i, t in enumerate(rest) if t.id in parent_ids) + 1
    return project.with_tasks(rest[:end] + block + rest[end:])


def move(project: Project, id: int, direction: int) -> Project:
    """Swap the task (with what's under it) with the sibling above (-1) or below (+1)."""
    task = project.task(id)
    siblings = [s.id for s in project.children(task.parent)]
    at = siblings.index(id)
    other = at + direction
    if not 0 <= other < len(siblings):
        return project
    a, b = (id, siblings[other]) if direction > 0 else (siblings[other], id)
    block_a, block_b = project.subtree(a), project.subtree(b)
    tasks = list(project.tasks)
    first = min(i for i, t in enumerate(tasks) if t.id in block_a)
    last = max(i for i, t in enumerate(tasks) if t.id in block_b)
    window = tasks[first:last + 1]
    ordered = ([t for t in window if t.id in block_b] + [t for t in window if t.id in block_a])
    return project.with_tasks(tasks[:first] + ordered + tasks[last + 1:])


def copy_subtree(project: Project, id: int, new_ids: dict[int, int]) -> list[Task]:
    """Copies of the task and what's under it, with ids from `new_ids`; dependencies inside the
    copied part follow the copies, those on the outside stay as they were."""
    block = project.subtree(id)
    out = []
    for t in project.tasks:
        if t.id not in block:
            continue
        deps = tuple(replace(d, pred=new_ids.get(d.pred, d.pred)) for d in t.deps)
        parent = new_ids.get(t.parent, t.parent) if t.id != id else t.parent
        out.append(replace(t, id=new_ids[t.id], parent=parent, deps=deps, uid=""))
    return out


def relocate(project: Project, id: int, parent: int | None, before: int | None = None) -> Project:
    """Put the task (with what's under it) inside `parent` (None: top level), right before
    the sibling `before`, or last when there is none. A task can't go inside itself."""
    block_ids = project.subtree(id)
    if parent in block_ids:
        return project
    rest = [t for t in project.tasks if t.id not in block_ids]
    block = [replace(t, parent=parent) if t.id == id else t
             for t in project.tasks if t.id in block_ids]
    if before is not None and before not in block_ids and any(t.id == before for t in rest):
        at = next(i for i, t in enumerate(rest) if t.id == before)
    elif parent is None:
        at = len(rest)
    else:
        inside = project.subtree(parent) - block_ids
        at = max(i for i, t in enumerate(rest) if t.id in inside) + 1
    moved = project.with_tasks(rest[:at] + block + rest[at:])
    return moved.update(parent, expanded=True) if parent is not None else moved
