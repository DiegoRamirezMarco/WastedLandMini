"""The icons of the screen a doll is made on: one for everything there is to press, so that
nothing on it has to be read.

They are drawn in the same hand as the game's own (`graphics/ui_art.py`), on the same square,
and are added to its icons: a tile with one of these on it is made as any other is. What each
is of is for whoever lays the screen out to say; here is only what each looks like, and the
colour of its tile, which goes by what kind of thing it does.
"""

import math
from collections.abc import Callable

import pygame

from graphics.hand import HandRules, Look, draw_hand
from graphics.hand import load_rules as load_hand_rules
from graphics.palette import Color
from graphics.ui_art import GLYPHS, HUES, Pen, tile

# The colour of a tile, by what kind of thing is pressed with it.
DRAWING: Color = (212, 104, 148)
SHAPES: Color = (88, 150, 196)
EDITING: Color = (146, 138, 128)
DANGER: Color = (206, 78, 84)
HELPING: Color = (112, 160, 78)
MEASURING: Color = (226, 134, 62)
MOVING: Color = (72, 162, 132)
FACE: Color = (222, 158, 48)
HANDS: Color = (88, 176, 196)
SETTING: Color = (128, 138, 142)
BODY: Color = (226, 104, 74)
HEAD: Color = (146, 108, 196)


def _eraser(p: Pen) -> None:
    p.turned(24, 21, 32, 17, -35)
    p.turned(15.4, 27, 4, 17, -35, p.cut)
    p.box(7, 39, 34, 3.4, 1.5, p.soft)


def _bucket(p: Pen) -> None:
    p.arc(21, 16, 11, 205, 335, 3, p.soft)
    p.poly([(9, 18), (32, 11), (37, 31), (16, 38)])
    p.line([(11.5, 19.6), (31, 13.8)], 2.6, p.cut)
    p.circle(40.5, 38, 4.2)
    p.poly([(40.5, 27.5), (36.6, 36.5), (44.4, 36.5)])


def _line(p: Pen) -> None:
    p.line([(10, 38), (38, 10)], 5)
    p.circle(10, 38, 5.2)
    p.circle(38, 10, 5.2)
    p.circle(10, 38, 2.2, p.cut)
    p.circle(38, 10, 2.2, p.cut)


def _box(p: Pen) -> None:
    p.box(7, 10, 34, 28, 4)
    p.box(12.5, 15.5, 23, 17, 1.5, p.cut)


def _oval(p: Pen) -> None:
    p.circle(24, 24, 17.5)
    p.circle(24, 24, 11.5, p.cut)


def _polygon(p: Pen) -> None:
    def corners(radius: float) -> list[tuple[float, float]]:
        return [(24 + radius * math.sin(math.radians(turn)), 25 - radius * math.cos(math.radians(turn))) for turn in range(0, 360, 72)]

    p.poly(corners(19))
    p.poly(corners(12), p.cut)
    for x, y in corners(19):
        p.circle(x, y, 3.4, p.light)


def _filled(p: Pen) -> None:
    p.box(6, 6, 24, 24, 4, p.soft)
    p.box(11, 11, 14, 14, 1.5, p.cut)
    p.box(18, 18, 24, 24, 4)


def _undo(p: Pen) -> None:
    p.arc(26, 27, 12.5, 185, 450, 6)
    p.poly([(3.5, 24.5), (23.5, 24.5), (13.5, 38.5)])


def _trash(p: Pen) -> None:
    p.box(18.5, 4.5, 11, 6, 2.5)
    p.box(7.5, 9.5, 33, 5.5, 2)
    p.box(11, 17, 26, 26, 4)
    for x in (16.6, 22.8, 29):
        p.box(x, 21.5, 2.4, 17, 1, p.cut)


def _body(p: Pen) -> None:
    # A trunk with its shoulders and the tops of its arms: what a shirt is the shape of.
    p.poly([(15, 6), (33, 6), (45, 14), (40, 23), (34.5, 20), (34.5, 44), (13.5, 44), (13.5, 20), (8, 23), (3, 14)])
    p.arc(24, 5.5, 6, 0, 180, 3.4, p.cut)


def _head(p: Pen) -> None:
    p.box(19, 33, 10, 11, 2.5, p.soft)
    p.circle(24, 20, 15.5)


_HAND_RULES: HandRules | None = None


