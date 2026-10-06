"""The ways a resident has of doing what everybody does: walking, eating, fighting. All of it data.

Which way is theirs changes nothing of what happens: it is how it looks, and it is kept with them.
"""

import zlib
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Any

# What a body is doing when a kind of manner shows.
WALK, EAT, FIGHT = "walk", "eat", "fight"
OCCASIONS = (WALK, EAT, FIGHT)
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

    def default(self, resident_id: str, kind_id: str) -> MannerDefinition | None:
        """The manner of someone who was never given one: always the same for the same ID, so
        that nobody moves like everybody else while they wait to be told how."""
        choices = self.of_kind(kind_id)
        if not choices:
            return None
        return choices[zlib.crc32(f"{resident_id}:{kind_id}".encode("utf-8")) % len(choices)]

    def of(self, resident_id: str, chosen: Mapping[str, str], kind_id: str) -> MannerDefinition | None:
        """The manner a resident has for one kind: the one chosen for them, or else their own by default."""
        manner = self.manners.get(chosen.get(kind_id, ""))
        if manner is not None and manner.kind == kind_id:
            return manner
        return self.default(resident_id, kind_id)

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
        )
    return MannerSettings(kinds, manners)
