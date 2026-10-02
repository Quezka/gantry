"""Everything the UI can ask for, in one place (built by `bootstrap`)."""
from __future__ import annotations

from dataclasses import dataclass

from .branding import Branding
from .currency import Currency
from .editor import Editor
from .updates import AvailableUpdate, UpdateService


@dataclass
class Services:
    editor: Editor
    branding: Branding
    currency: Currency
    updates: UpdateService


__all__ = ["AvailableUpdate", "Services"]
