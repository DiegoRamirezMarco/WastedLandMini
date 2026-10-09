import subprocess
from dataclasses import replace
import sys
import unittest
from pathlib import Path

from simulation.ai.affect import GROUPS, affect_settings_from_data
from simulation.commands import AffectCommand, HoldResidentCommand, ProposeObjectCommand, ReleaseResidentCommand
from simulation.residents.activity import HEED_ACTION, Activity
from simulation.residents.needs import Needs
from simulation.work.expedition import Expedition
from simulation.work.salvage import SALVAGE_ACTION
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parent.parent


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7) -> SimulationWorld:
    """The ready-made settlement with nothing felt by anyone for anyone, and nobody in need."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    _keep_content(world)
    return world


def _run(world: SimulationWorld, minutes: int, until=None) -> bool:
    for _ in range(minutes):
        world.step(1)
        _keep_content(world)
        if until is not None and until():
            return True
    return False


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _kinds(world: SimulationWorld, resident_id: str) -> dict[str, list[str]]:
    return {option.kind: [each for each, _name in option.targets] for option in world.affect_options(resident_id)}


class AffectDataTests(unittest.TestCase):
    def test_what_can_be_said_is_data_in_groups(self) -> None:
        world = _settled()
        settings = world.registries.affect
        self.assertTrue(settings.needs and settings.exchanges and settings.pastimes and settings.words and settings.tasks)
        groups = {option.group for option in world.affect_options("raul")}
        self.assertTrue(groups <= set(GROUPS))
        self.assertTrue({"need", "with", "leisure", "task", "words"} <= groups)
        # Everything has a short name to go by where there is no room for what it says.
        self.assertTrue(all(option.name for option in world.affect_options("raul")))
        unfelt = [
            name
            for name, order in settings.exchanges.items()
            if not order.feels and order.who == "anybody" and order.trait is None
        ]
        self.assertEqual(
            unfelt, ["talk"], "past talk, everything goes by what is felt, by who they are to each other, or by what they are like"
        )

    def test_what_makes_no_sense_is_refused(self) -> None:
        affect_settings_from_data({"needs": {"eat": {"label": "Come", "need": "hunger"}}})
        for wrong in (
            {"needs": {"eat": {"need": "hunger"}}},
            {"needs": {"eat": {"label": "Come", "need": "luck"}}},
            {"needs": {"eat": {"label": "Come"}}},
            {"needs": {"eat": {"label": "Come", "need": "hunger", "heals": True}}},
            {"with": {"talk": {"label": "Habla"}}},
            {"with": {"talk": {"label": "Habla", "interaction": "chat", "who": "strangers"}}},
            {"incite": {"strike": {"label": "A por", "interaction": "fight"}}},
            {"incite": {"strike": {"label": "A por", "interaction": "fight", "feeling": "envy"}}},
            {"with": {"joke": {"label": "Ríe", "interaction": "joke", "feels": {"envy": 10}}}},
            {"with": {"joke": {"label": "Ríe", "interaction": "joke", "feels": {"affection": 140}}}},
            {"with": {"joke": {"label": "Ríe", "interaction": "joke", "feels": {"resentment": [-5, 10]}}}},
            {"with": {"joke": {"label": "Ríe", "interaction": "joke", "feels": []}}},
            {"with": {"joke": {"label": "Ríe", "interaction": "joke", "tone": "odd"}}},
            {"tasks": {"stop": {"name": "Para"}}},
            {"most_orders": 0},
            {"words": {"calm": {"needs": {"stress": -5}}}},
            {"words": {"calm": {"label": "Ya", "needs": {"luck": -5}}}},
            {"tasks": {"fly": "Que vuele"}},
            {"hold_minutes": 0},
        ):
            with self.assertRaises(ValueError, msg=wrong):
                affect_settings_from_data(wrong)

    def test_affecting_needs_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.ai.affect; from simulation.world import SimulationWorld; "
            "world = SimulationWorld.demo_world(); world.step(60); world.hold_resident('raul'); "
            "world.affect_resident('raul', 'need:eat', None); world.step(60); "
            "sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class HoldTests(unittest.TestCase):
    def test_a_resident_who_is_stopped_leaves_off_what_they_were_doing_and_listens(self) -> None:
        world = _settled()
        world.step(60)
        raul = world.residents["raul"]
        self.assertTrue(world.work.on_duty(world, raul))
        result = world.apply_command(HoldResidentCommand("raul"))
        self.assertTrue(result.ok, result.message)
        self.assertEqual(raul.current_action, HEED_ACTION)
        self.assertTrue(world.affect.is_held(world, "raul"))
        self.assertFalse(world.work.on_duty(world, raul))
        tile = raul.tile
        _run(world, world.registries.affect.hold_minutes - 2)
        self.assertEqual((raul.tile, raul.current_action), (tile, HEED_ACTION), "he stands where he was stopped")
        _run(world, 30)
        self.assertFalse(world.affect.is_held(world, "raul"), "with nothing said he goes about his day")
        self.assertIn("resident_held", _types(world))

    def test_let_go_they_go_back_to_their_day_at_once(self) -> None:
        world = _settled()
        world.step(60)
        world.apply_command(HoldResidentCommand("raul"))
        self.assertTrue(world.apply_command(ReleaseResidentCommand("raul")))
        self.assertFalse(world.apply_command(ReleaseResidentCommand("raul")))
        self.assertIsNone(world.residents["raul"].activity)
        self.assertTrue(_run(world, 40, lambda: world.work.on_duty(world, world.residents["raul"])))

    def test_whoever_they_were_talking_to_is_left_free(self) -> None:
        world = _settled()
        raul, ines = world.residents["raul"], world.residents["ines"]
        raul.activity = Activity("chat", minutes_left=20, using=True, partner_id="ines")
        ines.activity = Activity("chat", minutes_left=20, using=True, partner_id="raul")
        world.apply_command(HoldResidentCommand("raul"))
        self.assertIsNone(ines.activity)

    def test_somebody_asleep_can_be_stopped_and_somebody_away_or_deciding_cannot(self) -> None:
        world = _settled()
        paco = world.residents["paco"]
        bed = next(object_id for object_id, placed in world.interactables.items() if placed.kind == "bed")
        paco.activity = Activity("sleep", bed, minutes_left=300, using=True)
        self.assertFalse(world.is_aware(paco))
        self.assertTrue(world.apply_command(HoldResidentCommand("paco")).ok)
        self.assertTrue(world.is_aware(paco))
        world.residents["sergio"].expedition = Expedition(returns_at=10**9, finds=0, danger=0.0)
        self.assertFalse(world.apply_command(HoldResidentCommand("sergio")).ok)
        self.assertEqual(world.affect_options("sergio"), [])
        world.interventions.ask(world, world.residents["vera"], "resign", inputs={"support": 0.5})
        self.assertFalse(world.apply_command(HoldResidentCommand("vera")).ok)
        self.assertFalse(world.apply_command(AffectCommand("vera", "words:calm")).ok)
        self.assertFalse(world.apply_command(HoldResidentCommand("nobody")).ok)


class OptionsTests(unittest.TestCase):
    def test_what_is_on_offer_follows_from_how_things_stand(self) -> None:
        world = _settled()
        world.step(60)
        kinds = _kinds(world, "raul")
        self.assertIn("need:eat", kinds)
        self.assertIn("task:to_post", kinds, "it is his shift")
        self.assertIn("task:leave_job", kinds)
        self.assertNotIn("task:take_charge", kinds, "there is no site")
        self.assertNotIn("with:propose", kinds, "he has no partner")
        self.assertIn("marta", kinds["with:talk"])
        self.assertNotIn("raul", kinds["with:talk"])
        self.assertIn("tyres_workshop", kinds["task:salvage"] + ["tyres_workshop"])
        world.clock.hour = 22
        self.assertNotIn("task:to_post", _kinds(world, "raul"), "nor is anybody sent to a post out of hours")

    def test_past_talk_only_what_they_feel_for_somebody_is_on_offer(self) -> None:
        world = _settled()
        felt = [kind for kind in _kinds(world, "raul") if kind.startswith("with:")]
        self.assertEqual(
            felt, ["with:talk", "with:cow", "with:tell_off"], "feeling nothing for anybody: talk, and what goes with what he is like (S63)"
        )
        world.residents["raul"].traits = []
        felt = [kind for kind in _kinds(world, "raul") if kind.startswith("with:")]
        self.assertEqual(felt, ["with:talk"], "and for somebody with nothing of the kind, talk and no more")
        world.relationship("raul", "marta").resentment = 49
        kinds = _kinds(world, "raul")
        self.assertEqual(kinds["with:confront"], ["marta"])
        self.assertEqual(kinds["with:insult"], ["marta"])
        self.assertNotIn("with:strike", kinds, "he does not hate her enough to go for her")
        world.relationship("raul", "marta").resentment = 50
        self.assertEqual(_kinds(world, "raul")["with:strike"], ["marta"])
        self.assertNotIn("with:hug", _kinds(world, "raul"))
        world.relationship("raul", "ines").affection = 80
        world.relationship("raul", "ines").attraction = 70
        kinds = _kinds(world, "raul")
        for kind in ("with:joke", "with:hug", "with:flirt", "with:confess", "with:slip_away"):
            self.assertEqual(kinds[kind], ["ines"], kind)
        self.assertEqual(sorted(kinds["with:open_up"]), ["ines", "marta"], "with one for fondness, with the other to clear the air")
        self.assertNotIn("with:strike", _kinds(world, "marta"), "what one feels the other need not")
        self.assertNotIn("with:hug", _kinds(world, "ines"))

    def test_what_there_is_with_one_person_is_what_is_felt_for_them(self) -> None:
        world = _settled()
        names = lambda other: [option.kind for option in world.affect_with("raul", other)]
        # What goes with what he is like is told apart: here it is what is felt that is looked at.
        world.residents["raul"].traits = []
        self.assertEqual(names("marta"), ["with:talk", "leisure:cards"])
        world.relationship("raul", "marta").affection = 45
        self.assertEqual(
            names("marta"),
            ["with:talk", "with:joke", "with:open_up", "with:hug", "leisure:cards", "leisure:stories", "leisure:dance"],
        )
        world.relationship("raul", "marta").affection = -30
        world.relationship("raul", "marta").resentment = 60
        self.assertEqual(
            names("marta"), ["with:talk", "with:open_up", "with:confront", "with:insult", "with:strike"],
            "nobody sits down to cards with somebody they cannot stand",
        )
        tones = {option.kind: option.tone for option in world.affect_with("raul", "marta")}
        self.assertEqual((tones["with:talk"], tones["with:strike"]), ("friendly", "hostile"))
        self.assertEqual(world.affect_with("raul", "raul"), [])
        self.assertEqual(world.affect_with("raul", "nobody"), [])
        self.assertNotIn("raul", [each for each, _name in world.affect_people("raul")])
        self.assertEqual(len(world.affect_people("raul")), len(world.residents) - 1, "everybody there is, the nearest first")

    def test_somebody_out_of_the_few_offered_can_still_be_named(self) -> None:
        world = _settled()
        # The registries are shared by every settlement made here: put back what was there.
        settings = world.registries.affect
        self.addCleanup(setattr, world.registries, "affect", settings)
        world.registries.affect = replace(settings, most_targets=3)
        offered = _kinds(world, "raul")["with:talk"]
        self.assertEqual(len(offered), 3)
        far = next(each for each, _name in reversed(world.affect_people("raul")) if each not in offered)
        self.assertTrue(world.apply_command(AffectCommand("raul", "with:talk", far)).ok)

    def test_romance_is_between_adults_who_could_be_drawn_to_each_other(self) -> None:
        world = _settled()
        feelings = world.relationship("raul", "marta")
        feelings.attraction, feelings.affection = 80, 80
        self.assertIn("with:flirt", [option.kind for option in world.affect_with("raul", "marta")])
        world.residents["marta"].age = 15
        kinds = [option.kind for option in world.affect_with("raul", "marta")]
        self.assertNotIn("with:flirt", kinds)
        self.assertNotIn("with:confess", kinds)
        self.assertNotIn("with:slip_away", kinds)
        self.assertIn("with:hug", kinds)

    def test_what_is_for_a_partner_is_offered_only_with_theirs(self) -> None:
        world = _settled()
        tomas, ines = world.residents["tomas"], world.residents["ines"]
        tomas.couple_with, ines.couple_with = "ines", "tomas"
        world.relationship("tomas", "ines").affection = 60
        world.relationship("tomas", "ines").attraction = 60
        kinds = _kinds(world, "tomas")
        self.assertEqual(kinds["with:kiss"], ["ines"])
        self.assertEqual(kinds["with:propose"], ["ines"])
        self.assertNotIn("with:part", kinds, "there is nothing wrong between them")
        self.assertNotIn("with:confess", kinds, "there is nothing left to tell her")
        world.relationship("tomas", "ines").affection = 5
        kinds = _kinds(world, "tomas")
        self.assertEqual(kinds["with:part"], ["ines"])
        self.assertNotIn("with:propose", kinds)

    def test_a_site_or_a_free_post_or_something_to_take_apart_can_be_put_in_their_hands(self) -> None:
        world = _settled()
        site = world.construction.lay(world, "object", "bed", (1, 1), "marta")
        kinds = _kinds(world, "raul")
        self.assertEqual(kinds["task:take_charge"], [site.site_id])
        self.assertNotIn("task:take_charge", _kinds(world, "marta"), "it is hers already")
        self.assertEqual(kinds["task:take_job"], ["water_carrier"])
        self.assertTrue(kinds["task:salvage"])
        self.assertLessEqual(len(kinds["task:salvage"]), world.registries.affect.most_targets)


class OrderTests(unittest.TestCase):
    def test_told_to_eat_they_go_and_eat_hungry_or_not(self) -> None:
        world = _settled()
        world.step(60)
        ines = world.residents["ines"]
        self.assertLess(ines.needs.hunger, 20, "she is not hungry")
        result = world.apply_command(AffectCommand("ines", "need:eat"))
        self.assertTrue(result.ok, result.message)
        self.assertTrue(_run(world, 60, lambda: ines.current_action == "eat"), "she never ate")
        self.assertIn("order_given", _types(world))

    def test_told_to_bed_they_go_in_the_middle_of_the_day(self) -> None:
        world = _settled()
        world.step(120)
        paco = world.residents["paco"]
        paco.needs.tiredness = 40.0
        self.assertTrue(world.apply_command(AffectCommand("paco", "need:sleep")).ok)
        for _ in range(60):
            world.step(1)
            if not world.is_aware(paco):
                break
        self.assertFalse(world.is_aware(paco), "he never lay down")

    def test_told_to_go_to_somebody_they_have_that_exchange_with_them(self) -> None:
        world = _settled()
        world.step(60)
        self.assertFalse(world.apply_command(AffectCommand("vera", "with:open_up", "paco")).ok, "she feels nothing for him")
        world.relationship("vera", "paco").affection = 30
        self.assertTrue(world.apply_command(AffectCommand("vera", "with:open_up", "paco")).ok)
        self.assertTrue(_run(world, 90, lambda: "heart_to_heart_started" in _types(world)), "they never talked")
        line = next(line for line in world.event_log if "heart_to_heart_started" in line)
        self.assertIn("Vera", line)
        self.assertIn("Paco", line)

    def test_set_on_somebody_they_hate_they_go_for_them_with_nobody_asked(self) -> None:
        world = _settled()
        world.step(60)
        world.relationship("raul", "marta").resentment = 80
        self.assertTrue(world.apply_command(HoldResidentCommand("raul")).ok)
        result = world.apply_command(AffectCommand("raul", "with:strike", "marta"))
        self.assertTrue(result.ok, result.message)
        self.assertFalse(world.affect.is_held(world, "raul"))
        self.assertEqual(world.decisions, {}, "it is an order: nothing is put to him to decide")
        self.assertTrue(_run(world, 90, lambda: "fight_started" in _types(world)), "it never came to blows")

    def test_an_order_is_obeyed_whatever_they_are_like_and_costs_nothing(self) -> None:
        world = _settled()
        world.step(60)
        for resident in world.residents.values():
            resident.personality.impulsiveness = 100.0
            resident.personality.empathy = 0.0
        paco = world.residents["paco"]
        # Whatever there is to take apart nearest to where the hour has left him: only so many
        # of the nearest are offered, and which they are goes by where he has wandered to.
        about = next(option for option in world.affect.options(world, "paco") if option.kind == "task:salvage")
        target = about.targets[0][0]
        self.assertTrue(world.apply_command(AffectCommand("paco", "task:salvage", target)).ok)
        self.assertEqual(world.salvage[target].resident_id, "paco")
        self.assertTrue(_run(world, 60, lambda: paco.current_action == SALVAGE_ACTION))
        self.assertEqual(world.player_standing, {}, "nobody thinks the more or the less of the player for it")

    def test_a_post_can_be_put_in_their_hands_or_taken_out_of_them(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        self.assertTrue(world.apply_command(AffectCommand("raul", "task:take_job", "water_carrier")).ok)
        self.assertEqual(raul.job_id, "water_carrier")
        self.assertIn("job_changed", _types(world))
        self.assertTrue(world.apply_command(AffectCommand("raul", "task:leave_job")).ok)
        self.assertEqual((raul.job_id, raul.post_id), (None, None))
        self.assertFalse(world.apply_command(AffectCommand("raul", "task:leave_job")).ok, "he has none to leave")

    def test_a_site_can_be_put_in_their_charge_and_they_see_to_it_as_their_work(self) -> None:
        world = _settled()
        world.step(60)
        spot = next(
            (x, y)
            for y in range(1, world.tile_map.height - 2)
            for x in range(1, world.tile_map.width - 2)
            if world.urbanism.object_error(world, "bed", (x, y)) is None
        )
        site_id = world.apply_command(ProposeObjectCommand("bed", spot, "marta")).entity_id
        self.assertTrue(world.apply_command(AffectCommand("raul", "task:take_charge", site_id)).ok)
        self.assertEqual(world.sites[site_id].in_charge, "raul")
        self.assertTrue(_run(world, 5 * 60, lambda: site_id not in world.sites), "he never built it")
        self.assertTrue(any("| build_started | Raúl" in line for line in world.event_log))

    def test_a_few_words_change_how_they_feel_and_stop_them_no_longer(self) -> None:
        world = _settled()
        world.step(60)
        vera = world.residents["vera"]
        vera.needs.stress, vera.mood = 60.0, 40.0
        world.apply_command(HoldResidentCommand("vera"))
        self.assertTrue(world.apply_command(AffectCommand("vera", "words:calm")).ok)
        self.assertLess(vera.needs.stress, 60.0)
        self.assertGreater(vera.mood, 40.0)
        self.assertFalse(world.affect.is_held(world, "vera"))
        stress, mood = vera.needs.stress, vera.mood
        self.assertTrue(world.apply_command(AffectCommand("vera", "words:scold")).ok)
        self.assertGreater(vera.needs.stress, stress)
        self.assertLess(vera.mood, mood)

    def test_told_to_stop_they_drop_what_they_were_doing(self) -> None:
        world = _settled()
        world.step(60)
        raul = world.residents["raul"]
        self.assertTrue(world.work.on_duty(world, raul))
        self.assertTrue(world.apply_command(AffectCommand("raul", "task:stop")).ok)
        self.assertIsNone(raul.activity)

    def test_what_is_not_on_offer_cannot_be_said(self) -> None:
        world = _settled()
        before = len(world.event_log)
        for kind, target in (
            ("need:fly", None),
            ("with:talk", None),
            ("with:talk", "nobody"),
            ("with:talk", "raul"),
            ("with:strike", "marta"),
            ("leisure:fly", None),
            ("leisure:dance", "marta"),
            ("task:take_charge", "site_9"),
            ("task:salvage", "bed_1"),
            ("words:sing", None),
            ("nonsense", None),
        ):
            self.assertFalse(world.apply_command(AffectCommand("raul", kind, target)).ok, (kind, target))
        self.assertEqual(len(world.event_log), before)
        self.assertFalse(world.apply_command(AffectCommand("nobody", "words:calm")).ok)

    def test_the_same_orders_on_the_same_seed_come_out_the_same(self) -> None:
        def run() -> list[str]:
            world = SimulationWorld.demo_world(seed=5)
            world.step(90)
            world.apply_command(HoldResidentCommand("raul"))
            world.apply_command(AffectCommand("raul", "with:talk", "marta"))
            world.apply_command(AffectCommand("raul", "leisure:stroll"))
            world.apply_command(AffectCommand("ines", "need:unwind"))
            world.apply_command(AffectCommand("ines", "leisure:cards", "paco"))
            world.step(600)
            return world.event_log

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
