"""The suite's icons (quezka_ui.icons), plus what only Gantry has: the school's emblem.
Everything else is looked up in the shared module, so `icons.svg`, `icons.APP_ICON` and the rest keep working."""
from pathlib import Path

from quezka_ui import icons as _shared

SCHOOL_EMBLEM = Path(__file__).resolve().parent.parent / "assets" / "school.png"


def __getattr__(name):
    return getattr(_shared, name)
