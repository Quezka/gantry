# Changelog

## [0.13.1] - 2026-11-09

- Smoother scrolling and window moves: the app only asks GNOME's Blur my Shell to blur behind its windows while they're see-through (with see-through off, that blur was redone on every frame for nothing). The glass header over scrolling pages is cheaper to draw.

## [0.13.0] - 2026-11-09

The suite's new shared look (one design system for every app, `suite-rs/design/tokens.json`):

- **Neutral greys** instead of blue-tinted backgrounds, sidebars and borders; indigo stays as the one accent colour.
- **Bigger, clearer text** on one type scale shared with the phone apps: body text 16 px, nothing smaller than 13 px;
  titles and buttons follow the same sizes everywhere (the Interface size setting still scales it all).
- The same corner radii and spacing in every app.

## [0.12.0] - 2026-11-09

Real transparency and corners that line up (suite-kit 0.10).

- **See-through windows**: where the desktop can blur what's behind a window, the main window and dialogs let it show
  through, like Windows Aero or macOS sidebars; cards stay solid. On Windows it's the system's Acrylic. On GNOME it
  needs the Blur my Shell extension (the app adds itself to its list). Switch it in Settings, Look.
- **Corners line up**: the sidebar, cards and the Settings list share one radius and one gap, and what's inside them is
  rounded to match, so the curves run side by side. The Settings header floats over the cards, as wide as them.
- The glass look's description in Settings says what it really does now.

## [0.11.0] - 2026-11-08

### Changed
- **Liquid glass done properly, the Apple way.** Backgrounds are plain again and content stays solid; the chrome is glass. Menus, drop-down lists and tooltips blur what's really under them, settings headers float over their cards and blur them as they scroll, and the sidebar floats as an inset panel. On Windows 11 the window shows the system's Mica behind the sidebar. The colour wash is gone.

## [0.10.0] - 2026-11-08

### Changed
- **A glass look on top of Material 3, with brighter colours:** frosted, see-through surfaces over a soft wash of colour. Settings turns it off; High contrast stays solid.
- **Settings is redone in the suite's new window:** sections on the left, cards of rows with switches, nothing cut off on a small screen. Every other window gets its title on top and a filled Save button.

## [0.9.0] - 2026-11-04

### Added
- **Zoom in small steps**: Ctrl and the wheel, a pinch on the trackpad, the new + and - buttons or Ctrl+= and Ctrl+-, keeping still the day under the pointer. Days, Weeks, Months and Quarters stay as quick levels, and Fit now fits exactly.

### Fixed
- **The task list and the chart scroll together.** The list counted rows and the chart pixels, so scrolling one barely moved the other. They now line up row by row, all the way to the bottom.
- **Main tasks show their colour** on the chart, not only their subtasks.

## [0.8.0] - 2026-11-04

### Changed
- The icons are Material Symbols now: outlined, and filled for what is selected.

## [0.7.0] - 2026-11-04

### Changed
- A new look: Material 3 shapes and tonal colours, and the Manrope typeface. A flick on a trackpad now keeps gliding; a mouse wheel works as before.

## [0.6.5] - 2026-11-04

Fixed: changing the interface size and pressing Restart now works, and a button's menu opens exactly under the button (kit 0.5.3).

## [0.6.4] - 2026-10-27

Fixed: the compact text size now reaches labels, buttons, menus and lists too (the desktop theme was keeping them at the system's larger size), so the whole interface really is smaller.

## [0.6.3] - 2026-10-27

The interface is compact: smaller text (never above 9 pt), tighter spacing and smaller icons and panels, instead of the zoom the size setting used to apply. "Automatic" size is 100% again.

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
