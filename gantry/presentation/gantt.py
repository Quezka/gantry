"""The chart: a time scale, rows, bars you can drag, and the arrows between them.

`build_scene` draws a project onto a scene (for the screen and for exports alike); `GanttView`
adds the interaction. Fonts are pixel-sized so an export measures the same as the screen.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsObject, QGraphicsPathItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsSimpleTextItem, QGraphicsView, QToolTip, QWidget,
)

from ..application.records import ProjectRecord, TaskRecord
from ..application.types import DepKind
from . import i18n, theme
from .i18n import _

ROW = 34
HEADER = 46
BAR = 18
ZOOMS = {"day": 40.0, "week": 16.0, "month": 6.0, "quarter": 2.4}
ZOOM_ORDER = ("day", "week", "month", "quarter")
LABEL_PAD = 8


def visible_rows(record: ProjectRecord) -> list[TaskRecord]:
    """The tasks you can see: those whose parents are all unfolded."""
    folded: set[int] = set()
    rows = []
    for t in record.tasks:
        if t.parent in folded:
            folded.add(t.id)
            continue
        rows.append(t)
        if t.summary and not t.expanded:
            folded.add(t.id)
    return rows


@dataclass(frozen=True)
class Timeline:
    origin: date
    ppd: float  # pixels per day
    days: int

    def x(self, d: date) -> float:
        return (d - self.origin).days * self.ppd

    def day_at(self, x: float) -> date:
        return self.origin + timedelta(days=int(x // self.ppd))

    @property
    def width(self) -> float:
        return self.days * self.ppd


def timeline_for(record: ProjectRecord, ppd: float, today: date,
                 min_days: int = 120) -> Timeline:
    first = min([d for d in (record.start, today) if d])
    last = max([d for d in (record.finish, today) if d])
    origin = first - timedelta(days=14 + first.weekday())
    days = max(min_days, (last - origin).days + 90)
    return Timeline(origin, ppd, days)


def font(size: int, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(size)
    f.setBold(bold)
    return f


def _color(text: str, t: theme.Theme) -> QColor:
    c = QColor(text) if text else QColor(t.accent)
    return c if c.isValid() else QColor(t.accent)


def _off(day: date, record: ProjectRecord) -> bool:
    return day.weekday() in record.off_weekdays


# ---- the time scale ------------------------------------------------------------------

def paint_header(p: QPainter, rect: QRectF, tl: Timeline, scroll: float, t: theme.Theme,
                 today: date):
    """Two rows of labels: months (or years), then days (or weeks, or months)."""
    p.save()
    p.fillRect(rect, QColor(t.surface))
    half = rect.height() / 2
    p.setPen(QPen(QColor(t.border), 1))
    p.drawLine(QPointF(rect.left(), rect.bottom() - 0.5), QPointF(rect.right(), rect.bottom() - 0.5))
    p.drawLine(QPointF(rect.left(), rect.top() + half), QPointF(rect.right(), rect.top() + half))
    first = tl.day_at(scroll)
    count = int(rect.width() / tl.ppd) + 3
    top_font, low_font = font(12, True), font(11)
    big = tl.ppd < 5  # years above, months below

    def label(text, x0, x1, row, f, color):
        p.setFont(f)
        p.setPen(QColor(color))
        w = QFontMetricsF(f).horizontalAdvance(text)
        box = QRectF(x0 + 6, rect.top() + row * half, max(0, x1 - x0 - 6), half)
        if w <= box.width() + 6 or row == 0:
            p.drawText(box, Qt.AlignVCenter | Qt.AlignLeft, text)

    prev = None
    for i in range(-1, count):
        d = first + timedelta(days=i)
        x = tl.x(d) - scroll + rect.left()
        group = d.year if big else (d.year, d.month)
        if group != prev:
            prev = group
            p.setPen(QPen(QColor(t.border), 1))
            p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.top() + half))
            nxt = (date(d.year + 1, 1, 1) if big else
                   date(d.year + (d.month == 12), d.month % 12 + 1, 1))
            x_end = tl.x(nxt) - scroll + rect.left()
            text = str(d.year) if big else f"{i18n.month_name(d)} {d.year}"
            label(text, max(x, rect.left() - 6), x_end, 0, top_font, t.text)
        # lower row
        if tl.ppd >= 28:
            text = str(d.day)
            sub = i18n.weekday_short(d)[:2]
            p.setFont(low_font)
            p.setPen(QColor(t.accent if d == today else (t.faint if _off_day(d) else t.muted)))
            cell = QRectF(x, rect.top() + half, tl.ppd, half)
            p.drawText(cell, Qt.AlignCenter, f"{sub} {text}" if tl.ppd >= 44 else text)
        elif tl.ppd >= 9:
            if d.weekday() == 0:
                p.setPen(QPen(QColor(t.border), 1))
                p.drawLine(QPointF(x, rect.top() + half), QPointF(x, rect.bottom()))
                p.setFont(low_font)
                p.setPen(QColor(t.muted))
                p.drawText(QRectF(x + 5, rect.top() + half, 7 * tl.ppd, half),
                           Qt.AlignVCenter | Qt.AlignLeft, str(d.day))
        else:
            if d.day == 1:
                p.setPen(QPen(QColor(t.border), 1))
                p.drawLine(QPointF(x, rect.top() + half), QPointF(x, rect.bottom()))
                nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
                width = tl.x(nxt) - tl.x(d)
                p.setFont(low_font)
                p.setPen(QColor(t.muted))
                if width >= 24:
                    p.drawText(QRectF(x + 4, rect.top() + half, width, half),
                               Qt.AlignVCenter | Qt.AlignLeft, i18n.month_short(d))
    p.restore()


def _off_day(d: date) -> bool:
    return d.weekday() >= 5


# ---- items ---------------------------------------------------------------------------

class BarItem(QGraphicsObject):
    """A task: a bar, a bracket (summary) or a diamond (milestone)."""

    def __init__(self, view, task: TaskRecord, row: int, tl: Timeline, t: theme.Theme,
                 critical_on: bool, selected: bool):
        super().__init__()
        self.view_ = view
        self.task = task
        self.t = t
        self.critical_on = critical_on
        self.is_selected = selected
        self.x0 = tl.x(task.start)
        self.x1 = tl.x(task.end + timedelta(days=1)) if not task.milestone else self.x0
        self.ppd = tl.ppd
        self.cy = row * ROW + ROW / 2
        self.setPos(0, 0)
        self.setAcceptHoverEvents(True)
        self.setZValue(2)
        self._mode = None
        self._origin = QPointF()
        self._hover = False
        self._shown_complete = task.complete
        self.dx = 0.0
        self.dw = 0.0

    # geometry
    @property
    def left(self) -> float:
        return self.x0 + self.dx

    @property
    def right(self) -> float:
        return (self.x1 + self.dx + self.dw) if not self.task.milestone else self.left

    def bar_rect(self) -> QRectF:
        if self.task.milestone:
            return QRectF(self.left - BAR / 2, self.cy - BAR / 2, BAR, BAR)
        return QRectF(self.left, self.cy - BAR / 2, max(self.right - self.left, 6), BAR)

    def boundingRect(self) -> QRectF:
        r = self.bar_rect().adjusted(-14, -8, 40, 8)
        return r

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.bar_rect().adjusted(-4, -3, 22, 3))  # the ring's room, too
        return path

    def _handle_rect(self) -> QRectF:
        r = self.bar_rect()
        return QRectF(r.right() + 6, self.cy - 6, 12, 12)

    # painting
    def paint(self, p: QPainter, _option, _widget=None):
        t, task = self.t, self.task
        p.setRenderHint(QPainter.Antialiasing)
        r = self.bar_rect()
        base = _color(task.color, t)
        crit = self.critical_on and task.critical
        outline = QColor(t.danger) if crit else None
        if task.milestone:
            path = QPolygonF([QPointF(r.center().x(), r.top()), QPointF(r.right(), r.center().y()),
                              QPointF(r.center().x(), r.bottom()),
                              QPointF(r.left(), r.center().y())])
            p.setBrush(QBrush(QColor(t.danger) if crit else base))
            p.setPen(QPen(outline or base.darker(130), 1.5))
            p.drawPolygon(path)
        elif task.summary:
            h = 8
            body = QRectF(r.left(), self.cy - BAR / 2 + 2, r.width(), h)
            color = QColor(t.danger) if crit else QColor(t.muted)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(body, 2, 2)
            done = QRectF(body.left(), body.top(), body.width() * task.complete / 100, h)
            if task.complete:
                p.setBrush(QColor(t.accent))
                p.drawRoundedRect(done, 2, 2)
            for x, sign in ((body.left(), 1), (body.right(), -1)):
                tri = QPolygonF([QPointF(x, body.top()), QPointF(x + sign * 7, body.top()),
                                 QPointF(x, body.bottom() + 6)])
                p.setBrush(color)
                p.drawPolygon(tri)
        else:
            fill = QColor(base)
            fill.setAlphaF(0.38 if not t.dark else 0.45)
            p.setPen(QPen(outline or base, 2 if crit else 1.2))
            p.setBrush(fill)
            p.drawRoundedRect(r, 6, 6)
            if task.complete:
                done = QRectF(r.left(), r.top(), r.width() * self._shown_complete / 100, r.height())
                p.save()
                clip = QPainterPath()
                clip.addRoundedRect(r, 6, 6)
                p.setClipPath(clip)
                p.setPen(Qt.NoPen)
                p.setBrush(base)
                p.drawRect(done)
                p.restore()
        if self.is_selected:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(t.accent), 2, Qt.DashLine))
            p.drawRoundedRect(r.adjusted(-3, -3, 3, 3), 8, 8)
        if task.late and not task.milestone:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t.danger))
            p.drawEllipse(QPointF(r.left() + 7, r.top() - 3), 3, 3)
        if self._hover and not task.summary and not task.milestone:
            kx = r.left() + r.width() * self._shown_complete / 100
            p.setPen(QPen(QColor(t.text), 1))
            p.setBrush(QColor(t.surface))
            p.drawPolygon(QPolygonF([QPointF(kx - 4, r.bottom() + 5), QPointF(kx + 4, r.bottom() + 5),
                                     QPointF(kx, r.bottom() - 1)]))
        if self._hover or self._mode == "link":
            h = self._handle_rect()
            p.setPen(QPen(QColor(t.accent), 1.5))
            p.setBrush(QColor(t.surface))
            p.drawEllipse(h.adjusted(2, 2, -2, -2))

    # interaction
    def hoverEnterEvent(self, e):
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, e):
        self._hover = False
        self.unsetCursor()
        self.update()

    def _where(self, pos: QPointF) -> str:
        r, task = self.bar_rect(), self.task
        if self._handle_rect().adjusted(-3, -3, 3, 3).contains(pos):
            return "link"
        if not task.summary and not task.milestone:
            kx = r.left() + r.width() * self._shown_complete / 100
            if r.bottom() - 6 <= pos.y() <= r.bottom() + 7 and abs(pos.x() - kx) <= 6:
                return "progress"
            if pos.x() >= r.right() - 6:
                return "resize"
        return "move"

    def hoverMoveEvent(self, e):
        where = self._where(e.pos())
        self.setCursor({"resize": Qt.SizeHorCursor, "link": Qt.CrossCursor,
                        "progress": Qt.SplitHCursor}.get(where, Qt.OpenHandCursor))

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            e.ignore()
            return
        self._mode = self._where(e.pos())
        self._origin = e.scenePos()
        self.view_.select_from_chart(self.task.id, e.modifiers() & Qt.ControlModifier)
        if self._mode == "move":
            self.setCursor(Qt.ClosedHandCursor)
        if self._mode == "link":
            self.view_.begin_link(self)
        e.accept()

    def mouseMoveEvent(self, e):
        if self._mode is None:
            return
        delta = e.scenePos().x() - self._origin.x()
        days = round(delta / self.ppd)
        if self._mode == "move":
            self.dx = days * self.ppd
            QToolTip.showText(e.screenPos(), self._tip(days))
        elif self._mode == "resize":
            self.dw = max(days * self.ppd, -(self.x1 - self.x0) + self.ppd)
            self.dx = 0
        elif self._mode == "progress":
            r = QRectF(self.x0, 0, max(self.x1 - self.x0, 1), 1)
            self._shown_complete = max(0, min(100, 5 * round(
                100 * (e.scenePos().x() - r.left()) / r.width() / 5)))
            QToolTip.showText(e.screenPos(), f"{self._shown_complete}%")
        elif self._mode == "link":
            self.view_.drag_link(e.scenePos())
        self.prepareGeometryChange()
        self.update()

    def _tip(self, days: int) -> str:
        d = self.task.start + timedelta(days=days)
        return f"{i18n.weekday_short(d)} {d.day} {i18n.month_short(d)}"

    def mouseReleaseEvent(self, e):
        mode, self._mode = self._mode, None
        self.unsetCursor()
        t = self.task
        if mode == "move":
            days = round(self.dx / self.ppd)
            if days:
                self.view_.later(self.view_.moved, t.id, days)
        elif mode == "resize":
            days = round(self.dw / self.ppd)
            if days:
                last = t.end + timedelta(days=days)
                self.view_.later(self.view_.resized, t.id, last)
        elif mode == "progress":
            if self._shown_complete != t.complete:
                self.view_.later(self.view_.progressed, t.id, self._shown_complete)
        elif mode == "link":
            target = self.view_.end_link(e.scenePos())
            if target is not None and target != t.id:
                self.view_.later(self.view_.linked, t.id, target)
        self.dx = self.dw = 0.0
        self._shown_complete = t.complete
        self.prepareGeometryChange()
        self.update()

    def mouseDoubleClickEvent(self, e):
        self.view_.later(self.view_.activated, self.task.id)

    def contextMenuEvent(self, e):
        self.view_.later(self.view_.menuRequested, self.task.id, e.screenPos())
        e.accept()


class ArrowItem(QGraphicsPathItem):
    def __init__(self, points: list[QPointF], head: QPolygonF, color: QColor, width: float):
        path = QPainterPath(points[0])
        for pt in points[1:]:
            path.lineTo(pt)
        super().__init__(path)
        self.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setZValue(1)
        self.head = QGraphicsPathItem(self)
        hp = QPainterPath()
        hp.addPolygon(head)
        self.head.setPath(hp)
        self.head.setBrush(color)
        self.head.setPen(QPen(color, 1))
        self.setAcceptedMouseButtons(Qt.NoButton)


def route(kind: DepKind, pred: BarItem, succ: BarItem) -> tuple[list[QPointF], QPolygonF]:
    sy, ty = pred.cy, succ.cy
    leaves_finish = kind in (DepKind.FINISH_START, DepKind.FINISH_FINISH)
    enters_start = kind in (DepKind.FINISH_START, DepKind.START_START)
    ax = pred.x1 if leaves_finish else pred.x0
    bx = succ.x0 if enters_start else succ.x1
    out = 9 if leaves_finish else -9
    entry = -9 if enters_start else 9
    p1x, ex = ax + out, bx + entry
    pts = [QPointF(ax, sy), QPointF(p1x, sy)]
    if out > 0 and entry < 0:
        direct = p1x <= ex
        x = p1x
    elif out < 0 and entry > 0:
        direct = p1x >= ex
        x = p1x
    elif out > 0:
        direct, x = True, max(p1x, ex)
    else:
        direct, x = True, min(p1x, ex)
    if direct:
        pts += [QPointF(x, sy), QPointF(x, ty), QPointF(bx, ty)]
    else:
        mid = sy + (ROW / 2 if ty >= sy else -ROW / 2) if ty != sy else sy + ROW / 2
        pts += [QPointF(p1x, mid), QPointF(ex, mid), QPointF(ex, ty), QPointF(bx, ty)]
    sign = 1 if entry < 0 else -1
    head = QPolygonF([QPointF(bx, ty), QPointF(bx - 7 * sign, ty - 4), QPointF(bx - 7 * sign, ty + 4)])
    return pts, head


# ---- the scene -------------------------------------------------------------------------

class ChartScene(QGraphicsScene):
    def __init__(self, view=None):
        super().__init__()
        self.owner = view
        self.tl: Timeline | None = None
        self.t: theme.Theme = theme.LIGHT
        self.record: ProjectRecord | None = None
        self.rows: list[TaskRecord] = []
        self.today = date.today()
        self.bars: dict[int, BarItem] = {}

    def build(self, record: ProjectRecord, rows: list[TaskRecord], tl: Timeline,
              t: theme.Theme, today: date, critical_on: bool, selected: set[int],
              labels: bool = True):
        self.clear()
        self.bars = {}
        self.tl, self.t, self.record, self.rows, self.today = tl, t, record, rows, today
        self.setSceneRect(0, 0, tl.width, max(len(rows), 1) * ROW + ROW)
        index = {task.id: i for i, task in enumerate(rows)}
        for i, task in enumerate(rows):
            bar = BarItem(self.owner, task, i, tl, t, critical_on, task.id in selected)
            self.addItem(bar)
            self.bars[task.id] = bar
            if labels:
                text = QGraphicsSimpleTextItem(task.name)
                text.setFont(font(12))
                text.setBrush(QColor(t.text if not task.summary else t.muted))
                text.setPos(max(bar.x1, bar.x0) + LABEL_PAD + (22 if not task.milestone else 14),
                            bar.cy - 8)
                text.setZValue(1)
                text.setAcceptedMouseButtons(Qt.NoButton)
                self.addItem(text)
        for task in rows:
            for dep in task.deps:
                if dep.pred in index and task.id in index:
                    crit = critical_on and self.bars[dep.pred].task.critical and task.critical
                    color = QColor(t.danger if crit else t.faint)
                    pts, head = route(dep.kind, self.bars[dep.pred], self.bars[task.id])
                    self.addItem(ArrowItem(pts, head, color, 1.6 if crit else 1.2))

    def drawBackground(self, p: QPainter, rect: QRectF):
        t, tl, record = self.t, self.tl, self.record
        p.fillRect(rect, QColor(t.surface))
        if tl is None or record is None:
            return
        first = max(0, int(rect.left() // tl.ppd))
        last = min(tl.days, int(rect.right() // tl.ppd) + 1)
        shade = QColor(t.raised)
        shade.setAlphaF(0.9)
        holidays = set(record.holidays)
        if tl.ppd >= 5:
            for i in range(first, last):
                d = tl.origin + timedelta(days=i)
                if _off(d, record) or d in holidays:
                    p.fillRect(QRectF(i * tl.ppd, rect.top(), tl.ppd, rect.height()), shade)
        p.setPen(QPen(QColor(t.border), 1))
        row0 = max(0, int(rect.top() // ROW))
        for r in range(row0, int(rect.bottom() // ROW) + 2):
            y = r * ROW + ROW - 0.5
            p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        if tl.ppd >= 9:
            weekly = QColor(t.border)
            weekly.setAlphaF(0.55)
            p.setPen(QPen(weekly, 1))
            for i in range(first, last):
                d = tl.origin + timedelta(days=i)
                if (d.weekday() == 0) if tl.ppd < 28 else True:
                    x = i * tl.ppd
                    p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        x = tl.x(self.today) + tl.ppd / 2
        p.setPen(QPen(QColor(t.accent), 1.5))
        p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))


class ScaleHeader(QWidget):
    def __init__(self, view: "GanttView"):
        super().__init__(view)
        self.view = view

    def paintEvent(self, _event):
        v = self.view
        if v.chart.tl is None:
            return
        p = QPainter(self)
        paint_header(p, QRectF(0, 0, self.width(), HEADER), v.chart.tl,
                     v.horizontalScrollBar().value(), v.chart.t, v.chart.today)


class GanttView(QGraphicsView):
    moved = Signal(int, int)  # task, calendar days
    resized = Signal(int, object)  # task, new last day
    progressed = Signal(int, int)
    linked = Signal(int, int)  # predecessor, successor
    activated = Signal(int)
    menuRequested = Signal(int, object)
    selectionPicked = Signal(object, bool)  # task id (or None), add to selection
    zoomRequested = Signal(int)  # +1 / -1
    scrolledV = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.chart = ChartScene(self)
        self.setScene(self.chart)
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportMargins(0, HEADER, 0, 0)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.header = ScaleHeader(self)
        self.horizontalScrollBar().valueChanged.connect(lambda _v: self.header.update())
        self._link_path: QGraphicsPathItem | None = None
        self._link_from: BarItem | None = None
        self._pan = None
        self.setMouseTracking(True)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.header.setGeometry(0, 0, self.viewport().width(), HEADER)

    def later(self, signal, *args):
        """Emit after the mouse event is over: the scene gets rebuilt in response."""
        QTimer.singleShot(0, lambda: signal.emit(*args))

    def select_from_chart(self, id, add):
        self.later(self.selectionPicked, id, bool(add))

    # linking
    def begin_link(self, bar: BarItem):
        self._link_from = bar
        self._link_path = QGraphicsPathItem()
        self._link_path.setPen(QPen(QColor(self.chart.t.accent), 2, Qt.DashLine))
        self._link_path.setZValue(5)
        self.chart.addItem(self._link_path)

    def drag_link(self, pos: QPointF):
        bar = self._link_from
        path = QPainterPath(QPointF(bar.right + 12, bar.cy))
        path.lineTo(pos)
        self._link_path.setPath(path)
        for other in self.chart.bars.values():
            other.is_selected = other is bar or (other.bar_rect().contains(pos))
            other.update()

    def end_link(self, pos: QPointF) -> int | None:
        if self._link_path is not None:
            self.chart.removeItem(self._link_path)
            self._link_path = None
        self._link_from = None
        for item in self.chart.items(pos):
            if isinstance(item, BarItem):
                return item.task.id
        for bar in self.chart.bars.values():
            if bar.bar_rect().adjusted(-2, -6, 2, 6).contains(pos):
                return bar.task.id
        return None

    # empty space
    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton
                                              and self.itemAt(e.position().toPoint()) is None
                                              and e.modifiers() & Qt.AltModifier):
            self._pan = (e.position(), self.horizontalScrollBar().value(),
                         self.verticalScrollBar().value())
            self.viewport().setCursor(Qt.ClosedHandCursor)
            return
        if e.button() == Qt.LeftButton and self.itemAt(e.position().toPoint()) is None:
            self.later(self.selectionPicked, None, False)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._pan:
            origin, hx, vy = self._pan
            d = e.position() - origin
            self.horizontalScrollBar().setValue(int(hx - d.x()))
            self.verticalScrollBar().setValue(int(vy - d.y()))
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._pan:
            self._pan = None
            self.viewport().unsetCursor()
            return
        super().mouseReleaseEvent(e)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.zoomRequested.emit(1 if e.angleDelta().y() > 0 else -1)
            e.accept()
        elif e.modifiers() & Qt.ShiftModifier or abs(e.angleDelta().x()) > abs(e.angleDelta().y()):
            bar = self.horizontalScrollBar()
            delta = e.angleDelta().x() or e.angleDelta().y()
            bar.setValue(bar.value() - delta)
            e.accept()
        else:
            super().wheelEvent(e)

    def scroll_to_date(self, d: date, margin: float = 80):
        tl = self.chart.tl
        if tl:
            self.horizontalScrollBar().setValue(max(0, int(tl.x(d) - margin)))
