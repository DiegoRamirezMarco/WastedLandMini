import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pygame

from graphics.doll import HEAD_CANVAS, DollStore, build_path, doll_path, load_template
from graphics.face import OPEN, SHUT, FaceLook, face_path, load_rules, plain_face
from graphics.face_examples import WHITE, example, plain_head
from graphics.figure import Figures
from graphics.illustrations import Illustrations
from graphics.mannequin import figures, tones_of
from settings import SCALE, SCREEN_HEIGHT, SCREEN_WIDTH
from skeleton.plan import builtin_plan

SKIN = (214, 170, 130)
LINE = (30, 22, 20)
GREEN = (40, 200, 60, 255)


def near(image: pygame.Surface, color: tuple[int, ...], by: int = 24) -> pygame.Rect:
    """Where on a picture there is anything of about a colour: nowhere, as a box of no size."""
    mask = pygame.mask.from_threshold(image, (*color[:3], 255), (by, by, by, 255))
    boxes = mask.get_bounding_rects()
    return boxes[0].unionall(boxes[1:]) if boxes else pygame.Rect(0, 0, 0, 0)


def count(image: pygame.Surface, color: tuple[int, ...], by: int = 24) -> int:
    return pygame.mask.from_threshold(image, (*color[:3], 255), (by, by, by, 255)).count()


