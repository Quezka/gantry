"""Dates that follow from the tree and the dependencies, and the critical path.

Summary tasks (those with children) have no dates of their own: they span their children and
their progress is the children's, weighted by length. A task with dependencies is never
earlier than they allow; Gantry only ever pushes tasks later, so nothing you placed by hand
is pulled away.
"""
from __future__ import annotations

from dataclasses import replace

from .model import DepKind, Dependency, Project, Task


def _bounds(project: Project, by_id: dict, id: int, cache: dict) -> tuple[int, int]:
    """(first, end) in working-day numbers; end is exclusive."""
    if id in cache:
        return cache[id]
    cal = project.calendar
    kids = [t for t in project.tasks if t.parent == id]
    if kids:
        spans = [_bounds(project, by_id, k.id, cache) for k in kids]
        result = (min(s for s, _ in spans), max(f for _, f in spans))
    else:
        t = by_id[id]
        s = cal.index(t.start)
        result = (s, s + t.duration)
    cache[id] = result
    return result


def span(project: Project, id: int) -> tuple[int, int]:
    by_id = {t.id: t for t in project.tasks}
    return _bounds(project, by_id, id, {})


def roll_up(project: Project) -> Project:
    """Give every summary task the dates and progress of what's under it."""
    cal = project.calendar
    by_id = {t.id: t for t in project.tasks}
    kids: dict[int, list[Task]] = {}
    for t in project.tasks:
        if t.parent is not None:
            kids.setdefault(t.parent, []).append(t)
    if not kids:
        return project
    done: dict[int, Task] = {}

    def settle(t: Task) -> Task:
        if t.id in done:
            return done[t.id]
        children = [settle(by_id[k.id]) for k in kids.get(t.id, [])]
        if not children:
            done[t.id] = t
            return t
        start = min(c.start for c in children)
        first = cal.index(start)
        finish = max(cal.index(c.start) + c.duration for c in children)
        weight = sum(c.duration for c in children)
        complete = (round(sum(c.duration * c.complete for c in children) / weight) if weight
                    else round(sum(c.complete for c in children) / len(children)))
        out = replace(t, start=start, duration=max(0, finish - first), complete=complete,
                      milestone=False)
        done[t.id] = out
        return out

    return project.with_tasks(settle(t) for t in project.tasks)


def _leaves_under(project: Project, id: int) -> list[int]:
    ids = project.subtree(id)
    return [t.id for t in project.tasks if t.id in ids and not project.is_summary(t.id)]


def _earliest(t_span: tuple[int, int], dep: Dependency,
              pred_span: tuple[int, int]) -> int:
    ps, pf = pred_span
    duration = t_span[1] - t_span[0]
    if dep.kind is DepKind.FINISH_START:
        return pf + dep.lag
    if dep.kind is DepKind.START_START:
        return ps + dep.lag
    if dep.kind is DepKind.FINISH_FINISH:
        return pf + dep.lag - duration
    return ps + dep.lag - duration


def enforce(project: Project) -> Project:
    """Push tasks later until every dependency holds."""
    project = roll_up(project)
    for _ in range(len(project.tasks) + 2):
        cal = project.calendar
        by_id = {t.id: t for t in project.tasks}
        cache: dict = {}
        moved = False
        for t in project.tasks:
            if not t.deps:
                continue
            mine = _bounds(project, by_id, t.id, cache)
            need = max((_earliest(mine, d, _bounds(project, by_id, d.pred, cache))
                        for d in t.deps if d.pred in by_id), default=mine[0])
            if need <= mine[0]:
                continue
            shift = need - mine[0]
            for leaf in _leaves_under(project, t.id):
                lt = by_id[leaf]
                project = project.replace_task(
                    replace(lt, start=cal.date_at(cal.index(lt.start) + shift)))
            moved = True
            break  # recompute with the new dates
        if not moved:
            break
        project = roll_up(project)
    return project


def normalise(project: Project) -> Project:
    return enforce(project)