def _held(pose_id: str) -> Callable[[Pen], None]:
    """The icon of a way of holding a hand: a hand that is made, held that way and seen from
    its palm, its fingers up. Drawn by hand, the icons were of the hand there was before, a
    ball with thin fingers, and of no hand the screen makes now."""

    def glyph(p: Pen) -> None:
        global _HAND_RULES
        if _HAND_RULES is None:
            _HAND_RULES = load_hand_rules()
        rules = _HAND_RULES
        pose = rules.poses[pose_id]
        # Shut, it is shorter: it is shown larger, and stands in the middle of its tile all the same.
        up, long = 43.0 - 3.0 * pose.curl, 28.0 + 9.0 * pose.curl
        draw_hand(
            p.surface, rules, (25.0 * p.k, up * p.k), long * p.k, math.pi, 1.0, pose, tuple(p.main[:3]), rules.fingers,
            look=Look(ink=tuple(p.cut[:3]), bold=1.2),
        )

    return glyph


def _hand(p: Pen) -> None:
    for x, top in ((11.5, 13), (17.7, 7), (23.9, 5), (30.1, 9)):
        p.box(x, top, 5, 22, 2.5)
    p.box(11.5, 23, 23.6, 20, 7)
    p.turned(38.5, 28.5, 5.4, 15, -38)


def _mannequin(p: Pen) -> None:
    p.circle(24, 8.5, 6)
    p.line([(11, 21), (24, 17), (37, 21)], 4.6)
    p.line([(24, 15), (24, 29)], 6.5)
    p.line([(14.5, 43.5), (24, 29), (33.5, 43.5)], 5)
    for x, y in ((24, 17), (24, 29)):
        p.circle(x, y, 2.3, p.cut)


def _measure(p: Pen) -> None:
    p.line([(13, 35), (35, 13)], 5.5, p.soft)
    for x, y in ((13, 35), (35, 13)):
        p.circle(x, y, 8.2)
        p.circle(x, y, 3.4, p.cut)


def _far_own(p: Pen) -> None:
    p.box(7, 7, 13, 34, 6.5, p.soft)
    p.line([(10.5, 14), (16.5, 20), (10.5, 26), (16.5, 32)], 2.4, p.cut)
    p.box(28, 7, 13, 34, 6.5)


def _far_same(p: Pen) -> None:
    p.box(7, 7, 13, 34, 6.5)
    p.box(28, 7, 13, 34, 6.5)
    p.poly([(21, 24), (27, 18.5), (27, 29.5)], p.light)


def _far_darker(p: Pen) -> None:
    p.box(7, 7, 13, 34, 6.5, p.cut)
    p.box(9, 9, 9, 30, 4.5, p.soft)
    p.box(28, 7, 13, 34, 6.5)
    p.poly([(21, 24), (27, 18.5), (27, 29.5)], p.light)


def _symmetry(p: Pen) -> None:
    p.poly([(20.5, 11), (20.5, 38), (5, 38)])
    p.poly([(27.5, 11), (27.5, 38), (43, 38)], p.soft)
    for y in (5, 13.5, 22, 30.5, 39):
        p.box(22.9, y, 2.2, 5.4, 1, p.light)


def _plus(p: Pen) -> None:
    p.box(19.5, 7, 9, 34, 2.5)
    p.box(7, 19.5, 34, 9, 2.5)


def _minus(p: Pen) -> None:
    p.box(7, 19.5, 34, 9, 2.5)


def _prev(p: Pen) -> None:
    p.poly([(33, 8), (33, 40), (11, 24)])


def _next(p: Pen) -> None:
    p.poly([(15, 8), (15, 40), (37, 24)])


def _stand(p: Pen) -> None:
    p.circle(24, 8.5, 6)
    p.box(17, 16, 14, 17, 5.5)
    p.box(17.6, 30, 5.2, 14, 2.4)
    p.box(25.2, 30, 5.2, 14, 2.4)


def _walk(p: Pen) -> None:
    p.circle(27.5, 8.5, 6)
    p.line([(26, 16), (22.5, 29)], 7)
    p.line([(26.5, 18), (35.5, 26)], 4.2)
    p.line([(25.5, 18), (15.5, 25)], 4.2, p.soft)
    p.line([(22.5, 29), (30.5, 35), (33.5, 43.5)], 4.8)
    p.line([(22.5, 29), (17.5, 36), (10.5, 42.5)], 4.8, p.soft)


