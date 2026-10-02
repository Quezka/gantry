import itertools
import os
from datetime import date, datetime
from pathlib import Path

import pytest

os.environ.setdefault("QT_SCALE_FACTOR", "1")  # tests measure pixels: no automatic scaling

from gantry.application.branding import Branding
from gantry.application.currency import Currency
from gantry.application.editor import Editor
from gantry.application.updates import UpdateService
from gantry.infrastructure.files import GanFiles
from gantry.infrastructure.settings import MemorySettings

from .fakes import FakeInstaller, FakeReleases

SAMPLE = Path(__file__).parent / "data" / "sample.gan"
TODAY = date(2026, 10, 2)  # a Friday


@pytest.fixture
def editor():
    counter = itertools.count(1)
    return Editor(GanFiles(), today=lambda: TODAY, new_uid=lambda: f"uid{next(counter)}")


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 30, 10, 0)

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def releases():
    return FakeReleases()


@pytest.fixture
def installer():
    return FakeInstaller()


@pytest.fixture
def services(editor, releases, installer, clock):
    from gantry.application.services import Services
    settings = MemorySettings()
    return Services(editor, Branding(settings), Currency(settings),
                    UpdateService(releases, installer, settings, "0.2.0", clock))


@pytest.fixture(scope="session", autouse=True)
def empty_clipboard():
    """Qt's headless test platform crashes at exit when the clipboard still holds data a
    test copied (real desktops don't), so empty it before the tests end."""
    yield
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    app = QApplication.instance()
    if app is not None:
        app.clipboard().clear()


@pytest.fixture(autouse=True)
def no_errors_in_slots(monkeypatch):
    """PySide prints an exception raised inside a Qt slot and carries on, so a broken redraw
    looks like a pass. Make any such exception fail the test."""
    import sys
    caught = []
    monkeypatch.setattr(sys, "excepthook", lambda kind, value, tb: caught.append(value))
    yield
    assert not caught, f"Uncaught exception in a Qt slot: {caught[0]!r}"
