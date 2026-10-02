"""The start page: new projects, a sample, and the files you opened lately."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout, QListWidget, QListWidgetItem, QSizePolicy, QToolButton, QVBoxLayout,
)

from .. import theme
from ..i18n import _
from .common import Card, Page, button, label


class HomePage(Page):
    newRequested = Signal()
    openRequested = Signal(str)  # a path, or "" to choose one
    sampleRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title.setText(_("Gantry"))
        self.subtitle.setText(_("Plan projects as Gantt charts. Opens and saves GanttProject files."))

        start = Card(_("Start"))
        grid = QGridLayout()
        grid.setSpacing(10)
        for column, (icon, text, detail, action) in enumerate((
                ("gantt", _("New project"), _("Tasks, dependencies, people"),
                 lambda: self.newRequested.emit()),
                ("folder", _("Open…"), _("A GanttProject .gan file"),
                 lambda: self.openRequested.emit("")))):
            tile = QToolButton(objectName="startTile")
            tile.setText(f"{text}\n{detail}")
            tile.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            tile.setIconSize(QSize(30, 30))
            tile.setMinimumSize(210, 120)
            tile.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            tile.setCursor(Qt.PointingHandCursor)
            theme.set_icon(tile, icon, "accent", size=30)
            tile.clicked.connect(action)
            grid.addWidget(tile, 0, column)
        start.body.addLayout(grid)
        start.add(label(_("Or look around a sample first:"), "hint"))
        sample = button(_("Class website project"), "flag")
        sample.clicked.connect(lambda: self.sampleRequested.emit("website"))
        start.add(sample)

        recent = Card(_("Recent"))
        self.recent = QListWidget(objectName="recent")
        self.recent.itemActivated.connect(
            lambda item: self.openRequested.emit(item.data(Qt.UserRole)))
        self.empty = label(_("Projects you open or save show up here."), "hint")
        recent.add(self.recent, 1)
        recent.add(self.empty)
        recent.body.addStretch(1)

        column = QVBoxLayout()
        column.setSpacing(16)
        column.addWidget(start)
        column.addWidget(recent, 1)
        self.root.addLayout(column, 1)

    def set_recent(self, paths: list[str]):
        self.recent.clear()
        for path in paths:
            p = Path(path)
            item = QListWidgetItem(f"{p.name}\n{p.parent}")
            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            self.recent.addItem(item)
        self.empty.setVisible(not paths)
        self.recent.setVisible(bool(paths))
