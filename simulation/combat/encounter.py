"""Coming on raiders: who they are, what can be done about it before a blow is struck, and
what is left when it is over.

No pygame here. The same seed is the same raiders and the same end.
"""

from simulation.rng import SimulationRNG
from dataclasses import dataclass, field

from simulation.combat.model import MELEE, CombatData, Fighter, RaiderKind, Weapon
from simulation.combat.rules import FLED, LOST, WON, Fight, sever_odds, severable, stumps

# What can be done on coming on them, before anything else.
FIGHT, RUN, PAY = "fight", "run", "pay"
CHOICES = (FIGHT, RUN, PAY)
# What the parts that can be lost are called.
PARTS = {
    "head": "la cabeza", "torso": "medio cuerpo",
    "arm_left": "un brazo", "arm_right": "un brazo", "forearm_left": "un antebrazo", "forearm_right": "un antebrazo",
    "hand_left": "una mano", "hand_right": "una mano",
    "leg_left": "una pierna", "leg_right": "una pierna", "shin_left": "media pierna", "shin_right": "media pierna",
    "foot_left": "un pie", "foot_right": "un pie",
}


def hero(
    data: CombatData,
    name: str,
    attributes: dict[str, float],
    weapon_id: str,
    level: int = 1,
    health: float | None = None,
    gun_id: str | None = None,
    rounds: int | None = None,
) -> Fighter:
    """Whoever the settlement sent out, as a fighter: as they are, with what they carry and
    the health they have. `gun_id` is something to fire, carried besides a weapon for the
    hand, and `rounds` how many times what they fire can be: what it holds, unless it is said."""
    most = data.tuning.hero_health
    weapon = data.weapons[weapon_id]
    gun = data.weapons[gun_id] if gun_id else None
    if gun is not None and (gun.kind == MELEE or weapon.kind != MELEE):
        raise ValueError("What is carried besides is something to fire, and what is in the hand is not")
    health = most if health is None else min(most, health)
    fired = gun if gun is not None else weapon
    return Fighter(
        name, level, dict(attributes), weapon, most, health, hero=True, gun=gun,
        rounds=fired.ammo if rounds is None else max(0, rounds),
    )


