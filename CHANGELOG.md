# Changelog

## [0.1.1] - 2026-10-02
- The task table can be resized: drag the grip between it and the chart (double-click to reset); the width is remembered.

## [0.1.0] - 2026-10-02
- First release.
- Opens and saves GanttProject (`.gan`) files. What Gantry doesn't use (column layout, custom columns, baselines, per-task extras) is kept as it was, so a project can go back and forth between the two programs.
- Plan page: task table and Gantt chart side by side. Drag bars to move them, drag their edge to change the length, drag the ring at a bar's end to link tasks, drag the little triangle to set progress.
- Task tree with indent, outdent, move up and down, duplicate, folding; milestones; notes, colours, links and fixed costs.
- Dependencies of all four kinds (finish→start, start→start, finish→finish, start→finish) with lag. Followers are pushed later, never pulled away from where you put them. A task can't be made to wait for itself.
- Working calendar: choose the working week, add days off; task lengths count working days.
- Critical path, late tasks, today line, weekends and days off shaded; zoom from days to quarters.
- Resources page: people with role, rate, email and phone; a workload chart that turns red when someone is over-booked; time off.
- Project page: details, totals, working week, days off and roles.
- Undo and redo for everything; unsaved-changes warnings; recent files.
- Export to PNG, SVG, PDF and CSV.
- School branding (I.T.S. "E. Alessandrini", Montesilvano) in the sidebar and, if you like, on exports; name, town and logo can be changed in Settings.
- English and Russian; light and dark themes; updates from inside the app.
