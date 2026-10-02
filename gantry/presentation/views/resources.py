"""People: who is on the project, how busy they are, and when they're away."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDateEdit, QHBoxLayout, QListWidget, QListWidgetItem, QMessageBox, QSplitter, QVBoxLayout,
    QWidget,
)

from ...application.records import ProjectRecord, ResourceRecord
from ...application.services import Services
from .. import theme
from ..dialogs import ResourceEditor
from ..formatting import money, pydate, qdate, range_text, short_date
from ..i18n import _, plural
from .common import Card, Page, button, caption, icon_button, label, primary_button


class WorkloadChart(QWidget):
    """How booked someone is, day by day (or week by week when the span is long)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self.days: tuple = ()
        self.today = date.today()

    def set_days(self, days, today):
        self.days = days
        self.today = today
        self.update()

    def paintEvent(self, _event):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height() - 22
        if not self.days:
            return
        weekly = len(self.days) > 120
        cols = []
        if weekly:
            for i in range(0, len(self.days), 7):
                chunk = self.days[i:i + 7]
                cols.append((chunk[0][0], max(c[1] for c in chunk), all(c[2] for c in chunk)))
        else:
            cols = [(d, load, away) for d, load, away in self.days]
        top = max(150.0, max(c[1] for c in cols) * 1.1)
        cw = w / len(cols)
        y100 = h - h * 100 / top
        for i, (d, load, away) in enumerate(cols):
            x = i * cw
            if away:
                p.fillRect(QRectF(x, 0, cw, h), QColor(t.raised))
            if load:
                bh = h * load / top
                color = QColor(t.danger if load > 100 else t.accent)
                p.setPen(Qt.NoPen)
                p.setBrush(color)
                p.drawRoundedRect(QRectF(x + 1, h - bh, max(cw - 2, 1), bh), 2, 2)
        p.setPen(QPen(QColor(t.faint), 1, Qt.DashLine))
        p.drawLine(QPointF(0, y100), QPointF(w, y100))
        p.setPen(QColor(t.faint))
        p.drawText(QRectF(4, y100 - 16, 60, 14), Qt.AlignLeft, "100%")
        # today
        for i, (d, _l, _a) in enumerate(cols):
            if d <= self.today < d + timedelta(days=7 if weekly else 1):
                p.setPen(QPen(QColor(t.accent), 1.5))
                p.drawLine(QPointF(i * cw + cw / 2, 0), QPointF(i * cw + cw / 2, h))
        p.setPen(QColor(t.muted))
        step = max(1, len(cols) // 8)
        for i in range(0, len(cols), step):
            p.drawText(QRectF(i * cw, h + 4, 90, 16), Qt.AlignLeft, short_date(cols[i][0]))


class ResourcesPage(Page):
    def __init__(self, services: Services, parent=None):
        super().__init__(parent)
        self.services = services
        self.editor = services.editor
        self.title.setText(_("Resources"))
        self.subtitle.setText(_("The people on the project"))
        self.record: ProjectRecord | None = None
        add = primary_button(_("Add person"))
        add.clicked.connect(self.add_person)
        self.add_actions(add)

        self.list = QListWidget()
        self.list.setSpacing(2)
        self.list.currentItemChanged.connect(lambda *_a: self._show())
        self.list.itemDoubleClicked.connect(lambda _i: self.edit_person())
        left = Card(_("People"))
        left.add(self.list, 1)
        self.empty = label(_("Nobody yet. Add the people who work on this project, then give "
                             "them tasks."), "hint")
        self.empty.setWordWrap(True)
        left.add(self.empty)

        self.name = label("", "sheetTitle")
        self.detail = label("", "pageSubtitle")
        self.chart = WorkloadChart()
        self.warning = label("", "danger")
        self.warning.setWordWrap(True)
        self.tasks = QListWidget()
        self.away = QListWidget()
        edit = button(_("Edit"), "edit")
        edit.clicked.connect(self.edit_person)
        remove = button(_("Delete"), "trash")
        remove.setObjectName("danger")
        remove.clicked.connect(self.delete_person)
        self.from_date = QDateEdit(calendarPopup=True, displayFormat="d MMM yyyy")
        self.to_date = QDateEdit(calendarPopup=True, displayFormat="d MMM yyyy")
        self.from_date.setDate(QDate.currentDate())
        self.to_date.setDate(QDate.currentDate().addDays(6))
        away_add = button(_("Add time off"), "palm")
        away_add.clicked.connect(self.add_away)
        away_remove = icon_button("x", _("Remove the selected time off"))
        away_remove.clicked.connect(self.remove_away)
        away_row = QHBoxLayout()
        away_row.addWidget(self.from_date)
        away_row.addWidget(self.to_date)
        away_row.addWidget(away_add)
        away_row.addWidget(away_remove)

        right = Card()
        right.add(self.name)
        right.add(self.detail)
        buttons = QHBoxLayout()
        buttons.addWidget(edit)
        buttons.addWidget(remove)
        buttons.addStretch()
        right.body.addLayout(buttons)
        right.add(caption(_("Workload")))
        right.add(self.chart)
        right.add(self.warning)
        right.add(caption(_("Tasks")))
        right.add(self.tasks, 1)
        right.add(caption(_("Time off")))
        right.add(self.away, 1)
        right.body.addLayout(away_row)
        self.right = right

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([320, 760])
        self.root.addWidget(split, 1)

    def refresh(self):
        if not self.editor.is_open:
            return
        self.record = self.editor.project()
        current = self.current_id()
        self.list.blockSignals(True)
        self.list.clear()
        t = theme.current()
        for r in self.record.resources:
            item = QListWidgetItem(self._line(r))
            item.setData(Qt.UserRole, r.id)
            if r.overloaded:
                item.setForeground(QBrush(QColor(t.danger)))
            self.list.addItem(item)
            if r.id == current:
                self.list.setCurrentItem(item)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self.list.blockSignals(False)
        self.empty.setVisible(not self.record.resources)
        self._show()

    def _line(self, r: ResourceRecord) -> str:
        second = [r.role_name] if r.role_name else []
        second.append(plural(r.tasks, "task"))
        if r.overloaded:
            second.append(_("over-booked ({percent}%)").format(percent=round(r.peak_load)))
        return f"{r.name}\n{'  ·  '.join(second)}"

    def current_id(self) -> int | None:
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _resource(self) -> ResourceRecord | None:
        id = self.current_id()
        return next((r for r in (self.record.resources if self.record else ()) if r.id == id), None)

    def _show(self):
        r = self._resource()
        self.right.setVisible(r is not None)
        if r is None or self.record is None:
            return
        today = self.editor.today()
        self.name.setText(r.name)
        bits = [b for b in (r.role_name, r.email, r.phone) if b]
        if r.rate is not None:
            bits.append(_("{amount} per day").format(amount=money(r.rate)))
        self.detail.setText("  ·  ".join(bits) or _("No details yet"))
        first = (self.record.start or today) - timedelta(days=7)
        last = (self.record.finish or today) + timedelta(days=14)
        self.chart.set_days(self.editor.workload(r.id, first, last).days, today)
        self.warning.setText(_("Booked at {percent}% on the busiest day: more than one person's "
                               "day.").format(percent=round(r.peak_load)) if r.overloaded else "")
        self.warning.setVisible(r.overloaded)
        self.tasks.clear()
        for t in self.record.tasks:
            mine = [a for a in t.assignments if a.resource == r.id]
            if mine:
                self.tasks.addItem(f"{t.name}\n{range_text(t.start, t.end, today)}  ·  "
                                   f"{mine[0].load:g}%")
        self.away.clear()
        for v in self.record.vacations:
            if v.resource == r.id:
                item = QListWidgetItem(range_text(v.start, v.end, today))
                item.setData(Qt.UserRole, v.start)
                self.away.addItem(item)

    def add_person(self):
        if not self.editor.is_open:
            return
        dialog = ResourceEditor(self.editor.project(), parent=self)
        if dialog.exec():
            id = self.editor.add_resource(dialog.to_input())
            self.editor.end_group()
            self.refresh()
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.UserRole) == id:
                    self.list.setCurrentRow(i)

    def edit_person(self):
        r = self._resource()
        if r is None:
            return
        dialog = ResourceEditor(self.record, r, self)
        if dialog.exec():
            self.editor.update_resource(r.id, dialog.to_input())
            self.editor.end_group()

    def delete_person(self):
        r = self._resource()
        if r and QMessageBox.question(self, _("Gantry"), _("Delete “{title}”?").format(
                title=r.name)) == QMessageBox.Yes:
            self.editor.delete_resource(r.id)

    def add_away(self):
        r = self._resource()
        if r:
            self.editor.add_vacation(r.id, pydate(self.from_date.date()), pydate(self.to_date.date()))
            self.editor.end_group()

    def remove_away(self):
        r, item = self._resource(), self.away.currentItem()
        if r and item:
            self.editor.remove_vacation(r.id, item.data(Qt.UserRole))
            self.editor.end_group()
