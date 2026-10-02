"""Errors the use cases raise. Their messages are shown to the user (translated)."""


class ApplicationError(Exception):
    """Something the user can understand and act on."""


class NotFound(ApplicationError):
    pass


class FileFormatError(ApplicationError):
    """The file isn't a GanttProject project (.gan) that Gantry can read."""


class FileAccessError(ApplicationError):
    """The file couldn't be read or written (missing, no permission, disk full…)."""


class UpdateError(ApplicationError):
    """Checking for, downloading or installing a new version didn't work."""
