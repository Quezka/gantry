# Changelog

## [0.6.2] - 2026-10-26

The interface size set to Automatic is a compact 85% now (the shared toolkit's new standard; 80% and 90% are new choices). Larger sizes stay in Settings.

## [0.6.1] - 2026-10-26

- The interface size set to Automatic is the system's own size again (100%); the shared toolkit had made it 115%, which was too big. Larger sizes stay one choice away in Settings.

## [0.6.0] - 2026-10-26

- The look now comes from the suite's shared toolkit (the school's blue and red kept): darker text and firmer borders, larger captions, and a High contrast option in Settings.

## [0.5.1] - 2026-10-26

- The Resources and Project pages scroll when the window is short instead of making it taller than a small laptop
  screen.

## [0.5.0] - 2026-10-26

- **Task priority**, as in GanttProject: lowest, low, normal, high or highest, set in the task window and shown in a new
  Priority column. It is stored the way GanttProject stores it, so the file still opens there with the same priorities.
- The task list follows the width of its pane: the task name column takes whatever room the other columns leave, so it
  grows and shrinks with the splitter, the sidebar and the window instead of keeping a fixed width.

## [0.4.0] - 2026-10-05

- Italian translation of the whole interface (Language in Settings; Italian systems start in Italian).

## [0.3.0] - 2026-10-02

- Pressing Enter in a one-line box now finishes with it: the cursor stops blinking and the box lets go of the focus.
- Currency in Settings (euro by default; also pound, dollar, franc, ruble). It shows next to costs, fixed costs and daily rates; the project file holds plain numbers, so nothing is converted.

## [0.2.2] - 2026-10-02

- Fixed: opening the app put a second icon on the dock instead of using the pinned one (the screen-size check forgot the app's desktop name).
- Fixed: the arrow into a milestone is no longer hidden by its diamond; arrows now meet its corner.
- The task table no longer shows a scroll bar at the bottom.
- The new-person dialog can't be resized.

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
