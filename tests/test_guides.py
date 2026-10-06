"""What is traced over in the editors: each piece in a zone of its own, named, with an example under it."""

import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.assets import ASSETS_DIR, AssetStore
from graphics.building_art import BUILDING_PARTS, DOOR_PART, INSIDE_PART, ROOF_PART, WALLS_PART
from graphics.doll import BODY_CANVAS, HEAD_CANVAS, Doll, load_template
from graphics.doll_guide import INK, SHIRT, SKIN, cuts, label_spots, reference
from graphics.illustrations import Illustrations
from graphics.object_art import ObjectArtStore
from graphics.object_sprites import ObjectSprites
from graphics.palette import PALETTE
from settings import SCALE
from simulation.registries import builtin_registries

LIMBS = (
    ("upper_arm_left", "forearm_left", "hand_left"),
    ("upper_arm_right", "forearm_right", "hand_right"),
    ("thigh_left", "shin_left", "foot_left"),
    ("thigh_right", "shin_right", "foot_right"),
)


def _mask(surface: pygame.Surface) -> pygame.mask.Mask:
    return pygame.mask.from_surface(surface)


def _colours(surface: pygame.Surface) -> set[tuple[int, int, int]]:
    return {
        tuple(surface.get_at((x, y)))[:3]
        for x in range(surface.get_width())
        for y in range(surface.get_height())
        if surface.get_at((x, y))[3]
    }


class DollGuideTests(unittest.TestCase):
    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        self.template = load_template()

    def test_the_parts_of_a_limb_each_have_a_zone_of_their_own(self) -> None:
        for limb in LIMBS:
            regions = [_mask(self.template.region(bone)) for bone in limb]
            for bone, region in zip(limb, regions):
                self.assertGreater(region.count(), 0, bone)
                # A part is its own only inside the zone it may be drawn in.
                zone = _mask(self.template.mask(bone))
                self.assertEqual(region.overlap_area(zone, (0, 0)), region.count(), bone)
            for first, second in zip(regions, regions[1:]):
                # Where one ends the next begins: they meet along the cut, and neither is on the other.
                self.assertLessEqual(first.overlap_area(second, (0, 0)), 4 * self.template.unit, limb)

    def test_a_drawing_is_cut_where_the_guide_says_and_nowhere_else(self) -> None:
        lines = cuts(self.template, BODY_CANVAS)
        joints = {(round((start[0] + end[0]) / 2), round((start[1] + end[1]) / 2)) for start, end in lines}
        self.assertEqual(len(joints), len(lines), "every cut is drawn once, though two parts meet at it")
        for limb in LIMBS:
            for bone in limb[1:]:
                joint = self.template.parts[bone].start
                self.assertIn((round(joint[0]), round(joint[1])), joints, f"{bone} is cut where it begins")
        self.assertEqual(cuts(self.template, HEAD_CANVAS), [], "a head is drawn in one piece")
        # What the game cuts out of a drawing is what the guide marked as the part, and the round end it adds.
        figure = reference(self.template, BODY_CANVAS)
        for bone in ("forearm_right", "shin_left"):
            kept = _mask(self.template.cut_mask(bone, figure))
            region = _mask(self.template.region(bone))
            self.assertEqual(region.overlap_area(kept, (0, 0)), region.count(), bone)

    def test_the_figure_under_the_guide_is_a_drawing_to_go_by_and_not_patches_of_colour(self) -> None:
        body, head = reference(self.template, BODY_CANVAS), reference(self.template, HEAD_CANVAS)
        for figure in (body, head):
            colours = _colours(figure)
            self.assertIn(INK, colours, "it has a dark line round it")
            self.assertIn(SKIN, colours)
            self.assertGreaterEqual(len(colours), 4, "and more than a colour or two")
        self.assertIn(SHIRT, _colours(body))
        # Every part has something of it, and nothing of it lies where no part could take it.
        allowed = pygame.Mask(self.template.canvases[BODY_CANVAS])
        for bone, spec in self.template.parts.items():
            if spec.canvas != BODY_CANVAS:
                continue
            region = _mask(self.template.region(bone))
            self.assertGreater(_mask(body).overlap_area(region, (0, 0)), 50, bone)
            allowed.draw(_mask(self.template.cut_mask(bone, body)), (0, 0))
        painted = _mask(body)
        self.assertEqual(painted.overlap_area(allowed, (0, 0)), painted.count())
        # It faces right: the eye is ahead of the middle of the head.
        skull = self.template.parts["skull"]
        white = pygame.mask.from_threshold(head, (*PALETTE["paper"], 255), (1, 1, 1, 255))
        self.assertGreater(white.count(), 0)
        self.assertGreater(white.get_bounding_rects()[0].centerx, skull.end[0])

    def test_the_figure_can_be_cut_and_put_together_like_any_drawing(self) -> None:
        doll = Doll(self.template, {name: reference(self.template, name) for name in self.template.canvases})
        self.assertEqual(set(doll.parts), set(self.template.parts))

    def test_every_part_can_be_named_where_it_is(self) -> None:
        spots = label_spots(self.template, BODY_CANVAS)
        self.assertEqual(set(spots), {bone for bone, spec in self.template.parts.items() if spec.canvas == BODY_CANVAS})
        canvas = pygame.Rect((0, 0), self.template.canvases[BODY_CANVAS])
        self.assertTrue(all(canvas.contains(spot) for spot in spots.values()))
        self.assertEqual(label_spots(self.template, HEAD_CANVAS), {})


