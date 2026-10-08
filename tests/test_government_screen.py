import os
import unittest

import pygame

from scenes.hud import GOVERNMENT_INTENT, JOBS_INTENT
from simulation.residents.activity import PROTEST_ACTION, Activity
from ui.government_board import (
    CHOOSE_LABEL,
    CONFIRM_LABEL,
    choose_intent,
    describe_kind,
    law_lines,
    status_lines,
)
from ui.law_board import (
    CHANGE_LABEL,
    ENACT_LABEL,
    KINDS_TAB,
    LAWS_TAB,
    ODD_TAB,
    REPEAL_LABEL,
    VOTE_LABEL,
    decided_at_once,
    degree_intent,
    enact_intent,
    item_intent,
    laws_of,
    named_items,
    picked_degree,
    picked_params,
    repeal_intent,
    tab_intent,
)
from ui.law_board import status_lines as law_status_lines


class GovernmentScreenTests(unittest.TestCase):
    """The entry of the menu for how the settlement is governed, through the real game shell without a window."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.hud, self.world = self.game.global_view, self.game.global_view.hud, self.game.world

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _entry(self) -> pygame.Rect:
        return next(button for button in self.hud.menu if button.intent == GOVERNMENT_INTENT).rect

    def _choose(self, government_id: str):
        return next(button for button in self.hud.buttons if button.intent == choose_intent(government_id))

    def test_the_menu_opens_it_over_the_map_and_shuts_it_again(self) -> None:
        self.assertFalse(self.hud.government_open)
        self.view.click(self._entry().center)
        self.assertTrue(self.hud.government_open)
        self.view.render()
        board = self.hud.government_rect()
        self.assertTrue(self.hud.layout.map.contains(board))
        self.assertTrue(self.hud.covers(board.center), "a click on it does not fall through to the map")
        self.view.click(next(button for button in self.hud.menu if button.intent == JOBS_INTENT).rect.center)
        self.assertFalse(self.hud.government_open, "one panel at a time in that corner")
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p, mod=0, unicode="p"))
        self.assertTrue(self.hud.government_open)
        self.view.click(self._entry().center)
        self.assertFalse(self.hud.government_open)

    def test_there_is_nothing_to_choose_until_they_have_to_govern_themselves(self) -> None:
        self.world.government.choosing_until = None
        self.hud.toggle_government()
        self.view.render()
        self.assertEqual([button for button in self.hud.buttons if button.label == CHOOSE_LABEL], [])
        self.assertIn("pocos", status_lines(self.world)[0][0])

    def test_a_kind_is_chosen_with_two_presses_and_the_settlement_has_it(self) -> None:
        self.world.step(1)
        self.assertIsNotNone(self.world.government.choosing_until)
        self.hud.toggle_government()
        self.view.render()
        kinds = list(self.world.registries.politics.governments)
        self.assertEqual(len([button for button in self.hud.buttons if button.label == CHOOSE_LABEL]), len(kinds))
        self.view.click(self._choose("commune").rect.center)
        self.assertIsNone(self.world.government.kind, "once is only saying which")
        self.assertEqual(self._choose("commune").label, CONFIRM_LABEL)
        # Pressing for another instead is saying which again.
        self.view.click(self._choose("council").rect.center)
        self.assertIsNone(self.world.government.kind)
        self.assertEqual(self._choose("commune").label, CHOOSE_LABEL)
        self.view.click(self._choose("council").rect.center)
        self.assertEqual(self.world.government.kind, "council")
        self.assertIn("Consejo", self.hud.notice)
        self.view.render()
        # What they have is not offered again, and the rest still are.
        offered = {button.intent for button in self.hud.buttons if button.label == CHOOSE_LABEL}
        self.assertEqual(offered, {choose_intent(kind) for kind in kinds if kind != "council"})
        self.view.click(self._choose("strong_mayor").rect.center)
        self.view.click(self._choose("strong_mayor").rect.center)
        self.assertEqual(self.world.government.kind, "strong_mayor")

    def test_shutting_the_panel_forgets_a_first_press(self) -> None:
        self.world.step(1)
        self.hud.toggle_government()
        self.view.click(self._choose("commune").rect.center)
        self.assertEqual(self.hud.government_armed, "commune")
        self.hud.toggle_government()
        self.hud.toggle_government()
        self.assertIsNone(self.hud.government_armed)

    def test_it_says_who_holds_the_seats_and_what_laws_there_are(self) -> None:
        world = self.world
        world.politics.leadership.establish(world, "strong_mayor")
        leader = world.residents[world.government.leader]
        said = " ".join(text for text, _ in status_lines(world))
        self.assertIn("Alcaldía", said)
        self.assertIn(leader.name, said)
        self.assertEqual(law_lines(self.view.font, world, 300), ["Ninguna ley en vigor."])
        law_id = next(iter(world.registries.laws.laws))
        self.assertTrue(world.politics.laws.enact(world, law_id))
        self.assertIn(world.registries.laws.laws[law_id].name, " ".join(law_lines(self.view.font, world, 300)))
        world.politics.leadership.change_kind(world, "council")
        self.assertIn("Consejo:", " ".join(text for text, _ in status_lines(world)))
        self.hud.toggle_government()
        self.view.render()

    def test_every_kind_is_put_into_words_from_its_data(self) -> None:
        governments = self.world.registries.politics.governments
        lines = {government_id: describe_kind(self.world, definition) for government_id, definition in governments.items()}
        self.assertTrue(all(lines.values()))
        self.assertEqual(len(set(lines.values())), len(lines), "no two kinds read the same")
        self.assertIn("consejo de 3", lines["council"])
        self.assertIn("75%", lines["commune"])


class LawsOnScreenTests(unittest.TestCase):
    """The laws on the government's panel, for the player to put, change and do away with (P51)."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(GovernmentScreenTests._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.hud, self.world = self.game.global_view, self.game.global_view.hud, self.game.world

    def _governed(self, kind: str) -> None:
        self.world.politics.leadership.establish(self.world, kind)
        self.hud.toggle_government()
        self._press(tab_intent(LAWS_TAB))

    def _button(self, intent):
        return next((button for button in self.hud.buttons if button.intent == intent), None)

    def _press(self, intent) -> None:
        button = self._button(intent)
        self.assertIsNotNone(button, intent)
        self.view.click(button.rect.center)
        self.view.render()

    def _listed(self) -> set[str]:
        return {button.intent[1] for button in self.hud.buttons if button.intent[:1] == ("law_enact",)}

    def test_the_panel_has_a_tab_for_the_laws_and_one_for_the_odd_ones(self) -> None:
        self._governed("strong_mayor")
        self.assertEqual(self.hud.government_tab, LAWS_TAB)
        laws = self.world.registries.laws.laws
        serious = [law_id for law_id, law in laws.items() if not law.absurd]
        self.assertEqual([law.law_id for law in laws_of(self.world, LAWS_TAB)], serious)
        self.assertEqual(self._listed(), set(serious), "every one of them has its button, and fits")
        board = self.hud.government_rect()
        self.assertTrue(self.hud.layout.map.contains(board))
        put = [button for button in self.hud.buttons if button.intent[:1] == ("law_enact",)]
        self.assertTrue(all(board.contains(button.rect) for button in put))
        self._press(tab_intent(ODD_TAB))
        self.assertEqual(self._listed(), {law_id for law_id, law in laws.items() if law.absurd})
        self._press(tab_intent(KINDS_TAB))
        self.assertEqual(self._listed(), set(), "and back on how they are governed there are none")

    def test_under_a_mayor_a_law_is_decreed_and_is_in_force_there_and_then(self) -> None:
        self._governed("strong_mayor")
        self.assertEqual(self._button(enact_intent("curfew")).label, ENACT_LABEL)
        self.assertIsNone(self._button(repeal_intent("curfew")))
        self._press(degree_intent("curfew", 1))
        self._press(enact_intent("curfew"))
        held = self.world.government.laws["curfew"]
        self.assertEqual((held.degree, held.imposed), (2, True))
        self.assertIn("decretado", self.hud.notice)
        self.assertIsNone(self._button(enact_intent("curfew")), "as it stands there is nothing to put")
        self.assertEqual(self._button(repeal_intent("curfew")).label, REPEAL_LABEL)
        self._press(degree_intent("curfew", -1))
        self._press(degree_intent("curfew", -1))
        self.assertEqual(self._button(enact_intent("curfew")).label, CHANGE_LABEL)
        self._press(enact_intent("curfew"))
        self.assertEqual(self.world.government.laws["curfew"].degree, 0)
        self._press(repeal_intent("curfew"))
        self.assertEqual(self.world.government.laws, {})

    def test_how_far_a_law_goes_stops_at_either_end(self) -> None:
        self._governed("strong_mayor")
        law = self.world.registries.laws.laws["curfew"]
        for _ in range(6):
            self._press(degree_intent("curfew", 1))
        self.assertEqual(picked_degree(self.world, law, self.hud.law_degrees), len(law.degrees) - 1)
        for _ in range(6):
            self._press(degree_intent("curfew", -1))
        self.assertEqual(picked_degree(self.world, law, self.hud.law_degrees), 0)
        self.assertIsNone(self._button(degree_intent("rest_day", 1)), "a law that goes one way has nothing to pick")

    def test_under_an_assembly_it_is_put_to_a_vote_and_the_panel_says_so(self) -> None:
        self._governed("direct_democracy")
        self.assertFalse(decided_at_once(self.world))
        self.assertEqual(self._button(enact_intent("rest_day")).label, VOTE_LABEL)
        self._press(enact_intent("rest_day"))
        self.assertEqual(self.world.government.laws, {}, "nothing is done until it is voted")
        self.assertEqual(len(self.world.government.proposals), 1)
        width = self.hud.government_rect().width
        said = " ".join(text for text, _ in law_status_lines(self.view.font, self.world, width))
        self.assertIn("Se vota en", said)
        self.assertIn("se vota:", said)
        self._press(enact_intent("rest_day"))
        self.assertEqual(len(self.world.government.proposals), 1, "the same thing is not put twice")
        self.assertTrue(self.hud.notice)

    def test_a_law_that_names_a_food_is_told_which(self) -> None:
        self._governed("strong_mayor")
        self._press(tab_intent(ODD_TAB))
        law = self.world.registries.laws.laws["banned_food"]
        options = named_items(self.world)
        self.assertGreater(len(options), 1)
        self.assertEqual(picked_params(self.world, law, self.hud.law_items), {"item": options[0]})
        self._press(item_intent("banned_food"))
        self.assertEqual(picked_params(self.world, law, self.hud.law_items), {"item": options[1]})
        self._press(enact_intent("banned_food"))
        self.assertEqual(self.world.government.laws["banned_food"].params, {"item": options[1]})

    def test_with_no_government_there_are_no_laws_to_put(self) -> None:
        self.world.government.choosing_until = None
        self.hud.toggle_government()
        self._press(tab_intent(LAWS_TAB))
        self.assertEqual(self._listed(), set())
        said = " ".join(text for text, _ in law_status_lines(self.view.font, self.world, 300))
        self.assertIn("Sin gobierno", said)

    def test_whoever_is_out_in_the_square_carries_a_placard_and_the_panel_counts_them(self) -> None:
        self._governed("strong_mayor")
        world = self.world
        self._press(degree_intent("long_hours", 1))
        self._press(enact_intent("long_hours"))
        protests = world.politics.protests
        world.clock.hour, world.clock.minute = protests.settings(world).hours[0], 0
        out = protests.call(world).get("long_hours", [])
        self.assertTrue(out, "longer hours put on them bring somebody out")
        centre = protests.square(world, (0, 0))
        for resident_id in out:
            resident = world.residents[resident_id]
            resident.x, resident.y = centre
            resident.activity = Activity(PROTEST_ACTION, minutes_left=60, item_id="long_hours")
        self.view.centre_on_resident(out[0])
        self.view.render()
        self.assertIn(out[0], self.view.placards)
        self.assertTrue(self.view.protesting(world.residents[out[0]]))
        others = [resident_id for resident_id in world.residents if resident_id not in out]
        self.assertTrue(all(resident_id not in self.view.placards for resident_id in others))
        said = " ".join(text for text, _ in law_status_lines(self.view.font, world, 300))
        self.assertIn("En la plaza contra Jornada larga", said)


if __name__ == "__main__":
    unittest.main()
