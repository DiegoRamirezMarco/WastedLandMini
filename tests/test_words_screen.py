"""Words on screen (P62): what is talked of over heads, the board of words, and no dock."""

import os
import unittest

import pygame

from graphics.assets import ASSETS_DIR
from graphics.font import BitmapFont
from graphics.icons import icon_path
from scenes.global_view import ASK_ICON
from scenes.hud import ASK_NOTICE
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.social.social_system import SocialSystem
from simulation.social.talk import ASK_NICKNAME, ASK_PHRASE, ASK_SUBJECT, ASK_WORD, Ask, Shown, subject_of
from simulation.tastes.taste import Taste
from tools.art.ui import ICONS
from ui.labels import talk_line
from ui.resident_panel import roster_words_hitbox, words_hitbox
from ui.talk_bubble import TEXT_LINES, TEXT_WIDTH, TURN_MINUTES, bubble_lines, bubble_of, bubble_size, said_aloud
from ui.words_board import (
    ANSWER_FIELD,
    ASKED,
    ITEMS_TAB,
    LISTS,
    NICKNAME_FIELD,
    ONE,
    PEOPLE_TAB,
    PHRASE_FIELD,
    PICK,
    SUBJECT_FIELD,
    WORD_FIELD,
    WORDS_BACK_INTENT,
    WORDS_GIVE_INTENT,
    WORDS_INTENT,
    ask_intent,
    dismiss_intent,
    one_intent,
    pick_intent,
    subject_intent,
    subjects_of,
    tab_intent,
    with_intent,
    words_buttons,
    words_view,
    write_intent,
)

HERE, BESIDE = (20, 18), (21, 18)


