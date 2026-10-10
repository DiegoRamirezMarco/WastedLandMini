"""Who fights out there and with what (S70): attributes, weapons and the figures a fight goes
by, all of it data.

It was tried apart from the game and carried in as it was. A fight knows nothing of the
settlement: whoever sets one up says who is in it, and takes what comes of it back.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "combat.json"
# The kind of weapon that has to be carried right up to whoever it is used on.
MELEE = "melee"


@dataclass(frozen=True)
class WeaponKind:
    kind_id: str
    name: str
    # The attributes a weapon of this kind may go by, and no others.
    scales_with: tuple[str, ...]
    # How much of the time between two blows goes by before the first: little for what is
    # fired from where they stand, more for what has to be carried up to somebody.
    opening: float = 0.8


@dataclass(frozen=True)
class Weapon:
    weapon_id: str
    name: str
    kind: str
    # The least and the most a blow does, before whoever deals it is counted.
    damage: tuple[float, float]
    # Seconds from one blow to the next.
    seconds: float
    # How much it goes by each attribute: shares of one.
    scales: dict[str, float]
    # How it is shown being used, for whoever shows it.
    clip: str = "fight"
    # How apt it is to take a part off somebody with a telling blow, from 0 for never to 1.
    severs: float = 0.0
    # How many times it can be fired in a fight before it is empty. None for what needs nothing.
    ammo: int = 0


@dataclass(frozen=True)
class RaiderKind:
    """A sort of raider: what they carry at each level and what they are better at."""

    kind_id: str
    name: str
    from_level: int
    weapons: tuple[str, ...]
    # Points over what anybody of their level has, by attribute.
    leans: dict[str, float] = field(default_factory=dict)
    weight: float = 1.0
    # Whether it is no raider but a beast: nothing can be handed to it to be let by, and it
    # carries nothing worth taking. How many times the health of anybody of its level it has,
    # and how many times as big it is shown.
    beast: bool = False
    health: float = 1.0
    size: float = 1.0


@dataclass(frozen=True)
class ZoneRaiders:
    zone_id: str
    name: str
    # The lowest and highest level of whoever lies in wait, and the most of them at once.
    levels: tuple[int, int]
    most: int = 3
    # How likely somebody going through it is to come on them, from 0 to 1.
    chance: float = 0.0


@dataclass(frozen=True)
class Tuning:
    """The figures a fight goes by. Every one of them is in the data."""

    middle: float = 5.0
    damage_per_point: float = 0.08
    least_damage: float = 0.3
    speed_per_point: float = 0.03
    dodge: float = 0.05
    dodge_per_point: float = 0.03
    most_dodge: float = 0.35
    hero_health: float = 100.0
    raider_health: float = 26.0
    raider_health_per_constitution: float = 4.0
    raider_health_per_level: float = 9.0
    raider_attribute: float = 3.0
    raider_attribute_per_level: float = 0.8
    raider_spread: float = 1.2
    weapon_step_levels: int = 2
    # Paces of ground there are between them on coming on one another, the least and the
    # most, and how far behind one another raiders stand.
    start_gap: tuple[float, float] = (7.0, 9.0)
    rank_gap: float = 1.3
    # How near somebody has to be to be struck with what is in a hand, and how fast anybody walks.
    reach: float = 1.0
    walk: float = 2.6
    walk_per_point: float = 0.12
    # How much of what somebody can take a blow has to be to make them reel, and to put them
    # on the ground; how long each costs them; how far each sends them; and how many times
    # over a telling blow at close quarters has to tell to floor anybody.
    reels_at: float = 0.11
    floors_at: float = 0.22
    reel_seconds: float = 0.45
    floored_seconds: float = 1.7
    reel_push: float = 0.2
    floored_push: float = 0.5
    crit_floors: float = 2.0
    # How many times as hard something fired has to land to put anybody on the ground.
    shot_floors: float = 1.7
    # A shove: how far it sends somebody, and how much further for each point of strength; how
    # long it takes to give; how long before another can be given; how likely it is to put
    # them on the ground, and how much likelier for each point of strength over what they
    # stand firm with; the little harm it does; and how often a raider right up to somebody
    # shoves them and does not strike.
    shove_push: float = 2.2
    shove_push_per_point: float = 0.15
    shove_seconds: float = 0.9
    shove_rest: float = 3.0
    shove_floors: float = 0.25
    shove_floors_per_point: float = 0.06
    shove_damage: tuple[float, float] = (1.0, 3.0)
    raider_shoves: float = 0.12
    # How likely a telling blow is to take a part off, by how many times over it tells, the
    # most first, before the weapon is counted.
    crit_severs: tuple[tuple[float, float], ...] = ((3.0, 0.75), (2.0, 0.3))
    # The parts there are to lose, as the game's body plan calls them. A head comes off only
    # with the blow that kills.
    # Each arm and each leg, as the parts of it that can come off, from the trunk outwards:
    # one for every joint it bends at. With any of them gone the limb is of no use.
    arms: tuple[tuple[str, ...], ...] = (("arm_left", "forearm_left", "hand_left"), ("arm_right", "forearm_right", "hand_right"))
    legs: tuple[tuple[str, ...], ...] = (("leg_left", "shin_left", "foot_left"), ("leg_right", "shin_right", "foot_right"))
    # What comes off only with the blow that kills: nobody goes on without it.
    deadly: tuple[str, ...] = ("head", "torso")
    # How likely each part of a limb is to be the one that comes off, from the trunk
    # outwards, each against the others: the smaller the part, the likelier. And the same
    # for what comes off with the blow that kills, in the order it is written.
    sever_odds: tuple[float, ...] = (1.0, 2.0, 4.0)
    deadly_odds: tuple[float, ...] = (3.0, 1.0)
    head: str = "head"
    # What somebody loses a second for each part that is gone, bleeding; and how much slower
    # they strike for each arm gone, and walk for each leg.
    bleed: float = 2.0
    arm_slower: float = 0.4
    leg_slower: float = 0.45
    # How likely a blow of somebody who is not the hero is to be a telling one: for anybody,
    # for each point of their strength over the constitution of whoever takes it, and at the
    # most; how many of those are as good as a mark stopped dead in the middle; and how much
    # less apt theirs are to take a part off than the hero's, with the same points making it
    # the likelier.
    foe_crit: float = 0.05
    foe_crit_per_point: float = 0.02
    most_foe_crit: float = 0.3
    foe_perfect: float = 0.2
    foe_severs: float = 0.5
    foe_sever_per_point: float = 0.1
    # What is taken from a beast that is beaten.
    beast_loot: str = "beast_claw"
    # What is taken from raiders that are beaten, by item ID: so much of it for each level of each.
    scrap: str = "scrap"
    # What raiders carry to mend themselves with, by item ID, and how likely each is to have
    # one on them when they are beaten.
    kit: str = "medicine"
    kit_drop: float = 0.35
    # Over somebody on the ground: how often a fist comes down, the die each throws with their
    # strength to see whether whoever is under throws the other off, and how far off.
    pound_seconds: float = 0.42
    pound_die: int = 6
    pound_push: float = 0.9
    # How long it takes to get down on somebody before the first blow, and how much whoever
    # is on top has over whoever is under when the dice are thrown: their weight is on them.
    pound_down: float = 0.3
    pound_edge: int = 2
    # How much of what a blow fills of the telling one a fist brought down on somebody fills.
    pound_crit: float = 0.4
    # What anybody strikes with when there is nothing else: by weapon ID.
    bare_hands: str = "fists"
    steady_per_point: float = 0.06
    # How much slower each raider strikes for each other one beside them: they get in one
    # another's way, so that three are not three times one.
    many_slower: float = 0.25
    crit_per_hit: float = 0.26
    crit_per_second: float = 0.035
    # How near the middle the mark has to be stopped for each multiplier, the nearest first,
    # as a share of half the bar, and what is said of it.
    crit_marks: tuple[tuple[float, float, str], ...] = ((0.1, 3.0, "¡PERFECTO!"), (0.3, 2.0, "¡Buen golpe!"), (1.0, 1.25, "Rozado"))
    crit_sweeps_per_second: float = 1.15
    crit_sweeps: int = 4
    # How fast the fight goes on while the mark is being stopped, as a share of its pace.
    aiming_time: float = 0.2
    medkit: float = 35.0
    heals_below: float = 0.35
    flees_below: float = 0.15
    flee: float = 0.5
    flee_per_point: float = 0.06
    flee_per_foe: float = 0.1
    flee_before: float = 0.2
    flee_stumble_seconds: float = 1.6
    pay_per_raider: int = 2
    death: float = 0.12
    maim: float = 0.18
    loot_scrap: tuple[int, int] = (1, 3)
    weapon_drop: float = 0.3
    experience_per_level: int = 40


@dataclass(frozen=True)
class CombatData:
    attributes: tuple[str, ...]
    kinds: dict[str, WeaponKind]
    weapons: dict[str, Weapon]
    raiders: dict[str, RaiderKind]
    zones: dict[str, ZoneRaiders]
    tuning: Tuning

    def zone(self, zone_id: str | None) -> ZoneRaiders:
        """Who lies in wait in a zone: for one nothing is written of, as in the last that is
        written of, which is the furthest there is."""
        if zone_id in self.zones:
            return self.zones[zone_id]
        return list(self.zones.values())[-1] if self.zones else ZoneRaiders(str(zone_id), str(zone_id), (1, 1), 1)


@dataclass
class Fighter:
    """Somebody in a fight: what they are capable of, what they hold, and how they stand."""

    name: str
    level: int
    attributes: dict[str, float]
    weapon: Weapon
    max_health: float
    health: float
    # The hero is whoever the settlement sent out. Everybody else is against them.
    hero: bool = False
    kind: str = ""
    # What they carry to fire besides what is in their hand, if anything.
    gun: Weapon | None = None
    # Seconds until their next blow.
    wait: float = 0.0
    # Where they stand along the line of the fight, in paces, and how many more seconds they
    # are on the ground for after a blow that put them there.
    at: float = 0.0
    floored: float = 0.0
    # The parts they have lost, in the order they did, and whether what bleeds has been seen to.
    lost: list[str] = field(default_factory=list)
    staunched: bool = False
    # Seconds until they can shove again.
    shove_wait: float = 0.0
    # Whether they are a beast and no raider.
    beast: bool = False
    # How many more times what they fire can be fired.
    rounds: int = 0

    @property
    def down(self) -> bool:
        return self.health <= 0.0

    def attribute(self, name: str, middle: float = 5.0) -> float:
        return float(self.attributes.get(name, middle))


def combat_from_data(data: dict[str, Any]) -> CombatData:
    attributes = tuple(str(name) for name in data.get("attributes", []))
    kinds = {
        str(kind_id): WeaponKind(
            str(kind_id), str(entry.get("name", kind_id)), tuple(str(each) for each in entry["scales_with"]),
            float(entry.get("opening", 0.8)),
        )
        for kind_id, entry in data.get("kinds", {}).items()
    }
    for kind in kinds.values():
        if not kind.scales_with or set(kind.scales_with) - set(attributes):
            raise ValueError(f"Weapons of kind {kind.kind_id} go by attributes there are not")
    weapons = {}
    for weapon_id, entry in data.get("weapons", {}).items():
        low, high = (float(value) for value in entry["damage"])
        weapon = Weapon(
            str(weapon_id), str(entry.get("name", weapon_id)), str(entry["kind"]), (low, high), float(entry["seconds"]),
            {str(name): float(share) for name, share in entry.get("scales", {}).items()}, str(entry.get("clip", "fight")),
            float(entry.get("severs", 0.0)), int(entry.get("ammo", 0)),
        )
        if weapon.ammo < 0 or (weapon.ammo and weapon.kind == MELEE):
            raise ValueError(f"Weapon {weapon_id} is fired so many times, if it is fired at all")
        if not 0.0 <= weapon.severs <= 1.0:
            raise ValueError(f"Weapon {weapon_id} takes parts off somebody never, always, or something between")
        kind = kinds.get(weapon.kind)
        if kind is None:
            raise ValueError(f"Weapon {weapon_id} is of a kind there is not: {weapon.kind}")
        if not weapon.scales or set(weapon.scales) - set(kind.scales_with) or any(share <= 0 for share in weapon.scales.values()):
            # A blade goes by strength and dexterity, a gun by dexterity and senses, a beam by
            # senses and mind: which of the two, and how much of each, is the weapon's to say.
            raise ValueError(f"Weapon {weapon_id} goes by something a {kind.name} weapon does not: one of {kind.scales_with}")
        if not 0 < low <= high or weapon.seconds <= 0:
            raise ValueError(f"Weapon {weapon_id} does some harm, the least first, every so often")
        weapons[weapon.weapon_id] = weapon
    raiders = {}
    for kind_id, entry in data.get("raiders", {}).items():
        raider = RaiderKind(
            str(kind_id), str(entry.get("name", kind_id)), int(entry.get("from_level", 1)),
            tuple(str(each) for each in entry["weapons"]),
            {str(name): float(points) for name, points in entry.get("leans", {}).items()}, float(entry.get("weight", 1.0)),
            bool(entry.get("beast", False)), float(entry.get("health", 1.0)), float(entry.get("size", 1.0)),
        )
        if raider.health <= 0 or raider.size <= 0:
            raise ValueError(f"Raiders of kind {kind_id} have some health and some size")
        if not raider.weapons or set(raider.weapons) - set(weapons) or raider.weight <= 0 or raider.from_level < 1:
            raise ValueError(f"Raiders of kind {kind_id} carry weapons there are, from a level of one or more")
        raiders[raider.kind_id] = raider
    zones = {}
    for zone_id, entry in data.get("zones", {}).items():
        low, high = (int(value) for value in entry.get("raiders", (1, 1)))
        if not 1 <= low <= high or int(entry.get("most", 3)) < 1:
            raise ValueError(f"Zone {zone_id} has raiders of a level from one up, the lowest first, and one at least")
        chance = float(entry.get("chance", 0.0))
        if not 0.0 <= chance <= 1.0:
            raise ValueError(f"Zone {zone_id} has raiders come on with a chance from 0 to 1")
        zones[str(zone_id)] = ZoneRaiders(
            str(zone_id), str(entry.get("name", zone_id)), (low, high), int(entry.get("most", 3)), chance
        )
    values = dict(data.get("tuning", {}))
    for name in ("loot_scrap", "start_gap", "shove_damage", "deadly"):
        if name in values:
            values[name] = tuple(values[name])
    for name in ("sever_odds", "deadly_odds"):
        if name in values:
            values[name] = tuple(float(odds) for odds in values[name])
            if not values[name] or min(values[name]) <= 0.0:
                raise ValueError(f"{name} says how likely each part is against the others: more than nothing, each")
    for name in ("arms", "legs"):
        if name in values:
            # A limb written as the one part is a limb that comes off whole or not at all.
            values[name] = tuple((limb,) if isinstance(limb, str) else tuple(limb) for limb in values[name])
    if "crit_severs" in values:
        values["crit_severs"] = tuple((float(times), float(chance)) for times, chance in values["crit_severs"])
    if "crit_marks" in values:
        values["crit_marks"] = tuple((float(reach), float(times), str(said)) for reach, times, said in values["crit_marks"])
    unknown = set(values) - set(Tuning.__dataclass_fields__)
    if unknown:
        raise ValueError(f"The tuning of a fight has figures nothing goes by: {sorted(unknown)}")
    tuning = Tuning(**values)
    reaches = [reach for reach, _, _ in tuning.crit_marks]
    if not reaches or reaches != sorted(reaches) or reaches[-1] < 1.0:
        raise ValueError("The marks of a telling blow go from the nearest the middle to the whole bar")
    return CombatData(attributes, kinds, weapons, raiders, zones, tuning)


def load_combat(path: Path = DATA_PATH) -> CombatData:
    return combat_from_data(json.loads(path.read_text(encoding="utf-8")))
