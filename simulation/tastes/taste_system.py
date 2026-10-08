"""Tastes at work in the settlement: made as things are met, shown in how they are taken, moved by
what is lived through, and found out."""

from collections.abc import Iterable
from typing import TYPE_CHECKING

from simulation.ai.utility_ai import need_urgency
from simulation.events.event import DomainEvent
from simulation.items.item import ItemDefinition, ItemInstance
from simulation.items.registry import UNKNOWN_CATEGORY
from simulation.memory.memory import Memory
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG
from simulation.tastes.knowledge import PLAYER
from simulation.tastes.leaning import leaning_for
from simulation.tastes.reaction import Moment, felt, liking, reaction_to, side_of
from simulation.tastes.settings import (
    ADVICE,
    DISLIKED,
    EXCHANGE,
    GIVEN,
    KNOWN,
    LIKED,
    NEUTRAL,
    SUSPECTED,
    UNKNOWN,
    PeopleTaste,
)
from simulation.tastes.taste import CATEGORY, HIGHEST, ITEM, LOWEST, PEOPLE, TAG, Taste, TasteProfile, key_of, parts_of

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

REACTION_EVENT = "taste_reaction"
FOUND_OUT_EVENT = "taste_found_out"
MENTION_EVENT = "taste_mentioned"
REFUSAL_EVENT = "trade_refused"
REACTION_IMPORTANCE = 8
SUSPECTED_IMPORTANCE = 12
KNOWN_IMPORTANCE = 22
MENTION_IMPORTANCE = 10
REFUSAL_IMPORTANCE = 12
# What is remembered of a meal that turned on someone: how much it weighs at the least and at the most.
SICKNESS_MEMORY = (20.0, 60.0)
# What a spoken taste and a swap turned down are filed under among the lines.
MENTIONED, REFUSED = "mentioned", "refused"
FOOD_CATEGORY = "food"
WATER_CATEGORY = "water"
# The article a thing is spoken of with once it is one in particular.
DEFINITE = {"un": "el", "una": "la", "unos": "los", "unas": "las"}


