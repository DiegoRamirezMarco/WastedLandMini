from dataclasses import dataclass, field

from simulation.health.injury import Injury
from simulation.items.inventory import Inventory
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.personality import Personality
from simulation.work.expedition import Expedition
from world.map import Tile
from world.pathfinding import Point

FACINGS = ("down", "left", "right", "up")


@dataclass
class Resident:
    resident_id: str
    name: str
    x: int = 0
    y: int = 0
    needs: Needs = field(default_factory=Needs)
    personality: Personality = field(default_factory=Personality)
    inventory: Inventory = field(default_factory=Inventory)
    # General spirits, separate from immediate stress. Low mood makes work slower and quarrels likelier.
    mood: float = 50.0
    current_action: str = "idle"
    facing: str = "down"
    activity: Activity | None = None
    # IDs of traits from the trait registry.
    traits: list[str] = field(default_factory=list)
    # Their way of walking, eating and so on: a manner from the manner registry for each kind
    # chosen for them. A kind not named here goes by one that is always the same for them.
    manners: dict[str, str] = field(default_factory=dict)
    # Job from the job registry, and the object that is this resident's post for it.
    job_id: str | None = None
    post_id: str | None = None
    # Minutes worked towards the next thing their job produces.
    work_progress: int = 0
    # Day of the week, counted from 0, on which they do not work. None for no day off.
    day_off: int | None = None
    # What their work has earned them and they have not spent yet.
    credits: float = 0.0
    # Age in years. Romance is only ever between adults.
    age: int = 30
    # ID of the resident they are a couple with, who names them in turn.
    couple_with: str | None = None
    # The trip outside the settlement they are on, while they are on one.
    expedition: Expedition | None = None
    # Day on which they last set out, so that nobody goes twice in a day.
    last_expedition_day: int = 0
    # Whether they are looking for a job to take, as someone newly arrived is.
    seeks_work: bool = False
    injuries: list[Injury] = field(default_factory=list)
    # IDs of the limbs they have lost for good, from the limb registry.
    lost_limbs: list[str] = field(default_factory=list)
    # Where they walked during the last tick, starting where the tick began: a point for each
    # tile stepped on, on the straight line they were following, so up to half a tile off the
    # middle of it. Lets the presentation animate movement, and tells the others which tiles
    # were walked over this minute. It is not saved: it starts again every minute.
    trail: list[Point] = field(default_factory=list, compare=False, repr=False)
    # The points of the stretch they are walking that are still ahead of them. Not saved either.
    ahead: list[Point] = field(default_factory=list, compare=False, repr=False)

    @property
    def health(self) -> float:
        """From 100, unhurt, down to 0, dead: what their injuries leave them."""
        return max(0.0, 100.0 - sum(injury.severity for injury in self.injuries))

    @property
    def away(self) -> bool:
        """Outside the settlement: they see nobody, and nobody sees or reaches them."""
        return self.expedition is not None

    @property
    def tile(self) -> Tile:
        return (self.x, self.y)

    @property
    def destination(self) -> Tile:
        """Where the resident will be standing once the current walk ends."""
        if self.activity is not None and self.activity.path:
            return self.activity.path[-1]
        return self.tile

    def adjust_mood(self, delta: float) -> None:
        self.mood = max(0.0, min(100.0, self.mood + delta))
