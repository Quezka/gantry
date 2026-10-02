"""The project itself: its details, working week, days off, roles, and the numbers."""
from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QToolButton,
    QVBoxLayout, QWidget,
)

from ...application.inputs import ProjectInfo
from ...application.services import Services
from ..formatting import money, pydate, short_date
from ..i18n import _, plural, weekday_names
from .common import Card, Page, button, caption, icon_button, label


def tile(caption_text: str) -> tuple[QWidget, "QLabel"]:  # noqa: F821
    box = QWidget()
    column = QVBoxLayout(box)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(2)
    column.addWidget(caption(caption_text))
    value = label("", "tileValue")
    column.addWidget(value)
    return box, value


class ProjectPage(Page):
    def __init__(self, services: Services, parent=None):
        super().__init__(parent)
        self.services = services
        self.editor = services.editor
        self.title.setText(_("Project"))
        self.subtitle.setText(_("Details, working week and days off"))

        stats = Card()
        row = QHBoxLayout()
        row.setSpacing(24)
        self.tiles = {}
        for key, text in (("start", _("Starts")), ("finish", _("Finishes")),
                          ("length", _("Length")), ("done", _("Done")), ("cost", _("Cost")),
                          ("late", _("Late"))):
            box, value = tile(text)
            self.tiles[key] = value
            row.addWidget(box, 1)
        stats.body.addLayout(row)

        about = Card(_("About"))
        self.name = QLineEdit(placeholderText=_("Project name"), objectName="titleEdit")
        self.company = QLineEdit(placeholderText=_("Company or class"))
        self.link = QLineEdit(placeholderText="https://…")
        self.description = QPlainTextEdit(placeholderText=_("What is this project about?"))
        self.description.setMinimumHeight(90)
        for w in (self.name, self.company, self.link):
            w.textEdited.connect(self._info_edited)
        self.description.textChanged.connect(self._description_edited)
        for w in (self.name, self.company, self.link, self.description):
            about.add(w)

        week = Card(_("Working week"))
        week.add(label(_("Days that count when a task is measured in days."), "hint"))
        days = QHBoxLayout()
        days.setSpacing(6)
        self.days = []
        for i, name in enumerate(weekday_names()):
            b = QToolButton(objectName="day", checkable=True, text=name[:2])
            b.setToolTip(name)
            b.setCursor(Qt.PointingHandCursor)
            b.toggled.connect(self._week_edited)
            self.days.append(b)
            days.addWidget(b)
        days.addStretch()
        week.body.addLayout(days)

        off = Card(_("Days off"))
        self.holidays = QListWidget()
        self.holidays.setMaximumHeight(150)
        self.holiday_date = QDateEdit(QDate.currentDate(), calendarPopup=True,
                                      displayFormat="d MMM yyyy")
        add = button(_("Add"), "plus")
        add.clicked.connect(lambda: self.editor.add_holiday(pydate(self.holiday_date.date())))
        remove = icon_button("x", _("Remove the selected day off"))
        remove.clicked.connect(self._remove_holiday)
        pick = QHBoxLayout()
        pick.addWidget(self.holiday_date)
        pick.addWidget(add)
        pick.addWidget(remove)
        pick.addStretch()
        off.add(self.holidays)
        off.body.addLayout(pick)

        roles = Card(_("Roles"))
        self.roles = QListWidget()
        self.roles.setMaximumHeight(120)
        self.role_name = QLineEdit(placeholderText=_("New role, e.g. Designer"))
        self.role_name.returnPressed.connect(self._add_role)
        role_remove = icon_button("x", _("Remove the selected role"))
        role_remove.clicked.connect(self._remove_role)
        role_row = QHBoxLayout()
        role_row.addWidget(self.role_name, 1)
        role_row.addWidget(role_remove)
        roles.add(self.roles)
        roles.body.addLayout(role_row)

        left = QVBoxLayout()
        left.setSpacing(16)
        left.addWidget(about)
        left.addWidget(roles)
        left.addStretch()
        right = QVBoxLayout()
        right.setSpacing(16)
        right.addWidget(week)
        right.addWidget(off)
        right.addStretch()
        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)
        self.root.addWidget(stats)
        self.root.addLayout(columns, 1)

    def refresh(self):
        if not self.editor.is_open:
            return
        r = self.editor.project()
        today = self.editor.today()
        self._set(self.name, r.name)
        self._set(self.company, r.company)
        self._set(self.link, r.web_link)
        if self.description.toPlainText() != r.description:
            self.description.blockSignals(True)
            self.description.setPlainText(r.description)
            self.description.blockSignals(False)
        for i, b in enumerate(self.days):
            b.blockSignals(True)
            b.setChecked(i not in r.off_weekdays)
            b.blockSignals(False)
        self.holidays.clear()
        for d in r.holidays:
            item = QListWidgetItem(short_date(d, today) + f"  ·  {self._weekday(d)}")
            item.setData(Qt.UserRole, d)
            self.holidays.addItem(item)
        self.roles.clear()
        for role in r.roles:
            item = QListWidgetItem(role.name)
            item.setData(Qt.UserRole, role.id)
            self.roles.addItem(item)
        t = self.tiles
        t["start"].setText(short_date(r.start, today) if r.start else "–")
        t["finish"].setText(short_date(r.finish, today) if r.finish else "–")
        t["length"].setText(plural(r.duration, "day") if r.start else "–")
        t["done"].setText(f"{r.complete}%")
        t["cost"].setText(money(r.cost) if r.cost else "–")
        t["late"].setText(str(r.late))

    @staticmethod
    def _weekday(d) -> str:
        return weekday_names()[d.weekday()]

    @staticmethod
    def _set(widget: QLineEdit, text: str):
        if widget.text() != text:
            widget.setText(text)

    def _info_edited(self, *_a):
        self.editor.set_info(ProjectInfo(self.name.text(), self.company.text(), self.link.text(),
                                         self.description.toPlainText()))

    def _description_edited(self):
        self._info_edited()

    def _week_edited(self, _checked):
        off = [i for i, b in enumerate(self.days) if not b.isChecked()]
        if len(off) < 7:
            self.editor.set_weekdays_off(off)
        else:
            self.refresh()
        self.editor.end_group()

    def _remove_holiday(self):
        item = self.holidays.currentItem()
        if item:
            self.editor.remove_holiday(item.data(Qt.UserRole))

    def _add_role(self):
        text = self.role_name.text().strip()
        if text:
            self.editor.add_role(text)
            self.role_name.clear()

    def _remove_role(self):
        item = self.roles.currentItem()
        if item:
            self.editor.remove_role(item.data(Qt.UserRole))
