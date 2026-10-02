# Changelog

## [0.2.1] - 2026-10-02
- Drag empty space in the chart to move around it (a plain click there still clears the selection). The cursor becomes a hand.
- The grip for resizing the task table is invisible until you point at it, and then only a soft tint.

## [0.2.0] - 2026-10-02
- Drag a task onto another to make it part of it (with everything under it); drop it between tasks to just move it. A task can't be dropped into its own branch.
- Interface size in Settings (Automatic, 80%–130%). Automatic makes everything a little smaller on small screens such as 1366x768. Applies after a restart.
- Windows and dialogs never open bigger than the screen; Settings and the editors scroll when they're taller than it.
- Fixed: after selecting a task the table and chart stopped redrawing (and didn't follow a theme change).

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
