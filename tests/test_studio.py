import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from graphics.assets import ASSETS_DIR
from graphics.doll import BODY_CANVAS, HEAD_CANVAS, DollStore, load_template
from graphics.figure import Figures
from graphics.font import FONT_SHEET, SHEET_SIZE, BitmapFont
from graphics.illustrations import Illustrations
from graphics.screen_layers import ScreenLayers
from graphics.studio_icons import ICONS, studio_tile
from scenes.doll_page import BACK_PAPER, BRUSH_TOOL, FILL_TOOL, MEASURE_TOOL
from ui.paintbox import BOX_TOOL, LINE_TOOL, OVAL_TOOL, POLYGON_TOOL
from scenes.studio import BODY_TAB, FACE_TAB, HANDS_TAB, HEAD_TAB, SHOW, SLIDER, WORK, Studio
from settings import INTERNAL_HEIGHT, INTERNAL_WIDTH, SCALE, SCREEN_HEIGHT, SCREEN_WIDTH
from skeleton.plan import builtin_plan


class Lab:
    """The one screen by itself, with no settlement: as it was tried apart from the game."""

    def __init__(self, root: Path, screen: pygame.Surface) -> None:
        pygame.init()
        self.screen = screen
        root.mkdir(parents=True, exist_ok=True)
        self.layers = ScreenLayers(SCALE)
        self.canvas = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT), pygame.SRCALPHA)
        self.font = BitmapFont(pygame.transform.scale(pygame.image.load(str(ASSETS_DIR / FONT_SHEET)), SHEET_SIZE))
        plan = builtin_plan()
        self.dolls = DollStore(Illustrations(root), load_template(), plan)
        cast = Figures(self.dolls, root)
        self.studio = Studio(self.canvas, self.font, self.layers, root, self.dolls, plan, cast.faces, cast.hands, cast.feet)

    @property
    def running(self) -> bool:
        return self.studio.running

    def handle_event(self, event: pygame.event.Event) -> None:
        self.studio.handle_event(event)

    def update(self, dt: float) -> None:
        self.studio.update(dt)

    def render(self) -> None:
        self.studio.render()
        self.layers.compose(self.screen, self.canvas)
        self.dolls.new_frame()