class EditorGuideTests(unittest.TestCase):
    """Runs the real editors without a window, with a folder of their own to keep drawings in."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "illustrations").mkdir()
        (self.root / "custom").mkdir()
        self.game = Game(
            illustrations_dir=self.root / "illustrations",
            voices_dir=None,
            custom_content_dir=self.root / "custom",
            save_path=self.root / "save.json",
            start_in_menu=False,
        )
        self.addCleanup(pygame.quit)

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _frame(self, scene) -> None:
        scene.update(1 / 60)
        scene.render()
        self.game.present()

    def test_the_guide_of_a_resident_names_its_parts_and_the_example_moves_until_something_is_drawn(self) -> None:
        editor = self.game.doll_editor
        editor.open("paco")
        bare = editor.template.guide(BODY_CANVAS)
        named = editor.guides[BODY_CANVAS]
        self.assertEqual(named.get_size(), bare.get_size())
        self.assertGreater(_mask(named).count(), _mask(bare).count(), "names are written on it, each on a patch of paper")
        self.assertTrue(editor._showing_example)
        self.assertIs(editor._preview, editor._example)
        self._frame(editor)

        body = editor.areas[BODY_CANVAS]
        for kind, position in (
            (pygame.MOUSEBUTTONDOWN, (body.x + 150, body.y + 100)),
            (pygame.MOUSEBUTTONUP, (body.x + 170, body.y + 130)),
        ):
            editor.handle_event(pygame.event.Event(kind, pos=(position[0] * SCALE, position[1] * SCALE), button=1))
        self.assertFalse(editor._showing_example, "from the first stroke it is their own drawing that moves")
        self.assertIsNot(editor._preview, editor._example)
        editor.clear()
        self.assertTrue(editor._showing_example)
        self._frame(editor)

    def test_each_part_of_a_building_has_named_zones_and_an_example_under_them(self) -> None:
        store = self.game.global_view.building_art
        room = self.game.world.rooms["shop"]
        names = {part: [name for name, _ in store.zones(room, part)] for part in BUILDING_PARTS}
        self.assertEqual(names[INSIDE_PART], ["floor"])
        self.assertEqual(names[ROOF_PART], ["roof"])
        self.assertEqual(set(names[DOOR_PART]), {"door"})
        self.assertEqual(set(names[WALLS_PART]), {"back", "side", "front", "gap"})
        gaps = [rect for name, rect in store.zones(room, WALLS_PART) if name == "gap"]
        self.assertEqual(gaps, [rect for _, rect in store.zones(room, DOOR_PART)], "the wall leaves a gap for each door")

        # The game has no picture of an inside, so the example is a floor of boards, and only there.
        floor = store.zones(room, INSIDE_PART)[0][1]
        boards = store.example(room, INSIDE_PART)
        self.assertEqual(_mask(boards).get_bounding_rects()[0], floor)
        self.assertIn(PALETTE["copper"], _colours(store.guide(room, INSIDE_PART)))
        # For the rest it is what the game draws, which is also what the starter puts on the paper.
        for part in (ROOF_PART, WALLS_PART, DOOR_PART):
            example = _mask(store.example(room, part))
            self.assertGreater(example.count(), 0, part)
            self.assertEqual(example.count(), _mask(store.starter(room, part)).count(), part)
            self.assertGreaterEqual(_mask(store.guide(room, part)).count(), example.count(), part)

        editor = self.game.building_editor
        editor.open("shop")
        for part in BUILDING_PARTS:
            editor._set_part(part)
            bare = store.guide(room, part)
            self.assertNotEqual(
                pygame.image.tobytes(editor.guide_picture, "RGBA"), pygame.image.tobytes(bare, "RGBA"), part
            )
            self._frame(editor)

    def test_a_building_put_up_by_the_player_gets_the_same_guides(self) -> None:
        world = self.game.world
        placed = None
        for y in range(8, world.tile_map.height - 8):
            for x in range(2, world.tile_map.width - 8):
                if world.urbanism.building_error(world, 4, 3, (x, y)) is None:
                    placed = world.urbanism.place_building(world, "shack", (x, y))
                    break
            if placed is not None:
                break
        self.assertTrue(placed is not None and placed.ok)
        self.game._build_scenes()
        store = self.game.global_view.building_art
        room = self.game.world.rooms[placed.entity_id]
        self.assertEqual(len([name for name, _ in store.zones(room, WALLS_PART) if name == "gap"]), 1)
        self.game.building_editor.open(room.room_id)
        self._frame(self.game.building_editor)

    def test_the_guide_of_an_object_shows_the_game_s_own_under_its_zones(self) -> None:
        store = self.game.global_view.object_art
        for kind in ("bed", "water_tank", "campfire", "wreck"):
            definition = self.game.world.registries.interactables.get(kind)
            guide = store.guide(definition)
            starter = store.starter(definition)
            self.assertEqual(guide.get_size(), store.canvas_size(definition))
            painted = [
                (x, y)
                for x in range(0, starter.get_width(), 3)
                for y in range(0, starter.get_height(), 3)
                if starter.get_at((x, y))[3]
            ]
            showing = [spot for spot in painted if guide.get_at(spot) == starter.get_at(spot)]
            # All of it but what the lines between tiles are drawn over.
            self.assertGreater(len(showing), len(painted) * 0.8, f"{kind}: the example is there to be seen")
            editor = self.game.object_editor
            editor.open(kind)
            self._frame(editor)
            self.assertFalse(_mask(editor.drawing).count(), "and the paper itself starts blank")


class ObjectGuideWithoutAFolderTests(unittest.TestCase):
    def test_with_nowhere_to_keep_drawings_there_is_still_a_guide_to_show(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        store = ObjectArtStore(Illustrations(None), ObjectSprites(AssetStore(ASSETS_DIR)))
        self.assertFalse(store.available)
        definition = builtin_registries().interactables.get("crate")
        self.assertEqual(store.guide(definition).get_size(), (64, 64))
        self.assertIsNone(store.drawing(definition))


if __name__ == "__main__":
    unittest.main()
