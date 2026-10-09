"""The ways a resident has of doing what everybody does: walking, eating, fighting, having
words, sitting. All of it data.

Which way is theirs changes nothing of what happens: it is how it looks, and it is kept with them.
"""

import zlib
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Any

# What a body is doing when a kind of manner shows.
WALK, EAT, FIGHT, ARGUE, SIT, TALK = "walk", "eat", "fight", "argue", "sit", "talk"
OCCASIONS = (WALK, EAT, FIGHT, ARGUE, SIT, TALK)
# The middle of what somebody's nature is measured in, and how far it is from there to either end.
NATURE_MIDDLE, NATURE_REACH = 50.0, 50.0
IDLE_CLIP = "idle"


@dataclass(frozen=True)
class MannerKind:
    kind_id: str
    name: str
    occasion: str
    # Fighting with something tagged so calls for this kind, and not for the bare-handed one.
    weapon_tag: str | None = None
    # Tag of something to put in the hand of whoever is shown trying the manner out.
    prop_tag: str | None = None
    # What a resident has to be at for a kind that is no doing of its own to show: sitting is
    # how they rest by a fire, or eat, and not something they do besides.
    actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class MannerDefinition:
    manner_id: str
    kind: str
    name: str
    description: str = ""
    # The clip of the body plan that shows it.
    clip: str = IDLE_CLIP
    # Turns of the clip a second. For walking, turns to a step with each foot: a whole number,
    # so that a stride ends where the next minute's begins.
    rate: float = 1.0
    # Whose it is before anybody chooses: what of somebody's nature it goes with, and how
    # much, less than nothing for what it goes against. A manner with none goes with nobody
    # more than with anybody else.
    leans: Mapping[str, float] = field(default_factory=dict)

    def suits(self, nature: Mapping[str, float]) -> float:
        """How well it goes with somebody's nature: nothing for one that leans no way, or
        for somebody in the middle of everything."""
        return sum(
            weight * (float(nature.get(part, NATURE_MIDDLE)) - NATURE_MIDDLE) / NATURE_REACH
            for part, weight in self.leans.items()
        )


@dataclass(frozen=True)
class MannerSettings:
    kinds: dict[str, MannerKind] = field(default_factory=dict)
    manners: dict[str, MannerDefinition] = field(default_factory=dict)

    def of_kind(self, kind_id: str) -> list[MannerDefinition]:
        """The manners there are to choose from for one kind, in the order they were given."""
        return [manner for manner in self.manners.values() if manner.kind == kind_id]

    def kind_for(self, occasion: str, tags: Collection[str] = ()) -> MannerKind | None:
        """The kind of manner that shows on an occasion, for whoever has things tagged `tags` to hand."""
        kinds = [kind for kind in self.kinds.values() if kind.occasion == occasion]
        armed = next((kind for kind in kinds if kind.weapon_tag is not None and kind.weapon_tag in tags), None)
        return armed or next((kind for kind in kinds if kind.weapon_tag is None), None)

    def during(self, occasion: str, action: str) -> MannerKind | None:
        """The kind of manner of an occasion that shows while a resident is at an action, if one does."""
        return next(
            (kind for kind in self.kinds.values() if kind.occasion == occasion and action in kind.actions), None
        )

    def default(
        self, resident_id: str, kind_id: str, nature: Mapping[str, float] | None = None
    ) -> MannerDefinition | None:
        """The manner of someone who was never given one: always the same for the same ID, so
        that nobody moves like everybody else while they wait to be told how.

        Where the manners of a kind lean towards one nature or another, and `nature` is
        somebody's, it is whichever suits them best, and among those that suit them as well
        as each other the same one for the same ID."""
        choices = self.of_kind(kind_id)
        if not choices:
            return None
        if nature is not None and any(manner.leans for manner in choices):
            best = max(manner.suits(nature) for manner in choices)
            choices = [manner for manner in choices if manner.suits(nature) >= best - 1e-9]
        return choices[zlib.crc32(f"{resident_id}:{kind_id}".encode("utf-8")) % len(choices)]

    def of(
        self, resident_id: str, chosen: Mapping[str, str], kind_id: str, nature: Mapping[str, float] | None = None
    ) -> MannerDefinition | None:
        """The manner a resident has for one kind: the one chosen for them, or else their own
        by default, which goes by their `nature` where the manners of that kind do."""
        manner = self.manners.get(chosen.get(kind_id, ""))
        if manner is not None and manner.kind == kind_id:
            return manner
        return self.default(resident_id, kind_id, nature)

    def tidy(self, chosen: Mapping[str, Any]) -> dict[str, str]:
        """What of a choice of manners can be kept: known manners, each under its own kind."""
        kept = {}
        for kind_id, manner_id in chosen.items():
            manner = self.manners.get(manner_id) if isinstance(manner_id, str) else None
            if manner is not None and manner.kind == kind_id:
                kept[str(kind_id)] = manner.manner_id
        return kept


def manner_settings_from_data(data: dict[str, Any]) -> MannerSettings:
    kinds = {}
    for kind_id, values in data.get("kinds", {}).items():
        occasion = str(values.get("occasion", kind_id))
        if occasion not in OCCASIONS:
            raise ValueError(f"Manner kind {kind_id} shows on an unknown occasion: {occasion}")
        weapon_tag = values.get("weapon_tag")
        prop_tag = values.get("prop_tag", weapon_tag)
        kinds[str(kind_id)] = MannerKind(
            str(kind_id),
            str(values.get("name", kind_id)),
            occasion,
            str(weapon_tag) if weapon_tag is not None else None,
            str(prop_tag) if prop_tag is not None else None,
            tuple(str(action) for action in values.get("actions", ())),
        )
    manners = {}
    for manner_id, values in data.get("manners", {}).items():
        kind = str(values.get("kind", ""))
        if kind not in kinds:
            raise ValueError(f"Manner {manner_id} is of an unknown kind: {kind}")
        rate = float(values.get("rate", 1.0))
        if rate <= 0 or (kinds[kind].occasion == WALK and rate != int(rate)):
            raise ValueError(f"Manner {manner_id} goes at a rate it cannot have: {rate}")
        manners[str(manner_id)] = MannerDefinition(
            str(manner_id),
            kind,
            str(values.get("name", manner_id)),
            str(values.get("description", "")),
            str(values.get("clip", IDLE_CLIP)),
            rate,
            {str(part): float(weight) for part, weight in values.get("leans", {}).items()},
        )
    return MannerSettings(kinds, manners)