class MovingFaceTests(unittest.TestCase):
    """A face of pieces doing things: by rule from the one drawing of each, and from a drawing
    of its own where there is one."""

    def setUp(self) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.addCleanup(pygame.quit)
        self.rules = load_rules()
        template = load_template()
        self.head = plain_head(template.built(template.starting()), SKIN, 4)
        self.face = plain_face(self.rules, self.head, example)

    def test_an_eye_shut_and_a_mouth_open_are_papers_and_not_pieces_of_their_own(self) -> None:
        rules = self.rules
        self.assertEqual(rules.kinds["eye_shut"].stands_for, "eye")
        self.assertEqual(rules.kinds["mouth_open"].when, OPEN)
        self.assertIs(rules.drawn_as("eye", SHUT), rules.kinds["eye_shut"])
        self.assertIsNone(rules.drawn_as("nose", SHUT))
        self.assertFalse(any(piece.startswith(("eye_shut", "mouth_open")) for piece in rules.instances))
        self.assertEqual((rules.moves.steps(SHUT), rules.moves.steps(OPEN)), (2, 2))
        self.assertEqual(set(rules.moves.moods), {"happy", "sad", "angry"})

    def test_a_face_doing_nothing_is_the_face_as_it_was_drawn(self) -> None:
        plain, _ = self.face.fronting(self.head, 0.0)
        same, _ = self.face.fronting(self.head, 0.0, FaceLook())
        self.assertEqual(pygame.image.tobytes(plain, "RGBA"), pygame.image.tobytes(same, "RGBA"))
        self.assertEqual(self.face.doing("eye", FaceLook()), ())
        self.assertEqual(self.face.doing("nose", FaceLook(lids=2, mouth=2, mood="angry")), (), "a nose does nothing")

    def test_eyes_shut_by_rule_are_a_line_where_nobody_has_drawn_them_shut(self) -> None:
        face = self.face
        face.drawings["eye_shut"].fill((0, 0, 0, 0))
        face.touch()
        open_, _ = face.fronting(self.head, 0.0)
        half, _ = face.fronting(self.head, 0.0, FaceLook(lids=1))
        shut, _ = face.fronting(self.head, 0.0, FaceLook(lids=2))
        whites = [count(picture, WHITE) for picture in (open_, half, shut)]
        self.assertGreater(whites[0], whites[1])
        self.assertGreater(whites[1], 0)
        self.assertEqual(whites[2], 0, "nothing of the white of an eye is left")
        # Shut, there is a dark line as wide as the eye was where the eye was.
        source, size, _, lid = face.doing("eye", FaceLook(lids=2))
        self.assertEqual((source, lid), ("eye", True))
        line = face._done(face.doing("eye", FaceLook(lids=2))).get_bounding_rect()
        was = face.painted("eye")
        self.assertAlmostEqual(line.width, was.width, delta=3)
        self.assertLess(line.height, was.height / 2)
        self.assertAlmostEqual(line.centery, was.centery, delta=4)

    def test_an_eye_drawn_shut_and_a_mouth_drawn_open_are_shown_and_not_the_rule(self) -> None:
        face = self.face
        for kind_id in ("eye_shut", "mouth_open"):
            paper = face.drawings[kind_id]
            paper.fill((0, 0, 0, 0))
            pygame.draw.circle(paper, GREEN, paper.get_rect().center, 6)
        face.touch()
        self.assertEqual(count(face.fronting(self.head, 0.0)[0], GREEN), 0)
        shut, _ = face.fronting(self.head, 0.0, FaceLook(lids=2))
        self.assertGreater(count(shut, GREEN), 100, "both eyes are the one somebody drew shut")
        self.assertEqual(count(shut, WHITE), 0)
        # Part of the way there it is still the rule: nobody drew that.
        self.assertEqual(count(face.fronting(self.head, 0.0, FaceLook(lids=1, mouth=1))[0], GREEN), 0)
        talking, _ = face.fronting(self.head, 0.0, FaceLook(mouth=2))
        self.assertGreater(count(talking, GREEN), 50)
        self.assertGreater(count(talking, WHITE), 0, "its eyes are open all the while")

    def test_a_mouth_opens_by_rule_taller_than_it_was_drawn(self) -> None:
        face = self.face
        face.drawings["mouth_open"].fill((0, 0, 0, 0))
        face.touch()
        tall = [face._picture("mouth", 1.0, look=FaceLook(mouth=step)).get_bounding_rect().height for step in (0, 1, 2)]
        self.assertLess(tall[0], tall[1])
        self.assertLess(tall[1], tall[2])
        # Its middle is where it was: it is laid by its middle.
        closed, wide = face._picture("mouth", 1.0), face._picture("mouth", 1.0, look=FaceLook(mouth=2))
        was = closed.get_bounding_rect().centery - closed.get_height() / 2
        now = wide.get_bounding_rect().centery - wide.get_height() / 2
        self.assertAlmostEqual(was * 1.7, now, delta=2.5)

    def test_brows_and_a_mouth_say_how_somebody_feels(self) -> None:
        face = self.face

        def ends(picture: pygame.Surface) -> tuple[float, float]:
            """How high the left end of what is on a picture is, and its right, from its middle down."""
            box = picture.get_bounding_rect()
            found = []
            for x in (box.left + 1, box.right - 2):
                column = [y for y in range(box.top, box.bottom) if picture.get_at((x, y))[3] > 60]
                found.append(sum(column) / len(column) - picture.get_height() / 2)
            return found[0], found[1]

        # The brow as drawn is the one on the left of the paper: its right end is by the nose.
        outer, inner = ends(face._picture("brow_near", 1.0, look=FaceLook(mood="sad")))
        self.assertLess(inner, outer - 3, "sad, the end by the nose is up")
        outer, inner = ends(face._picture("brow_near", 1.0, look=FaceLook(mood="angry")))
        self.assertGreater(inner, outer + 3, "angry, it is down")
        # And the other brow is the same in a mirror.
        inner, outer = ends(face._picture("brow_far", 1.0, look=FaceLook(mood="angry")))
        self.assertGreater(inner, outer + 3)
        level = face._picture("brow_near", 1.0).get_bounding_rect().centery - face._picture("brow_near", 1.0).get_height() / 2
        happy = face._picture("brow_near", 1.0, look=FaceLook(mood="happy"))
        self.assertLess(happy.get_bounding_rect().centery - happy.get_height() / 2, level - 2, "happy, they are up")
        # The ends of a mouth go down for whoever is sad, and up for whoever is happy.
        plain = ends(face._picture("mouth", 1.0))
        sad = ends(face._picture("mouth", 1.0, look=FaceLook(mood="sad")))
        glad = ends(face._picture("mouth", 1.0, look=FaceLook(mood="happy")))
        self.assertGreater(sad[0], plain[0] + 3)
        self.assertLess(glad[0], plain[0] - 3)

    def test_a_face_blinks_now_and_then_and_each_in_its_own_time(self) -> None:
        moves = self.rules.moves
        steps = [moves.lids_at(tick / 60, 0.3) for tick in range(60 * 30)]
        shut = sum(1 for step in steps if step)
        self.assertGreater(shut, 0)
        self.assertLess(shut, len(steps) * 0.1, "most of the time its eyes are open")
        self.assertEqual(max(steps), moves.steps(SHUT))
        # It goes by way of half shut, there and back.
        first = next(index for index, step in enumerate(steps) if step == moves.steps(SHUT))
        self.assertEqual(steps[first - 1], 1)
        others = [moves.lids_at(tick / 60, 0.8) for tick in range(60 * 30)]
        self.assertNotEqual(steps, others)

    def test_a_mouth_goes_open_and_shut_as_somebody_speaks_and_less_as_they_chew(self) -> None:
        moves = self.rules.moves
        speaking = [moves.mouth_at(tick / 60, 0.0) for tick in range(60)]
        self.assertEqual(set(speaking), {0, 1, 2})
        chewing = [moves.mouth_at(tick / 60, 0.0, chewing=True) for tick in range(120)]
        self.assertEqual(set(chewing), {0, 1})
        changes = lambda steps: sum(1 for earlier, later in zip(steps, steps[1:]) if earlier != later)
        self.assertGreater(changes(speaking) / 60, changes(chewing) / 120)


