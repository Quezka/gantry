# Gantry

Python 3.10+ / PySide6 desktop app (Linux + Windows): Gantt charts that open and save GanttProject
`.gan` files. Sibling of Quire (`../quire`), Ligature and Bivouac: same look, toolkit and release
process; school-branded (I.T.S. "E. Alessandrini", blue `#0066ff` family, emblem `assets/school.png`).

- Layers: `gantry/domain` → `gantry/application` → `gantry/infrastructure` + `gantry/presentation`; wired in `gantry/bootstrap.py`. `tests/test_architecture.py` enforces it; the UI never imports the domain (enums come through `application/types.py`).
- Run: `.venv/bin/gantry --demo`. Test: `.venv/bin/python -m pytest -q` (UI tests run offscreen). Real-GanttProject check: `GANTRY_TEST_GP=1`.
- Domain: `Calendar` works in working-day numbers (`index`/`date_at`); `schedule` rolls summaries up, pushes followers later (never earlier) and finds the critical path; `structure` indents/moves. A task's `duration` is working days; `Calendar.last_day` is the displayed end, `end_exclusive` what GanttProject calls the end.
- `.gan` format (`infrastructure/files.py`): `<depend id="B">` nested in task A means **B waits for A** (checked against GanttProject's own sample and CLI export). Unknown attributes/elements live in `extras`/`raw` and are written back verbatim; `calendars` is patched, not rebuilt. Keep `test_files.py` round-trip tests passing.
- All edits go through `application/editor.Editor` (immutable `Project` snapshots → undo/redo; `end_group()` ends a merged undo step). Folding a branch is `Change.LAYOUT`: not undoable, not "unsaved".
- The chart (`presentation/gantt.py`) is rebuilt from the `ProjectRecord`; bar drags emit signals via `QTimer.singleShot` because the scene is rebuilt in response. Fonts are pixel-sized so exports match the screen. The table (`views/plan.py`) and chart rows are both derived from `visible_rows(record)`.
- UI text: wrap in `_()`/`N_()`, add Russian and Italian to `presentation/locales/ru.py` and `it.py` (`tests/test_i18n.py`). Never use `_` as a variable.
- Releases: bump `__version__`, add a CHANGELOG section and a metainfo `<release>`, tag `vX.Y.Z`; CI publishes the .deb and setup .exe (asset names `gantry_<v>_<arch>.deb`, `Gantry-<v>-windows-x64-setup.exe`).
