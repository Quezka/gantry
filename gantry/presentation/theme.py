"""Gantry's look is the suite's theme (quezka_ui.theme) in the school's blue and red.
This module sets that brand and then stands in for the shared one, so the app's imports keep working."""
import sys

from quezka_ui import theme as _shared


def _css(t) -> str:
    return f"""
    QSplitter#planSplit::handle {{ background: transparent; }}
    QSplitter#planSplit::handle:hover {{ background: {t.accent_soft}; }}
    QSplitter#planSplit::handle:pressed {{ background: {t.border}; }}
    """


_shared.school_brand(css=_css)
sys.modules[__name__] = _shared
