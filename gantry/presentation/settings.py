"""Settings: appearance and language."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout,
)

from . import i18n, theme, uiscale
from .fit import scrollable
from .background import restart_app
from .i18n import _
from ..application.inputs import BrandingInput
from .icons import SCHOOL_EMBLEM
from .views.common import Card, Segmented, caption, label, logo_tile


class SettingsDialog(QDialog):
    def __init__(self, services, updater=None, parent=None):
        super().__init__(parent)
        self.services = services
        self.setWindowTitle(_("Settings"))
        self.setMinimumWidth(460)
        manager = theme.manager()
        appearance = Card(_("Appearance"))
        mode = Segmented([("system", _("System")), ("light", _("Light")), ("dark", _("Dark"))])
        mode.set_value(manager.mode)
        mode.changed.connect(manager.set_mode)
        appearance.add(mode)
        appearance.add(label(_("Exported pictures are always drawn on white."), "hint"))

        language = Card(_("Language"))
        self.language = QComboBox()
        for code, name in i18n.LANGUAGES:
            self.language.addItem(_(name) if code == "" else name, code)
        self.language.setCurrentIndex(max(0, self.language.findData(i18n.chosen_language())))
        self.restart_size = QPushButton(_("Restart Gantry now"))
        self.restart_size.hide()
        self.restart_size.clicked.connect(self._restart)
        self.restart = QPushButton(_("Restart Gantry now"))
        self.restart.hide()
        self.restart.clicked.connect(self._restart)
        self.language.currentIndexChanged.connect(self._language_changed)
        language.add(caption(_("Interface language")))
        language.add(self.language)
        language.add(self.restart)

        brand = services.branding.get()
        self.school = QLineEdit(brand.school)
        self.place = QLineEdit(brand.place)
        self.logo = brand.logo
        self.on_exports = QCheckBox(_("Put the school's name and emblem on exported charts"))
        self.on_exports.setChecked(brand.on_exports)
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
        form = QFormLayout()
        form.addRow(_("Name"), self.school)
        form.addRow(_("Town"), self.place)
        form.addRow(_("Logo"), logo_row)
        school = Card(_("School"))
        school.body.addLayout(form)
        school.add(self.on_exports)

        size = Card(_("Interface size"))
        self.scale = QComboBox()
        for choice in uiscale.CHOICES:
            self.scale.addItem(_("Automatic") if choice == "auto" else f"{choice}%", choice)
        self.scale.setCurrentIndex(max(0, self.scale.findData(uiscale.chosen())))
        self.scale.currentIndexChanged.connect(self._scale_changed)
        size.add(self.scale)
        size.add(label(_("Applies after a restart. Automatic makes everything a little smaller "
                         "on small screens."), "hint"))
        size.add(self.restart_size)

        updates = Card(_("Updates"))
        auto = QCheckBox(_("Check for new versions once a day"))
        auto.setChecked(services.updates.auto_check())
        auto.toggled.connect(services.updates.set_auto_check)
        updates.add(auto)
        check = QPushButton(_("Check now"))
        check.setEnabled(updater is not None)
        if updater is not None:
            check.clicked.connect(lambda: updater.check_now())
        updates.add(check)
        updates.add(label(_("You have version {version}.").format(
            version=services.updates.current_version), "hint"))

        close = QPushButton(_("Close"))
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)
        layout.addWidget(appearance)
        layout.addWidget(language)
        layout.addWidget(size)
        layout.addWidget(school)
        layout.addWidget(updates)
        layout.addLayout(row)
        scrollable(self)

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
