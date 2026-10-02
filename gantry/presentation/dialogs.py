"""The task sheet (read-only view) and the editors for tasks and people."""
from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QTextBrowser, QToolButton,
    QVBoxLayout, QWidget,
)

from ..application.inputs import AssignInput, DepInput, ResourceInput, TaskInput
from ..application.records import ProjectRecord, ResourceRecord, TaskRecord
from ..application.types import KIND_CODES, PALETTE, DepKind
from . import theme
from .formatting import dep_label, day_label, money, pydate, qdate, range_text
from .i18n import _, plural
from .views.common import Segmented, button, caption, label, primary_button


def chip(text: str, role: str = "chip") -> QLabel:
    return QLabel(text, objectName=role)


class TaskSheet(QDialog):
    """Double-click a task: everything about it, read-only. E edits, Space marks it done."""

    def __init__(self, task: TaskRecord, project: ProjectRecord, today, parent=None):
        super().__init__(parent)
        self.action: str | None = None
        self.setWindowTitle(task.name)
        self.setMinimumWidth(520)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        if task.milestone:
            chips.addWidget(chip(_("Milestone")))
        elif task.summary:
            chips.addWidget(chip(_("Group")))
        chips.addWidget(chip(range_text(task.start, task.end, today)))
        if not task.milestone:
            chips.addWidget(chip(plural(task.duration, "day")))
            chips.addWidget(chip(f"{task.complete}%"))
        if task.late:
            chips.addWidget(chip(_("Late"), "chipDanger"))
        if task.critical:
            chips.addWidget(chip(_("Critical path"), "chipDanger"))
        chips.addStretch()
        title = QLabel(task.name, objectName="sheetTitle")
        title.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)
        layout.addLayout(chips)
        layout.addWidget(title)

        body = QVBoxLayout()
        body.setSpacing(10)
        if task.deps:
            body.addWidget(caption(_("Waits for")))
            for d in task.deps:
                lag = f" {d.lag:+d}" if d.lag else ""
                body.addWidget(QLabel(f"{d.pred_name}  ·  {KIND_CODES[d.kind]}{lag}"))
        followers = [t for t in project.tasks if task.id in {d.pred for d in t.deps}]
        if followers:
            body.addWidget(caption(_("Then")))
            for f in followers:
                body.addWidget(QLabel(f.name))
        if task.assignments:
            body.addWidget(caption(_("People")))
            for a in task.assignments:
                body.addWidget(QLabel(f"{a.name}  ·  {a.load:g}%"))
        if task.cost:
            body.addWidget(caption(_("Cost")))
            body.addWidget(QLabel(money(task.cost)))
        if task.web_link:
            body.addWidget(caption(_("Link")))
            link = QLabel(f"<a href='{task.web_link}'>{task.web_link}</a>")
            link.setOpenExternalLinks(True)
            body.addWidget(link)
        layout.addLayout(body)
        if task.notes.strip():
            notes = QTextBrowser(objectName="sheetBody")
            notes.setPlainText(task.notes)
            notes.setMinimumHeight(90)
            layout.addWidget(notes)
        elif not (task.deps or followers or task.assignments):
            layout.addWidget(label(_("No notes yet. Press E to add some."), "hint"))

        delete = button(_("Delete"), "trash")
        delete.setObjectName("danger")
        delete.clicked.connect(lambda: self._finish("delete"))
        edit = button(_("Edit"), "edit")
        edit.clicked.connect(lambda: self._finish("edit"))
        done = primary_button(_("Mark not done") if task.complete == 100 else _("Mark done"),
                              "check")
        done.setEnabled(not task.summary)
        done.clicked.connect(lambda: self._finish("done"))
        row = QHBoxLayout()
        row.addWidget(delete)
        row.addStretch()
        row.addWidget(edit)
        row.addWidget(done)
        layout.addLayout(row)
        QShortcut(QKeySequence("E"), self, activated=lambda: self._finish("edit"))
        if not task.summary:
            QShortcut(QKeySequence(Qt.Key_Space), self, activated=lambda: self._finish("done"))

    def _finish(self, action: str):
        self.action = action
        self.accept()


