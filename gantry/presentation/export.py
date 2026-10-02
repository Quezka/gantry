"""The chart as a picture: PNG, SVG or PDF, always drawn on white (as it would print)."""
from __future__ import annotations

import math
from datetime import date, timedelta

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtSvg import QSvgGenerator

from ..application.records import BrandingRecord, ProjectRecord
from . import i18n, theme
from .gantt import HEADER, ROW, ChartScene, Timeline, font, paint_header, visible_rows
from .icons import SCHOOL_EMBLEM
from .views.common import logo_tile

BAND = 64
LABEL_ROOM = 320


def _layout(record: ProjectRecord, today: date) -> Timeline:
    first = (record.start or today) - timedelta(days=5)
    last = record.finish or today
    span = max((last - first).days + 8, 14)
    ppd = max(3.0, min(40.0, 1500 / span))
    extra = math.ceil(LABEL_ROOM / ppd)
    return Timeline(first, ppd, span + extra)


def _render(record: ProjectRecord, today: date, branding: BrandingRecord | None):
    """A scene plus what's needed to paint the rest around it."""
    t = theme.LIGHT
    tl = _layout(record, today)
    rows = visible_rows(record)
    scene = ChartScene()
    scene.build(record, rows, tl, t, today, critical_on=False, selected=set())
    width = tl.width
    band = BAND if branding is not None and branding.on_exports else 0
    height = band + HEADER + max(len(rows), 1) * ROW + 10
    return scene, tl, t, width, height, band


def _paint(p: QPainter, record: ProjectRecord, today: date, branding, scene, tl, t, width,
           height, band):
    p.fillRect(QRectF(0, 0, width, height), QColor("#ffffff"))
    if band:
        pm = logo_tile(branding.logo or str(SCHOOL_EMBLEM), str(SCHOOL_EMBLEM), 44, 2.0)
        p.drawPixmap(QRectF(14, 10, 44, 44), pm, QRectF(pm.rect()))
        p.setPen(QColor(t.text))
        p.setFont(font(15, True))
        p.drawText(QRectF(68, 8, width / 2, 26), Qt.AlignVCenter, branding.school)
        p.setPen(QColor(t.muted))
        p.setFont(font(12))
        p.drawText(QRectF(68, 32, width / 2, 22), Qt.AlignVCenter, branding.place)
        p.setPen(QColor(t.text))
        p.setFont(font(15, True))
        p.drawText(QRectF(width / 2, 8, width / 2 - 16, 26), Qt.AlignVCenter | Qt.AlignRight,
                   record.name or "")
        p.setPen(QColor(t.muted))
        p.setFont(font(12))
        p.drawText(QRectF(width / 2, 32, width / 2 - 16, 22), Qt.AlignVCenter | Qt.AlignRight,
                   f"{today.day} {i18n.month_of(today)} {today.year}")
        p.setPen(QColor(t.border))
        p.drawLine(QPointF(0, band - 0.5), QPointF(width, band - 0.5))
    p.save()
    p.translate(0, band)
    paint_header(p, QRectF(0, 0, width, HEADER), tl, 0, t, today)
    p.restore()
    p.save()
    p.translate(0, band + HEADER)
    scene.render(p, QRectF(0, 0, width, height - band - HEADER),
                 QRectF(0, 0, width, height - band - HEADER))
    p.restore()


def png_bytes(record: ProjectRecord, today: date, branding: BrandingRecord | None = None) -> bytes:
    scene, tl, t, width, height, band = _render(record, today, branding)
    scale = 2
    image = QImage(int(width * scale), int(height * scale), QImage.Format_ARGB32)
    image.fill(Qt.white)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.scale(scale, scale)
    _paint(p, record, today, branding, scene, tl, t, width, height, band)
    p.end()
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    return bytes(data)


def svg_bytes(record: ProjectRecord, today: date, branding: BrandingRecord | None = None) -> bytes:
    scene, tl, t, width, height, band = _render(record, today, branding)
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    gen = QSvgGenerator()
    gen.setOutputDevice(buf)
    gen.setSize(QSizeF(width, height).toSize())
    gen.setViewBox(QRectF(0, 0, width, height))
    gen.setTitle(record.name or "Gantry")
    p = QPainter(gen)
    p.setRenderHint(QPainter.Antialiasing)
    _paint(p, record, today, branding, scene, tl, t, width, height, band)
    p.end()
    buf.close()
    return bytes(data)


def pdf_bytes(record: ProjectRecord, today: date, branding: BrandingRecord | None = None) -> bytes:
    scene, tl, t, width, height, band = _render(record, today, branding)
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    pdf = QPdfWriter(buf)
    pdf.setResolution(150)
    # one page the size of the chart, in points, so nothing is cut or tiny
    pdf.setPageSize(QPageSize(QSizeF(width * 0.75, height * 0.75), QPageSize.Point))
    pdf.setPageMargins(QMarginsF(0, 0, 0, 0))
    pdf.setTitle(record.name or "Gantry")
    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(pdf.width() / width, pdf.width() / width)
    _paint(p, record, today, branding, scene, tl, t, width, height, band)
    p.end()
    buf.close()
    return bytes(data)