def _punch(p: Pen) -> None:
    p.circle(15.5, 9.5, 6)
    p.line([(15.5, 17), (17.5, 31)], 7.5)
    p.line([(17, 19.5), (36, 19.5)], 5)
    p.circle(39, 19.5, 5.4)
    p.line([(17.5, 31), (11.5, 43.5)], 4.8)
    p.line([(17.5, 31), (25.5, 43.5)], 4.8, p.soft)
    for start, end in (((40.5, 8.5), (44.5, 5)), ((44, 28.5), (46.5, 32))):
        p.line([start, end], 2.2, p.light)


def _turn(p: Pen) -> None:
    p.arc(24, 24, 14.5, 20, 160, 5.5)
    p.arc(24, 24, 14.5, 200, 340, 5.5, p.soft)
    p.poly([(31.5, 3.5), (44, 15.5), (29.5, 18.5)], p.soft)
    p.poly([(16.5, 44.5), (4, 32.5), (18.5, 29.5)])


def _guide(p: Pen) -> None:
    p.box(6, 14, 26, 28, 4, p.soft)
    p.box(16, 6, 26, 28, 4)
    p.line([(21.5, 14), (36.5, 14)], 2.4, p.cut)
    p.line([(21.5, 20.5), (36.5, 20.5)], 2.4, p.cut)
    p.line([(21.5, 27), (31, 27)], 2.4, p.cut)


def _thinner(p: Pen) -> None:
    p.box(18.5, 7, 11, 34, 5.5, p.soft)
    p.poly([(3, 15.5), (3, 32.5), (14, 24)])
    p.poly([(45, 15.5), (45, 32.5), (34, 24)])


def _thicker(p: Pen) -> None:
    p.box(14.5, 7, 19, 34, 9, p.soft)
    p.poly([(11, 15.5), (11, 32.5), (1.5, 24)])
    p.poly([(37, 15.5), (37, 32.5), (46.5, 24)])


def _reset(p: Pen) -> None:
    p.arc(24, 25.5, 13.5, -55, 235, 6)
    p.poly([(24, 3), (24, 21), (36.5, 12)])


def _place(p: Pen) -> None:
    for turn in range(4):
        cos, sin = math.cos(math.radians(turn * 90)), math.sin(math.radians(turn * 90))

        def at(x: float, y: float) -> tuple[float, float]:
            return (24 + x * cos - y * sin, 24 + x * sin + y * cos)

        p.poly([at(21, 0), at(11.5, -8.5), at(11.5, 8.5)])
        p.poly([at(3, -3.2), at(13, -3.2), at(13, 3.2), at(3, 3.2)])
    p.circle(24, 24, 5.4)


def _eye(p: Pen) -> None:
    p.poly([(3, 24), (12, 14), (24, 10.5), (36, 14), (45, 24), (36, 34), (24, 37.5), (12, 34)])
    p.circle(24, 24, 9, p.cut)
    p.circle(24, 24, 4, p.soft)
    p.circle(27.5, 20.5, 2.6, p.light)


def _eye_shut(p: Pen) -> None:
    # A lid down, and its lashes under it.
    p.arc(24, 2, 26, 42, 138, 7.5)
    for x, y, to_x, to_y in ((10, 27, 6, 35), (24, 30, 24, 39), (38, 27, 42, 35)):
        p.line([(x, y), (to_x, to_y)], 5)


def _mouth_open(p: Pen) -> None:
    p.poly([(24, 6), (37, 11), (42, 24), (37, 37), (24, 42), (11, 37), (6, 24), (11, 11)])
    p.circle(24, 22, 11.5, p.cut)
    p.circle(24, 32, 7, p.soft)


def _mood(p: Pen) -> None:
    # A face, and a smile on it.
    p.circle(24, 24, 21)
    p.circle(16, 19, 3.6, p.cut)
    p.circle(32, 19, 3.6, p.cut)
    p.arc(24, 20, 13, 30, 150, 4.5, p.cut)


def _talk(p: Pen) -> None:
    # What is said, in the air, and where it comes from.
    p.poly([(5, 8), (43, 8), (43, 32), (24, 32), (13, 43), (15, 32), (5, 32)])
    for x in (15, 24, 33):
        p.circle(x, 20, 2.8, p.cut)


