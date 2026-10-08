"""A doll for whoever nobody has drawn: the plain figure every doll starts from, in a colour of their own.

The game's own bodies are small pixel art, which is not how anything else is shown on the window.
Until somebody is drawn they are shown as this instead: an artist's figure with no clothes and no
face, in the colour of what their body wears, with thick dark lines round it as the rest of the
game's pictures have. It is cut at the joints and moved as any doll is, and it makes nobody out
to be anything: who they are is for whoever draws them to say.
"""

import pygame

from graphics.body_renderer import BodySkin
from graphics.cartoon import LINE
from graphics.doll import DollTemplate
from graphics.mannequin import figures, tones_of
from graphics.palette import Color
from graphics.ui_art import lighter

# The line round the figure, as a share of the template's unit.
EDGE = 0.34
# A colour darker than this, red, green and blue added up, is made lighter by this much: the
# line round the figure and the shade on it have to show.
DARKEST = 200
LIGHTER = 0.3


def figure_color(skin: BodySkin) -> Color:
    """The colour of the figure of a body: that of what it wears on its trunk, seen from the side."""
    sprite = skin.sprites[("side", "torso", False)]
    color: Color = tuple(sprite.image.get_at(sprite.anchor))[:3]  # type: ignore[assignment]
    return lighter(color, LIGHTER) if sum(color) < DARKEST else color


def stand_in(template: DollTemplate, skin: BodySkin) -> dict[str, pygame.Surface]:
    """The drawings of a doll for a body nobody has drawn, by canvas, as the template lays its paper out."""
    return figures(template, tones_of(figure_color(skin), LINE), max(2, round(template.unit * EDGE)))