def _weapon(data: CombatData, kind: RaiderKind, level: int, rng: SimulationRNG) -> Weapon:
    """What a raider of a level carries: the higher the level, the further along what their sort carries."""
    step = max(1, data.tuning.weapon_step_levels)
    best = min(len(kind.weapons) - 1, (level - 1) // step)
    # Now and then one carries something a step short of what they could.
    at = best if best == 0 or rng.random() < 0.7 else best - 1
    return data.weapons[kind.weapons[at]]


def raider(data: CombatData, kind: RaiderKind, level: int, rng: SimulationRNG) -> Fighter:
    """A raider of a sort and a level, with attributes and health of their own."""
    tuning = data.tuning
    attributes = {}
    for name in data.attributes:
        points = tuning.raider_attribute + tuning.raider_attribute_per_level * level + kind.leans.get(name, 0.0)
        attributes[name] = float(min(10, max(1, round(points + rng.uniform(-tuning.raider_spread, tuning.raider_spread)))))
    health = (
        tuning.raider_health
        + tuning.raider_health_per_constitution * attributes.get("constitution", tuning.middle)
        + tuning.raider_health_per_level * (level - 1)
    ) * kind.health
    weapon = _weapon(data, kind, level, rng)
    return Fighter(
        kind.name, level, attributes, weapon, health, health, kind=kind.kind_id, beast=kind.beast, rounds=weapon.ammo
    )


def raiders(
    data: CombatData,
    zone_id: str,
    rng: SimulationRNG,
    kind_id: str | None = None,
    count: int | None = None,
    level: int | None = None,
) -> list[Fighter]:
    """Whoever lies in wait in a zone this once: one to as many as the zone has at most, each
    of a level the zone has, and of a sort there is at that level. Whoever is trying a fight
    out may say the sort, how many and of what level in place of what the zone would have."""
    zone = data.zone(zone_id)
    # One is the commonest, and each more is half as common.
    counts = list(range(1, zone.most + 1))
    drawn = rng.choices(counts, weights=[0.5 ** (each - 1) for each in counts])[0]
    band = []
    for _ in range(count if count else drawn):
        of_level = level if level else rng.randint(*zone.levels)
        sorts = [kind for kind in data.raiders.values() if kind.from_level <= of_level]
        kind = rng.choices(sorts, weights=[each.weight for each in sorts])[0]
        band.append(raider(data, data.raiders[kind_id] if kind_id in data.raiders else kind, of_level, rng))
    return band


def payable(foes: list[Fighter]) -> bool:
    """Whether those met can be handed something to let somebody by: a beast takes nothing."""
    return not any(foe.beast for foe in foes)


def price(data: CombatData, foes: list[Fighter]) -> int:
    """How many things raiders take to let somebody by."""
    return data.tuning.pay_per_raider * len(foes)


@dataclass
class Aftermath:
    """What is left of coming on raiders."""

    outcome: str
    health: float
    # What is brought away from it, in units by item ID, and what their trade is the richer by.
    loot: dict[str, int] = field(default_factory=dict)
    experience: int = 0
    # Whether what they carried was taken from them, and how much of it was handed over to be let by.
    robbed: bool = False
    paid: int = 0
    died: bool = False
    # The part they lost for good to whoever stood over them once they were down, if any.
    maimed: str | None = None
    # Everything they are without of what they went in with, as the body plan calls it: of a
    # limb cut twice, where it was cut nearest the trunk.
    lost: list[str] = field(default_factory=list)

    def told(self, name: str) -> str:
        """What happened, in a line."""
        gone = [PARTS.get(part, part) for part in self.lost]
        if self.died:
            how = " sin cabeza" if "la cabeza" in gone else " partido en dos" if "medio cuerpo" in gone else ""
            return f"{name} no vuelve: acabaron con él{how}."
        missing = f" Vuelve sin {' ni '.join(gone)}." if gone else ""
        if self.outcome == WON:
            brought = ", ".join(f"{thing} ({units})" for thing, units in self.loot.items()) or "nada"
            return f"{name} los tumba y se lleva: {brought}. Experiencia +{self.experience}.{missing}"
        if self.outcome == FLED:
            return f"{name} escapa con {self.health:.0f} de salud y lo que llevaba encima.{missing}"
        if self.outcome == PAY:
            return f"{name} paga {self.paid} cosas y le dejan pasar."
        return f"{name} cae: le quitan lo que llevaba y vuelve arrastrándose.{missing}"


def aftermath(data: CombatData, fight: Fight, rng: SimulationRNG) -> Aftermath:
    """What comes of a fight that is over: what is taken from the fallen, or what is lost."""
    tuning = data.tuning
    health = fight.hero.health
    # What they are without: of a limb cut twice, where it was cut nearest the trunk.
    lost = stumps(fight.hero, tuning)
    if fight.outcome == WON:
        loot: dict[str, int] = {}
        for foe in fight.foes:
            if foe.beast:
                # A beast carries nothing: what is taken from it is a piece of it.
                loot[tuning.beast_loot] = loot.get(tuning.beast_loot, 0) + 1
                continue
            loot[tuning.scrap] = loot.get(tuning.scrap, 0) + rng.randint(*tuning.loot_scrap) * foe.level
            if foe.weapon.weapon_id != tuning.bare_hands and rng.random() < tuning.weapon_drop:
                loot[foe.weapon.weapon_id] = loot.get(foe.weapon.weapon_id, 0) + 1
            if rng.random() < tuning.kit_drop:
                # Now and then one of them had on them what they would have mended themselves with.
                loot[tuning.kit] = loot.get(tuning.kit, 0) + 1
        return Aftermath(WON, health, loot, tuning.experience_per_level * sum(foe.level for foe in fight.foes), lost=lost)
    if fight.outcome == FLED:
        return Aftermath(FLED, health, lost=lost)
    # Down among them: robbed for certain, and now and then worse. Nobody comes back without a head.
    if any(part in lost for part in tuning.deadly) or rng.random() < tuning.death:
        return Aftermath(LOST, 0.0, robbed=True, died=True, lost=lost)
    maimed = None
    left = severable(fight.hero, tuning)
    if not lost and left and rng.random() < tuning.maim:
        # Whoever stood over them took something of them: the smaller the part, the likelier.
        maimed = rng.choices(left, [sever_odds(part, tuning) for part in left])[0]
        lost = [maimed]
    return Aftermath(LOST, 1.0, robbed=True, maimed=maimed, lost=lost)


def decide_alone(fight: Fight, courage: float, carried: int, data: CombatData) -> str:
    """What somebody does on coming on raiders with nobody to ask: by how brave they are, from
    0 to 1, how they are faring and how many there are. They pay only if they have it to pay."""
    foes = fight.foes
    theirs = sum(foe.health for foe in foes) / max(1.0, fight.hero.health)
    odds = courage * 1.4 - 0.25 * (len(foes) - 1) - 0.3 * (theirs - 1.0)
    if odds >= 0.35:
        return FIGHT
    if payable(foes) and carried >= price(data, foes) and courage < 0.35:
        return PAY
    return RUN


def meet(
    data: CombatData,
    who: Fighter,
    zone_id: str,
    rng: SimulationRNG,
    choice: str | None = None,
    medkits: int = 0,
    courage: float = 0.5,
    carried: int = 0,
) -> Aftermath:
    """Come on raiders in a zone and see it through with nobody watching: what is chosen is
    what the player advised, or else what they would do themselves."""
    fight = Fight(data, who, raiders(data, zone_id, rng), rng, medkits)
    choice = choice if choice in CHOICES else decide_alone(fight, courage, carried, data)
    if choice == PAY and payable(fight.foes) and carried >= price(data, fight.foes):
        return Aftermath(PAY, who.health, paid=price(data, fight.foes))
    if choice == RUN and fight.flee(before=True):
        return Aftermath(FLED, who.health)
    fight.resolve()
    return aftermath(data, fight, rng)
