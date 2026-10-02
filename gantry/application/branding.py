"""The school's name, town and emblem, shown in the sidebar and on exports."""
from __future__ import annotations

from .inputs import BrandingInput
from .ports import KeyValueStore
from .records import BrandingRecord

DEFAULT_SCHOOL = 'I.T.S. "E. Alessandrini"'
DEFAULT_PLACE = "Montesilvano (PE)"


class Branding:
    def __init__(self, settings: KeyValueStore):
        self._settings = settings

    def get(self) -> BrandingRecord:
        return BrandingRecord(self._settings.get("school") or DEFAULT_SCHOOL,
                              self._settings.get("place") or DEFAULT_PLACE,
                              self._settings.get("school_logo") or None,
                              self._settings.get("school_on_exports") != "no")

    def set(self, data: BrandingInput) -> BrandingRecord:
        self._settings.set("school", data.school.strip() or None)
        self._settings.set("place", data.place.strip() or None)
        self._settings.set("school_logo", data.logo or None)
        self._settings.set("school_on_exports", None if data.on_exports else "no")
        return self.get()
