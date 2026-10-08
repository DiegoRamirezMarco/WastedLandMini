import functools
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from simulation.ai.affect import AffectSettings, affect_settings_from_data
from simulation.ai.leisure import LeisureSettings, leisure_settings_from_data
from simulation.economy.ledger import ResourceSettings, resource_settings_from_data
from simulation.economy.settings import EconomySettings, economy_settings_from_data
from simulation.events.decision import DecisionDefinition, decision_definition_from_data
from simulation.events.world_event import RAID, STRANGER, WorldEventSettings, world_event_settings_from_data
from simulation.family.settings import FamilySettings, family_settings_from_data
from simulation.politics.government import LEANINGS, PoliticsSettings, politics_settings_from_data
from simulation.politics.law import LawSettings, law_settings_from_data
from simulation.politics.proposal import ENACT_LAW, REPEAL_LAW, ProposalSettings, proposal_settings_from_data
from simulation.health.injury import (
    InjuryDefinition,
    LimbDefinition,
    injury_definition_from_data,
    limb_definition_from_data,
)
from simulation.items.custom_content import load_custom_items
from simulation.items.item import TASTE_TAG_PATTERN
from simulation.items.registry import ItemRegistry
from simulation.residents.manner import MannerSettings, manner_settings_from_data
from simulation.residents.attributes import AttributeSettings, attribute_settings_from_data
from simulation.residents.personality import Personality
from simulation.social.bonds import BondSettings, bond_settings_from_data
from simulation.social.interaction import InteractionDefinition, interaction_definition_from_data
from simulation.justice.settings import JusticeSettings, justice_settings_from_data
from simulation.substances.substance import SubstanceSettings, substance_settings_from_data
from simulation.tastes.settings import TasteSettings, taste_settings_from_data
from simulation.housing.decor import DecorSettings, decor_settings_from_data
from simulation.housing.housing import HousingSettings, housing_settings_from_data
from simulation.tutorial.tutorial import BUILDING, JOB, OBJECT, TutorialDefinition, tutorial_definition_from_data
from simulation.work.craft import CraftSettings, craft_settings_from_data
from simulation.work.construction import ConstructionSettings, construction_settings_from_data
from simulation.work.expedition import ExpeditionSettings, expedition_settings_from_data
from simulation.work.job import INTO_STATION, JobDefinition, job_definition_from_data
from simulation.work.research import EFFECTS, JOB_PACE, ResearchSettings, research_settings_from_data
from simulation.work.rush import RushSettings, rush_settings_from_data
from world.interactable import InteractableDefinition, interactable_definition_from_data
from world.custom_content import load_custom_buildings, load_custom_interactables
from world.map import TerrainDefinition
from world.settlement import SettlementLayout, layout_from_data
from world.urbanism import BuildingDefinition, building_definition_from_data

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CUSTOM_CONTENT_DIR = DATA_DIR.parent / "custom_content"
DEFAULT_MAP_ID = "settlement"


class PersonalityRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, Personality] = {}

    def register(self, personality_id: str, definition: Personality) -> None:
        if personality_id in self._definitions:
            raise ValueError(f"Duplicate personality id: {personality_id}")
        self._definitions[personality_id] = definition

    def get(self, personality_id: str) -> Personality:
        return self._definitions[personality_id]

    def load_json_file(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected object in {path}")
        for personality_id, values in data.items():
            if not isinstance(values, dict):
                raise ValueError(f"Expected object for personality {personality_id} in {path}")
            self.register(
                str(personality_id),
                Personality(
                    aggression=float(values.get("aggression", 50.0)),
                    empathy=float(values.get("empathy", 50.0)),
                    impulsiveness=float(values.get("impulsiveness", 50.0)),
                    sociability=float(values.get("sociability", 50.0)),
                    greed=float(values.get("greed", 50.0)),
                    courage=float(values.get("courage", 50.0)),
                    libido=float(values.get("libido", 50.0)),
                    charisma=float(values.get("charisma", 50.0)),
                    leadership=float(values.get("leadership", 50.0)),
                ),
            )


class JsonDefinitionRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, dict[str, Any]] = {}

    def register(self, definition_id: str, definition: dict[str, Any]) -> None:
        if definition_id in self._definitions:
            raise ValueError(f"Duplicate definition id: {definition_id}")
        self._definitions[definition_id] = definition

    def get(self, definition_id: str) -> dict[str, Any]:
        return self._definitions[definition_id]

    def find(self, definition_id: str) -> dict[str, Any] | None:
        return self._definitions.get(definition_id)

    def ids(self) -> list[str]:
        return list(self._definitions)

    def load_json_file(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected object in {path}")
        for definition_id, definition in data.items():
            if not isinstance(definition, dict):
                raise ValueError(f"Expected object for {definition_id} in {path}")
            self.register(str(definition_id), dict(definition))


class InteractableRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, InteractableDefinition] = {}

    def register(self, definition: InteractableDefinition) -> None:
        if definition.kind in self._definitions:
            raise ValueError(f"Duplicate interactable kind: {definition.kind}")
        self._definitions[definition.kind] = definition

    def replace(self, definition: InteractableDefinition) -> None:
        """Replace a known kind while every placed object keeps referring to its stable ID."""
        if definition.kind not in self._definitions:
            raise KeyError(f"Unknown interactable kind: {definition.kind}")
        self._definitions[definition.kind] = definition

    def get(self, kind: str) -> InteractableDefinition:
        return self._definitions[kind]

    def find(self, kind: str) -> InteractableDefinition | None:
        return self._definitions.get(kind)

    def kinds(self) -> list[str]:
        return list(self._definitions)

    def load_json_file(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected object in {path}")
        for kind, values in data.items():
            if not isinstance(values, dict):
                raise ValueError(f"Expected object for interactable {kind} in {path}")
            self.register(interactable_definition_from_data(str(kind), values))


@dataclass
class BuiltInRegistries:
    items: ItemRegistry = field(default_factory=ItemRegistry)
    personalities: PersonalityRegistry = field(default_factory=PersonalityRegistry)
    traits: JsonDefinitionRegistry = field(default_factory=JsonDefinitionRegistry)
    interactables: InteractableRegistry = field(default_factory=InteractableRegistry)
    buildings: dict[str, BuildingDefinition] = field(default_factory=dict)
    terrain: dict[str, TerrainDefinition] = field(default_factory=dict)
    maps: dict[str, SettlementLayout] = field(default_factory=dict)
    interactions: dict[str, InteractionDefinition] = field(default_factory=dict)
    decisions: dict[str, DecisionDefinition] = field(default_factory=dict)
    jobs: dict[str, JobDefinition] = field(default_factory=dict)
    # What a resident is capable of, and what each of the six is good for.
    attributes: AttributeSettings = field(default_factory=AttributeSettings)
    # The levels of a job, and the kinds of thing each job teaches.
    crafts: CraftSettings = field(default_factory=CraftSettings)
    injuries: dict[str, InjuryDefinition] = field(default_factory=dict)
    # Limbs a resident can lose for good, by limb ID.
    limbs: dict[str, LimbDefinition] = field(default_factory=dict)
    economy: EconomySettings = field(default_factory=EconomySettings)
    # What the settlement lives on, and which items count as each.
    resources: ResourceSettings = field(default_factory=ResourceSettings)
    # What pushing a post does, and what it risks.
    rush: RushSettings = field(default_factory=RushSettings)
    bonds: BondSettings = field(default_factory=BondSettings)
    expeditions: ExpeditionSettings = field(default_factory=ExpeditionSettings)
    # How building is gone about. What each thing takes is in its own definition.
    construction: ConstructionSettings = field(default_factory=ConstructionSettings)
    # What there is to work out, and what each subject opens up.
    research: ResearchSettings = field(default_factory=ResearchSettings)
    world_events: WorldEventSettings = field(default_factory=WorldEventSettings)
    # How tastes are made, how they are taken, and what they are called.
    tastes: TasteSettings = field(default_factory=TasteSettings)
    # How time tells on people, and how families come about.
    family: FamilySettings = field(default_factory=FamilySettings)
    politics: PoliticsSettings = field(default_factory=PoliticsSettings)
    # What the player can tell a resident they have stopped.
    affect: AffectSettings = field(default_factory=AffectSettings)
    leisure: LeisureSettings = field(default_factory=LeisureSettings)
    # The laws there are to pass, and how a settlement decides what is put to it.
    laws: LawSettings = field(default_factory=LawSettings)
    proposals: ProposalSettings = field(default_factory=ProposalSettings)
    # How substances work in general. What each one does is in its own item.
    substances: SubstanceSettings = field(default_factory=SubstanceSettings)
    # Trials and punishments: what can be tried, the scale of punishments, and how each is taken.
    justice: JusticeSettings = field(default_factory=JusticeSettings)
    # The ways there are of walking, eating and fighting, for each resident to have their own.
    manners: MannerSettings = field(default_factory=MannerSettings)
    event_settings: dict[str, Any] = field(default_factory=dict)
    dialogue: dict[str, list[str]] = field(default_factory=dict)
    # The steps a new settlement is led through, and the map it starts on.
    tutorial: TutorialDefinition = field(default_factory=TutorialDefinition)
    # Whose a building is and what follows from it, and what each thing adds to a house.
    housing: HousingSettings = field(default_factory=HousingSettings)
    # What there is to dress a building with: ornaments, floors and walls.
    decor: DecorSettings = field(default_factory=DecorSettings)

    @classmethod
    def load(cls, data_dir: Path | str = DATA_DIR, custom_dir: Path | str | None = None) -> "BuiltInRegistries":
        """Load definitions from `data_dir`, then items from the content packs in `custom_dir`.

        Built-in data must be valid or loading fails. A bad content pack is only skipped.
        """
        root = Path(data_dir)
        registries = cls()
        registries.items.load_collection_json_file(root / "items.json")
        if custom_dir is not None:
            load_custom_items(registries.items, Path(custom_dir))
        registries.personalities.load_json_file(root / "personalities.json")
        registries.traits.load_json_file(root / "traits.json")
        registries.interactables.load_json_file(root / "interactables.json")
        if custom_dir is not None:
            load_custom_interactables(registries.interactables, Path(custom_dir))
        urbanism_path = root / "urbanism.json"
        if urbanism_path.is_file():
            registries.buildings = {
                str(blueprint_id): building_definition_from_data(str(blueprint_id), values)
                for blueprint_id, values in _read_object(urbanism_path).items()
            }
        if custom_dir is not None:
            load_custom_buildings(registries.buildings, Path(custom_dir))
        registries.terrain = {
            str(terrain_id): TerrainDefinition(
                str(terrain_id), bool(values.get("walkable", True)), bool(values.get("opaque", False))
            )
            for terrain_id, values in _read_object(root / "terrain.json").items()
        }
        for path in sorted((root / "maps").glob("*.json")):
            layout = layout_from_data(_read_object(path), str(path))
            if layout.map_id in registries.maps:
                raise ValueError(f"Duplicate map id: {layout.map_id}")
            registries.maps[layout.map_id] = layout
        registries.event_settings = _read_object(root / "events.json")
        registries.dialogue = _read_object(root / "dialogue.json")
        registries.interactions = {
            str(interaction_id): interaction_definition_from_data(str(interaction_id), values)
            for interaction_id, values in _read_object(root / "social.json").items()
        }
        registries.decisions = {
            str(kind): decision_definition_from_data(str(kind), values)
            for kind, values in _read_object(root / "decisions.json").items()
        }
        injuries_path = root / "injuries.json"
        if injuries_path.is_file():
            registries.injuries = {
                str(kind): injury_definition_from_data(str(kind), values)
                for kind, values in _read_object(injuries_path).items()
            }
        body_path = root / "body.json"
        if body_path.is_file():
            registries.limbs = {
                str(limb_id): limb_definition_from_data(str(limb_id), values)
                for limb_id, values in _read_object(body_path).get("limbs", {}).items()
            }
        jobs_path = root / "jobs.json"
        if jobs_path.is_file():
            registries.jobs = {
                str(job_id): job_definition_from_data(str(job_id), values)
                for job_id, values in _read_object(jobs_path).items()
            }
        world_events_path = root / "world_events.json"
        if world_events_path.is_file():
            registries.world_events = world_event_settings_from_data(_read_object(world_events_path))
        expeditions_path = root / "expeditions.json"
        if expeditions_path.is_file():
            registries.expeditions = expedition_settings_from_data(_read_object(expeditions_path))
        construction_path = root / "construction.json"
        if construction_path.is_file():
            registries.construction = construction_settings_from_data(_read_object(construction_path))
        research_path = root / "research.json"
        if research_path.is_file():
            registries.research = research_settings_from_data(_read_object(research_path))
        bonds_path = root / "relationships.json"
        if bonds_path.is_file():
            registries.bonds = bond_settings_from_data(_read_object(bonds_path))
        crafts_path = root / "crafts.json"
        if crafts_path.is_file():
            registries.crafts = craft_settings_from_data(_read_object(crafts_path))
        attributes_path = root / "attributes.json"
        if attributes_path.is_file():
            registries.attributes = attribute_settings_from_data(_read_object(attributes_path))
        economy_path = root / "economy.json"
        if economy_path.is_file():
            registries.economy = economy_settings_from_data(_read_object(economy_path))
        resources_path = root / "resources.json"
        if resources_path.is_file():
            registries.resources = resource_settings_from_data(_read_object(resources_path))
        work_path = root / "work.json"
        if work_path.is_file():
            registries.rush = rush_settings_from_data(_read_object(work_path).get("rush", {}))
        tastes_path = root / "tastes.json"
        if tastes_path.is_file():
            registries.tastes = taste_settings_from_data(_read_object(tastes_path))
        family_path = root / "family.json"
        if family_path.is_file():
            registries.family = family_settings_from_data(_read_object(family_path))
        governments_path = root / "governments.json"
        if governments_path.is_file():
            registries.politics = politics_settings_from_data(_read_object(governments_path))
        affect_path = root / "affect.json"
        if affect_path.is_file():
            registries.affect = affect_settings_from_data(_read_object(affect_path))
        leisure_path = root / "leisure.json"
        if leisure_path.is_file():
            registries.leisure = leisure_settings_from_data(_read_object(leisure_path))
        laws_path = root / "laws.json"
        if laws_path.is_file():
            registries.laws = law_settings_from_data(_read_object(laws_path))
        proposals_path = root / "proposals.json"
        if proposals_path.is_file():
            registries.proposals = proposal_settings_from_data(_read_object(proposals_path))
        substances_path = root / "substances.json"
        if substances_path.is_file():
            registries.substances = substance_settings_from_data(_read_object(substances_path))
        punishments_path = root / "punishments.json"
        if punishments_path.is_file():
            registries.justice = justice_settings_from_data(_read_object(punishments_path))
        manners_path = root / "manners.json"
        if manners_path.is_file():
            registries.manners = manner_settings_from_data(_read_object(manners_path))
        housing_path = root / "housing.json"
        if housing_path.is_file():
            registries.housing = housing_settings_from_data(_read_object(housing_path))
        decor_path = root / "decor.json"
        if decor_path.is_file():
            registries.decor = decor_settings_from_data(_read_object(decor_path))
        tutorial_path = root / "tutorial.json"
        if tutorial_path.is_file():
            registries.tutorial = tutorial_definition_from_data(_read_object(tutorial_path))
        registries.validate()
        return registries

    def validate(self) -> None:
        """Check that definitions only reference IDs that exist."""
        for kind in self.interactables.kinds():
            use = self.interactables.get(kind).use
            if use is not None and use.item_id is not None and self.items.find(use.item_id) is None:
                raise ValueError(f"Interactable {kind} uses unknown item: {use.item_id}")
            shown = self.interactables.get(kind).display_of
            holder = self.interactables.find(shown) if shown is not None else None
            if shown is not None and (holder is None or not holder.container):
                raise ValueError(f"Interactable {kind} displays what is in {shown}, which is not a container kind")
        for blueprint_id, building in self.buildings.items():
            if building.floor not in self.terrain:
                raise ValueError(f"Building {blueprint_id} uses unknown floor terrain: {building.floor}")
        material_tags = {tag for item_id in self.items.ids() for tag in self.items.get(item_id).tags}
        built = [(f"Building {blueprint_id}", building.build) for blueprint_id, building in self.buildings.items()]
        built += [(f"Interactable {kind}", self.interactables.get(kind).build) for kind in self.interactables.kinds()]
        for label, rule in built:
            if rule is None:
                continue
            if rule.job is not None and rule.job not in self.jobs and self.jobs:
                raise ValueError(f"{label} is built by an unknown job: {rule.job}")
            unknown = sorted(tag for tag in rule.cost if tag not in material_tags)
            if unknown:
                raise ValueError(f"{label} is built with what no item is tagged as: {unknown}")
        for subject_id, subject in self.research.subjects.items():
            if subject.item is not None and self.items.find(subject.item) is None:
                raise ValueError(f"Research subject {subject_id} studies an unknown item: {subject.item}")
            unknown = [kind for kind in subject.objects if self.interactables.find(kind) is None]
            unknown += [blueprint for blueprint in subject.buildings if blueprint not in self.buildings]
            if unknown:
                raise ValueError(f"Research subject {subject_id} opens up what is not defined: {unknown}")
            for effect in subject.effects:
                paced = effect.removeprefix(JOB_PACE) if effect.startswith(JOB_PACE) else None
                if effect not in EFFECTS and (paced is None or (paced not in self.jobs and self.jobs)):
                    raise ValueError(f"Research subject {subject_id} has an unknown effect: {effect}")
        for interaction_id, interaction in self.interactions.items():
            if interaction.dialogue is not None and interaction.dialogue not in self.dialogue:
                raise ValueError(f"Interaction {interaction_id} uses unknown dialogue: {interaction.dialogue}")
        for job_id, job in self.jobs.items():
            if job.watch_for is not None and not any(
                event.kind == job.watch_for for event in self.world_events.events.values()
            ):
                raise ValueError(f"Job {job_id} keeps watch for a kind of event that never happens: {job.watch_for}")
            station = self.interactables.find(job.station)
            if station is None:
                raise ValueError(f"Job {job_id} is worked at unknown object kind: {job.station}")
            if job.research and not station.container:
                # What is studied is left at the post, so the post has to be able to hold it.
                raise ValueError(f"Job {job_id} studies at {job.station}, which is not a container kind")
            if job.tool is not None and not any(
                job.tool.tag in self.items.get(item_id).tags for item_id in self.items.ids()
            ):
                raise ValueError(f"Job {job_id} uses a tool that no item is tagged as: {job.tool.tag}")
            supply = job.supplies
            if supply is not None:
                if self.items.find(supply.item) is None:
                    raise ValueError(f"Job {job_id} supplies unknown item: {supply.item}")
                holder = self.interactables.find(supply.into)
                if holder is None or not holder.container:
                    raise ValueError(f"Job {job_id} supplies must go 'into' a container kind, not: {supply.into}")
            rule = job.produces
            if rule is None:
                continue
            if self.items.find(rule.item) is None:
                raise ValueError(f"Job {job_id} produces unknown item: {rule.item}")
            for label, kind in (("into", job.station if rule.into == INTO_STATION else rule.into), ("from", rule.source)):
                holder = self.interactables.find(kind) if kind is not None else None
                if kind is not None and (holder is None or not holder.container):
                    raise ValueError(f"Job {job_id} '{label}' must name a container kind, not: {kind}")
        for kind in self.interactables.kinds():
            use = self.interactables.get(kind).use
            if use is not None and use.staffed_by is not None and use.staffed_by not in self.jobs:
                raise ValueError(f"Interactable {kind} is staffed by unknown job: {use.staffed_by}")
            if use is not None and use.care_job is not None and use.care_job not in self.jobs:
                raise ValueError(f"Interactable {kind} is cared for by unknown job: {use.care_job}")
            source = self.interactables.find(use.care_from) if use is not None and use.care_from else None
            if use is not None and use.care_item is not None and (source is None or not source.container):
                raise ValueError(f"Interactable {kind} takes what its care uses up from no kind of container")
        for kind, decision in self.decisions.items():
            for outcome in decision.outcomes.values():
                if outcome.interaction is not None and outcome.interaction not in self.interactions:
                    raise ValueError(f"Decision {kind} uses unknown interaction: {outcome.interaction}")
        for name, order in {**self.affect.exchanges, **self.affect.incitements, **self.affect.pastimes}.items():
            if order.interaction not in self.interactions:
                raise ValueError(f"What a resident can be told ({name}) uses an unknown interaction: {order.interaction}")
        both = sorted(self.affect.pastimes.keys() & self.leisure.pastimes.keys())
        if both:
            raise ValueError(f"A pastime is done alone or with somebody, under one name each: {both}")
        for pastime_id in self.leisure.pastimes:
            if pastime_id in self.interactions:
                raise ValueError(f"Pastime {pastime_id} has the name of an exchange between two")
        for law_id, law in self.laws.laws.items():
            named = [law.needs_kind] if law.needs_kind is not None else []
            for degree in law.degrees:
                named += [*degree.effects.get("closes", ()), *degree.effects.get("dark", ())]
                if "requires" in degree.effects:
                    named.append(degree.effects["requires"]["kind"])
            unknown = sorted({kind for kind in named if self.interactables.find(kind) is None})
            if unknown:
                raise ValueError(f"Law {law_id} names kinds of object that are not defined: {unknown}")
        if self.laws.laws and not {ENACT_LAW, REPEAL_LAW} <= self.proposals.kinds.keys():
            raise ValueError("There are laws and no way of proposing one, or of doing away with one")
        hurt = self.rush.mishaps.get("hurt")
        unknown = sorted(kind for kind in (hurt.injuries if hurt is not None else ()) if kind not in self.injuries)
        if unknown and self.injuries:
            raise ValueError(f"A push leaves kinds of injury that are not defined: {unknown}")
        if self.substances.overdose_kind not in self.injuries and self.injuries:
            raise ValueError(f"Too much of a substance leaves an unknown kind of injury: {self.substances.overdose_kind}")
        for job_id, job in self.jobs.items():
            unknown = [item for item in (job.produces.also if job.produces is not None else ()) if self.items.find(item) is None]
            if unknown:
                raise ValueError(f"Job {job_id} also produces unknown items: {unknown}")
        for item_id in self.items.ids():
            if self.items.get(item_id).properties.get("wear", 0.0) < 0:
                raise ValueError(f"Item {item_id} has negative wear")
            if not 0.0 <= self.items.get(item_id).properties.get("sickens", 0.0) <= 1.0:
                raise ValueError(f"Item {item_id} makes whoever eats it ill with a chance outside 0 to 1")
        for taste in self.tastes.people.values():
            # Jobs are tolerated only if they exist: a taste for whoever holds a post nobody can hold is a mistake.
            unknown = [job for job in taste.jobs if job not in self.jobs]
            if unknown and self.jobs:
                raise ValueError(f"Taste in people {taste.taste_id} names unknown jobs: {unknown}")
        for trait_id in self.traits.ids():
            given = self.traits.get(trait_id).get("tastes", {})
            if not isinstance(given, dict) or not all(
                isinstance(tag, str)
                and TASTE_TAG_PATTERN.match(tag)
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
                and -100 <= value <= 100
                for tag, value in given.items()
            ):
                raise ValueError(f"Trait {trait_id} must give tastes as taste tags with a liking from -100 to 100")
            leans = self.traits.get(trait_id).get("politics", {})
            if not isinstance(leans, dict) or not all(
                leaning in LEANINGS and isinstance(value, (int, float)) and not isinstance(value, bool)
                for leaning, value in leans.items()
            ):
                raise ValueError(f"Trait {trait_id} must give politics as numbers for some of {LEANINGS}")
        for kind in self.interactables.kinds():
            use = self.interactables.get(kind).use
            source = self.interactables.find(use.material_from) if use is not None and use.material_from else None
            if use is not None and use.material is not None and (source is None or not source.container):
                raise ValueError(f"Interactable {kind} takes its repair material from no kind of container")
        # Unknown loot is tolerated, like unknown stock: it may come from an optional pack.
        for rule in self.expeditions.deliveries:
            holder = self.interactables.find(rule.to)
            if holder is None or not holder.container:
                raise ValueError(f"Expedition finds are delivered to {rule.to}, which is not a container kind")
            if rule.needs is not None and self.interactables.find(rule.needs) is None:
                raise ValueError(f"Expedition finds are delivered by a rule that needs an unknown object kind: {rule.needs}")
        traits = set(vars(Personality()))
        for newcomer in self.world_events.newcomers:
            unknown = newcomer.personality.keys() - traits
            if unknown:
                raise ValueError(f"Newcomer {newcomer.newcomer_id} has unknown personality traits: {sorted(unknown)}")
        for event_id, event in self.world_events.events.items():
            if event.kind in (STRANGER, RAID):
                if event.asks not in self.jobs:
                    raise ValueError(f"World event {event_id} asks an unknown job to answer the gate: {event.asks}")
                for kind in event.containers:
                    holder = self.interactables.find(kind)
                    if holder is None or not holder.container:
                        raise ValueError(f"World event {event_id} names {kind}, which is not a container kind")
                continue
            holder = self.interactables.find(event.container) if event.container is not None else None
            if event.container is not None and (holder is None or not holder.container):
                raise ValueError(f"World event {event_id} names {event.container}, which is not a container kind")
        if self.expeditions.injury_kind not in self.injuries and self.injuries:
            raise ValueError(f"Expeditions leave an unknown kind of injury: {self.expeditions.injury_kind}")
        if self.tutorial.steps and self.tutorial.map_id not in self.maps:
            raise ValueError(f"The tutorial starts on an unknown map: {self.tutorial.map_id}")
        for step in self.tutorial.steps:
            goal = step.goal
            known = {OBJECT: self.interactables.find, BUILDING: self.buildings.get, JOB: self.jobs.get}.get(goal.kind)
            if known is not None and goal.target is not None and known(goal.target) is None:
                raise ValueError(f"Tutorial step {step.step_id} waits for something unknown: {goal.target}")
            # Unknown items are tolerated, like unknown stock: a gift may come from an optional pack.
            for gift in step.gifts:
                holder = self.interactables.find(gift.into) if gift.into is not None else None
                if gift.into is not None and (holder is None or not holder.container):
                    raise ValueError(
                        f"Tutorial step {step.step_id} leaves a gift in {gift.into}, which is not a container kind"
                    )
        for map_id, layout in self.maps.items():
            tile_map = layout.tile_map
            unknown = {terrain for row in tile_map.tiles for terrain in row} - self.terrain.keys()
            if unknown:
                raise ValueError(f"Map {map_id} uses unknown terrain: {sorted(unknown)}")
            for placed in layout.interactables.values():
                definition = self.interactables.find(placed.kind)
                if definition is None:
                    raise ValueError(f"Map {map_id} places unknown interactable: {placed.kind}")
                if not all(tile_map.in_bounds(tile) for tile in placed.footprint(definition)):
                    raise ValueError(f"Map {map_id} places {placed.object_id} outside the map")
            for entry in [*layout.stock, *layout.supplies]:
                # Unknown items are tolerated here: a map may stock things from an optional pack.
                placed = layout.interactables.get(entry.container)
                definition = self.interactables.find(placed.kind) if placed is not None else None
                if definition is None or not definition.container:
                    raise ValueError(f"Map {map_id} puts items in {entry.container}, which is not a container")
            for spawn in layout.spawns:
                if not tile_map.in_bounds(spawn) or not self.terrain[tile_map.terrain_at(spawn)].walkable:
                    raise ValueError(f"Map {map_id} has a spawn on a blocked tile: {spawn}")


def _read_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {path}")
    return data


@functools.cache
def builtin_registries() -> BuiltInRegistries:
    """Built-in definitions, loaded once. They are read-only, so worlds can share them."""
    return BuiltInRegistries.load(custom_dir=CUSTOM_CONTENT_DIR)