def _brow(p: Pen) -> None:
    p.arc(24, 44, 26, 222, 318, 8.5)


def _mouth(p: Pen) -> None:
    # A smile, and no more.
    p.arc(24, 10, 21, 28, 152, 8.5)
    p.circle(5.5, 19.5, 3.4, p.soft)
    p.circle(42.5, 19.5, 3.4, p.soft)


def _nose(p: Pen) -> None:
    p.line([(27, 6.5), (21.5, 30), (13.5, 35), (25.5, 41), (35, 35.5)], 6.5)
    p.circle(31, 35.5, 2.4, p.cut)


def _ear(p: Pen) -> None:
    # The round of it, its lobe under that, and the fold inside it.
    p.circle(25, 19, 15.5)
    p.circle(21, 35, 8.5)
    p.arc(26, 19.5, 8, 150, 395, 4.2, p.cut)
    p.line([(20, 25), (22, 31)], 4.2, p.cut)


def _hair_front(p: Pen) -> None:
    p.circle(24, 28, 15.5, p.soft)
    p.arc(24, 24, 15, 172, 368, 11)
    p.poly([(9, 22), (18, 30), (26.5, 20.5), (34, 28), (39, 20.5), (30, 12), (16, 12)])


def _hair_back(p: Pen) -> None:
    p.box(6, 5, 36, 39, 15)
    p.circle(24, 22, 11.5, p.soft)
    p.box(18.5, 31, 11, 9, 2, p.soft)


def _wave(p: Pen) -> None:
    p.line([(5, 24), (12.5, 11), (24, 37), (35.5, 11), (43, 24)], 6)


def _stick(p: Pen) -> None:
    p.turned(24, 24, 44, 9, -32, p.soft)
    p.turned(24, 24, 15, 20, -32)
    for across in (-3.4, 3.4):
        p.turned(24 + across * math.cos(math.radians(-32)), 24 + across * math.sin(math.radians(-32)), 1.8, 14, -32, p.cut)


def _back(p: Pen) -> None:
    # A trunk seen from behind: its shoulders, and the line down the middle of a back.
    p.box(9, 9, 30, 33, 10)
    p.line([(24, 15), (24, 36)], 3.2, p.cut)
    p.line([(15, 19), (19, 22)], 2.6, p.cut)
    p.line([(33, 19), (29, 22)], 2.6, p.cut)


def _plate(p: Pen) -> None:
    # A chest plate: its shoulders, its waist, and the line down the middle of it.
    p.poly([(8, 9), (18, 6), (24, 10), (30, 6), (40, 9), (37, 24), (34, 41), (14, 41), (11, 24)])
    p.line([(24, 14), (24, 37)], 3.0, p.cut)
    p.line([(13.5, 25), (34.5, 25)], 2.4, p.cut)


def _ring(p: Pen) -> None:
    # The line round a thing, and nothing of the thing.
    p.circle(24, 24, 18)
    p.hole(24, 24, 11)


def _foot(p: Pen) -> None:
    # A leg coming down into a boot: its heel, its sole and its round toe.
    p.box(12, 3, 13, 30, 6, p.soft)
    p.box(7, 25, 35, 17, 8.5)
    p.circle(15.5, 31, 9.5)


def _finger(p: Pen) -> None:
    p.box(13, 5, 11, 38, 5.5)
    p.line([(15.5, 20), (21.5, 20)], 2.2, p.cut)
    p.line([(15.5, 30.5), (21.5, 30.5)], 2.2, p.cut)


def _finger_more(p: Pen) -> None:
    _finger(p)
    p.box(33, 16.5, 5, 16, 1.5, p.light)
    p.box(27.5, 22, 16, 5, 1.5, p.light)


def _finger_less(p: Pen) -> None:
    _finger(p)
    p.box(27.5, 22, 16, 5, 1.5, p.light)


def _bolt(p: Pen) -> None:
    p.poly([(28, 3.5), (9, 27), (21, 27), (17, 44.5), (38.5, 19), (26, 19)])


def _door(p: Pen) -> None:
    p.box(7, 5, 24, 38, 3)
    p.box(11.5, 9.5, 15, 29, 1.5, p.cut)
    p.poly([(44.5, 24), (33, 14), (33, 20.5), (20, 20.5), (20, 27.5), (33, 27.5), (33, 34)], p.light)


