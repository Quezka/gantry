"""Working days: which days count when a task's length is measured in days.

Everything is done on *working-day numbers*: `index(d)` is how many working days came before
`d`, so "10 days from Monday" is plain addition and weekends and holidays take care of
themselves.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

EPOCH = date(2000, 1, 3)  # a Monday
DEFAULT_OFF = frozenset({5, 6})  # Saturday, Sunday (Monday is 0)


@dataclass(frozen=True)
class Calendar:
    off_weekdays: frozenset[int] = DEFAULT_OFF
    holidays: frozenset[date] = field(default_factory=frozenset)  # days off that would work
    extra_days: frozenset[date] = field(default_factory=frozenset)  # days on that would be off

    def __post_init__(self):
        if len(self.off_weekdays) >= 7:  # a calendar with no working day can't measure anything
            object.__setattr__(self, "off_weekdays", DEFAULT_OFF)

    @property
    def per_week(self) -> int:
        return 7 - len(self.off_weekdays)

    def _weekly(self, d: date) -> bool:
        return d.weekday() not in self.off_weekdays

    def is_working(self, d: date) -> bool:
        if d in self.holidays:
            return False
        return d in self.extra_days or self._weekly(d)

    def index(self, d: date) -> int:
        """How many working days lie before `d` (counted from a fixed starting point)."""
        days = (d - EPOCH).days
        weeks, rest = divmod(days, 7)
        count = weeks * self.per_week + sum(1 for k in range(rest) if k not in self.off_weekdays)
        for h in self.holidays:
            if self._weekly(h):
                if EPOCH <= h < d:
                    count -= 1
                elif d <= h < EPOCH:
                    count += 1
        for x in self.extra_days:
            if not self._weekly(x) and x not in self.holidays:
                if EPOCH <= x < d:
                    count += 1
                elif d <= x < EPOCH:
                    count -= 1
        return count

    def date_at(self, n: int) -> date:
        """The working day with number `n`."""
        d = EPOCH + timedelta(days=round(n * 7 / self.per_week))
        while self.index(d) > n:
            d -= timedelta(days=1)
        while self.index(d) < n:
            d += timedelta(days=1)
        while not self.is_working(d):
            d += timedelta(days=1)
        return d

    def next_working(self, d: date) -> date:
        return self.date_at(self.index(d))

    def end_exclusive(self, start: date, duration: int) -> date:
        """The day after a task's last working day (the start itself for a milestone)."""
        if duration <= 0:
            return start
        return self.date_at(self.index(start) + duration - 1) + timedelta(days=1)

    def last_day(self, start: date, duration: int) -> date:
        """The last day work happens (the start day for a milestone)."""
        if duration <= 0:
            return start
        return self.date_at(self.index(start) + duration - 1)

    def duration_between(self, start: date, end_exclusive: date) -> int:
        return max(0, self.index(end_exclusive) - self.index(start))

    def duration_to_last(self, start: date, last: date) -> int:
        """Working days from `start` up to and including `last`, at least one."""
        return max(1, self.index(last) - self.index(start) + (1 if self.is_working(last) else 0))
