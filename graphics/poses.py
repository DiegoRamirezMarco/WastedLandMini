"""How what residents do is shown: the clip of each kind of work, with its tool and without, and
where the things they hold by a handle have theirs. All of it data, in `data/poses.json`.

None of it changes what happens. Whether somebody has a tool, and what they are doing, is the
simulation's to say; this is only how that looks.
"""

import functools
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Point = tuple[float, float]

POSES_PATH = Path(__file__).resolve().parent.parent / "data" / "poses.json"
# The clip of any work that has none of its own.
PLAIN_WORK = "work"


@dataclass(frozen=True)
class Handle:
    """Where the handle of a thing is on its picture, and how long the thing is in a hand."""

    # The end it is held by and its far end, in hundredths of the side of the picture.
    start: Point
    end: Point
    # How long the handle is shown from one of those to the other, in the skeleton's own measure.
    long: float


@dataclass(frozen=True)
class Doing:
    """How something done is shown: its clip, and how many turns of that a second."""

    clip: str = PLAIN_WORK
    rate: float = 1.0
    # Something seen in the hand meanwhile that is no item of anybody's: it is there for the look of it.
    prop: str | None = None


@dataclass(frozen=True)
class JobDoing:
    """How the work of a job is shown: with bare hands, and with the tool of the job in them."""

    bare: Doing = Doing()
    # None for a job that looks the same with its tool as without.
    tool: Doing | None = None


@dataclass(frozen=True)
class OnTheGround:
    """How somebody who sleeps on the ground is shown: lying down on it, once; lying there; and
    getting up from it, once."""

    down: Doing
    asleep: Doing
    up: Doing


@dataclass(frozen=True)
class Talking:
    """How two who have something to say to each other are shown. Whoever speaks does so in
    their own way, and `speak` is the way of anybody with none; the other listens. At what
    is told to make somebody laugh, whoever hears it laughs. Whoever brought it up greets
    the other first, for so many minutes of the game. And some of what two do together is
    not talk at all: `silent`, by what it is."""

    speak: Doing = Doing()
    listen: Doing = Doing()
    laugh: Doing | None = None
    laugh_at: tuple[str, ...] = ()
    greet: Doing | None = None
    greet_minutes: float = 0.0
    silent: tuple[str, ...] = ()


@dataclass(frozen=True)
class Poses:
    # By the ID of the item, or of the prop, that is held.
    handles: dict[str, Handle] = field(default_factory=dict)
    # Work at a post, whatever the job, and by job where it has a look of its own.
    work: Doing = Doing()
    jobs: dict[str, JobDoing] = field(default_factory=dict)
    # Building, and taking apart.
    build: Doing = Doing()
    # What a body does, once, when something is put among what it carries or taken out of it.
    # None where nothing is made of that.
    pocket: Doing | None = None
    # Sleeping on the ground, for want of a bed. None where nothing is made of that either.
    rough: OnTheGround | None = None
    # Sitting on something that is for sitting on, in place of one's own way of sitting on the
    # ground. None where whoever has a seat under them sits as they would without.
    seat: Doing | None = None
    # Talking. None where two who talk stand as anybody stands.
    talk: Talking | None = None

    def working(self, job_id: str | None, with_tool: bool) -> Doing:
        """How somebody at their post is shown, by their job and whether they have its tool in hand."""
        job = self.jobs.get(job_id or "")
        if job is None:
            return self.work
        return job.tool if with_tool and job.tool is not None else job.bare


def _point(value: Any, what: str) -> Point:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"Expected two numbers for {what}, got {value!r}")
    return (float(value[0]), float(value[1]))


def _doing(data: Any, what: str, fallback: Doing = Doing()) -> Doing:
    if data is None:
        return fallback
    if not isinstance(data, dict):
        raise ValueError(f"{what} must say what clip shows it")
    rate = float(data.get("rate", fallback.rate))
    if rate <= 0:
        raise ValueError(f"{what} goes at a rate it cannot have: {rate}")
    prop = data.get("prop")
    return Doing(str(data.get("clip", fallback.clip)), rate, str(prop) if prop is not None else None)


def poses_from_data(data: dict[str, Any]) -> Poses:
    handles = {}
    for thing, values in data.get("handles", {}).items():
        handle = Handle(_point(values["from"], f"handle of {thing}"), _point(values["to"], f"handle of {thing}"), float(values["long"]))
        if handle.start == handle.end or handle.long <= 0:
            raise ValueError(f"The handle of {thing} must run from one point to another and be of some length")
        handles[str(thing)] = handle
    work = _doing(data.get("work"), "Work")
    jobs = {}
    for job_id, values in data.get("jobs", {}).items():
        bare = _doing(values, f"The work of {job_id}", work)
        tool = _doing(values["tool"], f"The work of {job_id} with its tool", bare) if "tool" in values else None
        jobs[str(job_id)] = JobDoing(bare, tool)
    pocket = _doing(data["pocket"], "Putting away") if "pocket" in data else None
    rough = None
    if "sleep_rough" in data:
        said = data["sleep_rough"]
        if not isinstance(said, dict) or not {"down", "asleep", "up"} <= said.keys():
            raise ValueError("Sleeping on the ground is lying down, lying there and getting up: it needs all three")
        rough = OnTheGround(*(_doing(said[part], f"Sleeping on the ground ({part})") for part in ("down", "asleep", "up")))
    seat = _doing(data["seat"], "Sitting on a seat") if "seat" in data else None
    talk = None
    if "talk" in data:
        said = data["talk"]
        if not isinstance(said, dict) or not {"speak", "listen"} <= said.keys():
            raise ValueError("Talking is speaking and listening: it needs both")
        talk = Talking(
            _doing(said["speak"], "Speaking"), _doing(said["listen"], "Listening"),
            _doing(said["laugh"], "Laughing") if "laugh" in said else None,
            tuple(str(action) for action in said.get("laugh_at", ())),
            _doing(said["greet"], "Greeting") if "greet" in said else None,
            max(0.0, float(said.get("greet_minutes", 0.0))),
            tuple(str(action) for action in said.get("silent", ())),
        )
    return Poses(handles, work, jobs, _doing(data.get("build"), "Building", work), pocket, rough, seat, talk)


def load_poses(path: Path = POSES_PATH) -> Poses:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {path}")
    return poses_from_data(data)


@functools.cache
def builtin_poses() -> Poses:
    """The game's own, loaded once. It is read-only."""
    return load_poses()
