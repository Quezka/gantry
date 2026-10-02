"""The enums and fixed choices the UI needs, re-exported so it never imports the domain."""
from ..domain import DepKind  # noqa: F401

KIND_CODES = {  # what the interface shows for each kind of dependency
    DepKind.FINISH_START: "FS", DepKind.START_START: "SS",
    DepKind.FINISH_FINISH: "FF", DepKind.START_FINISH: "SF",
}

# Task colours (the first is the default look); any #rrggbb a file holds is shown as it is.
PALETTE = ("", "#5b5bd6", "#30a46c", "#f5a524", "#e5484d", "#0d9dda", "#d6409f", "#7c8798")

WEEKDAYS = tuple(range(7))  # Monday is 0
