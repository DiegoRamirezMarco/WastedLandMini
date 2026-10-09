"""Shapes laid down in one go, any colour to pick, and room on the paper: what the drawing screens share."""

import math
import os
import tempfile
import unittest
from pathlib import Path

import pygame

import json

from graphics.doll import (
    BODY_CANVAS,
    HEAD_CANVAS,
    DollBuild,
    DollStore,
    build_path,
    doll_path,
    load_template,
    template_from_data,
)
from graphics.illustrations import Illustrations
from graphics.palette import PALETTE
from settings import SCALE
from skeleton.plan import PLAN_PATH, builtin_plan
from ui.paintbox import (
    BOX_TOOL,
    CLOSE_WITHIN,
    GREY_STRIP,
    LINE_TOOL,
    OVAL_TOOL,
    POLYGON_TOOL,
    ColorField,
    ShapeDraft,
    paint_shape,
)

RED, BLUE = (200, 30, 30), (30, 60, 200)


def _paper(size: tuple[int, int] = (100, 100)) -> pygame.Surface:
    return pygame.Surface(size, pygame.SRCALPHA)


def _is(surface: pygame.Surface, at: tuple[int, int], color: tuple[int, int, int] | None) -> bool:
    pixel = surface.get_at(at)
    return pixel[3] == 0 if color is None else tuple(pixel) == (*color, 255)


class ShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)

    def test_a_line_runs_straight_from_end_to_end_as_thick_as_the_brush(self) -> None:
        paper = _paper()
        paint_shape(paper, LINE_TOOL, [(10, 50), (90, 50)], RED, 6, filled=False)
        for x in (10, 50, 90):
            self.assertTrue(_is(paper, (x, 50), RED))
        self.assertTrue(_is(paper, (50, 52), RED))
        self.assertTrue(_is(paper, (50, 60), None))
        self.assertTrue(_is(paper, (50, 40), None))

    def test_a_box_and_an_oval_are_hollow_or_filled_whichever_way_they_were_dragged(self) -> None:
        for corners in ([(20, 20), (80, 70)], [(80, 70), (20, 20)], [(20, 70), (80, 20)]):
            for tool in (BOX_TOOL, OVAL_TOOL):
                hollow, filled = _paper(), _paper()
                paint_shape(hollow, tool, corners, RED, 4, filled=False)
                paint_shape(filled, tool, corners, RED, 4, filled=True)
                self.assertTrue(_is(hollow, (50, 45), None), (tool, corners))
                self.assertTrue(_is(filled, (50, 45), RED), (tool, corners))
                for paper in (hollow, filled):
                    self.assertTrue(_is(paper, (50, 21), RED), "its top edge")
                    self.assertTrue(_is(paper, (21, 45), RED), "its left edge")
                    self.assertTrue(_is(paper, (50, 10), None), "nothing outside it")
        # An oval leaves the corners of its box bare, which a box does not.
        oval, box = _paper(), _paper()
        paint_shape(oval, OVAL_TOOL, [(20, 20), (80, 70)], RED, 4, filled=True)
        paint_shape(box, BOX_TOOL, [(20, 20), (80, 70)], RED, 4, filled=True)
        self.assertTrue(_is(oval, (22, 22), None))
        self.assertTrue(_is(box, (22, 22), RED))

    def test_a_polygon_is_made_corner_by_corner_and_closed_at_its_first_or_when_told(self) -> None:
        draft = ShapeDraft(POLYGON_TOOL, "", (20, 20))
        self.assertFalse(draft.drawn)
        for corner in ((80, 20), (80, 80)):
            draft.move(corner)
            self.assertFalse(draft.corner(corner))
        self.assertEqual(draft.fixed, [(20, 20), (80, 20), (80, 80)])
        # Seen while it is made, it is the line so far and out to the mouse, and nothing is filled.
        draft.move((30, 70))
        shown = draft.shown_on(_paper(), RED, 3, filled=True)
        self.assertTrue(_is(shown, (50, 20), RED))
        self.assertTrue(_is(shown, (70, 40), None))
        # A click by the first corner closes it. Fewer than three corners never do.
        early = ShapeDraft(POLYGON_TOOL, "", (20, 20))
        early.move((80, 20))
        early.corner((80, 20))
        self.assertFalse(early.corner((21, 21)), "two corners are a line yet")
        self.assertTrue(draft.corner((20 + CLOSE_WITHIN - 1, 20)))
        paper = _paper()
        draft.paint(paper, RED, 3, filled=True)
        self.assertTrue(_is(paper, (70, 40), RED), "closed and filled")
        self.assertTrue(_is(paper, (30, 70), None), "the corner still in hand was never put down")
        hollow = _paper()
        draft.paint(hollow, RED, 3, filled=False)
        self.assertTrue(_is(hollow, (70, 40), None))
        self.assertTrue(_is(hollow, (50, 50), RED), "the side that closes it")

    def test_a_shape_with_no_size_is_no_shape(self) -> None:
        paper = _paper()
        paint_shape(paper, BOX_TOOL, [(10, 10)], RED, 4, filled=True)
        self.assertFalse(pygame.mask.from_surface(paper).count())
        self.assertFalse(ShapeDraft(BOX_TOOL, "", (10, 10)).drawn)


