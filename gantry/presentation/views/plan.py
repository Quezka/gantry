"""The plan: the task table on the left, the Gantt chart on the right."""
from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import QPoint, QRect, QSettings, QSize, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QCursor, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox,
    QSplitter, QStackedLayout, QStyledItemDelegate, QToolButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from ...application.errors import ApplicationError
from ...application.records import ProjectRecord, TaskRecord
from ...application.services import Services
from .. import theme
from ..dialogs import TaskEditor, TaskSheet
from ..formatting import money, short_date, table_date
from ..gantt import HEADER, ROW, ZOOM_ORDER, ZOOMS, GanttView, timeline_for, visible_rows
from ..i18n import C_, N_, _, plural
from .common import Card, Page, Segmented, button, icon_button, label, primary_button

NAME, START, END, DAYS, DONE = range(5)
ID = Qt.UserRole
ZOOM_LABELS = {"day": N_("Days"), "week": N_("Weeks"), "month": N_("Months"),
               "quarter": N_("Quarters")}


class DoneDelegate(QStyledItemDelegate):
    """A round check, as in Quire, with the percentage beside it."""

    def paint(self, p, option, index):
        t = theme.current()
        record: TaskRecord | None = index.data(Qt.UserRole + 1)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if option.state & option.state.__class__.State_Selected:
            p.fillRect(option.rect, QColor(t.accent_soft))
        if record is not None:
            c = option.rect.left() + 16, option.rect.center().y()
            done = record.complete == 100
            if record.summary:
                p.setPen(Qt.NoPen)
            else:
                p.setPen(QColor(t.accent if done else t.faint))
                p.setBrush(QColor(t.accent) if done else Qt.NoBrush)
                p.drawEllipse(QPoint(*c), 8, 8)
                if done:
                    p.setPen(QColor(t.on_accent))
                    p.drawText(QRect(c[0] - 8, c[1] - 8, 16, 16), Qt.AlignCenter, "✓")
            p.setPen(QColor(t.muted if not done else t.faint))
            p.drawText(option.rect.adjusted(32, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft,
                       f"{record.complete}%")
        p.restore()


class PlanTree(QTreeWidget):
    dropped = Signal(list, object, object)  # task ids, parent id (or None), before id (or None)

    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setColumnCount(5)
        self.setHeaderLabels([_("Task"), _("Start"), _("End"), _("Days"), _("Done")])
        self.setUniformRowHeights(True)
        self.setRootIsDecorated(True)
        self.setIndentation(18)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditKeyPressed)
        # The bar is there (it takes the same room as the chart's, so rows line up) but drawn
        # invisible; a wide table still scrolls sideways with Shift + wheel.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setItemDelegateForColumn(DONE, DoneDelegate(self))
        self.setAllColumnsShowFocus(True)
        header = self.header()
        header.setFixedHeight(HEADER)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionsMovable(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for column, width in ((NAME, 230), (START, 78), (END, 78), (DAYS, 50), (DONE, 80)):
            self.setColumnWidth(column, int(QSettings().value(f"plan/col{column}", width)))
        header.sectionResized.connect(
            lambda i, _o, w: QSettings().setValue(f"plan/col{i}", w))
        theme.themed(self._style)

    def dropEvent(self, event):
        """Don't let Qt shuffle the items: say where the tasks should go and let the project
        decide (the table is redrawn from it)."""
        moving = [i.data(NAME, ID) for i in self.selectedItems()]
        target = self.itemAt(event.position().toPoint())
        where = self.dropIndicatorPosition()
        event.setDropAction(Qt.IgnoreAction)
        event.ignore()
        if not moving:
            return
        On, Above = QAbstractItemView.DropIndicatorPosition.OnItem, \
            QAbstractItemView.DropIndicatorPosition.AboveItem
        Below = QAbstractItemView.DropIndicatorPosition.BelowItem
        if target is None:
            self.dropped.emit(moving, None, None)
            return
        tid = target.data(NAME, ID)
        parent_item = target.parent()
        parent = parent_item.data(NAME, ID) if parent_item else None
        if where == On:
            self.dropped.emit(moving, tid, None)
        elif where == Above:
            self.dropped.emit(moving, parent, tid)
        elif where == Below:
            if target.childCount() and target.isExpanded():
                self.dropped.emit(moving, tid, target.child(0).data(NAME, ID))
            else:
                siblings = parent_item if parent_item else self.invisibleRootItem()
                nxt = siblings.child(siblings.indexOfChild(target) + 1)
                self.dropped.emit(moving, parent, nxt.data(NAME, ID) if nxt else None)
        else:
            self.dropped.emit(moving, None, None)

    def _style(self, t):
        self.setStyleSheet(
            "QTreeWidget::item{padding:0 6px;margin:0;border-radius:0;}"
            f"QTreeWidget::item:selected{{background:{t.accent_soft};color:{t.text};}}"
            f"QTreeWidget::item:hover{{background:{t.hover};}}"
            f"QHeaderView::section{{background:{t.surface};}}"
            "QScrollBar:horizontal{background:transparent;}"
            "QScrollBar::handle:horizontal{background:transparent;}")


class PlanPage(Page):
    problem = Signal(str)

    def __init__(self, services: Services, parent=None):
        super().__init__(parent, margins=(28, 22, 28, 20))
        self.services = services
        self.editor = services.editor
        self.zoom = str(QSettings().value("plan/zoom", "week"))
        if self.zoom not in ZOOMS:
            self.zoom = "week"
        self.critical_on = False
        self._building = False
        self.record: ProjectRecord | None = None
        self._first_show = True

        self.undo_button = icon_button("undo", _("Undo (Ctrl+Z)"))
        self.redo_button = icon_button("redo", _("Redo (Ctrl+Shift+Z)"))
        self.undo_button.clicked.connect(self.editor.undo)
        self.redo_button.clicked.connect(self.editor.redo)
        self.add_button = primary_button(_("Add task"))
        self.add_button.clicked.connect(lambda: self.add_task())
        self.add_actions(self.undo_button, self.redo_button, self.add_button)

        # ---- toolbar
        self.quick = QLineEdit(placeholderText=_("Add a task… press Enter"), objectName="search")
        self.quick.setMinimumWidth(240)
        self.quick.setMaximumWidth(320)
        self.quick.returnPressed.connect(self._quick_add)
        self.zoom_control = Segmented([(k, _(ZOOM_LABELS[k])) for k in ZOOM_ORDER])
        self.zoom_control.set_value(self.zoom)
        self.zoom_control.changed.connect(self.set_zoom)
        self.critical_button = icon_button("critical", _("Show the critical path"), checkable=True,
                                           checked_role="danger")
        self.critical_button.toggled.connect(self._critical_toggled)
        self.today_button = button(_("Today"))
        self.today_button.clicked.connect(self.go_today)
        self.fit_button = icon_button("fit", _("Fit the whole project (Ctrl+0)"))
        self.fit_button.clicked.connect(self.fit)
        self.tools = {}
        for key, icon, tip, slot in (
                ("outdent", "outdent", _("Outdent (Ctrl+[)"), self.outdent),
                ("indent", "indent", _("Make it part of the task above (Ctrl+])"), self.indent),
                ("up", "arrow-up", _("Move up (Alt+Up)"), lambda: self.move(-1)),
                ("down", "arrow-down", _("Move down (Alt+Down)"), lambda: self.move(+1)),
                ("link", "link", _("Make the lower task wait for the upper one (Ctrl+L)"),
                 self.link_selected),
                ("unlink", "unlink", _("Remove the links between the selected tasks"),
                 self.unlink_selected)):
            b = icon_button(icon, tip)
            b.clicked.connect(slot)
            self.tools[key] = b
        bar = QHBoxLayout()
        bar.setSpacing(4)
        bar.addWidget(self.quick)
        bar.addSpacing(8)
        for key in ("outdent", "indent", "up", "down"):
            bar.addWidget(self.tools[key])
        bar.addSpacing(6)
        for key in ("link", "unlink"):
            bar.addWidget(self.tools[key])
        bar.addStretch()
        bar.addWidget(self.critical_button)
        bar.addWidget(self.fit_button)
        bar.addWidget(self.today_button)
        bar.addSpacing(6)
        bar.addWidget(self.zoom_control)
        self.root.addLayout(bar)

        # ---- table + chart
        self.tree = PlanTree()
        self.view = GanttView()
        self.splitter = QSplitter(Qt.Horizontal, objectName="planSplit")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(7)
        self.tree.setMinimumWidth(180)
        self.view.setMinimumWidth(240)
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(self.view)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([int(QSettings().value("plan/split", 520)), 800])
        handle = self.splitter.handle(1)
        handle.setCursor(Qt.SplitHCursor)
        handle.setToolTip(_("Drag to resize the task table (double-click to reset)"))
        handle.installEventFilter(self)
        self.splitter.splitterMoved.connect(
            lambda _p, _i: QSettings().setValue("plan/split", self.splitter.sizes()[0]))
        self.card = Card(padding=0)
        self.card.add(self.splitter, 1)
        self.empty = Card()
        self.empty.body.addStretch()
        title = QLabel(_("Nothing planned yet"), objectName="sheetTitle", alignment=Qt.AlignCenter)
        hint = label(_("Type a task above and press Enter, or use Add task. "
                       "Drag bars to move them, drag their edge to change the length."),
                     "hint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        self.empty.add(title)
        self.empty.add(hint)
        self.empty.body.addStretch()
        self.stack = QStackedLayout()
        self.stack.addWidget(self.card)
        self.stack.addWidget(self.empty)
        self.root.addLayout(self.stack, 1)

        # ---- wiring
        self.tree.verticalScrollBar().valueChanged.connect(self.view.verticalScrollBar().setValue)
        self.view.verticalScrollBar().valueChanged.connect(self.tree.verticalScrollBar().setValue)
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        self.tree.dropped.connect(self._dropped)
        self.tree.itemExpanded.connect(lambda i: self._expanded(i, True))
        self.tree.itemCollapsed.connect(lambda i: self._expanded(i, False))
        self.tree.itemChanged.connect(self._renamed)
        self.tree.itemClicked.connect(self._clicked)
        self.tree.itemDoubleClicked.connect(lambda i, _c: self.open_sheet(i.data(NAME, ID)))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(
            lambda pos: self._menu(self._id_at(pos), self.tree.viewport().mapToGlobal(pos)))
        v = self.view
        v.moved.connect(self._moved)
        v.resized.connect(lambda id, last: self._act(lambda: self.editor.resize_task_to(id, last)))
        v.progressed.connect(lambda id, pct: self._act(lambda: self.editor.set_complete(id, pct)))
        v.linked.connect(self._linked)
        v.activated.connect(self.open_sheet)
        v.menuRequested.connect(lambda id, pos: self._menu(id, pos))
        v.selectionPicked.connect(self._picked)
        v.zoomRequested.connect(self._zoom_step)
        self._shortcuts()
        theme.manager().changed.connect(lambda _t: self.refresh())

    def eventFilter(self, obj, event):
        if (event.type() == event.Type.MouseButtonDblClick
                and obj is self.splitter.handle(1)):
            self.splitter.setSizes([520, max(self.width() - 520, 240)])
            QSettings().setValue("plan/split", 520)
            return True
        return super().eventFilter(obj, event)

    # ---- shortcuts ----------------------------------------------------------------------

    def _shortcuts(self):
        entries = [
            (Qt.Key_Return, lambda: self.open_sheet(self.current_id())),
            (Qt.Key_Enter, lambda: self.open_sheet(self.current_id())),
            ("E", lambda: self.edit(self.current_id())),
            (Qt.Key_Space, self.toggle_done),
            (Qt.Key_Delete, self.delete_selected),
            (Qt.Key_Insert, lambda: self.add_task(after=self.current_id())),
            ("Ctrl+]", self.indent), ("Ctrl+[", self.outdent),
            ("Alt+Up", lambda: self.move(-1)), ("Alt+Down", lambda: self.move(+1)),
            ("Ctrl+D", self.duplicate), ("Ctrl+L", self.link_selected),
        ]
        for widget in (self.tree, self.view):
            for keys, slot in entries:
                s = QShortcut(QKeySequence(keys), widget, activated=slot)
                s.setContext(Qt.WidgetWithChildrenShortcut)
        for widget in (self,):
            for keys, slot in (("Ctrl+0", self.fit), ("Ctrl+=", lambda: self._zoom_step(1)),
                               ("Ctrl+-", lambda: self._zoom_step(-1)),
                               ("Ctrl+T", self.go_today)):
                QShortcut(QKeySequence(keys), widget, activated=slot).setContext(
                    Qt.WidgetWithChildrenShortcut)

    # ---- state ---------------------------------------------------------------------------

    def selected_ids(self) -> list[int]:
        return [i.data(NAME, ID) for i in self._ordered_selection()]

    def _ordered_selection(self):
        items = self.tree.selectedItems()
        rows = {id: n for n, id in enumerate(t.id for t in self._rows())}
        return sorted(items, key=lambda i: rows.get(i.data(NAME, ID), 0))

    def current_id(self) -> int | None:
        item = self.tree.currentItem()
        return item.data(NAME, ID) if item else None

    def _id_at(self, pos) -> int | None:
        item = self.tree.itemAt(pos)
        return item.data(NAME, ID) if item else None

    def _rows(self) -> list[TaskRecord]:
        return visible_rows(self.record) if self.record else []

    def task(self, id) -> TaskRecord | None:
        return next((t for t in (self.record.tasks if self.record else ()) if t.id == id), None)

    def _act(self, action):
        try:
            action()
            self.editor.end_group()
        except ApplicationError as e:
            self.problem.emit(_(str(e)))

    # ---- drawing ----------------------------------------------------------------------------

    def refresh(self, fit: bool = False):
        if not self.editor.is_open:
            return
        record = self.editor.project()
        keep = set(self.selected_ids()) if self.record else set()
        current = self.current_id() if self.record else None
        vbar = self.tree.verticalScrollBar().value()
        hbar = self.view.horizontalScrollBar().value()
        self.record = record
        self._building = True
        self.tree.blockSignals(True)
        self.tree.clear()
        t = theme.current()
        items: dict[int, QTreeWidgetItem] = {}
        today = self.editor.today()
        for task in record.tasks:
            item = QTreeWidgetItem(self.tree if task.parent is None else items[task.parent])
            items[task.id] = item
            item.setData(NAME, ID, task.id)
            item.setData(DONE, Qt.UserRole + 1, task)
            item.setText(NAME, task.name)
            item.setIcon(NAME, self._dot(task, t))
            item.setText(START, table_date(task.start, today))
            item.setText(END, table_date(task.end, today) if not task.milestone else "")
            item.setText(DAYS, str(task.duration) if not task.milestone else "")
            item.setToolTip(NAME, f"{task.wbs}  {task.name}")
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            item.setSizeHint(NAME, QSize(0, ROW))
            if task.summary:
                f = item.font(NAME)
                f.setBold(True)
                item.setFont(NAME, f)
            if task.late:
                item.setForeground(END, QBrush(QColor(t.danger)))
            for column in (START, END, DAYS):
                if not task.summary or column != NAME:
                    item.setForeground(column, QBrush(QColor(t.danger if (
                        task.late and column == END) else t.muted)))
        for task in record.tasks:
            items[task.id].setExpanded(task.expanded and task.summary)
        for id in keep:
            if id in items:
                items[id].setSelected(True)
        if current in items:
            self.tree.setCurrentItem(items[current], 0, QItemSelectionModel.SelectionFlag.NoUpdate)
        self.tree.blockSignals(False)
        self._building = False
        self.stack.setCurrentIndex(1 if record.empty else 0)
        self._draw_chart()
        self.tree.verticalScrollBar().setValue(vbar)
        self.view.horizontalScrollBar().setValue(hbar)
        self._update_tools()
        self._subtitle()
        if fit or self._first_show:
            self._first_show = False
            self.go_today(initial=True)

    def _draw_chart(self):
        if self.record is None:
            return
        today = self.editor.today()
        tl = timeline_for(self.record, ZOOMS[self.zoom], today)
        self.view.chart.build(self.record, self._rows(), tl, theme.current(), today,
                              self.critical_on, set(self.selected_ids()))
        self.view.header.update()

    def layout_changed(self):
        """A branch was folded or unfolded: the rows changed, the tasks didn't."""
        if not self.editor.is_open:
            return
        self.record = self.editor.project()
        self._draw_chart()
        self.view.verticalScrollBar().setValue(self.tree.verticalScrollBar().value())

    def _dot(self, task: TaskRecord, t: theme.Theme) -> QIcon:
        pm = QPixmap(16, 16)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        color = QColor(task.color) if task.color else QColor(t.accent)
        p.setBrush(color if color.isValid() else QColor(t.accent))
        p.setPen(Qt.NoPen)
        if task.milestone:
            p.drawPolygon([QPoint(8, 2), QPoint(14, 8), QPoint(8, 14), QPoint(2, 8)])
        elif task.summary:
            p.drawRoundedRect(2, 5, 12, 6, 2, 2)
        else:
            p.drawEllipse(3, 3, 10, 10)
        p.end()
        return QIcon(pm)

    def _subtitle(self):
        r = self.record
        self.title.setText(r.name or _("Untitled project"))
        if r.empty:
            self.subtitle.setText(_("No tasks yet"))
            return
        today = self.editor.today()
        parts = [plural(len(r.tasks), "task"),
                 f"{short_date(r.start, today)} → {short_date(r.finish, today)}",
                 plural(r.duration, "working day"), _("{percent}% done").format(percent=r.complete)]
        if r.late:
            parts.append(_("{n} late").format(n=r.late))
        if r.cost:
            parts.append(money(r.cost))
        self.subtitle.setText("  ·  ".join(parts))

    def _update_tools(self):
        ids = self.selected_ids()
        one = len(ids) >= 1
        task = self.task(ids[0]) if ids else None
        self.tools["indent"].setEnabled(one)
        self.tools["outdent"].setEnabled(bool(task and task.parent is not None))
        self.tools["up"].setEnabled(one)
        self.tools["down"].setEnabled(one)
        self.tools["link"].setEnabled(len(ids) >= 2)
        self.tools["unlink"].setEnabled(len(ids) >= 2 or bool(task and (task.deps or task.successors)))
        self.undo_button.setEnabled(self.editor.can_undo)
        self.redo_button.setEnabled(self.editor.can_redo)

    # ---- zoom and scrolling -----------------------------------------------------------------

    def set_zoom(self, key: str):
        anchor = None
        tl = self.view.chart.tl
        if tl:
            width = self.view.viewport().width()
            anchor = tl.day_at(self.view.horizontalScrollBar().value() + width / 2)
        self.zoom = key
        QSettings().setValue("plan/zoom", key)
        self.zoom_control.set_value(key)
        self._draw_chart()
        if anchor and self.view.chart.tl:
            self.view.scroll_to_date(anchor, margin=self.view.viewport().width() / 2)

    def _zoom_step(self, direction: int):
        i = ZOOM_ORDER.index(self.zoom) - direction  # zoom in = bigger days = earlier entry
        self.set_zoom(ZOOM_ORDER[max(0, min(len(ZOOM_ORDER) - 1, i))])

    def fit(self):
        r = self.record
        if r is None or r.empty:
            return
        days = (r.finish - r.start).days + 14
        width = max(self.view.viewport().width(), 200)
        best = ZOOM_ORDER[-1]
        for key in ZOOM_ORDER:
            if ZOOMS[key] * days <= width:
                best = key
                break
        self.set_zoom(best)
        self.view.scroll_to_date(r.start - timedelta(days=4), margin=0)

    def go_today(self, initial: bool = False):
        if self.record is None:
            return
        today = self.editor.today()
        if initial and self.record.start and self.record.finish and not (
                self.record.start <= today <= self.record.finish):
            self.view.scroll_to_date(self.record.start, margin=40)
        else:
            self.view.scroll_to_date(today, margin=self.view.viewport().width() / 3)

    def _critical_toggled(self, on: bool):
        self.critical_on = on
        self._draw_chart()

    # ---- selection ----------------------------------------------------------------------------

    def _selection_changed(self):
        ids = set(self.selected_ids())
        for id, bar in self.view.chart.bars.items():
            if bar.is_selected != (id in ids):
                bar.is_selected = id in ids
                bar.update()
        self._update_tools()

    def _picked(self, id, add):
        if id is None:
            self.tree.clearSelection()
            return
        item = self._item(id)
        if item is None:
            return
        if add:
            item.setSelected(not item.isSelected())
        else:
            self.tree.clearSelection()
            item.setSelected(True)
        self.tree.setCurrentItem(item, 0, QItemSelectionModel.SelectionFlag.NoUpdate)

    def _item(self, id):
        it = self.tree.invisibleRootItem()
        stack = [it.child(i) for i in range(it.childCount())]
        while stack:
            node = stack.pop()
            if node.data(NAME, ID) == id:
                return node
            stack.extend(node.child(i) for i in range(node.childCount()))
        return None

    def select(self, id: int):
        item = self._item(id)
        if item:
            self.tree.clearSelection()
            item.setSelected(True)
            self.tree.setCurrentItem(item)
            self.tree.scrollToItem(item)

    # ---- editing the tree -----------------------------------------------------------------------

    def _expanded(self, item, expanded):
        if not self._building:
            self.editor.set_expanded(item.data(NAME, ID), expanded)

    def _renamed(self, item, column):
        if self._building or column != NAME:
            return
        self._act(lambda: self.editor.rename_task(item.data(NAME, ID), item.text(NAME)))

    def _clicked(self, item, column):
        if column != DONE:
            return
        x = self.tree.viewport().mapFromGlobal(QCursor.pos()).x() - self.tree.columnViewportPosition(DONE)
        task = self.task(item.data(NAME, ID))
        if task and not task.summary and x < 30:
            self._act(lambda: self.editor.set_complete(task.id, 0 if task.complete == 100 else 100))

    def _dropped(self, ids, parent, before):
        """Tasks were dropped in the table: onto a task (they become part of it) or between."""
        top = [i for i in ids if not any(self._under(self.task(i), j) for j in ids if j != i)]
        if parent is not None and any(parent == i or self._under(self.task(parent), i)
                                      for i in top):
            return  # a task can't go inside itself
        def go():
            for id in top:
                if id != before:
                    self.editor.relocate(id, parent, before)
            self.editor.end_group()
        self._act(go)
        for id in top:
            item = self._item(id)
            if item:
                item.setSelected(True)

    def _moved(self, id, days):
        self._act(lambda: self.editor.move_task_by(id, days))

    def _linked(self, pred, succ):
        self._act(lambda: self.editor.link(pred, succ))

    def _quick_add(self):
        text = self.quick.text().strip()
        if not text:
            return
        self.quick.clear()
        id = self.editor.add_task(after=self.current_id(), name=text)
        self.editor.end_group()
        self.select(id)
        self.quick.setFocus()

    def add_task(self, after: int | None = None, parent: int | None = None):
        if not self.editor.is_open:
            return
        dialog = TaskEditor(self.editor, None, self.editor.project(),
                            after=after if after is not None else self.current_id(), parent=self)
        if dialog.exec():
            def go():
                id = self.editor.add_task(dialog.to_input(), after=dialog.after, parent=parent)
                self.editor.end_group()
                self.select(id)
            self._act(go)

    def add_subtask(self, parent: int | None = None):
        parent = parent if parent is not None else self.current_id()
        if parent is None:
            return self.add_task()
        id = self.editor.add_task(parent=parent)
        self.editor.end_group()
        self.select(id)
        self.tree.editItem(self._item(id), NAME)

    def edit(self, id: int | None):
        task = self.task(id) if id is not None else None
        if task is None:
            return
        dialog = TaskEditor(self.editor, task, self.record, parent=self)
        if dialog.exec():
            self._act(lambda: self.editor.update_task(id, dialog.to_input()))

    def open_sheet(self, id: int | None):
        task = self.task(id) if id is not None else None
        if task is None:
            return
        sheet = TaskSheet(task, self.record, self.editor.today(), self)
        sheet.exec()
        if sheet.action == "edit":
            self.edit(id)
        elif sheet.action == "done":
            self._act(lambda: self.editor.set_complete(id, 0 if task.complete == 100 else 100))
        elif sheet.action == "delete":
            self.delete_ids([id])

    def toggle_done(self):
        ids = self.selected_ids()
        tasks = [t for t in map(self.task, ids) if t and not t.summary]
        if tasks:
            target = 0 if all(t.complete == 100 for t in tasks) else 100
            for t in tasks:
                self.editor.set_complete(t.id, target)
            self.editor.end_group()

    def delete_selected(self):
        self.delete_ids(self.selected_ids())

    def delete_ids(self, ids):
        if not ids:
            return
        tasks = [t for t in map(self.task, ids) if t]
        inside = sum(1 for t in self.record.tasks if t.id in set().union(
            *({x.id for x in self.record.tasks if self._under(x, i)} | {i} for i in ids)))
        text = (_("Delete “{title}”?").format(title=tasks[0].name) if inside == 1 else
                _("Delete {count} tasks?").format(count=inside))
        if QMessageBox.question(self, _("Gantry"), text) == QMessageBox.Yes:
            self._act(lambda: self.editor.delete_tasks(ids))

    def _under(self, task: TaskRecord, ancestor: int) -> bool:
        by_id = {t.id: t for t in self.record.tasks}
        node = task
        while node.parent is not None:
            if node.parent == ancestor:
                return True
            node = by_id[node.parent]
        return False

    def duplicate(self):
        id = self.current_id()
        if id is not None:
            new = self.editor.duplicate(id)
            self.editor.end_group()
            if new is not None:
                self.select(new)

    def _each(self, action, reverse=False):
        ids = self.selected_ids()
        top = [i for i in ids if not any(self._under(self.task(i), j) for j in ids if j != i)]
        for id in (reversed(top) if reverse else top):
            self._act(lambda id=id: action(id))

    def indent(self):
        self._each(self.editor.indent)

    def outdent(self):
        self._each(self.editor.outdent)

    def move(self, direction: int):
        self._each(self.editor.move_up if direction < 0 else self.editor.move_down,
                   reverse=direction > 0)

    def link_selected(self):
        ids = self.selected_ids()
        for pred, succ in zip(ids, ids[1:]):
            self._act(lambda pred=pred, succ=succ: self.editor.link(pred, succ))

    def unlink_selected(self):
        ids = self.selected_ids()
        if len(ids) >= 2:
            for a in ids:
                for b in ids:
                    if a != b:
                        self.editor.unlink(a, b)
        elif ids:
            task = self.task(ids[0])
            for d in task.deps:
                self.editor.unlink(d.pred, task.id)
            for s in task.successors:
                self.editor.unlink(task.id, s)
        self.editor.end_group()

    # ---- the context menu -------------------------------------------------------------------------

    def _menu(self, id, global_pos):
        if id is None:
            menu = QMenu(self)
            menu.addAction(_("Add task"), lambda: self.add_task())
            menu.exec(global_pos)
            return
        if id not in self.selected_ids():
            self.select(id)
        task = self.task(id)
        menu = QMenu(self)
        menu.addAction(_("Open"), lambda: self.open_sheet(id))
        menu.addAction(_("Edit…"), lambda: self.edit(id))
        if not task.summary:
            menu.addAction(_("Mark not done") if task.complete == 100 else _("Mark done"),
                           self.toggle_done)
        menu.addSeparator()
        menu.addAction(_("Add task below"), lambda: self.add_task(after=id))
        menu.addAction(_("Add subtask"), lambda: self.add_subtask(id))
        menu.addAction(_("Duplicate"), self.duplicate)
        menu.addSeparator()
        menu.addAction(_("Indent"), self.indent).setEnabled(self.tools["indent"].isEnabled())
        menu.addAction(_("Outdent"), self.outdent).setEnabled(self.tools["outdent"].isEnabled())
        menu.addAction(_("Move up"), lambda: self.move(-1))
        menu.addAction(_("Move down"), lambda: self.move(+1))
        menu.addSeparator()
        menu.addAction(_("Delete"), self.delete_selected)
        menu.exec(global_pos)
