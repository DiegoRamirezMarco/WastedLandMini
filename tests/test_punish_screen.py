"""Trials and punishments on the government's panel (P64): accusing of what is known, saying
what somebody found guilty is given, and what prisoners are given each day."""

import os
import unittest

import pygame

from scenes.hud import GOVERNMENT_INTENT, SENTENCE_HINT
from simulation.knowledge.fact import SOURCE_PARTICIPANT, SOURCE_WITNESS, Belief, Fact
from simulation.residents.needs import Needs
from ui.law_board import PUNISH_TAB, tab_intent
from ui.punish_board import (
    CONFIRM_LABEL,
    GIVE_LABEL,
    NO_TRIAL,
    NOTHING_KNOWN,
    ONE_AT_A_TIME,
    accusable,
    accuse_intent,
    awaiting,
    punish_view,
    ration_intent,
    ration_item_intent,
    sentence_intent,
)
from world.interactable import Interactable

WITNESSES = ("ines", "marta", "paco", "vera", "nuria")


class PunishScreenTests(unittest.TestCase):
    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.world, self.hud = self.game.global_view, self.game.world, self.game.global_view.hud
        self.world.relationships.clear()
        for resident in self.world.residents.values():
            resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _known(self, fact_id: str, kind: str, who: str, seen_by=WITNESSES) -> None:
        """Have something that somebody did be known of them by whoever saw it."""
        now = self.world.clock.total_minutes
        self.world.knowledge.add_fact(Fact(fact_id, kind, "algo que pasó", [who], 50, now))
        self.world.knowledge.set_belief(who, Belief(fact_id, 1.0, SOURCE_PARTICIPANT, now))
        for resident_id in seen_by:
            self.world.knowledge.set_belief(resident_id, Belief(fact_id, 1.0, SOURCE_WITNESS, now))

    def _said(self) -> list[str]:
        rect = self.hud.government_rect()
        return [text for text, _colour, _x, _y in punish_view(self.view.font, rect, rect.y, self.world, self.hud.sentence_armed).lines]

    def _button(self, intent):
        return next((button for button in self.hud.buttons if button.intent == intent), None)

    def _press(self, intent) -> None:
        button = self._button(intent)
        self.assertIsNotNone(button, intent)
        self.view.click(button.rect.center)

    def _found_guilty(self, who: str = "raul", fact_id: str = "fact_theft"):
        self._known(fact_id, "theft_committed", who)
        self.hud.open_punishments()
        self._press(accuse_intent(who, fact_id))
        for _ in range(8 * 60):
            self.world.step(1)
            if awaiting(self.world) is not None:
                return awaiting(self.world)
        self.fail("nobody was found guilty")

    def test_the_panel_of_the_government_has_a_tab_for_it_that_says_when_there_is_nothing(self) -> None:
        self.view.click(next(button for button in self.hud.menu if button.intent == GOVERNMENT_INTENT).rect.center)
        self._press(tab_intent(PUNISH_TAB))
        self.assertEqual(self.hud.government_tab, PUNISH_TAB)
        said = self._said()
        self.assertIn(NO_TRIAL, said)
        self.assertIn(NOTHING_KNOWN, said)
        self.assertIn("A los presos, al día", said)
        self.view.render()
        self.assertTrue(self.view.viewport.contains(self.hud.government_rect()))
        self.assertTrue(self.hud.covers(self.hud.government_rect().center))

    def test_only_what_somebody_else_knows_of_can_be_brought_and_the_player_brings_it(self) -> None:
        self._known("fact_secret", "theft_committed", "tomas", seen_by=())
        self._known("fact_fight", "fight_started", "raul")
        self.assertEqual([(resident.resident_id, fact.fact_id) for resident, fact in accusable(self.world)], [("raul", "fact_fight")])
        self.hud.open_punishments()
        self.assertTrue(any(text.startswith("Raúl: una pelea") for text in self._said()))
        self.assertIsNone(self._button(accuse_intent("tomas", "fact_secret")), "what nobody saw is nobody's to bring")
        self._press(accuse_intent("raul", "fact_fight"))
        trial = self.world.justice.open_trial(self.world)
        self.assertEqual((trial.accused, trial.fact_id), ("raul", "fact_fight"))
        self.assertIn("acusa a Raúl", self.hud.notice)
        said = self._said()
        self.assertIn("Juicio a Raúl por una pelea", said)
        self.assertTrue(any(text.startswith("Van por") for text in said), said)
        # One trial at a time: nothing else is brought meanwhile, and it is said.
        self._known("fact_other", "theft_committed", "ines", seen_by=("marta", "paco"))
        self.assertIn(ONE_AT_A_TIME, self._said())
        self.assertIsNone(self._button(accuse_intent("ines", "fact_other")))
        self.view.render()

    def test_what_somebody_found_guilty_is_given_is_said_there_out_of_what_there_is_a_place_for(self) -> None:
        trial = self._found_guilty()
        self.view.render()
        said = self._said()
        self.assertTrue(any(text.startswith("Culpable.") for text in said), said)
        self.assertTrue(any("hace falta un cepo" in text for text in said), said)
        self.assertIsNone(self._button(sentence_intent(trial.trial_id, "public_stocks")))
        self.assertIsNone(self._button(sentence_intent(trial.trial_id, "prison")))
        self.assertIsNone(self._button(sentence_intent(trial.trial_id, "execution")))
        self.assertEqual(self._button(sentence_intent(trial.trial_id, "fine")).label, GIVE_LABEL)
        # With stocks standing in the settlement, the stocks are one of them.
        self.world.interactables["stocks_1"] = Interactable("stocks_1", "stocks", 30, 20)
        self.assertIsNotNone(self._button(sentence_intent(trial.trial_id, "public_stocks")))
        self._press(sentence_intent(trial.trial_id, "community_service"))
        self.assertIsNone(awaiting(self.world))
        self.assertIsNone(self.world.justice.open_trial(self.world))
        self.assertEqual(self.world.courts.history[-1].punishment, "community_service")
        self.assertIn("Raúl", self.hud.notice)
        said = self._said()
        self.assertIn("Cumpliendo castigo", said)
        self.assertTrue(any(text.startswith("Raúl: trabajos para todos, hasta el día") for text in said), said)
        self.assertIn("Lo último que se ha dado", said)
        self.view.render()

    def test_while_somebody_waits_to_be_sentenced_the_game_says_so_and_where(self) -> None:
        self._found_guilty()
        self.hud.toggle_government()
        self.assertFalse(self.hud.government_open)
        drawn: list[str] = []
        font = self.view.font
        draw, font.draw = font.draw, lambda target, text, *rest, **more: drawn.append(text)
        self.addCleanup(setattr, font, "draw", draw)
        self.hud._notice_left = 0.0
        self.hud.render()
        self.assertIn(SENTENCE_HINT.format(name="Raúl"), drawn)

    def test_a_harsh_punishment_is_pressed_for_twice(self) -> None:
        trial = self._found_guilty()
        harsh = sentence_intent(trial.trial_id, "corporal_punishment")
        self._press(harsh)
        self.assertIsNotNone(awaiting(self.world), "once is not enough")
        self.assertEqual(self.hud.sentence_armed, (trial.trial_id, "corporal_punishment"))
        self.assertEqual(self._button(harsh).label, CONFIRM_LABEL)
        self.assertIn("pulsa otra vez", self.hud.notice)
        # Pressing for another, mild one gives that and forgets the harsh one.
        self._press(sentence_intent(trial.trial_id, "warning"))
        self.assertEqual(self.world.courts.history[-1].punishment, "warning")
        self.assertIsNone(self.hud.sentence_armed)
        # And pressed twice, it is given.
        trial = self._found_guilty("tomas", "fact_again")
        harsh = sentence_intent(trial.trial_id, "corporal_punishment")
        self._press(harsh)
        self._press(harsh)
        self.assertEqual(self.world.courts.history[-1].punishment, "corporal_punishment")
        self.assertEqual(self.world.courts.history[-1].resident_id, "tomas")

    def test_what_prisoners_are_given_each_day_is_set_there(self) -> None:
        self.hud.open_punishments()
        ration = self.world.justice.ration(self.world)
        self.assertEqual((ration.meals, ration.drinks, ration.food, ration.drink), (3, 2, "", ""))
        self._press(ration_intent("meals", -1))
        self._press(ration_intent("drinks", 1))
        ration = self.world.justice.ration(self.world)
        self.assertEqual((ration.meals, ration.drinks), (2, 3))
        for _ in range(6):
            self._press(ration_intent("meals", -1))
        self.assertEqual(self.world.justice.ration(self.world).meals, 0, "no fewer than none")
        self._press(ration_item_intent("food"))
        food = self.world.justice.ration(self.world).food
        self.assertEqual(self.world.registries.items.get(food).category, "food")
        self.assertTrue(any(self.world.registries.items.get(food).name in text for text in self._said()))
        self._press(ration_item_intent("drink"))
        self.assertEqual(self.world.registries.items.get(self.world.justice.ration(self.world).drink).category, "water")
        # Round and round, back to whatever there is most of.
        for _ in range(40):
            if not self.world.justice.ration(self.world).food:
                break
            self._press(ration_item_intent("food"))
        self.assertEqual(self.world.justice.ration(self.world).food, "")
        self.view.render()


if __name__ == "__main__":
    unittest.main()