class ColorFieldTests(unittest.TestCase):
    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        self.field = ColorField(pygame.Rect(8, 100, 168, 44))

    def test_any_colour_can_be_picked_and_not_only_the_ready_ones(self) -> None:
        rect = self.field.rect
        picked = {self.field.color_at((x, y)) for x in range(rect.left, rect.right, 4) for y in range(rect.top, rect.bottom, 4)}
        self.assertGreater(len(picked), 300)
        self.assertGreater(len(picked - set(PALETTE.values())), 250)
        # Round the colours from left to right, lighter above, darker below, and muted in the lower half.
        red = self.field.color_at((rect.left, rect.top + 8))
        green = self.field.color_at((rect.left + (rect.width - GREY_STRIP) // 3, rect.top + 8))
        self.assertGreater(red[0], red[1] + 60)
        self.assertGreater(green[1], green[0] + 60)
        top, low = self.field.color_at((rect.left + 40, rect.top)), self.field.color_at((rect.left + 40, rect.top + 20))
        self.assertGreater(sum(top), sum(low))
        full, muted = self.field.color_at((rect.left, rect.top + 10)), self.field.color_at((rect.left, rect.top + 32))
        self.assertGreater(max(full) - min(full), max(muted) - min(muted))

    def test_beside_them_are_the_greys_from_white_to_black(self) -> None:
        rect = self.field.rect
        strip = [self.field.color_at((rect.right - 3, y)) for y in range(rect.top, rect.bottom)]
        self.assertTrue(all(red == green == blue for red, green, blue in strip))
        self.assertEqual((strip[0], strip[-1]), ((255, 255, 255), (0, 0, 0)))

    def test_a_drag_that_runs_off_the_field_keeps_the_colour_at_its_edge(self) -> None:
        rect = self.field.rect
        self.assertTrue(self.field.contains(rect.center))
        self.assertFalse(self.field.contains((rect.right + 5, rect.centery)))
        self.assertEqual(self.field.color_at((rect.right + 50, rect.top - 50)), self.field.color_at((rect.right - 1, rect.top)))
        self.field.draw(pygame.Surface((200, 200)))


class RoomOnThePaperTests(unittest.TestCase):
    """The body's paper is wide enough for arms, trunk and legs to keep out of each other's way."""

    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        self.template = load_template()

    def _span(self, template, bones: tuple[str, ...]) -> tuple[float, float]:
        xs = [x for bone in bones for x, _ in template.parts[bone].zone()]
        return (min(xs), max(xs))

    def test_arms_trunk_and_legs_each_have_columns_of_their_own(self) -> None:
        arms = {side: tuple(f"{part}_{side}" for part in ("upper_arm", "forearm", "hand")) for side in ("left", "right")}
        for template in (self.template, self.template.built(self.template.starting())):
            far_arm, near_arm = self._span(template, arms["left"]), self._span(template, arms["right"])
            trunk = self._span(template, ("spine", "hips", "neck"))
            far_leg, near_leg = self._span(template, ("thigh_left", "shin_left")), self._span(template, ("thigh_right", "shin_right"))
            self.assertLessEqual(far_arm[1], min(trunk[0], far_leg[0]), "the far arm is clear of trunk and legs")
            self.assertGreaterEqual(near_arm[0], max(trunk[1], near_leg[1]), "and so is the near one")
            self.assertLessEqual(far_leg[1], near_leg[0], "the legs do not run into each other")
            width, height = template.canvases[BODY_CANVAS]
            self.assertTrue(all(0 <= x <= width and 0 <= y <= height for spec in template.parts.values() if not spec.whole for x, y in spec.zone()))
        # So an arm can be made a good deal longer without reaching a leg, and a foot too
        # without reaching the other.
        self.assertTrue(self.template.takes(DollBuild(joints={"hand.end": 4.0})))
        self.assertTrue(self.template.takes(DollBuild(joints={"upper_arm.end": 2.5, "forearm.end": 2.5})))
        self.assertTrue(self.template.takes(DollBuild(joints={"foot.end": 1.5})))

    def test_a_drawing_made_on_a_paper_of_before_is_laid_out_anew_and_nothing_of_it_is_resized(self) -> None:
        formers = self.template.formers
        self.assertEqual(len(formers), 3, "the paper has been laid out anew three times")
        sizes = [former.canvases[BODY_CANVAS] for former in formers]
        # The last time taller, to make room under the hips, and each time before that wider.
        self.assertGreater(self.template.canvases[BODY_CANVAS][1], sizes[0][1])
        self.assertGreater(sizes[0][0], sizes[1][0], "each time wider than the time before")
        self.assertGreater(sizes[1][0], sizes[2][0])
        for former in formers:
            for build in (DollBuild(), self.template.starting(), DollBuild(joints={"shin.end": -1.0, "upper_arm.start": -0.5})):
                was, now = former.built(build), self.template.built(build)
                old = pygame.Surface(former.canvases[BODY_CANVAS], pygame.SRCALPHA)
                marks = {}
                for index, (bone, spec) in enumerate(was.parts.items()):
                    if spec.canvas != BODY_CANVAS or not spec.reach:
                        # A part there was no room for then had nothing drawn for it.
                        continue
                    # A mark of its own in the middle of every part, as it was laid out then.
                    color = (20 + index * 13, 200 - index * 9, 40 + index * 5)
                    middle = (round((spec.start[0] + spec.end[0]) / 2), round((spec.start[1] + spec.end[1]) / 2))
                    pygame.draw.circle(old, color, middle, 5)
                    marks[bone] = color
                adopted = self.template.adopted(BODY_CANVAS, old, build)
                self.assertEqual(adopted.get_size(), self.template.canvases[BODY_CANVAS])
                for bone, color in marks.items():
                    spec = now.parts[bone]
                    middle = (round((spec.start[0] + spec.end[0]) / 2), round((spec.start[1] + spec.end[1]) / 2))
                    self.assertEqual(tuple(adopted.get_at(middle)), (*color, 255), f"{bone} is where it goes now")
                # As much paint as there was, but for a pixel on a cut: taken apart and put down, never stretched.
                self.assertAlmostEqual(
                    pygame.mask.from_surface(adopted).count(), pygame.mask.from_surface(old).count(), delta=len(marks)
                )

    def test_a_part_is_moved_by_whole_pixels_and_cut_by_the_zone_it_had_then(self) -> None:
        newest, latest, oldest = self.template.formers
        unit = self.template.unit
        # The last time the paper was laid out anew, the legs went down to make room under the
        # hips, by whole pixels, and nothing else moved.
        for bone, spec in self.template.parts.items():
            down = spec.start[1] - newest.parts[bone].start[1]
            self.assertAlmostEqual(down, round(down), 6, bone)
            self.assertEqual(spec.start[0], newest.parts[bone].start[0], bone)
            self.assertEqual(down > 0, bone.startswith(("thigh", "shin", "foot")), bone)
        for bone, spec in self.template.parts.items():
            for former in (latest, oldest):
                was = former.parts[bone]
                self.assertAlmostEqual(math.dist(was.start, was.end), math.dist(spec.start, spec.end), 6, bone)
            # From the paper before this one every part goes down on the very pixels it was drawn on.
            for now, then in zip((*spec.start, *spec.end), (*latest.parts[bone].start, *latest.parts[bone].end)):
                self.assertAlmostEqual(now - then, round(now - then), 6, f"{bone} would be put down between two pixels")
            self.assertEqual((oldest.parts[bone].reach, oldest.parts[bone].ends), (latest.parts[bone].reach, latest.parts[bone].ends))
            if spec.whole:
                continue
            # What was a part's own then is its own now: nothing drawn on a paper of before is left out of today's.
            was = latest.parts[bone]
            then, now = (pygame.mask.from_surface(each.region(bone)) for each in (latest, self.template))
            seam = 0
            for rider, other in self.template.parts.items():
                if other.rides == bone:
                    # What rides on it has what was its own past the joint it ends at: under the
                    # hips, what was drawn for them is now of the piece between the legs. The two
                    # are cut apart along a line a pixel wide, which is of neither.
                    now.draw(pygame.mask.from_surface(self.template.region(rider)), (0, 0))
                    seam = round(spec.reach * 2) + 2
            by = (round(spec.start[0] - was.start[0]), round(spec.start[1] - was.start[1]))
            self.assertGreaterEqual(now.overlap_area(then, by) + seam, then.count(), bone)
        hand = "hand_left"
        self.assertLess(latest.parts[hand].ends[1], self.template.parts[hand].ends[1], "a hand has more room now")
        # Drawn past the end of the zone a hand had then, though inside today's, it was nobody's: it is left behind.
        was = latest.parts[hand]
        old = pygame.Surface(latest.canvases[BODY_CANVAS], pygame.SRCALPHA)
        pygame.draw.circle(old, RED, (round(was.end[0]), round(was.end[1] - unit * 0.5)), 4)
        stray = (round(was.end[0]), round(was.end[1] + was.ends[1] + unit * 0.5))
        pygame.draw.circle(old, BLUE, stray, 4)
        adopted = self.template.adopted(BODY_CANVAS, old, DollBuild())
        # What is to be seen of a colour: paint of it that is not clear.
        painted = pygame.mask.from_surface(adopted)
        seen = lambda color: painted.overlap_area(pygame.mask.from_threshold(adopted, (*color, 255), (1, 1, 1, 255)), (0, 0))
        self.assertGreater(seen(RED), 30)
        self.assertEqual(seen(BLUE), 0)

    def test_laid_out_anew_a_piece_keeps_unseen_the_colour_it_had_beside_it_and_no_other(self) -> None:
        former = self.template.formers[0]
        was, now = former.parts["thigh_left"], self.template.parts["thigh_left"]
        old = pygame.Surface(former.canvases[BODY_CANVAS], pygame.SRCALPHA)
        # A leg drawn wider than its zone: what is past the edge of it is nobody's, and is cut off.
        middle = (was.start[1] + was.end[1]) / 2
        pygame.draw.rect(old, RED, pygame.Rect(was.start[0] - was.reach - 12, middle - 6, was.reach * 2 + 24, 12))
        adopted = self.template.adopted(BODY_CANVAS, old, DollBuild())
        y = round(middle + now.start[1] - was.start[1])
        inside = (round(now.start[0] - was.reach + 3), y)
        beside = (round(now.start[0] - was.reach - 3), y)
        self.assertEqual(tuple(adopted.get_at(inside)), (*RED, 255))
        # Cut off, it is not seen. Its colour is still there, so that the leg made smaller has
        # no dark edge where it was cut.
        self.assertEqual(tuple(adopted.get_at(beside)), (*RED, 0))
        # Far from any piece the paper is as nobody had ever drawn on it.
        self.assertEqual(tuple(adopted.get_at((2, adopted.get_height() - 2))), (0, 0, 0, 0))
        arm = self.template.parts["upper_arm_right"]
        self.assertEqual(tuple(adopted.get_at((round(arm.start[0]), round(arm.end[1])))), (0, 0, 0, 0))

    def test_two_papers_of_before_cannot_be_of_the_same_size_nor_of_today_s(self) -> None:
        data = json.loads(PLAN_PATH.read_text(encoding="utf-8"))["doll"]
        _, latest, oldest = data["former"]
        self.assertEqual(len(template_from_data({**data, "former": latest}).formers), 1, "one alone need not be in a list")
        self.assertEqual(template_from_data({key: value for key, value in data.items() if key != "former"}).formers, ())
        for wrong in (
            [latest, {**oldest, "canvases": latest["canvases"]}],
            [{**latest, "canvases": data["canvases"]}],
            [{**latest, "zones": {"tail": {"reach": 1}}}],
            [{**latest, "from": {"tail": [1, 1]}}],
            ["the one before"],
        ):
            with self.assertRaises(ValueError):
                template_from_data({**data, "former": wrong})

    def test_a_drawing_already_on_today_s_paper_or_of_any_other_size_is_left_alone(self) -> None:
        current = pygame.Surface(self.template.canvases[BODY_CANVAS], pygame.SRCALPHA)
        self.assertIs(self.template.adopted(BODY_CANVAS, current, DollBuild()), current)
        odd = pygame.Surface((77, 31), pygame.SRCALPHA)
        self.assertIs(self.template.adopted(BODY_CANVAS, odd, DollBuild()), odd)
        head = pygame.Surface(self.template.canvases[HEAD_CANVAS], pygame.SRCALPHA)
        self.assertIs(self.template.adopted(HEAD_CANVAS, head, DollBuild()), head)

    def test_the_store_hands_out_old_drawings_laid_out_for_today_and_leaves_their_files_as_they_are(self) -> None:
        for former in self.template.formers:
            self._check_the_store_with_a_drawing_on(former)

    def _check_the_store_with_a_drawing_on(self, former) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / doll_path("old", BODY_CANVAS)
            path.parent.mkdir(parents=True)
            old = pygame.Surface(former.canvases[BODY_CANVAS], pygame.SRCALPHA)
            trunk = former.parts["spine"]
            pygame.draw.circle(old, RED, (round(trunk.start[0]), round((trunk.start[1] + trunk.end[1]) / 2)), 8)
            pygame.image.save(old, str(path))
            store = DollStore(Illustrations(root), self.template, builtin_plan())
            drawing = store.drawings("old")[BODY_CANVAS]
            self.assertEqual(drawing.get_size(), self.template.canvases[BODY_CANVAS])
            spine = self.template.parts["spine"]
            self.assertEqual(tuple(drawing.get_at((round(spine.start[0]), round((spine.start[1] + spine.end[1]) / 2))))[:3], RED)
            self.assertIn("spine", store.get("old").parts)
            self.assertEqual(pygame.image.load(str(path)).get_size(), former.canvases[BODY_CANVAS])
            self.assertFalse((root / build_path("old")).exists())


class PaintingInTheEditorsTests(unittest.TestCase):
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

    def _event(self, editor, kind: int, position: tuple[float, float] | None = None, **particulars) -> None:
        if position is not None:
            particulars["pos"] = (round(position[0]) * SCALE, round(position[1]) * SCALE)
        editor.handle_event(pygame.event.Event(kind, **particulars))

    def _click(self, editor, position: tuple[float, float], button: int = 1) -> None:
        self._event(editor, pygame.MOUSEBUTTONDOWN, position, button=button)
        self._event(editor, pygame.MOUSEBUTTONUP, position, button=button)

    def _drag(self, editor, start: tuple[float, float], end: tuple[float, float]) -> None:
        self._event(editor, pygame.MOUSEBUTTONDOWN, start, button=1)
        self._event(editor, pygame.MOUSEMOTION, end, rel=(0, 0), buttons=(1, 0, 0))
        self._event(editor, pygame.MOUSEBUTTONUP, end, button=1)

    def _tool(self, editor, tool: str) -> None:
        self._click(editor, next(button for button in editor.buttons if button.intent == ("tool", tool)).rect.center)
        self.assertEqual(editor.tool, tool)

    def _frame(self, editor) -> None:
        editor.update(1 / 60)
        editor.render()
        self.game.present()

    def _painted(self, surface: pygame.Surface) -> int:
        return pygame.mask.from_surface(surface).count()

    def test_the_body_s_paper_has_the_head_and_the_figure_beside_it_and_none_of_them_overlap(self) -> None:
        editor = self.game.doll_editor
        editor.open("nuria")
        from scenes.studio import SHOW

        # One paper is up at a time, as large as it is drawn, with the figure that moves beside it.
        body = editor.areas[BODY_CANVAS]
        self.assertEqual(list(editor.areas), [BODY_CANVAS])
        self.assertEqual(body.size, editor.template.canvases[BODY_CANVAS])
        self.assertGreaterEqual(SHOW.left, body.right)
        screen = self.game.canvas.get_rect()
        self.assertTrue(all(screen.contains(rect) for rect in (body, SHOW)))
        tools = [button.rect for button in editor.buttons]
        tools += [rect for rect, _ in (*editor.swatches, *editor.brush_buttons)] + [editor.field.rect]
        self.assertTrue(all(screen.contains(rect) for rect in tools))
        self.assertTrue(all(not rect.colliderect(body) and not rect.colliderect(SHOW) for rect in tools), "the tools are clear of the paper")
        self.assertTrue(all(not one.colliderect(other) for index, one in enumerate(tools) for other in tools[index + 1 :]))
        # The head's paper takes its place, twice as large as it is drawn.
        self._click(editor, next(button for button in editor.buttons if button.intent == ("tab", "head")).rect.center)
        head = editor.areas[HEAD_CANVAS]
        self.assertEqual(list(editor.areas), [HEAD_CANVAS])
        self.assertEqual(head.size, tuple(2 * side for side in editor.template.canvases[HEAD_CANVAS]))
        self.assertTrue(screen.contains(head) and not head.colliderect(SHOW))
        self._frame(editor)

    def test_a_colour_off_the_field_paints_like_any_other(self) -> None:
        editor = self.game.doll_editor
        editor.open("nuria")
        field = editor.field.rect
        self._event(editor, pygame.MOUSEBUTTONDOWN, (field.left + 30, field.top + 6), button=1)
        first = editor.color
        self.assertNotIn(first, PALETTE.values())
        # Held and dragged, it goes on picking; let go, the mouse is a brush again.
        self._event(editor, pygame.MOUSEMOTION, (field.left + 90, field.top + 30), rel=(0, 0), buttons=(1, 0, 0))
        self.assertNotEqual(editor.color, first)
        self._event(editor, pygame.MOUSEBUTTONUP, (field.left + 90, field.top + 30), button=1)
        picked = editor.color
        body = editor.areas[BODY_CANVAS]
        self._drag(editor, (body.x + 150, body.y + 100), (body.x + 170, body.y + 100))
        self.assertEqual(tuple(editor.drawings[BODY_CANVAS].get_at((160, 100))), (*picked, 255))
        self._event(editor, pygame.MOUSEMOTION, (field.left + 10, field.top + 10), rel=(0, 0), buttons=(0, 0, 0))
        self.assertEqual(editor.color, picked)
        self._frame(editor)

    def test_shapes_are_laid_down_on_a_resident_s_paper_and_undone_like_a_stroke(self) -> None:
        editor = self.game.doll_editor
        editor.open("nuria")
        body = editor.areas[BODY_CANVAS]
        self._tool(editor, "box")
        self._event(editor, pygame.MOUSEBUTTONDOWN, (body.x + 150, body.y + 70), button=1)
        self._event(editor, pygame.MOUSEMOTION, (body.x + 230, body.y + 140), rel=(0, 0), buttons=(1, 0, 0))
        self.assertFalse(self._painted(editor.drawings[BODY_CANVAS]), "while it is dragged nothing is on the paper yet")
        self._frame(editor)
        self._event(editor, pygame.MOUSEBUTTONUP, (body.x + 230, body.y + 140), button=1)
        drawing = editor.drawings[BODY_CANVAS]
        self.assertEqual(tuple(drawing.get_at((190, 70)))[:3], editor.color)
        self.assertEqual(drawing.get_at((190, 105))[3], 0, "hollow until told otherwise")
        self.assertFalse(editor._showing_example, "the figure that moves is their own now")

        self._click(editor, next(button for button in editor.buttons if button.intent == ("fill",)).rect.center)
        self._tool(editor, "oval")
        # On the head's paper, which is put up in the body's place and shown twice as large.
        self._click(editor, next(button for button in editor.buttons if button.intent == ("tab", "head")).rect.center)
        head = editor.areas[HEAD_CANVAS]
        self._drag(editor, (head.x + 80, head.y + 100), (head.x + 300, head.y + 300))
        self.assertEqual(tuple(editor.drawings[HEAD_CANVAS].get_at((95, 100)))[:3], editor.color)
        self._click(editor, next(button for button in editor.buttons if button.intent == ("tab", "body")).rect.center)
        self._tool(editor, "line")
        before = self._painted(editor.drawings[BODY_CANVAS])
        self._drag(editor, (body.x + 30, body.y + 40), (body.x + 55, body.y + 180))
        self.assertGreater(self._painted(editor.drawings[BODY_CANVAS]), before)
        self._event(editor, pygame.KEYDOWN, key=pygame.K_z, mod=pygame.KMOD_CTRL, unicode="z")
        self.assertEqual(self._painted(editor.drawings[BODY_CANVAS]), before)
        # A press and release in one place is not a shape, and leaves nothing to undo.
        self._click(editor, (body.x + 300, body.y + 300))
        self.assertEqual(self._painted(editor.drawings[BODY_CANVAS]), before)
        self._frame(editor)

    def test_a_polygon_is_clicked_out_and_escape_lets_go_of_it_without_leaving_the_drawing(self) -> None:
        editor = self.game.doll_editor
        editor.open("nuria")
        body = editor.areas[BODY_CANVAS]
        corners = [(body.x + 110, body.y + 230), (body.x + 160, body.y + 230), (body.x + 160, body.y + 320)]
        self._tool(editor, "polygon")
        for corner in corners[:2]:
            self._click(editor, corner)
        self.assertTrue(editor.notice)
        self._event(editor, pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="")
        self.assertFalse(editor.closed)
        self.assertIsNone(editor._draft)
        self.assertFalse(self._painted(editor.drawings[BODY_CANVAS]))

        for corner in corners:
            self._click(editor, corner)
        self._event(editor, pygame.MOUSEMOTION, (body.x + 110, body.y + 330), rel=(0, 0), buttons=(0, 0, 0))
        self._frame(editor)
        self._event(editor, pygame.MOUSEBUTTONDOWN, (body.x + 110, body.y + 330), button=3)
        self.assertIsNone(editor._draft)
        drawing = editor.drawings[BODY_CANVAS]
        self.assertEqual(tuple(drawing.get_at((135, 230)))[:3], editor.color)
        self.assertEqual(drawing.get_at((112, 328))[3], 0, "where the mouse was when it was closed is no corner")
        # Closed by its first corner or by Enter just as well, and a change of tool lets go of one half made.
        painted = self._painted(drawing)
        for corner in ((body.x + 240, body.y + 230), (body.x + 290, body.y + 230), (body.x + 290, body.y + 300)):
            self._click(editor, corner)
        self._click(editor, (body.x + 241, body.y + 231))
        self.assertIsNone(editor._draft)
        self.assertGreater(self._painted(editor.drawings[BODY_CANVAS]), painted)
        self._click(editor, (body.x + 300, body.y + 40))
        self._tool(editor, "brush")
        self.assertIsNone(editor._draft)
        self._event(editor, pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="")
        self.assertTrue(editor.closed, "with no shape in hand, Escape is out of the drawing")

    def test_buildings_and_objects_have_the_same_shapes_and_field(self) -> None:
        building = self.game.building_editor
        building.open("shop")
        thing = self.game.object_editor
        thing.open("bed")
        for editor, drawing, scale in (
            (building, lambda: building.drawings[building.part], 1),
            (thing, lambda: thing.drawing, thing.zoom),
        ):
            field = editor.field.rect
            self._click(editor, (field.left + 50, field.top + 8))
            self.assertNotIn(editor.color, PALETTE.values())
            self._click(editor, next(button for button in editor.buttons if button.intent == ("fill",)).rect.center)
            self.assertTrue(editor.filled)
            self._tool(editor, "box")
            area = editor.area
            self._drag(editor, (area.x + 8 * scale, area.y + 8 * scale), (area.x + 30 * scale, area.y + 26 * scale))
            self.assertEqual(tuple(drawing().get_at((18, 16))), (*editor.color, 255))
            self.assertEqual(drawing().get_at((40, 40))[3], 0)
            painted = self._painted(drawing())
            self._tool(editor, "polygon")
            for corner in ((40, 40), (60, 40), (60, 60)):
                self._click(editor, (area.x + corner[0] * scale, area.y + corner[1] * scale))
            self._frame(editor)
            self._event(editor, pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r")
            self.assertGreater(self._painted(drawing()), painted)
            self._event(editor, pygame.KEYDOWN, key=pygame.K_z, mod=pygame.KMOD_CTRL, unicode="z")
            self.assertEqual(self._painted(drawing()), painted)
            tools = [button.rect for button in editor.buttons if button not in editor.top_buttons and button.rect.x < area.x]
            tools.append(field)
            self.assertTrue(all(not one.colliderect(other) for index, one in enumerate(tools) for other in tools[index + 1 :]))
            self._frame(editor)


if __name__ == "__main__":
    unittest.main()