def reaches(project: Project, start: int, target: int) -> bool:
    """Does `target` come after `start` through dependencies (or the tree)?"""
    follows: dict[int, set[int]] = {}
    for t in project.tasks:
        for d in t.deps:
            follows.setdefault(d.pred, set()).add(t.id)
    for t in project.tasks:  # a summary can't finish before its children do, and vice versa
        if t.parent is not None:
            follows.setdefault(t.parent, set()).add(t.id)
    seen, todo = set(), [start]
    while todo:
        node = todo.pop()
        if node == target:
            return True
        if node in seen:
            continue
        seen.add(node)
        todo.extend(follows.get(node, ()))
    return False


def can_link(project: Project, pred: int, succ: int) -> bool:
    if pred == succ or project.task(pred) is None or project.task(succ) is None:
        return False
    if project.is_ancestor(pred, succ) or project.is_ancestor(succ, pred):
        return False
    return not reaches(project, succ, pred)


def critical(project: Project) -> set[int]:
    """Tasks with no slack on a chain of dependencies that decides when the project ends."""
    by_id = {t.id: t for t in project.tasks}
    leaves = [t.id for t in project.tasks if not project.is_summary(t.id)]
    if not leaves:
        return set()
    cal = project.calendar
    first = {i: cal.index(by_id[i].start) for i in leaves}
    dur = {i: by_id[i].duration for i in leaves}
    edges: list[tuple[int, int, Dependency]] = []  # (pred leaf, succ leaf, dep)
    for t in project.tasks:
        for d in t.deps:
            if d.pred in by_id:
                for p in _leaves_under(project, d.pred):
                    for s in _leaves_under(project, t.id):
                        edges.append((p, s, d))
    linked = {p for p, _s, _d in edges} | {s for _p, s, _d in edges}
    # Kahn's algorithm; a cycle means the dates can't be trusted, so say nothing.
    incoming = {i: 0 for i in leaves}
    for _p, s, _d in edges:
        incoming[s] += 1
    order, ready = [], [i for i in leaves if incoming[i] == 0]
    while ready:
        n = ready.pop()
        order.append(n)
        for p, s, _d in edges:
            if p == n:
                incoming[s] -= 1
                if incoming[s] == 0:
                    ready.append(s)
    if len(order) != len(leaves):
        return set()
    end = max(first[i] + dur[i] for i in leaves)
    latest_finish = {i: end for i in leaves}
    for n in reversed(order):
        for p, s, d in edges:
            if s != n:
                continue
            ls = latest_finish[s] - dur[s]
            if d.kind is DepKind.FINISH_START:
                bound = ls - d.lag
            elif d.kind is DepKind.START_START:
                bound = ls - d.lag + dur[p]
            elif d.kind is DepKind.FINISH_FINISH:
                bound = latest_finish[s] - d.lag
            else:
                bound = latest_finish[s] - d.lag + dur[p]
            latest_finish[p] = min(latest_finish[p], bound)
    result = {i for i in leaves if i in linked and latest_finish[i] - (first[i] + dur[i]) <= 0}
    for t in project.tasks:  # a summary is critical when anything under it is
        if project.is_summary(t.id) and any(i in result for i in _leaves_under(project, t.id)):
            result.add(t.id)
    return result


def shift_days(project: Project, id: int, days: int) -> Project:
    """Move a task (and what's under it) by working days."""
    cal = project.calendar
    for leaf in _leaves_under(project, id):
        t = project.task(leaf)
        project = project.replace_task(replace(t, start=cal.date_at(cal.index(t.start) + days)))
    return project


def move_to(project: Project, id: int, start) -> Project:
    t = project.task(id)
    cal = project.calendar
    target = cal.index(start)
    current = _bounds(project, {x.id: x for x in project.tasks}, id, {})[0] if (
        project.is_summary(id)) else cal.index(t.start)
    return shift_days(project, id, target - current)


__all__ = ["normalise", "roll_up", "enforce", "critical", "can_link", "reaches", "shift_days",
           "move_to", "span"]
