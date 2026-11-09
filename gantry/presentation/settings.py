"""Settings: appearance and language."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget
from quezka_ui.settings import SettingsWindow

from . import i18n, theme, uiscale
from ..application.types import CURRENCIES
from .background import restart_app
from .i18n import _
from ..application.inputs import BrandingInput
from .icons import SCHOOL_EMBLEM
from .views.common import Segmented, logo_tile


class SettingsDialog(SettingsWindow):
    """Appearance, School, Updates in the suite's Settings window."""

    def __init__(self, services, updater=None, parent=None):
        super().__init__(_("Settings"), _("Close"), parent, width=860, height=600)
        self.services = services
        manager = theme.manager()

        look = self.section(_("Appearance"), "palette")
        card = look.card()
        mode = Segmented([("system", _("System")), ("light", _("Light")), ("dark", _("Dark"))])
        mode.set_value(manager.mode)
        mode.changed.connect(manager.set_mode)
        card.row(_("Appearance"), mode, _("Exported pictures are always drawn on white."))
        card.switch(_("Glass look"), manager.glass,
                    _("Menus, bars and headers blur what's under them."), manager.set_glass)
        if hasattr(manager, "set_see_through"):
            from quezka_ui import theme as kit_theme
            possible = kit_theme.SEE_THROUGH_POSSIBLE
            see_through = card.switch(_("See-through windows"), manager.see_through and possible,
                            _("The desktop shows through, blurred. Takes effect the next time the app starts.") if possible
                            else _("On GNOME this needs the Blur my Shell extension."), manager.set_see_through)
            see_through.setEnabled(possible)
        card.switch(_("High contrast (black and white, thick lines)"), manager.contrast,
                    on_toggled=manager.set_contrast)
        card = look.card()
        self.language = QComboBox()
        for code, name in i18n.LANGUAGES:
            self.language.addItem(_(name) if code == "" else name, code)
        self.language.setCurrentIndex(max(0, self.language.findData(i18n.chosen_language())))
        self.restart = QPushButton(_("Restart Gantry now"))
        self.restart.hide()
        self.restart.clicked.connect(self._restart)
        self.restart_size = self.restart
        self.language.currentIndexChanged.connect(self._language_changed)
        card.row(_("Interface language"), self.language, stretch_control=True)
        self.scale = QComboBox()
        for choice in uiscale.CHOICES:
            self.scale.addItem(_("Automatic") if choice == "auto" else f"{choice}%", choice)
        self.scale.setCurrentIndex(max(0, self.scale.findData(uiscale.chosen())))
        self.scale.currentIndexChanged.connect(self._scale_changed)
        card.row(_("Interface size"), self.scale, _("Applies after a restart. Automatic makes everything a little "
                                                   "smaller on small screens."), stretch_control=True)
        card.wide(self.restart)
        card = look.card()
        self.currency = QComboBox()
        for code, name, symbol in CURRENCIES:
            self.currency.addItem(f"{_(name)} ({symbol})", code)
        self.currency.setCurrentIndex(max(0, self.currency.findData(services.currency.code())))
        self.currency.currentIndexChanged.connect(
            lambda _row: services.currency.set(self.currency.currentData()))
        card.row(_("Currency"), self.currency, _("Shown next to costs and daily rates. A project file holds plain "
                                                "numbers, so nothing is converted."), stretch_control=True)

        school_page = self.section(_("School"), "school")
        brand = services.branding.get()
        self.school = QLineEdit(brand.school)
        self.place = QLineEdit(brand.place)
        self.logo = brand.logo
        self.preview = QLabel()
        self._preview()
        pick = QPushButton(_("Choose logo…"))
        pick.clicked.connect(self._pick_logo)
        reset = QPushButton(_("Use the school emblem"))
        reset.clicked.connect(lambda: (setattr(self, "logo", None), self._preview()))
        logo_row = QHBoxLayout()
        logo_row.addWidget(self.preview)
        logo_row.addWidget(pick)
        logo_row.addWidget(reset)
        logo_row.addStretch()
        card = school_page.card()
        card.row(_("Name"), self.school, stretch_control=True)
        card.row(_("Town"), self.place, stretch_control=True)
        logo_box = QWidget()
        logo_box.setLayout(logo_row)
        card.row(_("Logo"), logo_box)
        self.on_exports = card.switch(_("Put the school's name and emblem on exported charts"), brand.on_exports)

        updates = self.section(_("Updates"), "download")
        card = updates.card()
        card.switch(_("Check for new versions once a day"), services.updates.auto_check(),
                    on_toggled=services.updates.set_auto_check)
        check = QPushButton(_("Check now"))
        check.setEnabled(updater is not None)
        if updater is not None:
            check.clicked.connect(lambda: updater.check_now())
        card.row(_("You have version {version}.").format(version=services.updates.current_version), check)

    def _scale_changed(self):
        uiscale.set_chosen(self.scale.currentData())
        self.restart_size.show()

    def _preview(self):
        self.preview.setPixmap(logo_tile(self.logo or str(SCHOOL_EMBLEM), str(SCHOOL_EMBLEM), 38,
                                         self.devicePixelRatioF()))

    def _pick_logo(self):
        path, _chosen = QFileDialog.getOpenFileName(self, _("School logo"), "",
                                                    _("Pictures") + " (*.png *.jpg *.jpeg *.svg)")
        if path:
            self.logo = path
            self._preview()

    def done(self, result):
        self.services.branding.set(BrandingInput(self.school.text(), self.place.text(),
                                                 self.logo, self.on_exports.isChecked()))
        super().done(result)

    def _language_changed(self):
        i18n.set_chosen_language(self.language.currentData())
        self.restart.show()

    def _restart(self):
        self.accept()
        restart_app()