class WordsScreenTests(unittest.TestCase):
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

    # ----- helpers -----

    def _button(self, intent):
        return next((button for button in self.hud.buttons if button.intent == intent), None)

    def _press(self, intent) -> None:
        button = self._button(intent)
        self.assertIsNotNone(button, intent)
        self.view.click(button.rect.center)

    def _type(self, text: str) -> None:
        for letter in text:
            self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=0, unicode=letter))

    def _key(self, key: int) -> None:
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=""))

    def _said(self) -> list[str]:
        view = words_view(self.view.font, self.hud.words_rect().topleft, self.world, self.hud.words_entry)
        return [view.title, *(part.text for part in view.parts if part.text)]

    def _ask(self, resident_id: str, kind: str, what: str) -> Ask:
        words = self.world.words
        words.ask_count += 1
        ask = Ask(f"ask_{words.ask_count}", resident_id, kind, what, self.world.clock.total_minutes)
        words.asks.append(ask)
        return ask

    def _talking(self, subject: str, a_id: str = "marta", b_id: str = "raul"):
        """Have two residents stand side by side and the first start a chat about a subject."""
        world = self.world
        a, b = world.residents[a_id], world.residents[b_id]
        for resident, tile in ((a, HERE), (b, BESIDE)):
            resident.x, resident.y = tile
            resident.job_id = resident.post_id = None
            resident.activity = Activity("wander", minutes_left=6000, using=True)
        world.words.told[a_id] = (b_id, subject)
        a.activity = SocialSystem().pursue(world, a, b, "chat")
        world.step(1)
        self.assertEqual(a.activity.about, subject)
        self.view.on_events(world.events.drain())
        self.view.centre_on_resident(a_id)
        return a, b

    # ----- what is talked of, over their heads -----

    def test_a_thing_is_a_picture_somebody_a_face_and_anything_else_its_words(self) -> None:
        world = self.world
        world.add_word("places", "el Viejo Madrid")
        marta, raul = self._talking(subject_of("item", "stew"))
        self.assertEqual(bubble_of(world, marta), Shown(item_id="stew"))
        for activity in (marta.activity, raul.activity):
            activity.about = subject_of("person", "ines")
        self.assertEqual(bubble_of(world, marta), Shown(face_id="ines"))
        for activity in (marta.activity, raul.activity):
            activity.about, activity.about_text = subject_of("word", "places.el_viejo_madrid"), "aquella vez en el Viejo Madrid"
        self.assertEqual(bubble_of(world, marta), Shown(text="aquella vez en el Viejo Madrid"))
        self.assertEqual(said_aloud(bubble_of(world, marta)), "aquella vez en el Viejo Madrid")
        self.assertEqual(said_aloud(Shown(item_id="stew")), "", "a picture says nothing out loud")
        marta.activity = raul.activity = None
        self.assertIsNone(bubble_of(world, marta))

    def test_the_two_take_turns_and_whoever_brought_it_up_goes_first(self) -> None:
        world = self.world
        marta, raul = self._talking(subject_of("item", "stew"))
        self.assertIsNotNone(bubble_of(world, marta))
        self.assertIsNone(bubble_of(world, raul))
        for activity in (marta.activity, raul.activity):
            activity.began_at -= TURN_MINUTES
        self.assertIsNone(bubble_of(world, marta))
        self.assertEqual(bubble_of(world, raul), Shown(item_id="stew"))

    def test_the_bubble_is_drawn_over_whoever_speaks_and_stays_on_the_map(self) -> None:
        marta, raul = self._talking(subject_of("item", "stew"))
        self.view.render()
        self.assertIn("marta", self.view.talk_bubbles)
        self.assertNotIn("raul", self.view.talk_bubbles)
        bubble = self.view.talk_bubbles["marta"]
        self.assertTrue(self.view.viewport.contains(bubble))
        self.assertLess(bubble.bottom, self.view.hitboxes["marta"].top, "it is over her head")
        self.assertIsNone(self.hud.spoken, "a picture is not said out loud")
        # From as far as it goes there is no room for it.
        self.view.set_zoom(0)
        self.view.render()
        self.assertEqual(self.view.talk_bubbles, {})

    def test_a_phrase_of_their_own_is_a_bubble_of_words_and_is_what_is_said_out_loud(self) -> None:
        world = self.world
        world.set_phrase("marta", "greeting", "¡Buenas y santas!")
        marta, raul = self._talking(subject_of("item", "stew"))
        self.assertEqual(bubble_of(world, marta), Shown(text="¡Buenas y santas!"))
        self.hud.select_resident("marta")
        self.view.render()
        self.assertEqual(self.hud.spoken, ("marta", "¡Buenas y santas!"))
        self.hud.select_resident("raul")
        self.view.render()
        self.assertIsNone(self.hud.spoken, "only whoever is selected is heard")

    def test_words_too_long_for_a_bubble_are_cut_short(self) -> None:
        font: BitmapFont = self.view.font
        long = "esto es algo muy largo que no cabe de ninguna manera en un bocadillo tan pequeño como este, ni en tres"
        lines = bubble_lines(font, long)
        self.assertEqual(len(lines), TEXT_LINES)
        self.assertTrue(lines[-1].endswith("..."))
        self.assertTrue(all(font.width(line) <= TEXT_WIDTH for line in lines))
        width, height = bubble_size(font, Shown(text=long))
        self.assertLessEqual(width, TEXT_WIDTH + 10)
        self.assertGreater(height, bubble_size(font, Shown(text="corto"))[1])

    def test_pressing_on_whoever_talks_says_what_about_and_so_does_their_panel(self) -> None:
        world = self.world
        marta, raul = self._talking(subject_of("item", "stew"))
        said = talk_line(world, marta)
        self.assertEqual(said, f"Marta y Raúl están hablando sobre {marta.activity.about_text}")
        self.assertEqual(talk_line(world, raul), f"Raúl y Marta están hablando sobre {marta.activity.about_text}")
        self.view.render()
        self.view.click(self.view.hitboxes["raul"].center)
        self.assertEqual(self.hud.selected_id, "raul")
        self.assertEqual(self.hud.notice, talk_line(world, raul))
        marta.activity = raul.activity = None
        self.assertIsNone(talk_line(world, marta))

    def test_how_it_was_taken_is_seen_over_whoever_listened(self) -> None:
        world = self.world
        world.add_word("insults", "zopenco")
        marta, raul = self._talking(subject_of("word", "insults.zopenco"))
        world.tastes.profile(world, raul).tags[world.talk.tag_of("insults.zopenco")] = Taste(leaning=-90)
        world.talk.taken(world, raul, marta, subject_of("word", "insults.zopenco"))
        self.view.on_events(world.events.drain())
        self.assertEqual(self.view.mark_over("raul"), "disgust")

    def test_there_is_no_dock_for_whoever_is_talking(self) -> None:
        self._talking(subject_of("item", "stew"))
        self.hud.select_resident("marta")
        self.view.render()
        foot = (self.view.viewport.centerx, self.hud.layout.dock.centery)
        self.assertFalse(self.hud.covers(foot))
        self.assertFalse(hasattr(self.hud, "dock_rect"))

    # ----- residents who ask -----

    def test_whoever_asks_is_marked_and_listed_and_pressing_either_hears_them_out(self) -> None:
        self.view.centre_on_resident("tomas")
        self.view.render()
        box = self.view.hitboxes["tomas"]
        over = pygame.Rect(box.centerx - 8, box.top - 44, 16, 44).clip(self.view.viewport)
        plain = pygame.image.tobytes(self.game.canvas.subsurface(over), "RGBA")
        ask = self._ask("tomas", ASK_WORD, "insults")
        self.view.render()
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(over), "RGBA"), plain, "a mark over them")
        self.assertTrue((ASSETS_DIR / icon_path(ASK_ICON)).is_file())
        self.assertIn(ASK_ICON, ICONS, "and the tool that draws the icons knows it")
        notice = self._button(ask_intent(ask.ask_id))
        self.assertIsNotNone(notice)
        self.assertEqual(notice.label, ASK_NOTICE.format(name="Tomás"))
        self.assertTrue(self.hud.covers(notice.rect.center))
        self._press(ask_intent(ask.ask_id))
        self.assertTrue(self.hud.words_open)
        self.assertEqual((self.hud.words_entry.mode, self.hud.words_entry.field), (ASKED, ANSWER_FIELD))
        self.assertTrue(self.hud.typing, "what is typed now is the answer")
        self.assertIn(self.world.registries.talk.lists["insults"].ask, " ".join(self._said()))
        self.hud.toggle_words()
        self.assertFalse(self.hud.typing)
        # A click on them on the map does the same.
        self.view.render()
        self.view.click(self.view.hitboxes["tomas"].center)
        self.assertEqual(self.hud.words_entry.mode, ASKED)

    def test_a_word_asked_for_is_typed_and_given(self) -> None:
        ask = self._ask("tomas", ASK_WORD, "insults")
        self.view._words(ask_intent(ask.ask_id))
        self._type("zopenco")
        self.assertEqual(self.hud.words_entry.text, "zopenco")
        self._key(pygame.K_BACKSPACE)
        self._type("o")
        self._key(pygame.K_RETURN)
        self.assertEqual(self.world.words.asks, [])
        self.assertEqual(self.world.talk.find_word(self.world, "insults.zopenco")[1].by, "tomas")
        self.assertEqual(self.hud.words_entry.mode, LISTS)
        self.assertFalse(self.hud.typing)
        self.assertIn("zopenco", self.hud.notice)

    def test_an_answer_that_will_not_do_leaves_them_waiting_and_escape_leaves_it_for_later(self) -> None:
        ask = self._ask("tomas", ASK_WORD, "insults")
        self.view._words(ask_intent(ask.ask_id))
        self._key(pygame.K_RETURN)
        self.assertEqual(self.world.words.asks, [ask])
        self.assertEqual(self.hud.words_entry.mode, ASKED)
        self._key(pygame.K_ESCAPE)
        self.assertEqual(self.hud.words_entry.mode, LISTS)
        self.assertEqual(self.world.words.asks, [ask])
        self.assertFalse(self.hud.typing)

    def test_a_phrase_and_a_name_asked_for_are_given_the_same_way(self) -> None:
        phrase, name = self._ask("tomas", ASK_PHRASE, "greeting"), self._ask("marta", ASK_NICKNAME, "raul")
        self.view._words(ask_intent(phrase.ask_id))
        self._type("Buenas.")
        self._press(WORDS_GIVE_INTENT)
        self.assertEqual(self.world.talk.phrase(self.world, "tomas", "greeting"), "Buenas.")
        self.view._words(ask_intent(name.ask_id))
        self.assertIn("¿Cómo llamo a Raúl?", self._said())
        self._type("el Rulas")
        self._key(pygame.K_RETURN)
        self.assertEqual(self.world.talk.nickname(self.world, "marta", "raul"), "el Rulas")
        self.assertEqual(self.world.words.asks, [])

    def test_an_ask_let_go_while_it_was_being_answered_takes_the_board_back_to_its_lists(self) -> None:
        ask = self._ask("tomas", ASK_WORD, "insults")
        self.view._words(ask_intent(ask.ask_id))
        self._type("zop")
        self.world.words.asks.clear()
        self.view.render()
        self.assertEqual(self.hud.words_entry.mode, LISTS)
        self.assertFalse(self.hud.typing, "there is nobody to answer any more")
        # And so does whoever the board was about leaving the settlement.
        self.view._words(one_intent("marta"))
        self.view._words(write_intent(PHRASE_FIELD + "glad"))
        del self.world.residents["marta"]
        self.view.render()
        self.assertEqual(self.hud.words_entry.mode, LISTS)
        self.assertFalse(self.hud.typing)

    def test_not_now_lets_an_ask_go(self) -> None:
        ask = self._ask("tomas", ASK_WORD, "insults")
        self.hud.toggle_words()
        self.assertIn("Te preguntan", self._said())
        self._press(dismiss_intent(ask.ask_id))
        self.assertEqual(self.world.words.asks, [])
        self.assertNotIn("Te preguntan", self._said())

    def test_asked_what_to_talk_about_a_subject_is_picked_out_of_all_there_is(self) -> None:
        world = self.world
        world.add_word("subjects", "las nubes")
        ask = self._ask("tomas", ASK_SUBJECT, "ines")
        self.view._words(ask_intent(ask.ask_id))
        entry = self.hud.words_entry
        self.assertEqual((entry.mode, entry.tab, entry.resident_id, entry.other_id), (PICK, ITEMS_TAB, "tomas", "ines"))
        self.assertFalse(self.hud.typing, "nothing is being written until the box is pressed")
        self.assertEqual(self._said()[0], "¿De qué habla Tomás con Inés?")
        things = subjects_of(world, entry)
        self.assertTrue(things)
        self.assertTrue(all(item_id is not None for _subject, _name, item_id, _face in things))
        self._press(tab_intent(PEOPLE_TAB))
        people = subjects_of(world, self.hud.words_entry)
        self.assertNotIn("ines", [face for _subject, _name, _item, face in people], "not to her face")
        self.assertNotIn("tomas", [face for _subject, _name, _item, face in people])
        self._press(tab_intent("subjects"))
        self._press(subject_intent(subject_of("word", "subjects.las_nubes")))
        self.assertEqual(world.words.told["tomas"], ("ines", subject_of("word", "subjects.las_nubes")))
        self.assertEqual(world.words.asks, [])
        self.assertFalse(self.hud.words_open, "it is done, and the board is put away")

    def test_a_subject_can_be_made_up_on_the_spot_for_the_list_on_show(self) -> None:
        world = self.world
        ask = self._ask("tomas", ASK_SUBJECT, "ines")
        self.view._words(ask_intent(ask.ask_id))
        self._press(tab_intent("dangers"))
        self._press_box(SUBJECT_FIELD)
        self._type("los perros")
        self._key(pygame.K_RETURN)
        self.assertEqual(world.words.told["tomas"], ("ines", subject_of("word", "dangers.los_perros")))
        self.assertIsNotNone(world.talk.find_word(world, "dangers.los_perros"))

    # ----- the words of the settlement, and of each -----

    def test_the_board_opens_from_the_roster_and_from_a_residents_panel_and_with_a_key(self) -> None:
        panel = self.hud.layout.panel
        self.hud.select_resident(None)
        self.view.render()
        self.view.click(roster_words_hitbox(panel).center)
        self.assertTrue(self.hud.words_open)
        self.assertEqual(self.hud.words_entry.mode, LISTS)
        self.view.click(roster_words_hitbox(panel).center)
        self.assertFalse(self.hud.words_open)
        self.hud.select_resident("marta")
        self.view.render()
        self.view.click(words_hitbox(panel, self.world, self.world.residents["marta"]).center)
        self.assertEqual((self.hud.words_open, self.hud.words_entry.mode, self.hud.words_entry.resident_id), (True, ONE, "marta"))
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h, unicode="h"))
        self.assertFalse(self.hud.words_open)
        self.assertEqual(self._button(WORDS_INTENT), None, "there is no entry of the menu for it")
        # It shares its corner with the other boards.
        self.hud.toggle_words()
        self.hud.toggle_jobs()
        self.assertFalse(self.hud.words_open)

    def test_a_word_is_added_to_the_list_on_show(self) -> None:
        world = self.world
        self.hud.select_resident(None)
        self.hud.toggle_words()
        self._press(tab_intent("places"))
        self.assertIn("Todavía no hay ninguna.", self._said())
        self.assertFalse(self.hud.typing)
        self._press_box(WORD_FIELD)
        self.assertTrue(self.hud.typing)
        self._type("el Viejo Madrid")
        self._key(pygame.K_RETURN)
        self.assertEqual([word.text for word in world.talk.words(world, "places")], ["el Viejo Madrid"])
        self.assertTrue(self.hud.typing, "and the next can be written at once")
        self.assertEqual(self.hud.words_entry.text, "")
        self._type("El viejo madrid")
        self._key(pygame.K_RETURN)
        self.assertEqual(len(world.talk.words(world, "places")), 1, "the same word is not put twice")
        self._key(pygame.K_ESCAPE)
        self.assertFalse(self.hud.typing)
        self.assertTrue(self.hud.words_open)
        self.assertIn("el Viejo Madrid", " ".join(self._said()))

    def _press_box(self, name: str) -> None:
        view = words_view(self.view.font, self.hud.words_rect().topleft, self.world, self.hud.words_entry)
        box = next((part for part in view.parts if part.box == name), None)
        self.assertIsNotNone(box, name)
        self.view.click(box.rect.center)
        self.assertEqual(self.hud.words_entry.field, name)

    def test_keys_are_letters_while_something_is_written_and_shortcuts_otherwise(self) -> None:
        self.hud.select_resident(None)
        self.hud.toggle_words()
        self._press_box(WORD_FIELD)
        self._type("jk")
        self.assertEqual(self.hud.words_entry.text, "jk")
        self.assertFalse(self.hud.jobs_open, "j wrote a letter and opened nothing")
        self.assertTrue(self.hud.words_open)
        self._key(pygame.K_ESCAPE)
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j, unicode="j"))
        self.assertTrue(self.hud.jobs_open)

    def test_each_resident_is_given_phrases_of_their_own_and_names_for_the_others(self) -> None:
        world = self.world
        self.hud.select_resident(None)
        self.hud.toggle_words()
        self._press(one_intent("marta"))
        self.assertEqual(self._said()[0], "Palabras de Marta")
        self._press(write_intent(PHRASE_FIELD + "greeting"))
        self._type("¡Buenas!")
        self._key(pygame.K_RETURN)
        self.assertEqual(world.talk.phrase(world, "marta", "greeting"), "¡Buenas!")
        self.assertFalse(self.hud.typing)
        self.assertIn("Saludo: ¡Buenas!", self._said())
        # What there is already is there to be put right, and with nothing it is taken back.
        self._press(write_intent(PHRASE_FIELD + "greeting"))
        self.assertEqual(self.hud.words_entry.text, "¡Buenas!")
        for _ in "¡Buenas!":
            self._key(pygame.K_BACKSPACE)
        self._key(pygame.K_RETURN)
        self.assertEqual(world.talk.phrase(world, "marta", "greeting"), "")
        self._press(write_intent(NICKNAME_FIELD + "raul"))
        self._type("el Rulas")
        self._press(WORDS_GIVE_INTENT)
        self.assertEqual(world.talk.nickname(world, "marta", "raul"), "el Rulas")
        self.assertIn("Raúl: el Rulas", self._said())
        self._press(WORDS_BACK_INTENT)
        self.assertEqual(self.hud.words_entry.mode, LISTS)

    def test_somebody_is_told_unasked_what_to_talk_about_and_with_whom(self) -> None:
        world = self.world
        world.add_word("subjects", "las nubes")
        self.hud.select_resident("marta")
        self.hud.toggle_words()
        self._press(pick_intent("marta"))
        self.assertEqual(self._said()[0], "¿Con quién habla Marta?")
        self.assertIsNone(self._button(with_intent("marta")), "not with herself")
        self._press(with_intent("raul"))
        self.assertEqual(self._said()[0], "¿De qué habla Marta con Raúl?")
        self._press(tab_intent("subjects"))
        self._press(subject_intent(subject_of("word", "subjects.las_nubes")))
        self.assertEqual(world.words.told["marta"], ("raul", subject_of("word", "subjects.las_nubes")))
        self.assertIn("las nubes", self.hud.notice)
        self.assertEqual(world.residents["marta"].activity.partner_id, "raul", "and she goes to have it out")

    def test_the_board_draws_in_every_one_of_its_states(self) -> None:
        world = self.world
        for list_id, text in (("insults", "zopenco"), ("places", "el Viejo Madrid"), ("gossip", "el tendero se tiñe el pelo")):
            world.add_word(list_id, text)
        world.set_phrase("marta", "greeting", "¡Buenas!")
        asks = [self._ask("tomas", ASK_SUBJECT, "ines"), self._ask("lucia", ASK_WORD, "insults")]
        self.hud.select_resident("marta")
        seen = set()
        for steps in (
            [],
            [pick_intent("marta")],
            [pick_intent("marta"), with_intent("raul")],
            [pick_intent("marta"), with_intent("raul"), tab_intent(PEOPLE_TAB)],
            [pick_intent("marta"), with_intent("raul"), tab_intent("gossip")],
            [WORDS_BACK_INTENT],
            [WORDS_BACK_INTENT, ask_intent(asks[1].ask_id)],
            [WORDS_BACK_INTENT, ask_intent(asks[0].ask_id)],
        ):
            if self.hud.words_open:
                self.hud.toggle_words()
            self.hud.toggle_words()
            for intent in steps:
                self.view._words(intent)
            with self.assertNoLogs("graphics.assets", level="WARNING"):
                self.view.render()
            rect = self.hud.words_rect()
            self.assertTrue(self.view.viewport.contains(rect), steps)
            on_it = words_buttons(self.view.font, rect, world, self.hud.words_entry)
            self.assertTrue(on_it)
            self.assertTrue(all(rect.contains(button.rect) for button in on_it), steps)
            seen.add(pygame.image.tobytes(self.game.canvas.subsurface(rect), "RGB"))
        self.assertEqual(len(seen), 8, "each looks its own way")


if __name__ == "__main__":
    unittest.main()
