from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox,
    QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from .. import FILE_EXTENSION, HOMEPAGE, __version__
from ..application.errors import ApplicationError
from ..application.services import Services
from . import theme
from .bridge import ChangeRelay
from .export import pdf_bytes, png_bytes, svg_bytes
from .i18n import N_, _
from .icons import APP_ICON, SCHOOL_EMBLEM
from .settings import SettingsDialog
from .updates_ui import UpdateChecker
from .views.common import logo_tile
from .views.home import HomePage
from .views.plan import PlanPage
from .views.project import ProjectPage
from .views.resources import ResourcesPage

RECENT = 12


def _filters(*pairs) -> str:
    return ";;".join(f"{_(name)} ({pattern})" for name, pattern in pairs)


class Sidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(206)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        brand_icon = QLabel()
        brand_icon.setPixmap(QIcon(str(APP_ICON)).pixmap(28, 28))
        brand = QHBoxLayout()
        brand.setContentsMargins(12, 4, 12, 0)
        brand.setSpacing(10)
        brand.addWidget(brand_icon)
        brand.addWidget(QLabel(_("Gantry"), objectName="brand"))
        brand.addStretch()
        self.nav = QVBoxLayout()
        self.nav.setSpacing(2)
        self.footer = QVBoxLayout()
        self.footer.setSpacing(2)

        self.school_logo = QLabel()
        self.school_name = QLabel(objectName="school", wordWrap=True)
        self.school_place = QLabel(objectName="place")
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(self.school_name)
        names.addWidget(self.school_place)
        school = QHBoxLayout()
        school.setContentsMargins(10, 0, 6, 6)
        school.setSpacing(10)
        school.addWidget(self.school_logo, 0, Qt.AlignVCenter)
        school.addLayout(names, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 14)
        layout.setSpacing(6)
        layout.addLayout(brand)
        layout.addSpacing(18)
        layout.addLayout(self.nav)
        layout.addStretch()
        layout.addLayout(school)
        layout.addLayout(self.footer)

    def nav_button(self, icon_name: str, text: str, checkable: bool = True) -> QToolButton:
        button = QToolButton(objectName="nav", text=f"  {text}", checkable=checkable)
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.setIconSize(QSize(18, 18))
        button.setCursor(Qt.PointingHandCursor)
        theme.set_icon(button, icon_name, "muted", "accent" if checkable else None)
        return button

    def add_page(self, icon_name: str, text: str, shortcut: str) -> QToolButton:
        button = self.nav_button(icon_name, text)
        button.setToolTip(f"{text}  ({shortcut})")
        self.group.addButton(button, len(self.group.buttons()))
        self.nav.addWidget(button)
        return button

    def set_branding(self, brand):
        self.school_logo.setPixmap(logo_tile(brand.logo or str(SCHOOL_EMBLEM), str(SCHOOL_EMBLEM),
                                             38, self.devicePixelRatioF()))
        self.school_name.setText(brand.school)
        self.school_place.setText(brand.place)


