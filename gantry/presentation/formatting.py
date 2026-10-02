"""Dates, durations and money, written the way people read them."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate

from . import i18n
from .i18n import _


def qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def pydate(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


def day_label(d: date, today: date | None = None, weekday: bool = True) -> str:
    """"Mon 27 May", with the year when it isn't this year."""
    text = f"{d.day} {i18n.month_of(d)}"
    if weekday:
        text = f"{i18n.weekday_short(d)} {text}"
    if today is not None and d.year != today.year:
        text += f" {d.year}"
    return text


def short_date(d: date, today: date | None = None) -> str:
    """"27 May" or "27 May 2025"."""
    return day_label(d, today, weekday=False)


def table_date(d: date, today: date | None = None) -> str:
    """"27 May", short enough for a table column."""
    text = f"{d.day} {i18n.month_short(d)}"
    if today is not None and d.year != today.year:
        text += f" {d.year}"
    return text


def days_text(n: int) -> str:
    return i18n.plural(n, "day")


_symbol = "€"


def set_currency(symbol: str) -> None:
    """The symbol every amount is shown with (chosen in Settings)."""
    global _symbol
    _symbol = symbol


def currency_symbol() -> str:
    return _symbol


def money(value: float) -> str:
    """An amount with the chosen currency, in the system's number format: 1,500 € style."""
    from PySide6.QtCore import QLocale
    digits = 0 if round(value, 2) == int(round(value, 2)) else 2
    return QLocale.system().toCurrencyString(float(value), _symbol, digits)


def range_text(start: date, end: date, today: date | None = None) -> str:
    if start == end:
        return day_label(start, today)
    return f"{day_label(start, today)} → {day_label(end, today)}"


def dep_label(kind_code: str) -> str:
    return {"FS": _("finish → start"), "SS": _("start → start"),
            "FF": _("finish → finish"), "SF": _("start → finish")}[kind_code]
