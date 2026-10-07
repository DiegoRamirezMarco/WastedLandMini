"""A doll for whoever nobody has drawn: a plain figure in their own colours, with a face.

The game's own bodies are small pixel art, which is not how anything else is shown on the window.
Until somebody is drawn they are shown as this instead: the figure every doll starts from, in the
colours their body wears, with thick dark lines round it as the rest of the game's pictures have,
and a head with hair, an eye and a mouth. It is cut at the joints and moved as any doll is.
"""

import math

import pygame

from graphics.body_renderer import BodySkin
from graphics.cartoon import LINE
from graphics.doll import HEAD_CANVAS, DollTemplate
from graphics.palette import Color
from graphics.ui_art import darker, lighter

# How many times over the head is drawn before it is brought down to its canvas.
DETAIL = 3
# The line round every part, as a share of the template's unit.
EDGE = 0.34
# How many times as thick as the slim figure of the guide its limbs are, and how many times
# as large its head: whoever has been drawn has a large head and a body with some weight to it.
# A shoe is all under the ankle, and so is the half of its example that is its own: thick enough
# to stand on the ground.
STOUT = {"upper_arm": 1.22, "forearm": 1.22, "hand": 1.22, "thigh": 1.25, "shin": 1.25, "foot": 1.6, "neck": 1.2}
HEAD = 1.3
# How pale a colour has to be to be skin and not hair, when the hair is looked for on a head.
SKULL = "skull"


def _middle(skin: BodySkin, cell: str) -> Color:
    sprite = skin.sprites[("side", cell, False)]
    return tuple(sprite.image.get_at(sprite.anchor))[:3]  # type: ignore[return-value]


def _strip(skin: BodySkin, cell: str, end: int) -> Color:
    return skin.strips[("side", cell)].colors[end]


def figure_colors(skin: BodySkin) -> dict[str, Color]:
    """The colour of each part of a plain figure, from what a body wears: shirt, skin, trousers, shoes."""
    colors = {"spine": _middle(skin, "torso"), SKULL: _middle(skin, "head"), "neck": _middle(skin, "head"), "hips": _strip(skin, "thigh", 0)}
    for side in ("_left", "_right"):
        colors[f"upper_arm{side}"] = _strip(skin, "upper_arm", 0)
        colors[f"forearm{side}"] = _strip(skin, "forearm", -1)
        colors[f"hand{side}"] = _strip(skin, "forearm", -1)
        colors[f"thigh{side}"] = _strip(skin, "thigh", 0)
        colors[f"shin{side}"] = _strip(skin, "thigh", 0)
        colors[f"foot{side}"] = _strip(skin, "shin", -1)
    return colors


def hair_color(skin: BodySkin) -> Color:
    """The colour of a body's hair: what is at the top of its head, seen from the front."""
    image = skin.sprites[("front", "head", False)].image
    face = _middle(skin, "head")
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            pixel = image.get_at((x, y))
            # Not the dark line round the head, and not the face.
            if pixel[3] and sum(pixel[:3]) > 90 and tuple(pixel)[:3] != face:
                return tuple(pixel)[:3]  # type: ignore[return-value]
    return darker(face, 0.6)


def _head(size: tuple[int, int], centre: tuple[float, float], radius: float, face: Color, hair: Color, edge: float) -> pygame.Surface:
    """A head seen from its side, looking right: hair over the top and down the back, an eye, a nose, a mouth."""
    k = DETAIL
    sheet = pygame.Surface((size[0] * k, size[1] * k), pygame.SRCALPHA)
    x, y, r, line = centre[0] * k, centre[1] * k, radius * k, max(2, round(edge * k))

    def ring(points: list[tuple[float, float]], color: Color) -> None:
        pygame.draw.polygon(sheet, color, points)
        pygame.draw.lines(sheet, LINE, True, points, line)

    # The nose, which the face is then drawn over the root of.
    pygame.draw.circle(sheet, LINE, (x + r * 0.98, y + r * 0.12), r * 0.2 + line / 2)
    pygame.draw.circle(sheet, face, (x + r * 0.98, y + r * 0.12), r * 0.2 - line / 2)
    pygame.draw.circle(sheet, face, (x, y), r)
    # An ear, and the hair: over the top, and down behind it.
    pygame.draw.circle(sheet, darker(face, 0.12), (x - r * 0.18, y + r * 0.14), r * 0.17)
    pygame.draw.circle(sheet, LINE, (x - r * 0.18, y + r * 0.14), r * 0.17, max(2, line // 2))
    cap = [(x + r * 1.03 * math.cos(math.radians(angle)), y + r * 1.03 * math.sin(math.radians(angle))) for angle in range(128, 326, 6)]
    brow = [
        (x + r * 0.42 + r * 0.9 * math.cos(math.radians(angle)), y + r * 0.5 + r * 0.9 * math.sin(math.radians(angle)))
        for angle in range(292, 196, -8)
    ]
    ring(cap + brow, hair)
    pygame.draw.lines(sheet, lighter(hair, 0.3), False, [(x - r * 0.5, y - r * 0.62), (x - r * 0.1, y - r * 0.84), (x + r * 0.3, y - r * 0.82)], max(2, line // 2))
    pygame.draw.circle(sheet, LINE, (x, y), r + line / 2, line)
    # An eye with a light in it, a brow over it, and a mouth.
    eye = pygame.Rect(0, 0, r * 0.19, r * 0.27)
    eye.center = (round(x + r * 0.5), round(y - r * 0.02))
    pygame.draw.ellipse(sheet, LINE, eye)
    pygame.draw.circle(sheet, (255, 255, 255), (eye.centerx + r * 0.03, eye.centery - r * 0.06), max(1, r * 0.045))
    pygame.draw.lines(sheet, LINE, False, [(x + r * 0.34, y - r * 0.26), (x + r * 0.66, y - r * 0.28)], max(2, line // 2))
    pygame.draw.lines(sheet, LINE, False, [(x + r * 0.4, y + r * 0.46), (x + r * 0.58, y + r * 0.52), (x + r * 0.74, y + r * 0.46)], max(2, line * 2 // 3))
    pygame.draw.circle(sheet, (*lighter((200, 90, 80), 0.2), 90), (x + r * 0.3, y + r * 0.28), r * 0.15)
    return pygame.transform.smoothscale(sheet, size)


def stand_in(template: DollTemplate, skin: BodySkin) -> dict[str, pygame.Surface]:
    """The drawings of a doll for a body nobody has drawn, by canvas, as the template lays its paper out."""
    colors = figure_colors(skin)
    edge = max(2, round(template.unit * EDGE))
    drawings = template.mannequin(colors, LINE, edge, STOUT)
    skull = template.parts[SKULL]
    size = template.canvases[HEAD_CANVAS]
    # As large as it is made, the head still has to stand on the neck and stay on its paper.
    radius = min(skull.radius * HEAD, size[0] / 2 - edge * 2 - skull.radius * 0.24, skull.end[1] - edge * 2)
    centre = (skull.end[0] - skull.radius * 0.1, skull.start[1] - radius * 0.86)
    drawings[HEAD_CANVAS] = _head(size, centre, radius, colors[SKULL], hair_color(skin), edge)
    return drawings
