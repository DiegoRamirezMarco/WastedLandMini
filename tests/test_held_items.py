"""What is seen in a resident's hand, and what flies from a mouthful."""

import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.assets import ASSETS_DIR, AssetStore
from graphics.crumbs import BITE_AT, CRUMBS, DEPTH, FADES_OVER, LATEST, LIFE, Crumb, CrumbArt, crumbs
from graphics.item_icons import BITES, ICON_SIZE, ItemIcons
from graphics.palette import PALETTE
from scenes.body_stage import ground_spot
from scenes.global_view import BITES_AT, HELD_SIZE
from settings import SCALE
from simulation.commands import SetMannerCommand
from simulation.residents.activity import Activity

INK, CHEESE, SAUCE = PALETTE["ink"], (230, 190, 60), (190, 40, 40)
# Brought down smoothly to the size of a hand, a colour comes out a shade off what was drawn.
NEAR = (8, 8, 8, 255)
# How far under a mouth the feet are, for crumbs let fall with nobody there.
GROUND = 17.0
# A moment of the eating clip by which the crumbs of the last bite are gone and the next is not yet taken.
QUIET = BITE_AT - 0.02


def _is(pixel, color: tuple[int, int, int]) -> bool:
    return all(abs(pixel[index] - color[index]) <= NEAR[index] for index in range(3))


def _after(bite: float, turns: int = 3) -> float:
    """A moment of a meal, so long after the bite of one of its turns."""
    return turns + BITE_AT + bite


