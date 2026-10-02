"""The only place that knows which adapters implement which ports."""
from __future__ import annotations

from . import HOMEPAGE, __version__
from .application.branding import Branding
from .application.editor import Editor
from .application.ports import KeyValueStore, ProjectFiles, ReleaseFeed, UpdateInstaller
from .application.services import Services
from .application.updates import UpdateService
from .infrastructure.files import GanFiles
from .infrastructure.settings import JsonSettings
from .infrastructure.updates import GitHubReleaseFeed, platform_installer


def build_services(files: ProjectFiles | None = None, settings: KeyValueStore | None = None,
                   releases: ReleaseFeed | None = None,
                   installer: UpdateInstaller | None = None) -> Services:
    settings = settings or JsonSettings()
    return Services(
        editor=Editor(files or GanFiles()),
        branding=Branding(settings),
        updates=UpdateService(
            releases or GitHubReleaseFeed(HOMEPAGE.removeprefix("https://github.com/"),
                                          __version__),
            installer or platform_installer(), settings, __version__),
    )
