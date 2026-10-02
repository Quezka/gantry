"""Which currency costs and daily rates are shown in. Only the symbol changes: a .gan file
holds plain numbers, so nothing is converted."""
from __future__ import annotations

from .ports import KeyValueStore

DEFAULT = "EUR"
CURRENCIES = (  # (code, name, symbol)
    ("EUR", "Euro", "€"),
    ("GBP", "Pound sterling", "£"),
    ("USD", "US dollar", "$"),
    ("CHF", "Swiss franc", "CHF"),
    ("RUB", "Russian ruble", "₽"),
)
SYMBOLS = {code: symbol for code, _name, symbol in CURRENCIES}


class Currency:
    def __init__(self, settings: KeyValueStore):
        self._settings = settings

    def code(self) -> str:
        code = self._settings.get("currency")
        return code if code in SYMBOLS else DEFAULT

    def set(self, code: str) -> None:
        self._settings.set("currency", code if code in SYMBOLS else None)

    def symbol(self) -> str:
        return SYMBOLS[self.code()]