class CrumbTests(unittest.TestCase):
    def test_crumbs_are_about_from_a_bite_until_they_have_faded_and_gone_before_the_next(self) -> None:
        self.assertLess(LIFE, 1.0)
        for turn in (_after(-0.01), _after(LIFE + 0.01), 3 + QUIET):
            self.assertEqual(crumbs(turn, 1, GROUND), [])
        self.assertTrue(crumbs(_after(0.005), 1, GROUND))
        self.assertEqual(len(crumbs(_after(LATEST + 0.01), 1, GROUND)), CRUMBS, "soon every one of them is out")
        self.assertEqual(len(crumbs(_after(LIFE - 0.01), 1, GROUND)), CRUMBS)
        self.assertEqual(len(crumbs(0.5, 1, GROUND)), CRUMBS, "the first turn of all is like any other")

    def test_the_same_moment_is_always_the_same_and_no_two_bites_scatter_alike(self) -> None:
        self.assertEqual(crumbs(3.5, 1, GROUND), crumbs(3.5, 1, GROUND))
        self.assertNotEqual(crumbs(3.5, 1, GROUND), crumbs(4.5, 1, GROUND))
        self.assertNotEqual(crumbs(3.5, 1, GROUND), crumbs(3.6, 1, GROUND))

    def test_they_go_the_way_the_eater_faces_and_to_both_sides_of_one_seen_from_the_front(self) -> None:
        for bite in (0.02, 0.3, 0.8):
            self.assertTrue(all(crumb.x > 0 for crumb in crumbs(_after(bite), 1, GROUND)))
            self.assertTrue(all(crumb.x < 0 for crumb in crumbs(_after(bite), -1, GROUND)))
        sides = {crumb.x > 0 for crumb in crumbs(_after(0.3), 0, GROUND)}
        self.assertEqual(sides, {True, False})

    def test_they_are_thrown_up_fall_to_the_feet_hop_and_lie_there(self) -> None:
        early = crumbs(_after(0.1), 1, GROUND)
        self.assertTrue(any(crumb.y < 0 for crumb in early), "some are thrown up first")
        self.assertTrue(all(crumb.y < GROUND / 2 for crumb in early), "and none is down yet")
        # Never under the ground, at any moment, and all of them on it at the last.
        lowest = GROUND + DEPTH[1] + 1.0
        highest_lying = GROUND + DEPTH[0] - 1.0
        hopped = False
        deepest: dict[int, float] = {}
        for step in range(1, 95):
            about = crumbs(_after(step / 100), 1, GROUND)
            self.assertTrue(all(crumb.y <= lowest for crumb in about), step)
            for crumb in about:
                # Having been down among the lying ones, it is up over them again: that is the hop.
                if deepest.get(crumb.shade, 0.0) >= highest_lying and crumb.y < deepest[crumb.shade] - 0.2:
                    hopped = True
                deepest[crumb.shade] = max(deepest.get(crumb.shade, crumb.y), crumb.y)
        self.assertTrue(hopped)
        lying, later = crumbs(_after(LIFE - 0.04), 1, GROUND), crumbs(_after(LIFE - 0.01), 1, GROUND)
        self.assertTrue(all(highest_lying <= crumb.y <= lowest for crumb in lying))
        self.assertEqual(
            [(crumb.x, crumb.y, crumb.turned) for crumb in lying],
            [(crumb.x, crumb.y, crumb.turned) for crumb in later],
            "once down they are still",
        )
        # A taller eater's crumbs fall farther.
        self.assertTrue(all(crumb.y > GROUND + 4 for crumb in crumbs(_after(LIFE - 0.01), 1, GROUND + 8)))

    def test_they_scatter_turn_and_fade(self) -> None:
        early, late = crumbs(_after(0.1), 1, GROUND), crumbs(_after(LIFE - 0.04), 1, GROUND)

        def width(flying) -> float:
            return max(crumb.x for crumb in flying) - min(crumb.x for crumb in flying)

        self.assertGreater(width(late), width(early) * 2)
        self.assertGreater(width(late), 5.0, "a scatter, not a clump")
        self.assertNotEqual([crumb.turned for crumb in early], [crumb.turned for crumb in crumbs(_after(0.2), 1, GROUND)])
        self.assertGreater(len({round(crumb.across, 2) for crumb in early}), CRUMBS // 2, "of all sizes")
        self.assertGreater(len({crumb.shape % 4 for crumb in early}), 1, "and not all of one shape")
        self.assertTrue(all(crumb.alpha == 255 for crumb in early), "solid for most of the time")
        self.assertTrue(all(crumb.alpha == 255 for crumb in crumbs(_after(LIFE - FADES_OVER - 0.01), 1, GROUND)))
        self.assertTrue(all(crumb.alpha < 60 for crumb in late))


class CrumbArtTests(unittest.TestCase):
    def setUp(self) -> None:
        pygame.init()
        pygame.display.set_mode((8, 8))
        self.addCleanup(pygame.quit)
        self.art = CrumbArt()

    def _drawn(self, crumb: Crumb, detail: float) -> pygame.Surface:
        target = pygame.Surface((80, 80), pygame.SRCALPHA)
        self.art.draw(target, [crumb], [CHEESE, SAUCE], (40.0, 40.0), detail)
        return target

    def test_a_crumb_is_a_chip_of_the_food_where_it_is_and_no_ball_with_a_line_round_it(self) -> None:
        crumb = Crumb(x=2.0, y=-3.0, across=2.0, turned=0.4, alpha=255, shade=1, shape=0)
        target = self._drawn(crumb, 6.0)
        chip = pygame.mask.from_surface(target, 200)
        self.assertEqual(len(chip.get_bounding_rects()), 1)
        box = chip.get_bounding_rects()[0]
        self.assertAlmostEqual(box.centerx, 52, delta=2)
        self.assertAlmostEqual(box.centery, 22, delta=2)
        self.assertLessEqual(max(box.size), 12)
        self.assertGreater(min(box.size), 6)
        # Corners, not a round: a good part of the square it stands in is empty.
        self.assertLess(chip.count(), box.width * box.height * 0.75)
        colours = {tuple(target.get_at((x, y)))[:3] for x in range(box.left, box.right) for y in range(box.top, box.bottom) if target.get_at((x, y))[3] == 255}
        self.assertIn(SAUCE, colours, "its lit face is the colour of the food")
        self.assertTrue(any(sum(colour) < sum(SAUCE) * 0.8 for colour in colours), "and its other side darker")
        self.assertNotIn(INK, colours)

    def test_it_turns_fades_and_from_afar_is_a_square_or_two(self) -> None:
        still = Crumb(x=0.0, y=0.0, across=2.0, turned=0.0, alpha=255, shade=0, shape=0)
        turned = Crumb(x=0.0, y=0.0, across=2.0, turned=1.3, alpha=255, shade=0, shape=0)
        self.assertNotEqual(pygame.image.tobytes(self._drawn(still, 6.0), "RGBA"), pygame.image.tobytes(self._drawn(turned, 6.0), "RGBA"))
        faint = Crumb(x=0.0, y=0.0, across=2.0, turned=0.0, alpha=60, shade=0, shape=0)
        self.assertEqual(max(self._drawn(faint, 6.0).get_at((x, y))[3] for x in range(80) for y in range(80)), 60)
        self.assertEqual(self._drawn(still, 6.0).get_at((40, 40))[3], 255, "and the next one is solid again")
        far = self._drawn(Crumb(x=0.0, y=0.0, across=1.0, turned=0.7, alpha=255, shade=0, shape=2), 1.0)
        self.assertEqual(pygame.mask.from_surface(far).count(), 1)
        self.assertEqual(tuple(far.get_at((40, 40)))[:3], CHEESE)


class HeldPictureTests(unittest.TestCase):
    def setUp(self) -> None:
        pygame.init()
        pygame.display.set_mode((8, 8))
        self.addCleanup(pygame.quit)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.custom = Path(self._tmp.name)
        self._draw_pack("slice")
        self.icons = ItemIcons(AssetStore(ASSETS_DIR), AssetStore(self.custom))

    def _save(self, item_id: str, picture: pygame.Surface) -> None:
        folder = self.custom / "items" / item_id
        folder.mkdir(parents=True, exist_ok=True)
        pygame.image.save(picture, str(folder / "icon.png"))

    def _draw_pack(self, item_id: str, sauce: tuple[int, int, int] = SAUCE) -> None:
        """A food as someone would draw it in the game: 64 across, a dark line round it, two colours inside."""
        picture = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.rect(picture, INK, (4, 4, 56, 56))
        pygame.draw.rect(picture, CHEESE, (8, 8, 48, 48))
        pygame.draw.rect(picture, sauce, (20, 20, 24, 24))
        self._save(item_id, picture)

    def test_a_drawn_item_is_kept_as_large_as_it_was_drawn_for_where_it_is_seen_large(self) -> None:
        self.assertEqual(self.icons.icon("slice").get_size(), ICON_SIZE)
        self.assertEqual(self.icons.picture("slice").get_size(), (64, 64))
        self.assertEqual(self.icons.picture("canned_beans").get_size(), ICON_SIZE, "the game's own are as they are")
        self.assertEqual(self.icons.picture("no_such_thing").get_size(), ICON_SIZE, "and a missing one is the placeholder")

    def test_in_a_hand_it_is_as_large_as_asked_and_more_can_be_made_out_than_of_the_small_one(self) -> None:
        for size in (18, 36, 54, 90):
            held = self.icons.held("slice", size)
            self.assertEqual(held.get_size(), (size, size))
            self.assertIs(held, self.icons.held("slice", size))
        held = self.icons.held("slice", 36)
        self.assertTrue(_is(held.get_at((18, 18)), SAUCE))
        self.assertTrue(_is(held.get_at((7, 18)), CHEESE))
        self.assertTrue(_is(held.get_at((1, 18)), INK))
        # The game's own little pictures are made larger with their hard edges, not smeared.
        icon = self.icons.icon("canned_beans")
        longer = max(icon.get_bounding_rect().size)
        beans = self.icons.held("canned_beans", longer * 3)
        own = {tuple(icon.get_at((x, y))) for x in range(16) for y in range(16)}
        across, down = beans.get_size()
        self.assertLessEqual({tuple(beans.get_at((x, y))) for x in range(across) for y in range(down)}, own)

    def test_none_of_the_empty_paper_round_a_drawing_is_held_and_it_keeps_its_shape(self) -> None:
        # A bar three times as long as it is high, drawn small in a corner of the paper.
        picture = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.rect(picture, CHEESE, (30, 44, 30, 10))
        self._save("bar", picture)
        held = self.icons.held("bar", 60)
        self.assertEqual(held.get_size(), (60, 20))
        self.assertTrue(all(_is(held.get_at(spot), CHEESE) for spot in ((0, 0), (59, 0), (0, 19), (59, 19))))
        # Paper with nothing on it at all is held as it is.
        self._save("nothing", pygame.Surface((64, 64), pygame.SRCALPHA))
        self.assertEqual(self.icons.held("nothing", 20).get_size(), (20, 20))
        self.assertEqual(self.icons.held("nothing", 20, 2).get_size(), (20, 20))

    def test_bites_are_gone_from_the_corner_at_the_mouth_whichever_way_it_is_held(self) -> None:
        whole = pygame.mask.from_surface(self.icons.held("slice", 40)).count()
        left = None
        for bites in range(1, BITES + 1):
            bitten = self.icons.held("slice", 40, bites)
            now = pygame.mask.from_surface(bitten).count()
            self.assertLess(now, whole if left is None else left)
            left = now
        self.assertGreater(left, whole // 3, "a good part of it is in the hand to the last")
        self.assertEqual(self.icons.held("slice", 40, 1).get_at((2, 2))[3], 0, "facing right, the bite is at its upper left")
        self.assertNotEqual(self.icons.held("slice", 40, 1).get_at((37, 2))[3], 0)
        mirrored = self.icons.held("slice", 40, 1, mirrored=True)
        self.assertEqual(mirrored.get_at((37, 2))[3], 0, "and facing left, at its upper right")
        self.assertNotEqual(mirrored.get_at((2, 2))[3], 0)
        self.assertIs(self.icons.held("slice", 40, 99), self.icons.held("slice", 40, BITES))

    def test_a_bite_is_taken_from_what_is_drawn_and_not_from_the_empty_corner_of_its_paper(self) -> None:
        # A wedge with nothing in the upper left of its paper, where the mouth is.
        picture = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.polygon(picture, CHEESE, ((60, 4), (60, 60), (4, 60)))
        self._save("wedge", picture)
        whole = pygame.mask.from_surface(self.icons.held("wedge", 56)).count()
        bitten = pygame.mask.from_surface(self.icons.held("wedge", 56, 1)).count()
        self.assertLess(bitten, whole * 0.95)
        # The game's own little pictures are bitten too, and not by the square.
        small = pygame.mask.from_surface(self.icons.held("canned_beans", 48)).count()
        self.assertLess(pygame.mask.from_surface(self.icons.held("canned_beans", 48, 1)).count(), small * 0.97)

    def test_crumbs_take_the_colours_of_the_food_and_not_of_the_line_round_it(self) -> None:
        colours = self.icons.crumb_colors("slice")
        self.assertEqual(set(colours), {CHEESE, SAUCE})
        self.assertEqual(colours[0], CHEESE, "the commonest first")
        self.assertTrue(self.icons.crumb_colors("no_such_thing"))

    def test_an_item_drawn_anew_is_seen_anew_in_the_hand(self) -> None:
        before, bitten = self.icons.held("slice", 36), self.icons.held("slice", 36, 2)
        self._draw_pack("slice", sauce=(40, 160, 60))
        self.assertTrue(_is(self.icons.held("slice", 36).get_at((18, 18)), SAUCE), "kept until told")
        self.icons.forget("slice")
        after = self.icons.held("slice", 36)
        self.assertIsNot(after, before)
        self.assertTrue(_is(after.get_at((18, 18)), (40, 160, 60)))
        self.assertIsNot(self.icons.held("slice", 36, 2), bitten)
        self.assertTrue(_is(self.icons.held("slice", 36, 2).get_at((18, 18)), (40, 160, 60)))
        self.assertIn((40, 160, 60), self.icons.crumb_colors("slice"))


class HeldOnTheMapTests(unittest.TestCase):
    """Runs the real game without a window, with folders of its own for drawings and content."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "illustrations").mkdir()
        folder = self.root / "custom" / "items" / "canned_beans"
        folder.mkdir(parents=True)
        # The beans as a player might have drawn them over: large, and of two colours nothing else is.
        picture = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.rect(picture, INK, (2, 2, 60, 60))
        pygame.draw.rect(picture, CHEESE, (6, 6, 52, 52))
        pygame.draw.circle(picture, SAUCE, (32, 36), 14)
        pygame.image.save(picture, str(folder / "icon.png"))
        self.game = Game(
            illustrations_dir=self.root / "illustrations",
            voices_dir=None,
            custom_content_dir=self.root / "custom",
            save_path=self.root / "save.json",
            start_in_menu=False,
        )
        self.addCleanup(pygame.quit)
        self.view = self.game.global_view
        self.world = self.game.world
        self.world.clock.paused = True
        self.raul = self.world.residents["raul"]
        # He eats the way everybody once did, at the pace these meals are timed by.
        self.world.apply_command(SetMannerCommand("raul", "eat", "eat_calm"))
        self.raul.x, self.raul.y, self.raul.trail, self.raul.facing = 20, 14, [], "right"
        self.raul.inventory.items.clear()
        self.view.centre_on((20.5, 13.5))
        self.view.following = None

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _draw_raul(self) -> None:
        """Give Raúl a body somebody drew, so that he is shown on the window itself."""
        editor = self.game.doll_editor
        editor.open("raul")
        editor.mannequin()
        self.assertTrue(editor.save())
        self.assertIsNotNone(self.view._doll_of("raul"))

    def _eat(self, minutes_left: int = 20) -> None:
        self.raul.activity = Activity("eat", "pantry_1", minutes_left=minutes_left, using=True, item_id="canned_beans")
        self.raul.current_action = "eat"

    def _show(self, phase: float = QUIET, bite: int = 3) -> pygame.Surface:
        from scenes.global_view import CLIP_RATES, EAT_CLIP

        self.view.time = (bite + phase) / CLIP_RATES[EAT_CLIP]
        self.view.render()
        self.game.present()
        return self.game.screen

    def _count(self, window: pygame.Surface, color: tuple[int, int, int]) -> int:
        clip = self.game.layers.on_screen(self.view.viewport)
        mask = pygame.mask.from_threshold(window.subsurface(clip), (*color, 255), NEAR)
        return mask.count()

    def test_what_a_drawn_resident_eats_is_in_their_hand_at_the_size_of_the_window(self) -> None:
        self._draw_raul()
        self.raul.activity = None
        self.assertEqual(self._count(self._show(), SAUCE), 0)
        self.assertEqual(self.view._held, [])

        self._eat()
        window = self._show()
        self.assertEqual([entry[0] for entry in self.view._held], ["canned_beans"])
        self.assertEqual(self.view._held[0][4], [], "between bites nothing flies")
        detail = self.view.tile_px * SCALE / 16
        across = round(HELD_SIZE * detail)
        # It was 8 pixels of the canvas across before, and the same few pixels however it had been drawn.
        self.assertGreater(across, 20)
        self.assertGreater(self._count(window, SAUCE), across * across // 12, "what was drawn on it can be made out")
        self.assertGreater(self._count(window, CHEESE), across * across // 4)
        # Closer, it is larger and no less sharp.
        near = self._count(window, SAUCE)
        self.view.set_zoom(self.view.zoom + 1)
        self.view.centre_on((20.5, 13.5))
        self.assertGreater(self._count(self._show(), SAUCE), near * 2)

    def test_a_bite_scatters_crumbs_of_the_food_and_the_meal_is_seen_going(self) -> None:
        self._draw_raul()
        self._eat(minutes_left=20)
        self._show()
        whole = self._count(self.game.screen, CHEESE)
        self._show(phase=0.6)
        item_id, hand, left, bites, flying, mouth = self.view._held[0]
        self.assertEqual((item_id, left, bites), ("canned_beans", False, 0))
        self.assertEqual(len(flying), CRUMBS)
        self.assertLess(mouth[1], hand[1] + 12, "from the mouth, which is up by the head")
        # A crumb of sauce is in the air well away from what is in the hand.
        window = self.game.screen
        clip = self.game.layers.on_screen(self.view.viewport)
        sauce = pygame.mask.from_threshold(window.subsurface(clip), (*SAUCE, 255), NEAR)
        self.assertGreater(len(sauce.get_bounding_rects()), 1)

        use = self.world.definition_of(self.world.interactables["pantry_1"]).use
        seen = []
        for share in (0.0, *BITES_AT):
            self._eat(minutes_left=max(0, round(use.minutes * (1.0 - share)) - 1) if share else use.minutes)
            self._show()
            seen.append((self.view._held[0][3], self._count(self.game.screen, CHEESE)))
        self.assertEqual([bites for bites, _ in seen], list(range(BITES + 1)))
        self.assertTrue(all(later < earlier for (_, earlier), (_, later) in zip(seen, seen[1:])), "less of it each time")
        self.assertEqual(seen[0][1], whole)
        self.assertEqual(len(BITES_AT), BITES)

    def test_the_crumbs_of_a_bite_come_down_at_the_feet_of_whoever_took_it(self) -> None:
        self._draw_raul()
        self._eat()
        self._show(phase=BITE_AT + LIFE - 0.03 - 1.0, bite=4)
        _, _, _, _, lying, mouth = self.view._held[0]
        self.assertEqual(len(lying), CRUMBS)
        feet = ground_spot(self.raul.x, self.raul.y)[1]
        self.assertLess(mouth[1], feet - 8)
        for crumb in lying:
            self.assertAlmostEqual(mouth[1] + crumb.y, feet, delta=2.5)

    def test_facing_left_it_is_held_in_a_mirror_and_the_crumbs_go_the_other_way(self) -> None:
        self._draw_raul()
        self._eat()
        self.raul.facing = "left"
        self._show(phase=0.7)
        _, hand, left, _, flying, mouth = self.view._held[0]
        self.assertTrue(left)
        self.assertTrue(all(crumb.x < 0 for crumb in flying))
        self.raul.facing = "right"
        self._show(phase=0.7)
        self.assertFalse(self.view._held[0][2])
        self.assertTrue(all(crumb.x > 0 for crumb in self.view._held[0][4]))

    def test_what_a_drawn_resident_carries_is_in_their_pockets_and_they_are_seen_to_put_it_there(self) -> None:
        self._draw_raul()
        self.raul.activity = None
        before = self._count(self._show(), SAUCE)
        body = self.view.bodies.characters["raul"]
        self.assertIsNone(body.gesturing)
        self.world.stock(self.raul.inventory, "canned_beans", 3, None)
        window = self._show()
        self.assertEqual(self.view._held, [], "nothing is in their hands but what they are using")
        self.assertEqual(self._count(window, SAUCE), before, "and nothing of it is to be seen")
        self.assertIsNone(body.overlay, "their arms are not held out for it")
        self.assertEqual(body.gesturing, self.view.poses.pocket.clip, "a hand goes to the pocket as they take it up")

    def test_whoever_nobody_has_drawn_has_their_meal_in_their_hand_on_the_window_too(self) -> None:
        # Nobody is drawn: he is the figure the game draws of him, on the window like a doll of his own.
        self.assertIsNone(self.game.dolls.get("raul"))
        self.assertIsNotNone(self.view._doll_of("raul"))
        self._eat()
        window = self._show(phase=0.6)
        self.assertTrue(self.game.layers.active and self.view._doll_draws)
        self.assertEqual([entry[0] for entry in self.view._held], ["canned_beans"])
        self.assertEqual(self.game.canvas.get_at(self.view.viewport.center)[3], 0, "the map is on the window")
        sauce = pygame.mask.from_threshold(
            window.subsurface(self.game.layers.on_screen(self.view.viewport)), (*SAUCE, 255), NEAR
        )
        self.assertGreater(sauce.count(), 20)
        self.assertGreater(len(sauce.get_bounding_rects()), 1, "and crumbs of it fly there too")


if __name__ == "__main__":
    unittest.main()