def _spark(p: Pen) -> None:
    p.poly([(24, 3), (28.5, 19.5), (45, 24), (28.5, 28.5), (24, 45), (19.5, 28.5), (3, 24), (19.5, 19.5)])
    p.circle(38.5, 9.5, 3.2, p.light)
    p.circle(9.5, 38.5, 2.6, p.light)


ICONS: dict[str, tuple] = {
    "brush": (GLYPHS["draw"], DRAWING),
    "eraser": (_eraser, DRAWING),
    "bucket": (_bucket, DRAWING),
    "line": (_line, SHAPES),
    "box": (_box, SHAPES),
    "oval": (_oval, SHAPES),
    "polygon": (_polygon, SHAPES),
    "filled": (_filled, SHAPES),
    "undo": (_undo, EDITING),
    "trash": (_trash, DANGER),
    "tab_body": (_body, BODY),
    "tab_head": (_head, HEAD),
    "tab_face": (GLYPHS["mood"], FACE),
    "tab_hands": (_hand, HANDS),
    "mannequin": (_mannequin, HELPING),
    "measure": (_measure, MEASURING),
    "far_own": (_far_own, MEASURING),
    "far_same": (_far_same, MEASURING),
    "far_darker": (_far_darker, MEASURING),
    "symmetry": (_symmetry, MEASURING),
    "gear": (GLYPHS["scrap"], SETTING),
    "plus": (_plus, HELPING),
    "minus": (_minus, HELPING),
    "prev": (_prev, SETTING),
    "next": (_next, SETTING),
    "new": (_plus, HELPING),
    "save_all": (GLYPHS["save"], SHAPES),
    "leave": (_door, SETTING),
    "stand": (_stand, MOVING),
    "walk": (_walk, MOVING),
    "punch": (_punch, MOVING),
    "hammer": (GLYPHS["work"], MOVING),
    "turn": (_turn, MOVING),
    "guide": (_guide, SETTING),
    "thinner": (_thinner, SETTING),
    "thicker": (_thicker, SETTING),
    "reset": (_reset, SETTING),
    "spark": (_spark, HELPING),
    "place": (_place, FACE),
    "eye": (_eye, FACE),
    "brow": (_brow, FACE),
    "mouth": (_mouth, FACE),
    "eye_shut": (_eye_shut, FACE),
    "mouth_open": (_mouth_open, FACE),
    "mood": (_mood, MOVING),
    "talk": (_talk, MOVING),
    "nose": (_nose, FACE),
    "ear": (_ear, FACE),
    "hair": (_hair_front, FACE),
    "hair_back": (_hair_back, FACE),
    "hand_made": (_hand, HANDS),
    "foot_made": (_foot, HANDS),
    "line_color": (_ring, HANDS),
    "back_paper": (_back, BODY),
    "fitting": (_plate, BODY),
    "hand_open": (_held("open"), HANDS),
    "hand_relaxed": (_held("relaxed"), HANDS),
    "hand_grip": (_held("grip"), HANDS),
    "hand_fist": (_held("fist"), HANDS),
    "by_gesture": (_bolt, HANDS),
    "open_shut": (_wave, HANDS),
    "holding": (_stick, HANDS),
    "finger_more": (_finger_more, HANDS),
    "finger_less": (_finger_less, HANDS),
}

for _name, (_glyph, _hue) in ICONS.items():
    GLYPHS[f"studio:{_name}"] = _glyph
    HUES[f"studio:{_name}"] = _hue

_made: dict[tuple[str, int, bool, bool], pygame.Surface] = {}
# How much of itself a tile that cannot be pressed just now is shown at.
OFF_ALPHA = 70


def studio_tile(name: str, size: int, lit: bool = False, off: bool = False) -> pygame.Surface:
    """The tile of one of this screen's icons, a number of pixels across: lit while what it
    stands for is on, and faint while it cannot be pressed. Made once, and kept."""
    key = (name, size, lit, off)
    if key not in _made:
        picture = tile(f"studio:{name}", size, lit)
        if off:
            picture = picture.copy()
            picture.fill((255, 255, 255, OFF_ALPHA), special_flags=pygame.BLEND_RGBA_MULT)
        _made[key] = picture
    return _made[key]