class TasteSystem:
    def __init__(self) -> None:
        # How many units of each kind of item the settlement holds, counted once a game hour.
        # Worked out from the world, so it is not saved.
        self._census: tuple[int, dict[str, int]] | None = None

    # ----- what a resident likes -----

    def profile(self, world: "SimulationWorld", resident: Resident) -> TasteProfile:
        """A resident's tastes so far. The first time, it holds what their traits give them."""
        profile = world.taste_profiles.get(resident.resident_id)
        if profile is None:
            profile = world.taste_profiles[resident.resident_id] = TasteProfile()
            settings = world.registries.tastes
            for trait_id in resident.traits:
                trait = world.registries.traits.find(trait_id) or {}
                for tag, value in trait.get("tastes", {}).items():
                    profile.tags[str(tag)] = Taste(leaning=float(value))
                    # A trait is there for anyone to see, and so is the taste that comes of it.
                    world.taste_knowledge.observe(
                        PLAYER,
                        resident.resident_id,
                        key_of(TAG, str(tag)),
                        settings.known_at,
                        settings,
                        reaction_to(float(value), settings),
                    )
        return profile

    def taste(self, world: "SimulationWorld", resident: Resident, kind: str, name: str) -> Taste | None:
        """A resident's taste for something, made now if they have never had one.

        It is kept from then on. None for one item in particular that they have no feeling about
        beyond what its category and tags give them.
        """
        tastes = self.profile(world, resident).of(kind)
        if name not in tastes:
            leaning = leaning_for(world.rng.seed, resident.resident_id, kind, name, world.registries.tastes)
            if leaning is None:
                return None
            tastes[name] = Taste(leaning=leaning)
        return tastes[name]

    def meet(self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition) -> list[str]:
        """Have a resident come across an item: whatever of it they had no taste for, they have now.

        Returns the tastes that were made for it, which are the ones it is their first time of.
        """
        if definition.category == UNKNOWN_CATEGORY:
            return []
        before = set(self.profile(world, resident).keys())
        self.taste(world, resident, CATEGORY, definition.category)
        for tag in definition.preference_tags:
            self.taste(world, resident, TAG, tag)
        self.taste(world, resident, ITEM, definition.item_id)
        return [key for key in self.profile(world, resident).keys() if key not in before]

    def liking(self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition) -> float:
        """How much a resident likes an item, by the tastes they have so far. Makes none."""
        return liking(self.profile(world, resident), definition, world.registries.tastes)

    def believed_liking(
        self, world: "SimulationWorld", observer: Resident, subject: Resident, definition: ItemDefinition
    ) -> float:
        """How much one resident thinks another likes an item: by what they have seen of their tastes, and no more."""
        settings = world.registries.tastes
        knowledge, observer_id, subject_id = world.taste_knowledge, observer.resident_id, subject.resident_id
        return liking(
            self.profile(world, subject),
            definition,
            settings,
            counts=lambda key: knowledge.state(observer_id, subject_id, key, settings) != UNKNOWN,
        )

    def favourites(self, world: "SimulationWorld", resident: Resident) -> dict[str, str | None]:
        """The food and the thing a resident likes best and least, as item IDs, among what the game has.

        Read off the tastes they have so far: None where nothing stands out yet.
        """
        settings = world.registries.tastes
        foods: list[tuple[float, str]] = []
        things: list[tuple[float, str]] = []
        for item_id in world.registries.items.ids():
            definition = world.registries.items.get(item_id)
            if definition.category == WATER_CATEGORY:
                continue
            liked = self.liking(world, resident, definition)
            (foods if definition.category == FOOD_CATEGORY else things).append((liked, item_id))

        def best(scored: list[tuple[float, str]]) -> str | None:
            top = max(scored, key=lambda entry: (entry[0], entry[1]), default=None)
            return top[1] if top is not None and top[0] >= settings.thresholds[LIKED] else None

        def worst(scored: list[tuple[float, str]]) -> str | None:
            bottom = min(scored, key=lambda entry: (entry[0], entry[1]), default=None)
            return bottom[1] if bottom is not None and bottom[0] <= settings.thresholds[DISLIKED] else None

        return {
            "favorite_food": best(foods),
            "hated_food": worst(foods),
            "favorite_item": best(things),
            "hated_item": worst(things),
        }

    # ----- what a thing is worth to them -----

    def worth(
        self,
        world: "SimulationWorld",
        resident: Resident,
        definition: ItemDefinition,
        item: ItemInstance | None = None,
    ) -> float:
        """What an item is worth to a resident: its base value, and what their tastes, their
        needs, who it came from and how few there are make of it. With `item`, one in particular."""
        settings = world.registries.tastes
        share = self.liking(world, resident, definition) / 100.0 * settings.worth_taste
        share += self._need(resident, definition) * settings.worth_need
        if item is not None and item.given_by is not None:
            feelings = world.relationships.get((resident.resident_id, item.given_by))
            if feelings is not None:
                share += max(0.0, feelings.affection) / 100.0 * settings.worth_keepsake
        share += settings.worth_scarcity / max(1, self._units(world, definition.item_id))
        return max(0.0, definition.base_value * (1.0 + share))

    def _need(self, resident: Resident, definition: ItemDefinition) -> float:
        """How pressing the needs an item answers are, from 0 to 1."""
        relief = sum(
            need_urgency(resident, need) for need, delta in definition.effects.items() if delta < 0 and need in NEED_NAMES
        )
        return min(1.0, relief)

    def _units(self, world: "SimulationWorld", definition_id: str) -> int:
        hour = world.clock.total_minutes // 60
        if self._census is None or self._census[0] != hour:
            counted: dict[str, int] = {}
            inventories = [resident.inventory for resident in world.residents.values()] + list(world.containers.values())
            for inventory in inventories:
                for held in inventory.items:
                    counted[held.definition_id] = counted.get(held.definition_id, 0) + held.quantity
            self._census = (hour, counted)
        return self._census[1].get(definition_id, 0)

    # ----- how a thing is taken -----

    def react(
        self,
        world: "SimulationWorld",
        resident: Resident,
        definition: ItemDefinition,
        how: str,
        giver: Resident | None = None,
    ) -> str:
        """Have a resident eat, use or be handed an item, and take it as their tastes have them.

        Tastes they did not have for it are made first. The reaction moves their mood, and what
        they feel for whoever gave it; it is seen by whoever is there, and shows something of
        their tastes to them and to the player. Returns the reaction.
        """
        settings = world.registries.tastes
        if definition.category == UNKNOWN_CATEGORY:
            return NEUTRAL
        first_time = self.meet(world, resident, definition)
        feelings = world.relationships.get((resident.resident_id, giver.resident_id)) if giver is not None else None
        moment = Moment(
            need=self._need(resident, definition),
            mood=resident.mood,
            fondness=feelings.affection if feelings is not None else 0.0,
        )
        reaction = reaction_to(felt(self.liking(world, resident, definition), moment, settings), settings)
        if reaction == NEUTRAL and not definition.preference_tags and giver is None:
            # There is nothing about it to like or loathe, and they do neither: nothing to see.
            return reaction
        effects = settings.effects_of(reaction)
        resident.adjust_mood(effects.mood)
        if giver is not None:
            towards = world.relationship(resident.resident_id, giver.resident_id)
            towards.adjust("affection", effects.affection)
            towards.adjust("trust", effects.trust)
        onlookers = [giver.resident_id] if giver is not None else []
        line = settings.lines.get(how, {}).get(reaction)
        if line:
            room = world.room_at(resident.tile)
            event = DomainEvent(
                REACTION_EVENT,
                REACTION_IMPORTANCE,
                line.format(
                    name=resident.name,
                    thing=f"{definition.article} {definition.name}",
                    giver=giver.name if giver is not None else "",
                ),
                [resident.resident_id, *onlookers],
                location_id=room.room_id if room is not None else None,
                data={
                    "resident_id": resident.resident_id,
                    "item_id": definition.item_id,
                    "reaction": reaction,
                    "how": how,
                    "giver_id": giver.resident_id if giver is not None else None,
                },
            )
            world.emit_event(event, at=resident.tile)
            onlookers.extend(event.witnesses)
        self._show_reaction(world, resident, definition, reaction, effects.shows, onlookers)
        self._learn_from(world, resident, definition, reaction, first_time, moment.fondness if how == GIVEN else 0.0)
        return reaction

    def takes(self, world: "SimulationWorld", resident: Resident, tag: str) -> str:
        """How a resident takes something they do, by the taste for it they have: one of the
        five reactions. The taste is made if they had none. Nothing shows, and nothing moves."""
        taste = self.taste(world, resident, TAG, tag)
        return reaction_to(taste.value if taste is not None else 0.0, world.registries.tastes)

    def pastime(self, world: "SimulationWorld", resident: Resident, tag: str, onlookers: Iterable[str] = ()) -> str:
        """Have a resident set about something they do for the sake of it, and take it as their
        taste for it has them: it moves their mood, and shows something of that taste to the
        player and to whoever is with them. Returns the reaction."""
        reaction = self.takes(world, resident, tag)
        effects = world.registries.tastes.effects_of(reaction)
        resident.adjust_mood(effects.mood)
        self._shown(world, resident, key_of(TAG, tag), effects.shows, onlookers)
        return reaction

    # ----- what living does to a taste -----

    def learn(
        self, world: "SimulationWorld", resident: Resident, kind: str, name: str, push: float, importance: float
    ) -> float:
        """Have something lived through move a taste: what was learned, never the leaning.

        `push` is how good or bad it was, from -1 to 1, and `importance` how much it mattered,
        from 0 to 1: a meal like any other hardly counts, and nearly dying of one counts for a
        great deal. Returns how far the taste moved.
        """
        tastes = self.profile(world, resident).of(kind)
        taste = tastes.get(name) or self.taste(world, resident, kind, name)
        if taste is None:
            # No feeling for the thing itself until now: this is where one begins.
            taste = tastes[name] = Taste()
        before = taste.learned
        moved = max(-1.0, min(1.0, push)) * max(0.0, min(1.0, importance)) * world.registries.tastes.learning
        # What is learned cannot take the taste past the ends of the scale.
        taste.learned = max(LOWEST - taste.leaning, min(HIGHEST - taste.leaning, taste.learned + moved))
        return taste.learned - before

    def _learn_from(
        self,
        world: "SimulationWorld",
        resident: Resident,
        definition: ItemDefinition,
        reaction: str,
        first_time: list[str],
        fondness: float,
    ) -> None:
        """What taking a thing leaves behind: a little for having it again, a little more the
        first time, and something of who it came from."""
        settings = world.registries.tastes
        side = side_of(reaction)
        profile = self.profile(world, resident)
        for tag in definition.preference_tags if side else ():
            taste = profile.tags[tag]
            habit = settings.habits.get(tag, 1.0)
            # Having it again adds less each time, and nothing once that alone has taken it as far as it goes.
            room = max(0.0, 1.0 - abs(taste.learned) / (settings.exposure_cap * habit)) if settings.exposure_cap else 0.0
            self.learn(world, resident, TAG, tag, side, settings.exposure * habit * room / settings.learning if settings.learning else 0.0)
            if key_of(TAG, tag) in first_time:
                self.learn(world, resident, TAG, tag, side, settings.first_mark)
        if fondness:
            # Something of the giver stays with the thing.
            self.learn(world, resident, ITEM, definition.item_id, fondness / 100.0, settings.keepsake_mark)

    def sickened(self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition, harm: float) -> None:
        """A meal has turned on someone. They turn against it, and against what it tasted of, by how bad it was, and remember why."""
        settings = world.registries.tastes
        importance = min(1.0, harm / settings.sickness_full)
        self.learn(world, resident, ITEM, definition.item_id, -1.0, importance)
        for tag in definition.preference_tags:
            self.learn(world, resident, TAG, tag, -1.0, importance * settings.sickness_tags)
        low, high = SICKNESS_MEMORY
        world.memories.remember(
            resident.resident_id,
            Memory(
                f"Enfermé después de comer {definition.article} {definition.name}.",
                low + (high - low) * importance,
                -0.8,
                tags=["taste", "sickness"],
                timestamp=world.clock.total_minutes,
            ),
        )

    # ----- what they like in people -----

    def _concerns(self, taste: PeopleTaste, other: Resident | None, occasion: str) -> bool:
        """Whether a taste in people comes into what is passing between a resident and someone."""
        if occasion not in (taste.when or (EXCHANGE,)):
            return False
        if not (taste.who or taste.jobs or taste.under):
            return True
        if other is None:
            return False
        if taste.under and not set(taste.under) & {intake.sign for intake in other.under}:
            return False
        if taste.jobs and other.job_id not in taste.jobs:
            return False
        return all(low <= getattr(other.personality, side) <= high for side, (low, high) in taste.who.items())

    def take_to(self, world: "SimulationWorld", resident: Resident, other: Resident, occasion: str = EXCHANGE) -> None:
        """Have what a resident likes and dislikes in people weigh on what they feel for
        someone, once something has passed between the two. It goes one way only."""
        settings = world.registries.tastes
        for definition in settings.people.values():
            if not self._concerns(definition, other, occasion):
                continue
            taste = self.taste(world, resident, PEOPLE, definition.taste_id)
            if taste is None:
                continue
            moved = taste.value / 100.0 * settings.people_push
            if moved:
                world.relationship(resident.resident_id, other.resident_id).adjust(definition.feeling, moved)
            self._shown(world, resident, key_of(PEOPLE, definition.taste_id), settings.people_shows, [other.resident_id])

    def heed(self, world: "SimulationWorld", resident: Resident) -> float:
        """How much being told what to do counts with a resident, beside anyone else: 1 for no more and no less."""
        settings = world.registries.tastes
        factor = 1.0
        for definition in settings.people.values():
            if self._concerns(definition, None, ADVICE):
                taste = self.taste(world, resident, PEOPLE, definition.taste_id)
                factor += (taste.value if taste is not None else 0.0) / 100.0 * settings.advice_weight
        return max(0.0, factor)

    def advised(self, world: "SimulationWorld", resident: Resident) -> None:
        """A resident has been told what to do, and done as they would: something of how they take that shows."""
        settings = world.registries.tastes
        for definition in settings.people.values():
            if self._concerns(definition, None, ADVICE):
                self._shown(world, resident, key_of(PEOPLE, definition.taste_id), settings.people_shows)

    def _show_reaction(
        self,
        world: "SimulationWorld",
        resident: Resident,
        definition: ItemDefinition,
        reaction: str,
        shows: float,
        onlookers: Iterable[str],
    ) -> None:
        """What a reaction tells of the tastes behind it.

        Only the tastes that pull the way the reaction went are any the plainer for it: one
        that was outweighed, or that hunger or good company got the better of, stays out of
        sight. The more tags there are to share it, the less each one shows.
        """
        settings = world.registries.tastes
        profile = self.profile(world, resident)
        side = side_of(reaction)

        def agrees(kind: str, name: str) -> bool:
            taste = profile.find(kind, name)
            return taste is not None and side_of(reaction_to(taste.value, settings)) == side

        shown = {}
        if side_of(reaction_to(self.liking(world, resident, definition), settings)) == side:
            shown[key_of(ITEM, definition.item_id)] = shows
        tags = [tag for tag in definition.preference_tags if agrees(TAG, tag)]
        for tag in tags:
            shown[key_of(TAG, tag)] = shows / len(tags)
        if agrees(CATEGORY, definition.category):
            shown[key_of(CATEGORY, definition.category)] = shows * settings.category_share
        onlookers = list(onlookers)
        for key, amount in shown.items():
            self._shown(world, resident, key, amount, onlookers)

    # ----- what is found out -----

    def _shown(
        self, world: "SimulationWorld", resident: Resident, key: str, shows: float, onlookers: Iterable[str] = ()
    ) -> None:
        """Something of a taste has shown: to the player, and to the residents who were there."""
        settings = world.registries.tastes
        showing = self._band(world, resident, key)
        for observer_id in dict.fromkeys([PLAYER, *onlookers]):
            became = world.taste_knowledge.observe(observer_id, resident.resident_id, key, shows, settings, showing)
            if became is not None and observer_id == PLAYER:
                self._announce(world, resident, key, became)

    def _announce(self, world: "SimulationWorld", resident: Resident, key: str, state: str) -> None:
        settings = world.registries.tastes
        leaning = self._seen_as(world, resident, key, state)
        line = settings.lines.get(state, {}).get(leaning)
        if not line:
            return
        world.emit_event(
            DomainEvent(
                FOUND_OUT_EVENT,
                KNOWN_IMPORTANCE if state == KNOWN else SUSPECTED_IMPORTANCE,
                line.format(name=resident.name, label=self.label(world, key)),
                [resident.resident_id],
                data={"resident_id": resident.resident_id, "taste": key, "state": state, "leaning": leaning},
            )
        )

    def _band(self, world: "SimulationWorld", resident: Resident, key: str) -> str:
        """The reaction a taste comes to as it stands right now."""
        settings = world.registries.tastes
        kind, name = parts_of(key)
        if kind == ITEM:
            return reaction_to(self.liking(world, resident, world.registries.items.resolve(name)), settings)
        taste = self.profile(world, resident).find(kind, name)
        return reaction_to(taste.value if taste is not None else 0.0, settings)

    def _seen_as(
        self, world: "SimulationWorld", resident: Resident, key: str, state: str, observer_id: str = PLAYER
    ) -> str:
        """A taste as an onlooker has it, at that much knowledge of it: which way it goes while
        it is only suspected, and how far once it is known. Never how much.

        It is as it looked the last time it showed. If it has moved since, they do not know.
        """
        reaction = world.taste_knowledge.looked(observer_id, resident.resident_id, key) or self._band(world, resident, key)
        if state == KNOWN:
            return reaction
        return (DISLIKED, NEUTRAL, LIKED)[side_of(reaction) + 1]

    def found_out(self, world: "SimulationWorld", resident: Resident, observer_id: str = PLAYER) -> list[tuple[str, str, str]]:
        """What an onlooker, by default the player, has found out of a resident's tastes.

        Each as the taste, how sure it is (`suspected` or `known`) and how it shows: liked,
        disliked or neither while it is suspected, any of the five reactions once it is known.
        There is no number in it, and nothing that has not shown.
        """
        settings = world.registries.tastes
        # What their traits give them is known from the first look.
        self.profile(world, resident)
        found = []
        for key in world.taste_knowledge.keys(observer_id, resident.resident_id):
            state = world.taste_knowledge.state(observer_id, resident.resident_id, key, settings)
            if state in (SUSPECTED, KNOWN):
                found.append((key, state, self._seen_as(world, resident, key, state, observer_id)))
        return found

    def label(self, world: "SimulationWorld", key: str) -> str:
        """What a taste is called where it is spoken of."""
        kind, name = parts_of(key)
        if kind == ITEM:
            definition = world.registries.items.resolve(name)
            return f"{DEFINITE.get(definition.article, definition.article)} {definition.name}"
        return world.registries.tastes.name_of(kind, name) or name.replace("_", " ")

    # ----- other ways a taste shows -----

    def after_exchange(self, world: "SimulationWorld", resident: Resident, partner: Resident) -> bool:
        """Now and then, at the end of a friendly exchange, someone speaks of something they like or cannot stand."""
        settings = world.registries.tastes
        rng = SimulationRNG.keyed(world.rng.seed, "mention", resident.resident_id, world.clock.total_minutes)
        if rng.random() >= settings.mention_chance:
            return False
        profile = self.profile(world, resident)
        strong = [
            (key_of(kind, name), reaction)
            for kind in (TAG, ITEM, PEOPLE)
            for name, taste in sorted(profile.of(kind).items())
            if (reaction := reaction_to(taste.value, settings)) != NEUTRAL
        ]
        if not strong:
            return False
        key, reaction = rng.choice(strong)
        line = settings.lines.get(MENTIONED, {}).get(reaction)
        if not line:
            return False
        event = DomainEvent(
            MENTION_EVENT,
            MENTION_IMPORTANCE,
            line.format(name=resident.name, other=partner.name, label=self.label(world, key)),
            [resident.resident_id, partner.resident_id],
            data={"resident_id": resident.resident_id, "taste": key},
        )
        world.emit_event(event, at=resident.tile)
        self._shown(world, resident, key, settings.mention_shows, [partner.resident_id, *event.witnesses])
        return True

    def bought(self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition) -> None:
        """Someone has paid for a thing. If it is to their liking, that says something."""
        settings = world.registries.tastes
        if side_of(reaction_to(self.liking(world, resident, definition), settings)) > 0:
            self._shown(world, resident, key_of(ITEM, definition.item_id), settings.purchase_shows)

    def refused(self, world: "SimulationWorld", resident: Resident, proposer: Resident, definition: ItemDefinition) -> None:
        """Someone will not take a thing in a swap because it is not to their liking."""
        settings = world.registries.tastes
        reaction = reaction_to(self.liking(world, resident, definition), settings)
        line = settings.lines.get(REFUSED, {}).get(reaction)
        if not line:
            return
        event = DomainEvent(
            REFUSAL_EVENT,
            REFUSAL_IMPORTANCE,
            line.format(name=resident.name, thing=f"{definition.article} {definition.name}", giver=proposer.name),
            [resident.resident_id, proposer.resident_id],
            data={"resident_id": resident.resident_id, "item_id": definition.item_id},
        )
        world.emit_event(event, at=resident.tile)
        self._shown(
            world,
            resident,
            key_of(ITEM, definition.item_id),
            settings.refusal_shows,
            [proposer.resident_id, *event.witnesses],
        )