class FacesOnFiguresTests(unittest.TestCase):
    """Faces that move, on the dolls the game shows."""

    def setUp(self) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.addCleanup(pygame.quit)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.base = load_template()
        self.template = self.base.built(self.base.starting())
        self.plain = figures(self.template, tones_of(SKIN, LINE), 5)

    def keep(self, body_id: str, pieces: bool = False) -> None:
        for canvas, drawing in self.plain.items():
            path = self.root / doll_path(body_id, canvas)
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(drawing, str(path))
        (self.root / build_path(body_id)).write_text(json.dumps(self.base.starting().to_data()), encoding="utf-8")
        if pieces:
            face = plain_face(load_rules(), self.plain[HEAD_CANVAS], example)
            for kind_id in ("eye", "brow", "mouth"):
                pygame.image.save(face.drawings[kind_id], str(self.root / face_path(body_id, kind_id)))

    def cast(self) -> Figures:
        return Figures(DollStore(Illustrations(self.root), self.base, builtin_plan()), self.root)

    def test_whoever_nobody_has_drawn_has_a_plain_face_and_whoever_drew_theirs_on_their_head_has_none(self) -> None:
        self.keep("drawn")
        cast = self.cast()
        nobody = cast.dolls.stand_in("nobody", lambda template: figures(template, tones_of(SKIN, LINE), 5))
        face = cast.face_of("nobody", nobody)
        self.assertTrue(face.drawn)
        self.assertIs(cast.face_of("nobody", nobody), face, "made once")
        self.assertGreater(count(cast.shown("nobody", nobody).doll.parts["skull"].image, WHITE), 20, "it has eyes")
        drawn = cast.dolls.get("drawn")
        self.assertFalse(cast.face_of("drawn", drawn).drawn)
        self.assertIs(cast.shown("drawn", drawn, look=FaceLook(lids=2)).doll, drawn, "a face drawn on a head does not move")

    def test_a_doll_is_shown_with_its_face_doing_something_on_the_body_it_had(self) -> None:
        self.keep("pieces", pieces=True)
        cast = self.cast()
        doll = cast.dolls.get("pieces")
        plain = cast.shown("pieces", doll, 0.0)
        cast.new_frame()
        asleep = cast.shown("pieces", doll, 0.0, look=FaceLook(lids=2))
        self.assertIsNot(asleep.doll, plain.doll)
        self.assertIs(asleep.doll.parts["spine"].image, plain.doll.parts["spine"].image, "its trunk is not made again")
        self.assertGreater(count(plain.doll.parts["skull"].image, WHITE), 20)
        self.assertEqual(count(asleep.doll.parts["skull"].image, WHITE), 0)
        self.assertIs(cast.shown("pieces", doll, 0.0, look=FaceLook(lids=2)).doll, asleep.doll, "and it is kept")
        self.assertIs(cast.shown("pieces", doll, 0.0, look=FaceLook()).doll, plain.doll)
        # From behind there is no face to do anything.
        cast.new_frame()
        behind = cast.shown("pieces", doll, 180.0)
        self.assertIs(cast.shown("pieces", doll, 180.0, look=FaceLook(lids=2, mouth=2)).doll, behind.doll)

    def test_a_face_of_pieces_is_what_is_shown_wherever_a_face_is_shown_by_itself(self) -> None:
        self.keep("pieces", pieces=True)
        self.keep("drawn")
        cast = self.cast()
        self.assertIsNone(cast.portrait("drawn", "neutral", (64, 64)))
        self.assertIsNone(cast.portrait("nobody", "neutral", (64, 64)))
        self.assertEqual(cast.portrait("pieces", "neutral", (64, 64)).get_size(), (64, 64))
        calm = cast.portrait("pieces", "neutral", (192, 192))
        self.assertGreater(count(calm, WHITE), 20, "its eyes are on it")
        angry = cast.portrait("pieces", "angry", (192, 192))
        self.assertNotEqual(pygame.image.tobytes(calm, "RGBA"), pygame.image.tobytes(angry, "RGBA"))
        # And the game's own maker of faces asks for it before it shows a bare head.
        from graphics.assets import ASSETS_DIR, AssetStore
        from graphics.face_renderer import FaceRenderer

        faces = FaceRenderer(AssetStore(ASSETS_DIR), None, Illustrations(self.root))
        bare = faces.portrait("pieces", "neutral", (192, 192))
        self.assertEqual(count(bare, WHITE), 0)
        faces.pieces = cast.portrait
        self.assertGreater(count(faces.portrait("pieces", "neutral", (192, 192)), WHITE), 20)
        self.assertIsNotNone(faces.portrait("drawn", "neutral", (64, 64)), "a head with its face drawn on it is still that")


