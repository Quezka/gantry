# Gantry

Gantt charts that open and save [GanttProject](https://www.ganttproject.biz/) (`.gan`) files,
in the look and feel of [Quire](https://github.com/Quezka/quire). Made for the students of
I.T.S. "E. Alessandrini", Montesilvano.

- **Compatible.** Opens and saves `.gan` files. What Gantry doesn't use is kept as it was, so you
  can move a project back and forth between the two. The dates it works out match GanttProject's.
- **Direct.** Drag bars to move or resize them, drag a ring to link tasks, drag a triangle to
  set progress. Everything can be undone.
- **Clear.** Critical path, late tasks, working days and days off, people and an over-booking
  warning, all in a light or dark interface.
- **Shareable.** Export the chart to PNG, SVG or PDF (with the school's name and emblem), or the
  table to CSV.

## Run it

```
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/gantry            # or: .venv/bin/gantry project.gan   /   --demo
```

Linux `.deb` and Windows installers are on the [releases page](https://github.com/Quezka/gantry/releases).

## Develop

```
.venv/bin/pip install pytest && .venv/bin/python -m pytest -q
```

Clean Architecture: `gantry/domain` (pure Python: calendar, scheduling) → `gantry/application`
(use cases, ports) → `gantry/infrastructure` (`.gan` files, settings, updates) and
`gantry/presentation` (Qt), wired in `gantry/bootstrap.py`. `tests/test_architecture.py` enforces it.
To check against the real thing, run the tests with `GANTRY_TEST_GP=1` and GanttProject installed.

GPL-3.0-or-later.
