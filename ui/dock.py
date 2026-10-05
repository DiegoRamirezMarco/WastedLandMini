"""The strip under the map: two large faces, what is being said between them, and a column beside."""

from dataclasses import dataclass

import pygame

from graphics.face_renderer import FACE_SIZE, FaceRenderer
from graphics.font import BitmapFont
from graphics.palette import PALETTE
from ui.bubble import TAIL, draw_speech
from ui.dialogue_box import draw_dialogue_box
from ui.panel import draw_panel

FACE_SCALE = 2
PORTRAIT = (FACE_SIZE[0] * FACE_SCALE, FACE_SIZE[1] * FACE_SCALE)
GAP = 4
# Width of the column at the right end: advice to give, or what one feels for the other.
SIDE_WIDTH = 170
PLATE_HEIGHT = 13


@dataclass(frozen=True)
class DockAreas:
    left: pygame.Rect
    right: pygame.Rect
    # Between the two faces: what is said.
    speech: pygame.Rect
    side: pygame.Rect


def dock_areas(dock: pygame.Rect) -> DockAreas:
    top = dock.y + (dock.height - PORTRAIT[1]) // 2
    left = pygame.Rect(dock.x + GAP, top, *PORTRAIT)
    side = pygame.Rect(dock.right - GAP - SIDE_WIDTH, top, SIDE_WIDTH, PORTRAIT[1])
    right = pygame.Rect(side.left - GAP - PORTRAIT[0], top, *PORTRAIT)
    speech = pygame.Rect(left.right + GAP + TAIL, top + 6, right.left - left.right - (GAP + TAIL) * 2, PORTRAIT[1] - 30)
    return DockAreas(left, right, speech, side)


def draw_portrait(
    target: pygame.Surface, font: BitmapFont, faces: FaceRenderer, area: pygame.Rect, face_id: str, expression: str, name: str
) -> None:
    """A large face in a frame, with a name plate across the bottom of it."""
    draw_panel(target, area, fill="iron", border="stone")
    target.blit(pygame.transform.scale(faces.face(face_id, expression), area.size), area)
    pygame.draw.rect(target, PALETTE["stone"], area, 1)
    width = font.width(name) + 10
    plate = pygame.Rect(area.centerx - width // 2, area.bottom - PLATE_HEIGHT - 2, width, PLATE_HEIGHT)
    draw_panel(target, plate, fill="ink", border="stone")
    font.draw(target, name, (plate.x + 5, plate.y + 1), PALETTE["paper"])


def draw_scene(
    target: pygame.Surface,
    font: BitmapFont,
    faces: FaceRenderer,
    dock: pygame.Rect,
    left: tuple[str, str, str],
    right: tuple[str, str, str] | None,
    text: str,
    speaker: int = -1,
    narration: bool = False,
) -> DockAreas:
    """Draw the dock as a scene between two residents, or with one alone.

    `left` and `right` are a resident's ID, the face they wear and their name. `text` is what the
    one on the side `speaker` points at says, in a bubble, or what happened, in a plain box.
    Returns the areas of the dock, the last of which is left for the caller to fill.
    """
    draw_panel(target, dock, fill="shadow", border="iron")
    areas = dock_areas(dock)
    draw_portrait(target, font, faces, areas.left, *left)
    speech = areas.speech
    if right is not None:
        draw_portrait(target, font, faces, areas.right, *right)
    else:
        # Nobody across from them: what they say takes the room.
        speech = pygame.Rect(speech.x, speech.y, areas.right.right - speech.x, speech.height)
    if narration:
        draw_dialogue_box(target, font, speech, text)
    elif text:
        draw_speech(target, font, speech, text, towards=speaker if right is not None else -1, shout=text.endswith("!"))
    return areas
