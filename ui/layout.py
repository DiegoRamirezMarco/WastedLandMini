"""Where everything goes on the screen: a bar on top, a menu down the left, the map and a panel on the
right. Somebody asking for advice, while anybody is, is heard in a strip over the foot of the menu and the map."""

from dataclasses import dataclass

import pygame

TOP_HEIGHT = 26
SIDEBAR_WIDTH = 58
PANEL_WIDTH = 196
DOCK_HEIGHT = 136


@dataclass(frozen=True)
class Layout:
    # The bar across the top: day, hour, what the settlement has, and the controls.
    top: pygame.Rect
    # The menu down the left of the map.
    sidebar: pygame.Rect
    # The part of the canvas that shows the settlement.
    map: pygame.Rect
    # Over the foot of the menu and the map, and only while there is something to show in it:
    # somebody asking for advice. The rest of the time the map is seen there.
    dock: pygame.Rect
    # Down the right: whoever or whatever is selected.
    panel: pygame.Rect


def layout_for(size: tuple[int, int]) -> Layout:
    """Lay the screen out for a canvas of a given size."""
    width, height = size
    below = height - TOP_HEIGHT
    left = width - PANEL_WIDTH
    return Layout(
        top=pygame.Rect(0, 0, width, TOP_HEIGHT),
        sidebar=pygame.Rect(0, TOP_HEIGHT, SIDEBAR_WIDTH, below),
        map=pygame.Rect(SIDEBAR_WIDTH, TOP_HEIGHT, left - SIDEBAR_WIDTH, below),
        dock=pygame.Rect(0, height - DOCK_HEIGHT, left, DOCK_HEIGHT),
        panel=pygame.Rect(left, TOP_HEIGHT, PANEL_WIDTH, below),
    )