class FacesInTheGameTests(unittest.TestCase):
    """What faces do on the map, and on the screen they are drawn on."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "illustrations"
        self.root.mkdir()
        self.addCleanup(pygame.quit)
        self.window = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        from game.game import Game

        self.game = Game(illustrations_dir=self.root, voices_dir=None, start_in_menu=False)
        self.view = self.game.global_view
        self.raul = self.game.world.residents["raul"]

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def frame(self) -> None:
        self.game.active_scene.update(1 / 60)
        self.game.active_scene.render()
        self.game.present(self.window)

    def test_on_the_map_they_blink_speak_chew_and_sleep_with_their_eyes_shut(self) -> None:
        view, raul, moves = self.view, self.raul, self.game.figures.rules.moves
        raul.x, raul.y, raul.trail, raul.activity, raul.facing = 20, 14, [], None, "down"
        view.centre_on((20, 14))
        seen, looks = set(), []
        for _ in range(60 * 7):
            self.frame()
            seen.add(id(view.doll_shown["raul"]))
            looks.append(view._look_of(raul))
        self.assertGreater(len(seen), 1, "he is not one picture all the while")
        self.assertTrue(any(look.lids == moves.steps(SHUT) for look in looks))
        self.assertTrue(all(look.mouth == 0 for look in looks), "saying nothing, his mouth is as it was drawn")
        self.assertEqual(view._look_of(raul, asleep=True), FaceLook(lids=moves.steps(SHUT)))
        # While it is his turn to speak his mouth goes.
        from ui.talk_bubble import Shown

        with mock.patch("scenes.global_view.bubble_of", return_value=Shown(text="Hola")):
            speaking = set()
            for _ in range(40):
                self.frame()
                speaking.add(view._look_of(raul).mouth)
        self.assertEqual(speaking, {0, 1, 2})
        # A picture over him says nothing aloud.
        with mock.patch("scenes.global_view.bubble_of", return_value=Shown(item_id="canned_beans")):
            self.assertEqual({view._look_of(raul).mouth for _ in range(3)}, {0})

    def test_the_screen_they_are_drawn_on_shows_the_face_in_hand_moving(self) -> None:
        from scenes.studio import FACE_TAB

        game = self.game
        studio = game.doll_editor
        studio.open("raul")
        game.scene_name = "editor"

        def press(intent: tuple) -> None:
            center = next(button for button in studio.buttons if button.intent == intent).rect.center
            for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                game.active_scene.handle_event(pygame.event.Event(kind, pos=(center[0] * SCALE + 1, center[1] * SCALE + 1), button=1))

        self.frame()
        press(("mannequin",))
        press(("tab", FACE_TAB))
        press(("mannequin",))
        self.frame()
        moves = studio.face.rules.moves
        # A tile for each paper, the two that are other drawings of a piece among them.
        for kind_id in ("eye", "eye_shut", "mouth_open"):
            self.assertTrue(any(button.intent == ("kind", kind_id) for button in studio.buttons), kind_id)
        press(("kind", "eye_shut"))
        self.frame()
        self.assertEqual(studio._look().lids, moves.steps(SHUT), "while it is drawn, the doll beside it holds it")
        press(("kind", "mouth_open"))
        self.assertEqual(studio._look().mouth, moves.steps(OPEN))
        press(("kind", "nose"))
        self.assertEqual(studio._look().mouth, 0)
        # Each feeling in turn, and then none again.
        felt = []
        for _ in range(len(moves.moods) + 1):
            press(("mood",))
            felt.append(studio._look().mood)
            self.frame()
        self.assertEqual(felt, [*moves.moods, ""])
        press(("talk",))
        mouths = set()
        for _ in range(40):
            self.frame()
            mouths.add(studio._look().mouth)
        self.assertEqual(mouths, {0, 1, 2})
        press(("talk",))
        self.assertEqual(studio._look().mouth, 0)


if __name__ == "__main__":
    unittest.main()
