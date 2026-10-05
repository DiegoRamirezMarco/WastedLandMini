from dataclasses import dataclass, field

from simulation.health.injury import Injury
from simulation.items.inventory import Inventory
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.personality import Personality
from world.map import Tile

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
    current_action: str = "idle"
    facing: str = "down"
    activity: Activity | None = None
    # IDs of traits from the trait registry.
    traits: list[str] = field(default_factory=list)
    # Job from the job registry, and the object that is this resident's post for it.
    job_id: str | None = None
    post_id: str | None = None
    # Minutes worked towards the next thing their job produces.
    work_progress: int = 0
    injuries: list[Injury] = field(default_factory=list)
    # Tiles walked during the last tick, starting where the tick began. Lets the
    # presentation animate movement; it is not saved.
    trail: list[Tile] = field(default_factory=list, compare=False, repr=False)

    @property
    def health(self) -> float:
        """From 100, unhurt, down to 0, dead: what their injuries leave them."""
        return max(0.0, 100.0 - sum(injury.severity for injury in self.injuries))

    @property
    def tile(self) -> Tile:
        return (self.x, self.y)

    @property
    def destination(self) -> Tile:
        """Where the resident will be standing once the current walk ends."""
        if self.activity is not None and self.activity.path:
            return self.activity.path[-1]
        return self.tile
