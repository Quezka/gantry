import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import date

import pytest

from gantry.application.errors import FileAccessError, FileFormatError
from gantry.domain import DepKind
from gantry.infrastructure.files import GanFiles

from .conftest import SAMPLE

files = GanFiles()


def test_reads_the_structure():
    p = files.read(str(SAMPLE))
    assert (p.name, p.company, p.description) == ("Kitchen", "Home", "Refit the kitchen")
    assert [t.name for t in p.tasks] == ["Prepare", "Empty the room", "Remove old units",
                                         "Fit new units", "Done"]
    assert [t.parent for t in p.tasks] == [None, 0, 0, None, None]
    assert p.task(4).milestone and p.task(4).duration == 0
    assert p.calendar.holidays == {date(2026, 10, 14)}
    assert p.calendar.off_weekdays == {5, 6}
    assert p.resource(0).rate == 40 and p.resource(0).email == "dad@example.com"
    assert [r.name for r in p.roles] == ["Helper"]
    assert p.vacations[0].resource == 1


def test_a_dependency_is_stored_on_the_follower():
    """In a .gan file `<depend id="2">` inside task 1 means task 2 waits for task 1."""
    p = files.read(str(SAMPLE))
    assert p.task(1).deps == ()
    d = p.task(2).deps[0]
    assert (d.pred, d.kind, d.lag, d.strong) == (1, DepKind.FINISH_START, 0, True)
    d = p.task(3).deps[0]
    assert (d.pred, d.lag, d.strong) == (2, 1, False)


def test_costs_follow_the_calculated_flag():
    p = files.read(str(SAMPLE))
    assert p.task(3).cost == 1500 and p.task(0).cost is None


def test_writing_and_reading_again_changes_nothing():
    p = files.read(str(SAMPLE))
    data = files.encode(p)
    assert files.decode(data) == p
    assert files.encode(files.decode(data)) == data


def test_what_gantry_does_not_use_survives():
    out = ET.fromstring(files.encode(files.read(str(SAMPLE))))
    assert out.find("view/field[@id='tpd3']") is not None
    assert out.find("tasks/taskproperties/taskproperty[@id='tpc0']") is not None
    task1 = out.find(".//task[@id='1']")
    assert task1.get("priority") == "1" and task1.findtext("notes") == "Ask the neighbours first"
    assert task1.find("customproperty").get("value") == "true"
    assert out.find(".//task[@id='4']").get("thirdDate") == "2026-10-21"
    assert out.find("roles[@roleset-name='Default']") is not None
    assert out.find("previous") is not None
    assert out.get("version") == "3.3.3309" and out.get("view-date") == "2026-10-01"


def test_changing_the_calendar_rewrites_only_the_dates():
    from dataclasses import replace

    from gantry.domain import Calendar
    p = files.read(str(SAMPLE))
    cal = Calendar(frozenset({6}), frozenset({date(2026, 12, 25)}), frozenset())
    out = ET.fromstring(files.encode(replace(p, calendar=cal)))
    week = out.find("calendars/day-types/default-week")
    assert week.get("sat") == "0" and week.get("sun") == "1"
    dates = [(d.get("month"), d.get("date")) for d in out.findall("calendars/date")]
    assert dates == [("12", "25")]
    assert out.find("calendars/day-types/overriden-day-types") is not None


def test_a_new_project_gets_a_complete_file():
    from gantry.domain import Project, Task
    data = files.encode(Project(name="x", tasks=(Task(0, "a", date(2026, 10, 5), 2),)))
    out = ET.fromstring(data)
    assert out.tag == "project" and out.find("tasks/task").get("uid")
    assert files.decode(data).task(0).duration == 2


@pytest.mark.parametrize("data", [b"not xml", b"<other/>", b""])
def test_other_files_are_refused(data):
    with pytest.raises(FileFormatError):
        files.decode(data)


def test_missing_file_is_an_access_error(tmp_path):
    with pytest.raises(FileAccessError):
        files.read(str(tmp_path / "nope.gan"))


def test_write_is_atomic_and_leaves_no_temp_files(tmp_path):
    target = tmp_path / "a.gan"
    files.write(str(target), b"one")
    files.write(str(target), b"two")
    assert target.read_bytes() == b"two" and [p.name for p in tmp_path.iterdir()] == ["a.gan"]


@pytest.mark.skipif(not shutil.which("ganttproject") or not os.environ.get("GANTRY_TEST_GP"),
                    reason="set GANTRY_TEST_GP=1 with GanttProject installed")
def test_ganttproject_reads_what_gantry_writes(tmp_path):
    """The real thing: GanttProject exports the same table from the original and the copy."""
    copy = tmp_path / "copy.gan"
    copy.write_bytes(files.encode(files.read(str(SAMPLE))))
    tables = []
    for name, path in (("a", SAMPLE), ("b", copy)):
        out = tmp_path / f"{name}.csv"
        subprocess.run(["ganttproject", "-export", "csv", "-out", str(out), str(path)],
                       check=True, capture_output=True, timeout=180)
        tables.append(out.read_text())
    assert tables[0] == tables[1]
