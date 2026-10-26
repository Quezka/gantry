"""Gantry's look is the suite's theme (quezka_ui.theme) in the school's blue and red.
This module sets that brand and then stands in for the shared one, so the app's imports keep working."""
import sys

from quezka_ui import theme as _shared


def _css(t) -> str:
    return f"""
    #school {{ color: {t.text}; font-weight: 600; font-size: 9pt; }}
    #place {{ color: {t.muted}; font-size: 8.5pt; }}
    QSplitter#planSplit::handle {{ background: transparent; }}
    QSplitter#planSplit::handle:hover {{ background: {t.accent_soft}; }}
    QSplitter#planSplit::handle:pressed {{ background: {t.border}; }}
    """


_shared.set_brand(
    light={"sidebar": "#eceef3", "accent": "#0a5ad6", "accent_hover": "#0047b3", "accent_soft": "#e2ecfd",
           "warning": "#d97706", "flag": "#b3121b"},
    dark={"sidebar": "#131519", "accent": "#4d94ff", "accent_hover": "#6aa6ff", "accent_soft": "#15264a",
          "warning": "#f5a524", "flag": "#ff5c5c"},
    css=_css)
sys.modules[__name__] = _shared