class StudioTests(unittest.TestCase):
    def setUp(self) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.folder = Path(tempfile.mkdtemp())
        self.root = self.folder / "illustrations"
        self.root.mkdir()
        self.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.lab = Lab(self.root, self.screen)
        self.studio = self.lab.studio

    def tearDown(self) -> None:
        shutil.rmtree(self.folder, ignore_errors=True)

    def mouse(self, kind: int, position: tuple[int, int]) -> None:
        window = (position[0] * SCALE, position[1] * SCALE)
        extra = {"rel": (0, 0), "buttons": (1, 0, 0)} if kind == pygame.MOUSEMOTION else {"button": 1}
        self.lab.handle_event(pygame.event.Event(kind, pos=window, **extra))

    def click(self, position: tuple[int, int]) -> None:
        self.mouse(pygame.MOUSEBUTTONDOWN, position)
        self.mouse(pygame.MOUSEBUTTONUP, position)

    def stroke(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        self.mouse(pygame.MOUSEBUTTONDOWN, start)
        self.mouse(pygame.MOUSEMOTION, end)
        self.mouse(pygame.MOUSEBUTTONUP, end)

    def button(self, intent: tuple):
        return next(each for each in self.studio._buttons() if each.intent == intent)

    def press(self, intent: tuple) -> None:
        self.click(self.button(intent).rect.center)

    def frame(self) -> None:
        self.lab.update(1 / 60)
        self.lab.render()

    def test_everything_to_press_has_a_picture_a_name_and_room_of_its_own(self) -> None:
        studio = self.studio
        for tab in (BODY_TAB, HEAD_TAB, FACE_TAB, HANDS_TAB):
            self.press(("tab", tab))
            for cog in (False, True):
                if tab != HANDS_TAB and cog:
                    self.press(("cog",))
                found = studio._buttons()
                for button in found:
                    self.assertIn(button.icon, ICONS, (tab, button.intent))
                    self.assertTrue(button.name, (tab, button.intent))
                    self.assertTrue(studio.canvas.get_rect().contains(button.rect), (tab, button.intent))
                    self.assertEqual(studio_tile(button.icon, button.rect.width * SCALE).get_width(), button.rect.width * SCALE)
                for one in found:
                    for other in found:
                        if one is not other:
                            self.assertFalse(one.rect.colliderect(other.rect), (tab, one.intent, other.intent))
                # Nothing to press is over the work or over the doll, but what goes with the bar of the hands.
                for button in found:
                    if button.rect.colliderect(WORK) or button.rect.colliderect(SHOW):
                        self.assertEqual(tab, HANDS_TAB, button.intent)
                self.frame()

    def test_the_paper_of_the_tab_that_is_up_is_the_one_that_is_drawn_on(self) -> None:
        studio, body = self.studio, self.studio.body
        self.press(("mannequin",))
        area = body.areas[BODY_CANVAS]
        self.assertEqual(list(body.areas), [BODY_CANVAS])
        # It is as wide as the work and stands on its foot: taller than it, it has the room above too.
        self.assertTrue(studio.canvas.get_rect().contains(area))
        self.assertEqual((area.x, area.right, area.bottom), (WORK.x, WORK.right, WORK.bottom))
        self.click(studio.swatches[26][0].center)
        red = tuple(studio.color)
        self.stroke((area.centerx - 20, area.y + 120), (area.centerx + 20, area.y + 120))
        self.assertEqual(tuple(body.drawings[BODY_CANVAS].get_at((area.centerx - area.x, 120)))[:3], red)
        self.assertFalse(pygame.mask.from_surface(body.drawings[HEAD_CANVAS]).count())
        # The head is shown twice as large, and a press on it lands where it is pressed.
        self.press(("tab", HEAD_TAB))
        head = body.areas[HEAD_CANVAS]
        self.assertEqual(body.zooms[HEAD_CANVAS], 2)
        self.stroke((head.x + 100, head.y + 80), (head.x + 120, head.y + 80))
        self.assertEqual(tuple(body.drawings[HEAD_CANVAS].get_at((55, 40)))[:3], red)
        # What is taken back is what was last done, on the paper it was done on.
        self.press(("undo",))
        self.assertFalse(pygame.mask.from_surface(body.drawings[HEAD_CANVAS]).count())
        self.assertEqual(tuple(body.drawings[BODY_CANVAS].get_at((area.centerx - area.x, 120)))[:3], red)
        self.frame()

    def test_a_doll_with_no_head_drawn_is_not_shown_without_one(self) -> None:
        body = self.studio.body
        self.press(("mannequin",))
        self.frame()
        self.assertFalse(body._showing_example)
        self.assertIn("skull", body._preview.parts)

    def test_measuring_is_a_tool_of_the_body_and_the_head_only(self) -> None:
        studio = self.studio
        self.press(("tool", MEASURE_TOOL))
        self.assertEqual(studio.tool, MEASURE_TOOL)
        self.frame()
        self.press(("tab", FACE_TAB))
        self.assertEqual(studio.tool, BRUSH_TOOL)
        self.assertFalse(any(button.intent == ("tool", MEASURE_TOOL) for button in studio._buttons()))

    def test_pieces_of_a_face_are_put_in_place_on_a_head_shown_large(self) -> None:
        studio, face = self.studio, self.studio.face
        self.press(("tab", HEAD_TAB))
        self.press(("mannequin",))
        self.press(("tab", FACE_TAB))
        self.press(("mannequin",))
        self.assertTrue(studio.arranging)
        self.assertEqual(face.stage_zoom, 2)
        self.assertTrue(WORK.contains(face.stage))
        # Nothing is drawn while pieces are put in place: there is no paper up, and no brush.
        self.assertEqual(face.areas, {})
        self.assertTrue(self.button(("tool", BRUSH_TOOL)).off)
        studio.yaw = 0.0
        self.frame()
        key = face._key("eye_near")
        start = (face.stage.x + round(key.x * 2), face.stage.y + round(key.y * 2))
        self.assertEqual(face.piece_at(start), "eye_near")
        self.stroke(start, (start[0] - 10, start[1] + 16))
        moved, other = face._key("eye_near"), face._key("eye_far")
        self.assertAlmostEqual(moved.x, key.x - 5, delta=1.5)
        self.assertAlmostEqual(moved.y, key.y + 8, delta=1.5)
        # Each piece goes by itself: the other eye is where it was, until the two are asked
        # to go together (P77).
        self.assertAlmostEqual(other.y, key.y, delta=0.01)
        face.symmetric = True
        self.stroke((start[0] - 10, start[1] + 16), (start[0] - 10, start[1] + 20))
        moved, other = face._key("eye_near"), face._key("eye_far")
        self.assertAlmostEqual(other.y, moved.y, delta=0.01)
        # Its paper comes up to be drawn on when its icon is pressed, and goes when pieces are placed again.
        self.press(("kind", "mouth"))
        self.assertEqual(list(face.areas), ["mouth"])
        self.assertFalse(self.button(("tool", BRUSH_TOOL)).off)
        self.press(("place",))
        self.assertEqual(face.areas, {})
        # The view they are placed in is the one nearest how far round the doll is.
        studio.yaw = 80.0
        self.frame()
        self.assertEqual(face.view, "profile")
        studio.yaw = -40.0
        self.frame()
        self.assertEqual(face.view, "three_quarter")

    def test_on_the_tab_of_the_hands_the_colour_is_theirs(self) -> None:
        studio, hand = self.studio, self.studio.hand
        self.click(studio.swatches[26][0].center)
        brush = tuple(studio.color)
        self.press(("tab", HANDS_TAB))
        self.assertTrue(self.button(("tool", BRUSH_TOOL)).off)
        self.press(("made",))
        self.assertTrue(hand.hands.choice.made)
        self.click(studio.swatches[14][0].center)
        self.assertEqual(tuple(hand.hands.color), tuple(studio.swatches[14][1]))
        self.press(("pose", "fist"))
        self.assertEqual(hand.pose_id, "fist")
        bar = hand.bar
        self.click((bar.x + bar.width // 4, bar.centery))
        self.assertAlmostEqual(hand.manual, 0.25, delta=0.02)
        self.frame()
        # Back on a paper, the brush has the colour it had.
        self.press(("tab", BODY_TAB))
        self.assertEqual(tuple(studio.color), brush)

    def test_feet_are_made_on_the_tab_of_the_hands_and_have_a_colour_of_their_own(self) -> None:
        studio, hand = self.studio, self.studio.hand
        # A body is drawn first: one nobody has drawn is shown as the plain figure, feet and all.
        self.press(("mannequin",))
        self.press(("tab", HANDS_TAB))
        self.press(("made",))
        self.click(studio.swatches[14][0].center)
        of_hands = tuple(hand.hands.color)
        self.press(("feet_made",))
        self.assertTrue(hand.feet.choice.made)
        self.assertTrue(self.button(("feet_made",)).lit)
        # From then on the colour in hand is that of the feet, and the hands keep theirs.
        self.assertEqual(tuple(studio.color), tuple(hand.feet.color))
        self.click(studio.swatches[20][0].center)
        self.assertEqual(tuple(hand.feet.color), tuple(studio.swatches[20][1]))
        self.assertEqual(tuple(hand.hands.color), of_hands)
        before = hand.feet.size
        self.press(("feet_size", 1))
        self.assertGreater(hand.feet.size, before)
        # A press on the hands shown large gives the colour back to them, and one on the feet to the feet.
        room = hand.room
        self.click((room.centerx, room.y + 30))
        self.assertEqual(tuple(studio.color), of_hands)
        self.click((room.centerx, room.bottom - 20))
        self.assertEqual(tuple(studio.color), tuple(studio.swatches[20][1]))
        self.frame()
        # The doll beside the work is cut without what is made, and they are kept with it.
        self.assertNotIn("foot_right", studio.body._preview.parts)
        name = studio.body.resident_id
        self.press(("save",))
        self.assertTrue((self.root / "dolls" / name / "feet.json").is_file())
        again = Lab(self.root, self.screen).studio
        self.assertTrue(again.foot_store.get(name).choice.made)
        self.assertEqual(again.foot_store.get(name).color, tuple(studio.swatches[20][1]))

    def test_the_line_round_hands_and_feet_has_a_colour_and_a_thickness_of_its_own(self) -> None:
        studio, hand = self.studio, self.studio.hand
        self.press(("mannequin",))
        self.press(("tab", HANDS_TAB))
        self.press(("made",))
        inside = tuple(hand.hands.color)
        # The colour in hand is that of the line while its button is lit, and of the inside again after.
        self.press(("line_color",))
        self.assertTrue(self.button(("line_color",)).lit)
        self.assertEqual(tuple(studio.color), tuple(hand.hands.ink))
        self.click(studio.swatches[26][0].center)
        self.assertEqual(tuple(hand.hands.ink), tuple(studio.swatches[26][1]))
        self.assertEqual(tuple(hand.hands.color), inside)
        self.press(("line_color",))
        self.assertEqual(tuple(studio.color), inside)
        # Thicker and thinner, down to none: and then there is no thinner to press.
        self.press(("line", 1))
        self.assertGreater(hand.hands.bold, 1.0)
        for _ in range(12):
            if not self.button(("line", -1)).off:
                self.press(("line", -1))
        self.assertEqual(hand.hands.bold, 0.0)
        self.assertTrue(self.button(("line", -1)).off)
        # The feet have theirs apart.
        self.press(("feet_made",))
        self.assertEqual(hand.feet.bold, 1.0)
        self.press(("line", 1))
        self.assertGreater(hand.feet.bold, 1.0)
        self.assertEqual(hand.hands.bold, 0.0)
        self.frame()
        # The doll beside the work tells them how wide its limbs are, and how high its ankles.
        self.assertGreater(hand.hands.joins, 0.0)
        self.assertGreater(hand.feet.joins, 0.0)
        self.assertAlmostEqual(hand.feet.stands, 1.5, delta=0.3)
        name = studio.body.resident_id
        self.press(("save",))
        again = Lab(self.root, self.screen).studio
        self.assertEqual(again.hand_store.get(name).ink, tuple(studio.swatches[26][1]))
        self.assertEqual(again.hand_store.get(name).bold, 0.0)

    def test_limbs_taken_from_the_near_side_are_not_on_the_paper_to_be_drawn(self) -> None:
        studio, body = self.studio, self.studio.body
        self.press(("mannequin",))
        self.frame()
        area = body.areas[BODY_CANVAS]
        zoom = body.zooms[BODY_CANVAS]
        guide = pygame.mask.from_surface(body.guides[BODY_CANVAS], 0)
        self.assertIsNone(body._undrawn[BODY_CANVAS])
        self.press(("far",))
        self.assertNotEqual(body.far_side, "own")
        undrawn = body._undrawn[BODY_CANVAS]
        self.assertIsNotNone(undrawn)
        hidden = pygame.mask.from_surface(undrawn)
        self.assertGreater(hidden.count(), 2000)
        # They were on the guide, and are not: no zone, no figure, no ring at a joint.
        self.assertGreater(guide.overlap_area(hidden, (0, 0)), 2000)
        self.assertEqual(pygame.mask.from_surface(body.guides[BODY_CANVAS], 0).overlap_area(hidden, (0, 0)), 0)
        # They are in the drawing all the same, to be kept and cut: it is the paper that leaves them out.
        self.assertGreater(pygame.mask.from_surface(body.drawings[BODY_CANVAS]).overlap_area(hidden, (0, 0)), 1000)
        self.frame()
        box = hidden.get_bounding_rects()[0]
        spot = (area.x + box.centerx * zoom, area.y + box.centery * zoom)
        self.assertTrue(hidden.get_at(box.center))
        paper = tuple(self.screen.get_at((spot[0] * SCALE, spot[1] * SCALE)))[:3]
        # Told to draw them by hand again, they are back on it.
        self.press(("far",))
        self.press(("far",))
        self.assertEqual(body.far_side, "own")
        self.assertIsNone(body._undrawn[BODY_CANVAS])
        self.frame()
        self.assertNotEqual(tuple(self.screen.get_at((spot[0] * SCALE, spot[1] * SCALE)))[:3], paper)

    def key(self, key: int, mod: int = 0) -> None:
        self.lab.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod, unicode=""))

    def right_click(self, position: tuple[int, int]) -> None:
        self.lab.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(position[0] * SCALE, position[1] * SCALE), button=3))

    def count(self, color: tuple[int, int, int], name: str = BODY_CANVAS) -> int:
        return pygame.mask.from_threshold(self.studio.body.drawings[name], (*color, 255), (2, 2, 2, 255)).count()

    def test_shapes_are_drawn_hollow_or_filled_and_a_polygon_corner_by_corner(self) -> None:
        studio, body = self.studio, self.studio.body
        area = body.areas[BODY_CANVAS]
        self.click(studio.swatches[26][0].center)
        red = tuple(studio.color)
        # A clear corner of the paper, well away from every zone's figure.
        at = (area.x + 150, area.y + 12)
        self.press(("tool", LINE_TOOL))
        self.stroke(at, (at[0] + 40, at[1]))
        line = self.count(red)
        self.assertGreater(line, 30)
        self.press(("tool", BOX_TOOL))
        self.stroke((at[0], at[1] + 10), (at[0] + 30, at[1] + 30))
        hollow = self.count(red) - line
        self.assertGreater(hollow, 40)
        self.press(("undo",))
        self.assertEqual(self.count(red), line)
        self.press(("fill",))
        self.assertTrue(self.button(("fill",)).lit)
        self.stroke((at[0], at[1] + 10), (at[0] + 30, at[1] + 30))
        self.assertGreater(self.count(red) - line, hollow * 1.3)
        self.press(("tool", OVAL_TOOL))
        before = self.count(red)
        self.stroke((at[0] + 50, at[1] + 10), (at[0] + 80, at[1] + 30))
        self.assertGreater(self.count(red), before + 100)
        # A press and no more is no shape at all.
        before = self.count(red)
        self.click((at[0] + 100, at[1] + 20))
        self.assertEqual(self.count(red), before)
        # A polygon: a click at each corner, and a click of the other button closes it.
        self.press(("tool", POLYGON_TOOL))
        for corner in ((at[0] + 100, at[1] + 4), (at[0] + 130, at[1] + 4), (at[0] + 115, at[1] + 30)):
            self.click(corner)
        self.assertEqual(self.count(red), before)
        self.right_click((at[0] + 115, at[1] + 30))
        self.assertGreater(self.count(red), before + 150)
        # Escape lets go of one half made, and leaves the screen up.
        self.click((at[0] + 100, at[1] + 40))
        self.assertIsNotNone(body._draft)
        self.key(pygame.K_ESCAPE)
        self.assertIsNone(body._draft)
        self.assertTrue(self.lab.running)
        self.frame()

    def test_the_bucket_fills_and_a_paper_is_wiped_and_both_are_taken_back(self) -> None:
        studio, body = self.studio, self.studio.body
        self.press(("mannequin",))
        area = body.areas[BODY_CANVAS]
        spec = body.template.parts["spine"]
        chest = (round(spec.start[0]), round((spec.start[1] + spec.end[1]) / 2))
        skin = tuple(body.drawings[BODY_CANVAS].get_at(chest))[:3]
        whole = pygame.mask.from_surface(body.drawings[BODY_CANVAS]).count()
        self.click(studio.swatches[26][0].center)
        red = tuple(studio.color)
        self.press(("tool", FILL_TOOL))
        self.click((area.x + chest[0], area.y + chest[1]))
        self.assertEqual(tuple(body.drawings[BODY_CANVAS].get_at(chest))[:3], red)
        self.assertGreater(self.count(red), 2000)
        # Ctrl+Z takes it back, as the tile does.
        self.key(pygame.K_z, pygame.KMOD_CTRL)
        self.assertEqual(tuple(body.drawings[BODY_CANVAS].get_at(chest))[:3], skin)
        self.assertEqual(self.count(red), 0)
        self.press(("clear",))
        self.assertEqual(pygame.mask.from_surface(body.drawings[BODY_CANVAS]).count(), 0)
        self.press(("undo",))
        self.assertEqual(pygame.mask.from_surface(body.drawings[BODY_CANVAS]).count(), whole)
        # Any colour may be taken off the field, not only the ready ones.
        field = studio.field.rect
        self.click((field.x + field.width // 3, field.y + 4))
        picked = tuple(studio.color)
        self.assertNotEqual(picked, red)
        self.assertEqual(picked, tuple(studio.field.color_at((field.x + field.width // 3, field.y + 4))))
        self.frame()

    def test_a_joint_is_moved_with_the_measures_in_hand_and_the_doll_is_cut_by_them(self) -> None:
        studio, body = self.studio, self.studio.body
        self.press(("mannequin",))
        self.press(("tool", MEASURE_TOOL))
        area, zoom = body.areas[BODY_CANVAS], body.zooms[BODY_CANVAS]
        handle = next(each for each in body.joint_handles(BODY_CANVAS) if each.key == "forearm.end")
        before = body.build.joints.get("forearm.end", 0.0)
        start = (area.x + round(handle.point[0] * zoom), area.y + round(handle.point[1] * zoom))
        painted = pygame.mask.from_surface(body.drawings[BODY_CANVAS]).count()
        self.stroke(start, (start[0], start[1] + 16))
        # A forearm a unit longer: and nothing was painted for the mouse having gone over the paper.
        self.assertAlmostEqual(body.build.joints["forearm.end"], before + 16 / zoom / body.template.unit, delta=0.05)
        self.assertEqual(pygame.mask.from_surface(body.drawings[BODY_CANVAS]).count(), painted)
        self.assertIsNone(body._grab)
        self.frame()
        self.press(("save",))
        again = Lab(self.root, self.screen).studio
        again.body.open(body.resident_id)
        self.assertAlmostEqual(again.body.build.joints["forearm.end"], body.build.joints["forearm.end"])

    def test_a_piece_of_a_face_is_hidden_and_put_behind_the_head_from_the_keys(self) -> None:
        studio, face = self.studio, self.studio.face
        self.press(("tab", HEAD_TAB))
        self.press(("mannequin",))
        self.press(("tab", FACE_TAB))
        self.press(("mannequin",))
        studio.yaw = 0.0
        self.frame()
        key = face._key("nose")
        spot = (face.stage.x + round(key.x * 2), face.stage.y + round(key.y * 2))
        self.assertEqual(face.piece_at(spot), "nose")
        self.assertTrue(key.shown)
        self.right_click(spot)
        self.assertFalse(face._key("nose").shown)
        self.assertEqual(face.chosen, "nose")
        self.right_click(spot)
        self.assertTrue(face._key("nose").shown)
        behind = face._key("nose").behind
        self.key(pygame.K_b)
        self.assertEqual(face._key("nose").behind, not behind)
        self.frame()

    def test_the_bar_of_the_hands_is_dragged_to_open_and_shut_them(self) -> None:
        studio, hand = self.studio, self.studio.hand
        self.press(("tab", HANDS_TAB))
        bar = hand.bar
        self.mouse(pygame.MOUSEBUTTONDOWN, (bar.x + 10, bar.centery))
        self.mouse(pygame.MOUSEMOTION, (bar.x + bar.width * 3 // 4, bar.centery))
        self.assertAlmostEqual(hand.manual, 0.75, delta=0.02)
        self.mouse(pygame.MOUSEMOTION, (bar.right + 50, bar.centery))
        self.assertEqual(hand.manual, 1.0)
        self.mouse(pygame.MOUSEBUTTONUP, (bar.right + 50, bar.centery))
        # Let go, a move of the mouse with nothing held does not move it.
        self.lab.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(bar.x * SCALE, bar.centery * SCALE), rel=(0, 0), buttons=(0, 0, 0)))
        self.assertEqual(hand.manual, 1.0)
        self.frame()

    def test_the_doll_is_turned_with_the_bar_and_told_what_to_be_at(self) -> None:
        studio = self.studio
        side = studio.faces.rules.side
        # From right behind at either end of the bar, by way of each side, to the front in the middle.
        self.click((SLIDER.x, SLIDER.centery))
        self.assertAlmostEqual(studio.yaw, -2 * side)
        self.click((SLIDER.x + SLIDER.width // 4, SLIDER.centery))
        self.assertAlmostEqual(studio.yaw, -side, delta=3)
        self.click((SLIDER.right, SLIDER.centery))
        self.assertAlmostEqual(studio.yaw, 2 * side)
        self.frame()
        self.click((SLIDER.centerx, SLIDER.centery))
        self.assertAlmostEqual(studio.yaw, 0.0, delta=3)
        self.press(("clip", "punch"))
        self.assertEqual(studio.clip, "fight")
        self.assertTrue(self.button(("clip", "punch")).lit)
        self.press(("spin",))
        self.assertTrue(studio.spinning)
        for _ in range(30):
            self.frame()
        self.assertNotAlmostEqual(studio.yaw, 0.0, places=1)
        # Taking hold of the bar stops it turning by itself.
        self.click((SLIDER.right, SLIDER.centery))
        self.assertFalse(studio.spinning)

    def test_the_back_of_a_trunk_has_a_paper_of_its_own_and_is_plain_until_it_is_drawn(self) -> None:
        studio, body = self.studio, self.studio.body
        self.press(("mannequin",))
        before = studio.yaw
        self.assertIsNone(body.back_drawn())
        self.press(("back_paper",))
        self.assertTrue(self.button(("back_paper",)).lit)
        self.assertEqual(list(body.areas), [BACK_PAPER])
        # The doll beside it is seen from behind while its back is drawn.
        self.assertEqual(studio.yaw, 2 * studio.faces.rules.side)
        self.assertTrue(self.button(("tool", MEASURE_TOOL)).off)
        self.assertTrue(self.button(("far",)).off)
        self.frame()
        # Only the trunk is on that paper: a stroke across it is kept on the trunk and nowhere else shown.
        area, zoom = body.areas[BACK_PAPER], body.zooms[BACK_PAPER]
        clear = pygame.mask.from_surface(body._undrawn[BACK_PAPER])
        clear.invert()
        trunk = clear.get_bounding_rects()[0]
        self.assertLess(trunk.width, body.template.canvases[BODY_CANVAS][0] // 2)
        self.click(studio.swatches[26][0].center)
        red = tuple(studio.color)
        start = (area.x + (trunk.centerx - 15) * zoom, area.y + trunk.centery * zoom)
        self.stroke(start, (start[0] + 30 * zoom, start[1]))
        self.assertEqual(tuple(body.drawings[BACK_PAPER].get_at((trunk.centerx, trunk.centery)))[:3], red)
        self.assertIsNotNone(body.back_drawn())
        self.assertNotEqual(tuple(body.drawings[BODY_CANVAS].get_at((trunk.centerx, trunk.centery)))[:3], red)
        # It is on the doll seen from behind, and not on the doll seen from the front.
        rules = studio.faces.rules
        behind = body._seen(2 * rules.side, 2 * rules.side)
        ahead = body._seen(0.0, 0.0)

        def reds(doll) -> int:
            return sum(pygame.mask.from_threshold(doll.limbs[bone].image, (*red, 255), (30, 30, 30, 255)).count() for bone in ("spine",) if bone in doll.limbs)

        self.assertGreater(reds(behind), 20)
        self.assertEqual(reds(ahead), 0)
        name = body.resident_id
        self.press(("save",))
        self.assertTrue((self.root / "dolls" / name / "back.png").is_file())
        self.press(("back_paper",))
        self.assertEqual(list(body.areas), [BODY_CANVAS])
        self.assertEqual(studio.yaw, before)
        again = Lab(self.root, self.screen).studio
        again.body.open(name)
        self.assertIsNotNone(again.body.back_drawn())

    def test_what_is_made_is_kept_and_found_again(self) -> None:
        studio = self.studio
        self.press(("mannequin",))
        self.press(("far",))
        self.press(("tab", HANDS_TAB))
        self.press(("made",))
        name = studio.body.resident_id
        self.press(("save",))
        kept = sorted(each.name for each in (self.root / "dolls" / name).iterdir())
        for wanted in ("body.png", "head.png", "build.json", "face.json", "hands.json"):
            self.assertIn(wanted, kept)
        again = Lab(self.root, self.screen).studio
        again.body.open(name)
        self.assertEqual(again.body.far_side, "same")
        self.assertTrue(again.hand_store.get(name).choice.made)
        # Escape leaves nothing: only the door does.
        self.lab.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
        self.assertTrue(self.lab.running)
        self.press(("close",))
        self.assertFalse(self.lab.running)


if __name__ == "__main__":
    unittest.main()