class Swatches(QWidget):
    """A row of round colour choices."""

    def __init__(self, value: str, parent=None):
        super().__init__(parent)
        self.value = value if value in PALETTE else value or ""
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.buttons: dict[str, QToolButton] = {}
        colors = list(PALETTE)
        if self.value and self.value not in colors:
            colors.insert(1, self.value)
        for c in colors:
            b = QToolButton(checkable=True)
            b.setFixedSize(26, 26)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(_("Default") if not c else c)
            b.clicked.connect(lambda _c=False, c=c: self.pick(c))
            self.buttons[c] = b
            row.addWidget(b)
        row.addStretch()
        theme.themed(self._style)
        self.pick(self.value, quiet=True)

    def _style(self, t):
        for c, b in self.buttons.items():
            fill = c or t.accent
            ring = t.text if b.isChecked() else "transparent"
            b.setStyleSheet(f"QToolButton{{background:{fill};border:2px solid {ring};"
                            f"border-radius:13px;padding:0;}}")

    def pick(self, color: str, quiet: bool = False):
        self.value = color
        for c, b in self.buttons.items():
            b.setChecked(c == color)
        self._style(theme.current())


class TaskEditor(QDialog):
    def __init__(self, editor, task: TaskRecord | None, project: ProjectRecord,
                 after: int | None = None, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.task = task
        self.project = project
        self.after = after
        self.setWindowTitle(_("Edit task") if task else _("New task"))
        self.setMinimumWidth(580)
        today = editor.today()
        summary = bool(task and task.summary)
        start = task.start if task else today
        if task is None and after is not None:
            near = next((t for t in project.tasks if t.id == after), None)
            start = near.start if near else today

        self.name = QLineEdit(task.name if task else "", objectName="titleEdit",
                              placeholderText=_("What needs doing?"))
        self.start = QDateEdit(qdate(start), calendarPopup=True)
        self.start.setDisplayFormat("d MMM yyyy")
        self.duration = QSpinBox(minimum=1, maximum=9999, value=max(1, task.duration if task else 1),
                                 suffix=_(" days"))
        self.end = QDateEdit(calendarPopup=True)
        self.end.setDisplayFormat("d MMM yyyy")
        self.milestone = QCheckBox(_("Milestone (a moment, not a stretch of work)"))
        self.milestone.setChecked(bool(task and task.milestone))
        self.complete = QSpinBox(minimum=0, maximum=100, value=task.complete if task else 0,
                                 suffix="%")
        self.note = label("", "hint")

        quick = QHBoxLayout()
        quick.setSpacing(6)
        for text, days in ((_("Today"), 0), (_("Tomorrow"), 1), (_("Next Monday"), None)):
            b = button(text)
            b.clicked.connect(lambda _c=False, days=days: self._quick(days))
            quick.addWidget(b)
        quick.addStretch()

        def column(title, widget):
            box = QVBoxLayout()
            box.setSpacing(4)
            box.addWidget(caption(title))
            box.addWidget(widget)
            return box

        times = QHBoxLayout()
        times.setSpacing(10)
        times.addLayout(column(_("Starts"), self.start), 2)
        times.addLayout(column(_("Length"), self.duration), 1)
        times.addLayout(column(_("Ends"), self.end), 2)
        times.addLayout(column(_("Done"), self.complete), 1)

        self.when = QWidget()
        when = QVBoxLayout(self.when)
        when.setContentsMargins(0, 0, 0, 0)
        when.setSpacing(8)
        when.addLayout(times)
        when.addLayout(quick)
        when.addWidget(self.note)

        self.colors = Swatches(task.color if task else "")
        self.link = QLineEdit(task.web_link if task else "", placeholderText="https://…")
        self.notes = QPlainTextEdit(task.notes if task else "", minimumHeight=80,
                                    placeholderText=_("Notes"))
        self.fixed = QCheckBox(_("Fixed cost"))
        self.fixed.setChecked(bool(task and task.cost_fixed))
        self.cost = QDoubleSpinBox(maximum=1e9, decimals=2, value=task.cost if task else 0.0)
        self.cost.setEnabled(self.fixed.isChecked())
        self.fixed.toggled.connect(self.cost.setEnabled)
        cost_row = QHBoxLayout()
        cost_row.addWidget(self.fixed)
        cost_row.addWidget(self.cost)
        cost_row.addStretch()

        self.dep_rows: list[tuple[QComboBox, QComboBox, QSpinBox, QWidget]] = []
        self.deps_box = QVBoxLayout()
        self.deps_box.setSpacing(6)
        self.candidates = [t for t in project.tasks if not task or (
            t.id != task.id and not self._inside(task.id, t))]
        for d in (task.deps if task else ()):
            self._add_dep(d.pred, d.kind, d.lag)
        add_dep = button(_("Add a task it waits for"), "plus")
        add_dep.clicked.connect(lambda: self._add_dep(None, DepKind.FINISH_START, 0))
        add_dep.setEnabled(bool(self.candidates))

        self.people: list[tuple[ResourceRecord, QCheckBox, QSpinBox]] = []
        people_box = QVBoxLayout()
        people_box.setSpacing(6)
        have = {a.resource: a for a in (task.assignments if task else ())}
        for r in project.resources:
            check = QCheckBox(r.name)
            check.setChecked(r.id in have)
            load = QSpinBox(minimum=1, maximum=1000, suffix="%",
                            value=int(have[r.id].load) if r.id in have else 100)
            load.setEnabled(check.isChecked())
            check.toggled.connect(load.setEnabled)
            row = QHBoxLayout()
            row.addWidget(check, 1)
            row.addWidget(load)
            people_box.addLayout(row)
            self.people.append((r, check, load))
        if not project.resources:
            people_box.addWidget(label(_("Add people on the Resources page first."), "hint"))

        content = QWidget()
        form = QVBoxLayout(content)
        form.setContentsMargins(0, 0, 8, 0)
        form.setSpacing(12)
        form.addWidget(self.name)
        form.addWidget(self.when)
        form.addWidget(self.milestone)
        form.addWidget(caption(_("Colour")))
        form.addWidget(self.colors)
        form.addWidget(caption(_("Waits for")))
        form.addLayout(self.deps_box)
        form.addWidget(add_dep, 0, Qt.AlignLeft)
        form.addWidget(caption(_("People")))
        form.addLayout(people_box)
        form.addWidget(caption(_("Notes")))
        form.addWidget(self.notes)
        form.addLayout(cost_row)
        form.addWidget(self.link)
        form.addStretch()
        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(content)
        scroll.setFrameShape(QFrame.NoFrame)

        cancel = button(_("Cancel"))
        cancel.clicked.connect(self.reject)
        self.save = primary_button(_("Save") if task else _("Add task"), "check")
        self.save.setDefault(True)
        self.save.clicked.connect(self._accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(self.save)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(scroll, 1)
        layout.addLayout(row)
        self.resize(600, 700)

        self._settle(initial=True)
        self.start.dateChanged.connect(lambda _d: self._settle())
        self.duration.valueChanged.connect(lambda _v: self._settle())
        self.end.userDateChanged.connect(self._end_edited)
        self.milestone.toggled.connect(lambda _c: self._settle())
        if summary:
            for w in (self.duration, self.end, self.complete, self.milestone):
                w.setEnabled(False)
            self.cost.setEnabled(False)
            self.fixed.setEnabled(False)
            for _r, check, load in self.people:
                check.setEnabled(False)
                load.setEnabled(False)
        self.name.setFocus()
        self.name.selectAll()

    def _inside(self, id: int, t: TaskRecord) -> bool:
        """Is `t` the task, or somewhere under it?"""
        node = t
        by_id = {x.id: x for x in self.project.tasks}
        while node is not None:
            if node.id == id:
                return True
            node = by_id.get(node.parent) if node.parent is not None else None
        return False

    def _add_dep(self, pred, kind, lag):
        pick = QComboBox()
        for t in self.candidates:
            pick.addItem(f"{t.wbs}  {t.name}", t.id)
        if pred is not None:
            pick.setCurrentIndex(max(0, pick.findData(pred)))
        how = QComboBox()
        for k, code in KIND_CODES.items():
            how.addItem(f"{code}  {dep_label(code)}", k)
        how.setCurrentIndex(max(0, how.findData(kind)))
        gap = QSpinBox(minimum=-999, maximum=999, value=lag, suffix=_(" d"))
        gap.setToolTip(_("Extra working days between the two (negative: overlap)"))
        remove = QToolButton(objectName="icon")
        theme.set_icon(remove, "x", "muted")
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(pick, 3)
        row.addWidget(how, 2)
        row.addWidget(gap)
        row.addWidget(remove)
        entry = (pick, how, gap, holder)
        remove.clicked.connect(lambda: self._remove_dep(entry))
        self.dep_rows.append(entry)
        self.deps_box.addWidget(holder)

    def _remove_dep(self, entry):
        self.dep_rows.remove(entry)
        entry[3].deleteLater()

    def _quick(self, days):
        today = self.editor.today()
        d = today + timedelta(days=days) if days is not None else today + timedelta(
            days=7 - today.weekday())
        self.start.setDate(qdate(d))

    def _settle(self, initial: bool = False):
        milestone = self.milestone.isChecked()
        self.duration.setEnabled(not milestone and not (self.task and self.task.summary))
        self.end.setEnabled(self.duration.isEnabled())
        first, last = self.editor.preview(pydate(self.start.date()),
                                          0 if milestone else self.duration.value())
        self.end.blockSignals(True)
        self.end.setDate(qdate(last))
        self.end.blockSignals(False)
        chosen = pydate(self.start.date())
        self.note.setText(_("{day} is a day off, so it starts on {first}.").format(
            day=day_label(chosen), first=day_label(first)) if first != chosen else "")

    def _end_edited(self, qd: QDate):
        days = self.editor.duration_for(pydate(self.start.date()), pydate(qd))
        self.duration.blockSignals(True)
        self.duration.setValue(days)
        self.duration.blockSignals(False)
        self._settle()

    def to_input(self) -> TaskInput:
        deps = tuple(DepInput(p.currentData(), k.currentData(), g.value())
                     for p, k, g, _h in self.dep_rows if p.currentData() is not None)
        people = tuple(AssignInput(r.id, load.value()) for r, check, load in self.people
                       if check.isChecked())
        milestone = self.milestone.isChecked()
        return TaskInput(
            name=self.name.text(), start=pydate(self.start.date()),
            duration=0 if milestone else self.duration.value(), complete=self.complete.value(),
            color=self.colors.value, milestone=milestone, notes=self.notes.toPlainText(),
            web_link=self.link.text(), cost=self.cost.value() if self.fixed.isChecked() else None,
            deps=deps, assignments=people)

    def _accept(self):
        if not self.name.text().strip():
            self.name.setFocus()
            self.name.setStyleSheet(f"border-color: {theme.current().danger};")
            return
        self.accept()


class ResourceEditor(QDialog):
    def __init__(self, project: ProjectRecord, resource: ResourceRecord | None = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Edit person") if resource else _("New person"))
        self.setMinimumWidth(440)
        self.name = QLineEdit(resource.name if resource else "", objectName="titleEdit",
                              placeholderText=_("Name"))
        self.role = QComboBox()
        self.role.addItem(_("No role"), "")
        for r in project.roles:
            self.role.addItem(r.name, r.id)
        if resource and resource.role and self.role.findData(resource.role) < 0:
            self.role.addItem(resource.role_name or resource.role, resource.role)
        if resource:
            self.role.setCurrentIndex(max(0, self.role.findData(resource.role)))
        self.email = QLineEdit(resource.email if resource else "", placeholderText="name@example.com")
        self.phone = QLineEdit(resource.phone if resource else "")
        self.fixed = QCheckBox(_("Charges by the day"))
        self.fixed.setChecked(bool(resource and resource.rate is not None))
        self.rate = QDoubleSpinBox(maximum=1e9, decimals=2, value=(resource.rate or 0.0) if resource else 0.0)
        self.rate.setEnabled(self.fixed.isChecked())
        self.fixed.toggled.connect(self.rate.setEnabled)

        def field(title, widget):
            box = QVBoxLayout()
            box.setSpacing(4)
            box.addWidget(caption(title))
            box.addWidget(widget)
            return box

        cancel = button(_("Cancel"))
        cancel.clicked.connect(self.reject)
        save = primary_button(_("Save") if resource else _("Add person"), "check")
        save.setDefault(True)
        save.clicked.connect(self._accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(save)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(self.name)
        layout.addLayout(field(_("Role"), self.role))
        two = QHBoxLayout()
        two.setSpacing(10)
        two.addLayout(field(_("Email"), self.email))
        two.addLayout(field(_("Phone"), self.phone))
        layout.addLayout(two)
        rate = QHBoxLayout()
        rate.addWidget(self.fixed)
        rate.addWidget(self.rate)
        rate.addStretch()
        layout.addLayout(rate)
        layout.addLayout(row)
        self.name.setFocus()

    def _accept(self):
        if self.name.text().strip():
            self.accept()
        else:
            self.name.setFocus()

    def to_input(self) -> ResourceInput:
        return ResourceInput(self.name.text(), self.role.currentData() or "", self.email.text(),
                             self.phone.text(), self.rate.value() if self.fixed.isChecked() else None)


def color_of(text: str, t: theme.Theme) -> QColor:
    c = QColor(text) if text else QColor(t.accent)
    return c if c.isValid() else QColor(t.accent)
