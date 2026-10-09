import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from graphics.doll import BODY_CANVAS, DOLL_FACINGS, HEAD_CANVAS, Doll, doll_plan, load_template
from graphics.face import FAR, FRONT, NEAR, STILL, UNDER, Face, FaceStore, Key, faced, head_of, load_rules, turned, with_head
from graphics.face_examples import example, plain_head
from graphics.mannequin import figures, tones_of
from dataclasses import replace

from skeleton.plan import FACINGS, builtin_plan
from skeleton.rig import Skeleton

SKIN = (214, 170, 130)
PROFILE, THREE_QUARTER = "profile", "three_quarter"


class FaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.rules = load_rules()
        cls.template = load_template()
        build = cls.template.starting()
        cls.template = cls.template.built(build)
        cls.plan = doll_plan(builtin_plan(), cls.template, build)
        cls.head = plain_head(cls.template, SKIN, 5)

    def drawn_face(self) -> Face:
        face = Face(self.rules)
        measure = head_of(self.head)
        for kind in self.rules.kinds.values():
            on_paper = face.on_paper(kind.kind_id, measure, self.head.get_size())
            face.drawings[kind.kind_id] = example(kind.kind_id, kind.paper, SKIN, on_paper)
        face.touch()
        return face

    def test_a_pair_starts_out_either_side_of_the_middle(self) -> None:
        face, measure = self.drawn_face(), head_of(self.head)
        near = face.key(f"eye_{NEAR}", FRONT, measure, self.head.get_size())
        far = face.key(f"eye_{FAR}", FRONT, measure, self.head.get_size())
        self.assertAlmostEqual(near.x + far.x, 2 * measure.x)
        self.assertEqual(near.y, far.y)
        self.assertLess(near.x, far.x)

    def test_turned_to_its_side_a_face_goes_to_the_front_of_the_head(self) -> None:
        face, measure, size = self.drawn_face(), head_of(self.head), self.head.get_size()
        for piece in ("nose", "mouth", f"eye_{NEAR}"):
            front = face.key(piece, FRONT, measure, size)
            side = face.key(piece, PROFILE, measure, size)
            self.assertGreater(side.x, front.x, piece)
            self.assertTrue(side.shown, piece)
        # What is flat on the face is seen narrower from its side, and what stands out of it is not.
        self.assertLess(face.key("mouth", PROFILE, measure, size).wide, 1.0)
        self.assertEqual(face.key("nose", PROFILE, measure, size).wide, 1.0)

    def test_the_far_one_of_a_pair_goes_round_the_back(self) -> None:
        face, measure, size = self.drawn_face(), head_of(self.head), self.head.get_size()
        for kind in ("eye", "brow", "ear"):
            self.assertFalse(face.key(f"{kind}_{FAR}", PROFILE, measure, size).shown, kind)
            self.assertTrue(face.key(f"{kind}_{NEAR}", PROFILE, measure, size).shown, kind)
        self.assertTrue(face.key(f"eye_{FAR}", THREE_QUARTER, measure, size).shown)

    def test_an_ear_is_behind_the_head_from_the_front_and_on_it_from_the_side(self) -> None:
        face, measure, size = self.drawn_face(), head_of(self.head), self.head.get_size()
        self.assertTrue(face.key(f"ear_{NEAR}", FRONT, measure, size).behind)
        side = face.key(f"ear_{NEAR}", PROFILE, measure, size)
        self.assertFalse(side.behind)
        self.assertLess(abs(side.x - measure.x), measure.across / 2)

    def test_what_is_said_by_hand_holds_and_the_rest_follows_the_front(self) -> None:
        face, measure, size = self.drawn_face(), head_of(self.head), self.head.get_size()
        face.set_key("nose", FRONT, Key(measure.x, measure.y + 10))
        worked_out = face.key("nose", PROFILE, measure, size)
        self.assertEqual(worked_out.y, measure.y + 10)
        face.set_key("nose", PROFILE, Key(12.0, 34.0))
        self.assertEqual(face.key("nose", PROFILE, measure, size), Key(12.0, 34.0))
        self.assertTrue(face.said("nose", PROFILE))
        face.forget_keys(PROFILE, "nose")
        self.assertEqual(face.key("nose", PROFILE, measure, size).x, worked_out.x)

    def test_between_two_views_a_piece_is_between_them(self) -> None:
        face, measure, size = self.drawn_face(), head_of(self.head), self.head.get_size()
        front = face.key("nose", FRONT, measure, size)
        quarter = face.key("nose", THREE_QUARTER, measure, size)
        half = face.at("nose", self.rules.views[THREE_QUARTER] / 2, measure, size)
        self.assertAlmostEqual(half.x, (front.x + quarter.x) / 2)
        self.assertEqual(face.at("nose", 0.0, measure, size), front)
        # Turned the other way it is the same head in a mirror: whoever shows it flips it.
        self.assertEqual(face.at("nose", -30.0, measure, size), face.at("nose", 30.0, measure, size))

    def test_nothing_turns_a_piece_that_stays(self) -> None:
        measure = head_of(self.head)
        kind = replace(self.rules.kinds["hair"], turn=STILL)
        self.assertEqual(turned(self.rules, kind, Key(90, 90), measure, 90.0), Key(90, 90))

    def test_hair_in_front_goes_forwards_and_hair_behind_goes_back(self) -> None:
        face, measure, size = self.drawn_face(), head_of(self.head), self.head.get_size()
        front, back = face.key("hair", FRONT, measure, size), face.key("hair_back", FRONT, measure, size)
        self.assertEqual(front.x, back.x)
        self.assertFalse(front.behind)
        self.assertTrue(back.behind)
        quarter = face.key("hair", THREE_QUARTER, measure, size).x
        self.assertGreater(face.key("hair", PROFILE, measure, size).x, quarter)
        self.assertGreater(quarter, front.x)
        self.assertLess(face.key("hair_back", PROFILE, measure, size).x, back.x)
        self.assertTrue(face.key("hair_back", PROFILE, measure, size).behind)
        # Behind, it is narrower from the side, and less so on the way there: no great lump of
        # it at the back of the head. In front it is as wide as it was drawn.
        self.assertLess(face.key("hair_back", PROFILE, measure, size).wide, face.key("hair_back", THREE_QUARTER, measure, size).wide)
        self.assertLess(face.key("hair_back", THREE_QUARTER, measure, size).wide, back.wide)
        self.assertEqual(face.key("hair", PROFILE, measure, size).wide, front.wide)
        behind = face.backing(self.head, 90.0)
        self.assertLess(behind[0].get_width(), face.backing(self.head, 0.0)[0].get_width())
        # What is behind the head is under it: where the two are both painted, the head is what shows.
        whole = face.composed(self.head, 0.0)
        middle = (round(measure.x), round(measure.y + measure.down * 0.8))
        self.assertEqual(tuple(whole.get_at(middle)), tuple(self.head.get_at(middle)))

    def test_a_head_with_its_face_on_is_as_large_as_its_paper(self) -> None:
        face = self.drawn_face()
        for yaw in (0.0, 45.0, 90.0):
            whole = face.composed(self.head, yaw)
            self.assertEqual(whole.get_size(), self.head.get_size())
            self.assertGreater(pygame.mask.from_surface(whole).count(), pygame.mask.from_surface(self.head).count())

    def test_a_face_is_kept_and_read_back(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = FaceStore(Path(folder), self.rules)
            face = store.get("somebody")
            measure = head_of(self.head)
            face.drawings["nose"] = example("nose", self.rules.kinds["nose"].paper, SKIN, measure)
            face.touch()
            face.set_key("nose", PROFILE, Key(150.5, 99.0, 0.8, False, True))
            self.assertTrue(store.save("somebody"))
            again = FaceStore(Path(folder), self.rules).get("somebody")
            self.assertEqual(again.keys, {"nose": {PROFILE: Key(150.5, 99.0, 0.8, False, True)}})
            self.assertTrue(again.painted("nose").width)
            self.assertFalse(again.painted("mouth").width)

    def test_hair_behind_the_head_comes_over_it_behind_the_ear_as_it_turns(self) -> None:
        face, measure, size = self.drawn_face(), head_of(self.head), self.head.get_size()
        skin = tuple(self.head.get_at((round(measure.x), round(measure.y))))
        level = round(measure.y - measure.down * 0.1)

        def at(yaw: float, across: float) -> tuple[int, ...]:
            # With nothing in front of the head, so that what is on the head itself is seen.
            bare = Face(self.rules, {"hair_back": face.drawings["hair_back"]})
            return tuple(bare.composed(self.head, yaw).get_at((round(measure.x + across * measure.across), level)))

        # From the front the whole of the head is skin. From the side its back half is hair, and
        # its front half is skin still. Three quarters on, less of it is hair than from the side.
        for across in (-0.7, -0.3, 0.3, 0.7):
            self.assertEqual(at(0.0, across), skin, across)
        self.assertNotEqual(at(90.0, -0.6), skin)
        self.assertEqual(at(90.0, 0.4), skin)
        self.assertNotEqual(at(45.0, -0.85), skin)
        self.assertEqual(at(45.0, -0.3), skin)
        # It is on the head and not beside it: the head with hair over it is no larger for it.
        ear = face.at("ear_near", 90.0, measure, size).x
        self.assertLess(abs(ear - measure.x), measure.across / 2)

    def test_the_two_hairs_are_one_shape_with_one_line_round_it(self) -> None:
        face, measure = self.drawn_face(), head_of(self.head)
        front_only = Face(self.rules, {"hair": face.drawings["hair"]})
        back_only = Face(self.rules, {"hair_back": face.drawings["hair_back"]})
        no_back = Face(self.rules, {kind: drawing for kind, drawing in face.drawings.items() if kind != "hair_back"})
        count = lambda picture: pygame.mask.from_surface(picture).count()
        fill = tuple(face.drawings["hair"].get_at((round(measure.x), round(measure.y - measure.down * 0.8))))
        back_fill = tuple(face.drawings["hair_back"].get_at(face.drawings["hair_back"].get_rect().center))
        line = (30, 22, 20, 255)
        self.assertNotEqual(fill, back_fill)
        of_front = lambda picture: pygame.mask.from_threshold(picture, fill, (1, 1, 1, 255)).count()
        room = pygame.Rect(-80, -40, 420, 460)

        def seen(which: Face, yaw: float) -> pygame.Surface:
            """All of a head turned some way: what is on it, over what is behind the whole body."""
            front, corner = which.fronting(self.head, yaw)
            picture = pygame.Surface(room.size, pygame.SRCALPHA)
            behind = which.backing(self.head, yaw)
            if behind is not None:
                picture.blit(behind[0], (behind[1][0] - room.x, behind[1][1] - room.y))
            picture.blit(front, (corner[0] - room.x, corner[1] - room.y))
            return picture

        def spot(across: float, down: float) -> tuple[int, int]:
            return (round(measure.x + across * measure.across) - room.x, round(measure.y + down * measure.down) - room.y)

        def like(got: tuple[int, ...], wanted: tuple[int, ...]) -> bool:
            # Made narrower, a colour comes out a shade off.
            return all(abs(one - other) <= 3 for one, other in zip(got, wanted))

        # From the front nothing of the hair in front is open, and with no hair behind it never is.
        self.assertEqual(of_front(face.fronting(self.head, 0.0)[0]), of_front(no_back.fronting(self.head, 0.0)[0]))
        self.assertEqual(of_front(front_only.fronting(self.head, 90.0)[0]), of_front(face.drawings["hair"]))
        self.assertLess(of_front(face.fronting(self.head, 90.0)[0]), of_front(no_back.fronting(self.head, 90.0)[0]))
        whole = seen(face, 90.0)
        # From the side, ahead of the ear it is the hair in front, and behind it the hair behind.
        self.assertEqual(tuple(whole.get_at(spot(0.5, -0.75))), fill)
        self.assertTrue(like(tuple(whole.get_at(spot(-0.5, -0.75))), back_fill))
        # Across where a lock of the hair in front lay over the hair behind, edges and all, there
        # is the one colour and no line: nothing tells the one from the other there.
        alone = seen(no_back, 90.0)
        lock = [tuple(alone.get_at((x, spot(0.0, -0.3)[1]))) for x in range(spot(-0.95, 0)[0], spot(-0.35, 0)[0])]
        self.assertIn(line, lock, "the plain fringe has no lock with a line round it where it was looked for")
        self.assertIn(fill, lock)
        for x in range(spot(-0.95, 0)[0], spot(-0.35, 0)[0]):
            self.assertTrue(like(tuple(whole.get_at((x, spot(0.0, -0.3)[1]))), back_fill), x)
        # Round the two of them there is a line still, and only one: down from the top of the
        # head behind the ear it is line, then colour, and no line again.
        column = [tuple(whole.get_at((spot(-0.5, 0)[0], y))) for y in range(whole.get_bounding_rect().top, spot(0.0, -0.5)[1])]
        # Made narrower, a line is a shade off its colour and soft at its edge: it is told by being dark.
        dark = [sum(color[:3]) < 130 for color in column if color[3] > 200]
        self.assertTrue(dark[0], column[:4])
        runs = sum(1 for before, after in zip(dark, dark[1:]) if after and not before) + 1
        self.assertEqual(runs, 1, column)
        self.assertIn(False, dark)
        # The hair behind is all there, the line round it too: nothing of it is taken away.
        self.assertEqual(count(face.backing(self.head, 90.0)[0]), count(back_only.backing(self.head, 90.0)[0]))

    def test_hair_behind_the_head_is_behind_the_body_too(self) -> None:
        face = self.drawn_face()
        plain = figures(self.template, tones_of(SKIN, (30, 22, 20)), 5)
        doll = faced(Doll(self.template, {BODY_CANVAS: plain[BODY_CANVAS], HEAD_CANVAS: self.head}, self.plan), face, self.head, 90.0)
        self.assertEqual(doll.under, {f"skull{UNDER}": "skull"})
        # The head it wears has no hair behind it, which is a picture of its own under everything.
        with_all, without = face.composed(self.head, 90.0), face.composed(self.head, 90.0, backed=False)
        back, corner = face.backing(self.head, 90.0)
        count = lambda picture: pygame.mask.from_surface(picture).count()
        self.assertGreater(count(with_all), count(without))
        self.assertGreater(count(back), 0)
        # It goes on down past the foot of the head's own paper: there is hair to go behind a trunk.
        self.assertGreater(corner[1] + back.get_height(), self.head.get_height())
        self.assertIsNone(Face(self.rules).backing(self.head, 90.0))
        facing = DOLL_FACINGS["right"]
        skeleton = Skeleton(self.plan, facing)
        skeleton.set_pose(self.plan.pose(facing))
        from graphics.doll import _laid

        first = next(iter(_laid(doll, self.plan, skeleton, 8.0)))
        self.assertIs(first[0], doll.placed(f"skull{UNDER}", False, 8.0, skeleton.bones["skull"].angle)[0])
        # A doll with no face is left as it was.
        bare = Doll(self.template, {BODY_CANVAS: plain[BODY_CANVAS]}, self.plan)
        self.assertIs(faced(bare, Face(self.rules), self.head, 90.0), bare)

    def test_hair_gone_forwards_past_the_paper_is_not_cut_off(self) -> None:
        face = self.drawn_face()
        # Hair right up to the edges of its paper, as a great deal of it is drawn.
        face.drawings["hair"].fill((90, 56, 36, 255))
        face.touch()
        picture, corner = face.fronting(self.head, 90.0)
        count = lambda surface: pygame.mask.from_surface(surface).count()
        self.assertGreater(corner[0] + picture.get_width(), self.head.get_width())
        # What of it has gone past the edge of the paper is all there, from top to bottom.
        past = picture.subsurface((self.head.get_width() - corner[0], -corner[1], corner[0] + picture.get_width() - self.head.get_width(), self.head.get_height()))
        self.assertEqual(count(past), past.get_width() * past.get_height())
        # On the paper alone, where pieces are put in place, it is cut at the edge as before.
        self.assertLess(count(face.composed(self.head, 90.0, backed=False)), count(picture))

    def test_another_head_leaves_the_body_as_it_was(self) -> None:
        plain = figures(self.template, tones_of(SKIN, (30, 22, 20)), 5)
        doll = Doll(self.template, {BODY_CANVAS: plain[BODY_CANVAS]}, self.plan)
        headed = with_head(doll, self.drawn_face().fronting(self.head, 45.0))
        self.assertIn("skull", headed.parts)
        self.assertNotIn("skull", doll.parts)
        self.assertIs(headed.parts["spine"], doll.parts["spine"])
        self.assertIs(headed.limbs, doll.limbs)


    def test_seen_from_behind_a_head_has_its_hair_over_it_and_no_face(self) -> None:
        face = self.drawn_face()
        measure = head_of(self.head)
        middle = (round(measure.x), round(measure.y))
        ahead, corner = face.fronting(self.head, 0.0)
        behind, where = face.behind(self.head, 180.0)
        back_hair = pygame.transform.flip(face.drawings["hair_back"], True, False)
        key = face.key("hair_back", FRONT, measure, self.head.get_size())
        on_hair = (middle[0] - round(2 * measure.x - key.x - back_hair.get_width() / 2), middle[1] - round(key.y - back_hair.get_height() / 2))
        self.assertGreater(back_hair.get_at(on_hair)[3], 200)
        # In the middle of the head there is the hair at the back of it, which from the front is behind it.
        self.assertEqual(tuple(behind.get_at((middle[0] - where[0], middle[1] - where[1]))), tuple(back_hair.get_at(on_hair)))
        self.assertNotEqual(tuple(ahead.get_at((middle[0] - corner[0], middle[1] - corner[1]))), tuple(back_hair.get_at(on_hair)))
        # Nothing of it is under the body, and nothing is said of where its pieces go from behind.
        body = figures(self.template, tones_of(SKIN, (30, 22, 20)), 5)[BODY_CANVAS]
        doll = Doll(self.template, {BODY_CANVAS: body, HEAD_CANVAS: self.head}, self.plan)
        self.assertTrue(faced(doll, face, self.head, 0.0).under)
        self.assertFalse(faced(doll, face, self.head, 180.0).under)
        self.assertFalse(faced(doll, face, self.head, 135.0).under)
        # A little past its side it is still the head seen from its side.
        side = faced(doll, face, self.head, 90.0)
        self.assertEqual(
            pygame.image.tobytes(faced(doll, face, self.head, 95.0).parts["skull"].image, "RGBA"),
            pygame.image.tobytes(side.parts["skull"].image, "RGBA"),
        )
        # And from there to three quarters from behind it is both at once, the one going as the
        # other comes: nothing of it is there all at once or gone all at once.
        from graphics.face import BEHIND_BY, BEHIND_FROM, UNDER

        from_behind = faced(doll, face, self.head, BEHIND_BY)
        self.assertFalse(from_behind.under)
        half = faced(doll, face, self.head, (BEHIND_FROM + BEHIND_BY) / 2)
        under = half.parts[f"skull{UNDER}"].image
        whole = side.parts[f"skull{UNDER}"].image
        middle = whole.get_bounding_rect().center
        self.assertGreater(whole.get_at(middle)[3], 250)
        self.assertAlmostEqual(under.get_at(under.get_bounding_rect().center)[3], 128, delta=6)
        # The head itself is as solid as it was, where it is in both.
        skull = half.parts["skull"]
        spot = (round(skull.start[0]), round((skull.start[1] + skull.end[1]) / 2))
        self.assertGreater(skull.image.get_at(spot)[3], 250)
        self.assertGreater(skull.image.get_bounding_rect().width, self.head.get_bounding_rect().width - 2)

    def test_a_head_with_no_hair_is_a_head_and_its_ears_from_behind(self) -> None:
        face = self.drawn_face()
        for kind_id in ("hair", "hair_back"):
            face.drawings[kind_id].fill((0, 0, 0, 0))
        face.touch()
        measure = head_of(self.head)
        behind, where = face.behind(self.head, 180.0)
        middle = (round(measure.x) - where[0], round(measure.y) - where[1])
        self.assertEqual(tuple(behind.get_at(middle))[:3], SKIN)
        # No eye, no mouth: all of the head but its edge is the one colour.
        for across in range(-int(measure.across * 0.5), int(measure.across * 0.5), 4):
            for down in range(-int(measure.down * 0.5), int(measure.down * 0.5), 4):
                self.assertEqual(tuple(behind.get_at((middle[0] + across, middle[1] + down)))[:3], SKIN, (across, down))
        # An ear at either edge: it is wider than the head alone.
        self.assertGreater(behind.get_bounding_rect().width, self.head.get_bounding_rect().width + 6)
        box = behind.get_bounding_rect()
        self.assertAlmostEqual(middle[0] - box.left, box.right - middle[0], delta=4)


if __name__ == "__main__":
    unittest.main()