class MainWindow(QMainWindow):
    HOME, PLAN, RESOURCES, PROJECT = range(4)
    PAGES = [("home", N_("Home")), ("gantt", N_("Plan")), ("users", N_("Resources")),
             ("project", N_("Project"))]

    def __init__(self, services: Services):
        super().__init__()
        self.services = services
        self.editor = services.editor
        self.resize(1360, 860)
        self.setMinimumSize(1020, 660)
        self.setAcceptDrops(True)

        self.relay = ChangeRelay(self.editor, self)
        self.home = HomePage()
        self.plan = PlanPage(services)
        self.resources = ResourcesPage(services)
        self.project = ProjectPage(services)
        self.sidebar = Sidebar()
        self.sidebar.set_branding(services.branding.get())
        self.stack = QStackedWidget()
        for i, (page, (icon, text)) in enumerate(zip(
                (self.home, self.plan, self.resources, self.project), self.PAGES)):
            self.stack.addWidget(page)
            self.sidebar.add_page(icon, _(text), f"Ctrl+{i + 1}")
        self.sidebar.group.idClicked.connect(self.show_page)
        more = self.sidebar.nav_button("more", _("More"), checkable=False)
        more.setPopupMode(QToolButton.InstantPopup)
        more.setMenu(self._more_menu())
        self.sidebar.footer.addWidget(more)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.relay.projectChanged.connect(self._project_changed)
        self.relay.layoutChanged.connect(self.plan.layout_changed)
        self.relay.documentChanged.connect(self._document_changed)
        self.home.newRequested.connect(self.new_project)
        self.home.openRequested.connect(lambda path: self.open_file(path or None))
        self.home.sampleRequested.connect(self.open_sample)
        self.plan.problem.connect(lambda text: QMessageBox.warning(self, _("Gantry"), text))
        self.updater = UpdateChecker(services, self)  # not `update`: that's QWidget's
        self._shortcuts()

        settings = QSettings()
        geometry = settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        self.home.set_recent(self.recent_files())
        self._document_changed()
        self.show_page(self.HOME)

    # ---- pages ------------------------------------------------------------------------

    def show_page(self, index: int):
        if index != self.HOME and not self.editor.is_open:
            index = self.HOME
        self.stack.setCurrentIndex(index)
        self.sidebar.group.button(index).setChecked(True)
        if index == self.RESOURCES:
            self.resources.refresh()
        elif index == self.PROJECT:
            self.project.refresh()
        elif index == self.PLAN:
            self.plan.tree.setFocus()

    def _project_changed(self):
        if not self.editor.is_open:
            return
        self.plan.refresh()
        if self.stack.currentIndex() == self.RESOURCES:
            self.resources.refresh()
        elif self.stack.currentIndex() == self.PROJECT:
            self.project.refresh()

    def _document_changed(self):
        editor = self.editor
        open_ = editor.is_open
        for page in (self.PLAN, self.RESOURCES, self.PROJECT):
            button = self.sidebar.group.button(page)
            button.setEnabled(open_)
            text = _(self.PAGES[page][1])
            button.setToolTip(f"{text}  (Ctrl+{page + 1})" if open_ else
                              _("{page}: start or open a project first").format(page=text))
        if not open_:
            self.setWindowTitle(_("Gantry"))
            return
        record = editor.project()
        title = record.name or (Path(editor.path).stem if editor.path else _("Untitled project"))
        self.plan.undo_button.setEnabled(editor.can_undo)
        self.plan.redo_button.setEnabled(editor.can_redo)
        self.setWindowTitle(("• " if editor.dirty else "") + f"{title} — Gantry")

    # ---- documents ---------------------------------------------------------------------

    def _run(self, action) -> bool:
        try:
            action()
            return True
        except ApplicationError as e:
            QMessageBox.warning(self, _("Gantry"), _(str(e)))
            return False

    def maybe_keep_changes(self) -> bool:
        """Before closing or replacing the project: False means stay (the user cancelled)."""
        if not (self.editor.is_open and self.editor.dirty):
            return True
        box = QMessageBox(QMessageBox.Warning, _("Unsaved changes"),
                          _("Save the changes to this project first?"),
                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, self)
        box.setDefaultButton(QMessageBox.Save)
        answer = box.exec()
        if answer == QMessageBox.Save:
            return self.save()
        return answer == QMessageBox.Discard

    def new_project(self):
        if self.maybe_keep_changes():
            self.editor.new()
            self.plan.refresh(fit=True)
            self.show_page(self.PLAN)
            self.plan.quick.setFocus()

    def open_sample(self, name: str):
        from ..demo import website
        if self.maybe_keep_changes():
            {"website": website}[name](self.editor)
            self.plan.refresh(fit=True)
            self.show_page(self.PLAN)

    def open_file(self, path: str | None = None):
        if not self.maybe_keep_changes():
            return
        if not path:
            path, _chosen = QFileDialog.getOpenFileName(
                self, _("Open a project"), self._folder(),
                _filters((N_("GanttProject files"), f"*{FILE_EXTENSION}"),
                         (N_("All files"), "*")))
            if not path:
                return
        if self._run(lambda: self.editor.open(path)):
            self._remember(path)
            self.plan.refresh(fit=True)
            self.show_page(self.PLAN)
        else:
            self._forget(path)

    def save(self) -> bool:
        if not self.editor.is_open:
            return False
        if not self.editor.path:
            return self.save_as()
        return self._save_to(self.editor.path)

    def save_as(self) -> bool:
        if not self.editor.is_open:
            return False
        name = (self.editor.project().name or _("Project")) + FILE_EXTENSION
        path, _chosen = QFileDialog.getSaveFileName(
            self, _("Save the project"), str(Path(self._folder()) / name),
            _filters((N_("GanttProject file"), f"*{FILE_EXTENSION}")))
        if not path:
            return False
        if not Path(path).suffix:
            path += FILE_EXTENSION
        return self._save_to(path)

    def _save_to(self, path: str) -> bool:
        if self._run(lambda: self.editor.save(path)):
            self._remember(path)
            return True
        return False

    def export(self, kind: str):
        if not self.editor.is_open:
            return
        record = self.editor.project()
        names = {"png": (N_("PNG picture"), ".png"), "svg": (N_("SVG picture"), ".svg"),
                 "pdf": (N_("PDF document"), ".pdf"), "csv": (N_("CSV table"), ".csv")}
        label, suffix = names[kind]
        stem = record.name or (Path(self.editor.path).stem if self.editor.path else _("Project"))
        path, _chosen = QFileDialog.getSaveFileName(
            self, _("Export"), str(Path(self._folder()) / (stem + suffix)),
            _filters((label, f"*{suffix}")))
        if not path:
            return
        if not path.lower().endswith(suffix):
            path += suffix
        today, brand = self.editor.today(), self.services.branding.get()
        if kind == "csv":
            data = self.editor.csv().encode("utf-8-sig")
        else:
            data = {"png": png_bytes, "svg": svg_bytes, "pdf": pdf_bytes}[kind](
                record, today, brand)
        self._run(lambda: self.editor.export(path, data))

    # ---- recent files -----------------------------------------------------------------

    def recent_files(self) -> list[str]:
        value = QSettings().value("recent", [])
        paths = [value] if isinstance(value, str) else list(value or [])
        return [p for p in paths if Path(p).exists()][:RECENT]

    def _remember(self, path: str):
        path = str(Path(path).resolve())
        paths = [path] + [p for p in self.recent_files() if p != path]
        QSettings().setValue("recent", paths[:RECENT])
        QSettings().setValue("folder", str(Path(path).parent))
        self.home.set_recent(paths[:RECENT])

    def _forget(self, path: str):
        paths = [p for p in self.recent_files() if p != str(path)]
        QSettings().setValue("recent", paths)
        self.home.set_recent(paths)

    def _folder(self) -> str:
        folder = QSettings().value("folder", "")
        return folder if folder and Path(folder).is_dir() else str(Path.home())

    # ---- menus and shortcuts ---------------------------------------------------------------

    def _shortcut(self, keys, slot):
        action = QAction(self)
        action.setShortcut(QKeySequence(keys))
        action.setShortcutContext(Qt.ApplicationShortcut)
        action.triggered.connect(slot)
        self.addAction(action)

    def _shortcuts(self):
        for i in range(len(self.PAGES)):
            self._shortcut(f"Ctrl+{i + 1}", lambda _c=False, i=i: self.show_page(i))
        self._shortcut(QKeySequence.New, self.new_project)
        self._shortcut(QKeySequence.Open, lambda: self.open_file())
        self._shortcut(QKeySequence.Save, self.save)
        self._shortcut("Ctrl+Shift+S", self.save_as)
        self._shortcut("Ctrl+E", lambda: self.export("png"))
        self._shortcut("Ctrl+P", lambda: self.export("pdf"))
        self._shortcut(QKeySequence.Undo, self.editor.undo)
        self._shortcut("Ctrl+Shift+Z", self.editor.redo)
        self._shortcut("Ctrl+Y", self.editor.redo)
        self._shortcut("Ctrl+,", self.open_settings)
        self._shortcut(QKeySequence.Quit, self.close)
        self._shortcut("Ctrl+Q", self.close)

    def _more_menu(self) -> QMenu:
        menu = QMenu(self)
        entries = [
            (_("New project"), "Ctrl+N", self.new_project),
            (_("Open…"), "Ctrl+O", lambda: self.open_file()),
            None,
            (_("Save"), "Ctrl+S", self.save),
            (_("Save as…"), "Ctrl+Shift+S", self.save_as),
            (_("Export as PNG…"), "Ctrl+E", lambda: self.export("png")),
            (_("Export as SVG…"), None, lambda: self.export("svg")),
            (_("Export as PDF…"), "Ctrl+P", lambda: self.export("pdf")),
            (_("Export as CSV…"), None, lambda: self.export("csv")),
            None,
            (_("Settings…"), "Ctrl+,", self.open_settings),
            (_("Check for updates…"), None, lambda: self.updater.check_now()),
            (_("Keyboard shortcuts"), None, self.show_shortcuts),
            (_("About Gantry"), None, self.about),
            None,
            (_("Quit Gantry"), "Ctrl+Q", self.close),
        ]
        for entry in entries:
            if entry is None:
                menu.addSeparator()
                continue
            text, keys, slot = entry
            action = menu.addAction(text, slot)
            if keys:
                action.setShortcut(QKeySequence(keys))
                action.setShortcutVisibleInContextMenu(True)
                action.setShortcutContext(Qt.WidgetShortcut)  # the window-level ones fire
        return menu

    def open_settings(self):
        SettingsDialog(self.services, self.updater, self).exec()
        self.sidebar.set_branding(self.services.branding.get())

    def show_shortcuts(self):
        rows = [("Ctrl+1 … 4", " / ".join(_(t) for _i, t in self.PAGES)),
                ("Ctrl+N, Ctrl+O, Ctrl+S", _("New, open, save")),
                ("Ctrl+Shift+S", _("Save as")),
                ("Enter, E", _("Open the task, edit it")),
                ("Space", _("Mark done / not done")),
                ("Insert", _("Add a task below")), ("Delete", _("Delete the selection")),
                ("F2", _("Rename the task")),
                ("Ctrl+], Ctrl+[", _("Indent, outdent")),
                ("Alt+Up / Alt+Down", _("Move the task up or down")),
                ("Ctrl+L", _("Make the lower selected task wait for the upper")),
                ("Ctrl+D", _("Duplicate")),
                (_("Drag a bar"), _("Move it; drag its right edge to change the length")),
                (_("Drag the ring at a bar's end"), _("Link it to another task")),
                ("Ctrl+scroll, Ctrl+= / Ctrl+-", _("Zoom the time scale")),
                ("Ctrl+0, Ctrl+T", _("Fit the project, jump to today")),
                ("Ctrl+Z / Ctrl+Shift+Z", _("Undo / redo")),
                ("Ctrl+E, Ctrl+P", _("Export as PNG, PDF"))]
        table = "".join(f"<tr><td style='padding:3px 18px 3px 0'><b>{k}</b></td><td>{v}</td></tr>"
                        for k, v in rows)
        QMessageBox.information(self, _("Keyboard shortcuts"), f"<table>{table}</table>")

    def about(self):
        QMessageBox.about(
            self, _("About Gantry"),
            f"<h3>Gantry {__version__}</h3>"
            f"<p>{_('Gantt charts that open and save GanttProject files.')}</p>"
            f"<p><a href='{HOMEPAGE}'>{HOMEPAGE}</a></p>"
            f"<p>{_('Free software under the GNU General Public License, version 3 or later.')}"
            "</p>")

    # ---- window ----------------------------------------------------------------------------

    def dragEnterEvent(self, event):
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.open_file(url.toLocalFile())
                break

    def closeEvent(self, event):
        if not self.maybe_keep_changes():
            event.ignore()
            return
        QSettings().setValue("window/geometry", self.saveGeometry())
        super().closeEvent(event)
