"""A hand or a foot that is made, joined to the limb it hangs from: one line round the two.

What is made has a line all round it, and is laid over the end of a limb that was drawn. Left
at that, its line goes across the limb where the two meet, and it is a thing stuck on the end
of an arm. So wherever that line lies over the limb it hangs from, it is taken away, and the
made part is there what it is without a line: its own colour to its own edge. Its line stays
wherever there is no limb under it, so it still goes round whatever of it is wider than the
limb, and meets the edge of the limb on either side.

Only the limb it hangs from counts. A hand in front of a chest keeps its line all round.

And only well inside that limb: as far in from its edge as the line is thick. Where the edge
of the made part runs along the edge of the limb, as the heel of a boot does down the back of
a thick leg, its line is the line round the two of them, and stays. Taken away wherever there
was any limb under it, a boot on a thick leg had a line only round its toe.
"""

from collections.abc import Sequence

import pygame

# How solid a pixel of a limb must be for a line over it to be taken away, and how solid a
# pixel of a made part without its line for that pixel to be none of its line.
LIMB_FROM = 100
WHOLE_FROM = 250

# A pixel no lighter than this, red, green and blue added up, is taken to be of a line and not
# of what the line is round.
DARKEST_FILL = 215

Laid = tuple[pygame.Surface, float, float]
Color = tuple[int, int, int]


def colour_at(image: pygame.Surface, where: tuple[float, float], reach: int) -> Color | None:
    """The colour a drawing is for the most part round a spot on it, its lines apart: what a
    hand or a foot that is made is given, where nobody has picked it a colour, so that it is
    of a piece with the limb it is joined to. None where there is nothing drawn but line.
    """
    found = []
    width, height = image.get_size()
    middle = (round(where[0]), round(where[1]))
    for x in range(max(0, middle[0] - reach), min(width, middle[0] + reach + 1)):
        for y in range(max(0, middle[1] - reach), min(height, middle[1] + reach + 1)):
            red, green, blue, solid = image.get_at((x, y))
            if solid >= WHOLE_FROM and red + green + blue > DARKEST_FILL:
                found.append((red, green, blue))
    if not found:
        return None
    half = len(found) // 2
    return tuple(sorted(each[channel] for each in found)[half] for channel in range(3))


def half_width_at(image: pygame.Surface, start: tuple[float, float], end: tuple[float, float], back: float = 0.15) -> float:
    """How far to either side of the line through its joints a part of a drawing goes, a
    little way back from where it ends, in pixels: how wide a hand or a foot that is made
    begins, to be of a piece with it. Nothing for a part with nothing drawn there.
    """
    along = (end[0] - start[0], end[1] - start[1])
    long = (along[0] ** 2 + along[1] ** 2) ** 0.5
    if long <= 0:
        return 0.0
    across = (-along[1] / long, along[0] / long)
    spot = (end[0] - along[0] * back, end[1] - along[1] * back)
    width, height = image.get_size()
    reach = 0.0
    for way in (1.0, -1.0):
        far = 0.0
        while far < max(width, height):
            x, y = round(spot[0] + across[0] * far * way), round(spot[1] + across[1] * far * way)
            if not (0 <= x < width and 0 <= y < height) or image.get_at((x, y))[3] < LIMB_FROM:
                break
            far += 0.5
        reach += far
    return reach / 2.0


# What was drawn of a hand or a foot begins a little before the joint it hangs from, to either
# side of the limb: the top of a foot, the ball of a thumb. So for this share of its last part,
# back from that joint, a limb cut short is no wider than it is this far back, and a little over.
SLEEVE = 0.3
MEASURED_AT = 0.38
SLEEVE_WIDER = 1.12


def cut_short(image: pygame.Surface, before: tuple[float, float], joint: tuple[float, float], keep: float) -> pygame.Surface:
    """A picture of a limb with nothing on it past its last joint but a round end no wider than
    the limb, and nothing wider than the limb for a little way before that joint: whatever was
    drawn of the hand or the foot that is made instead is gone from it. `keep` is the least
    that end goes past the joint, in pixels.

    The end is round so that what is made can turn about the joint with nothing of the limb
    showing beside it. Cut straight across, a corner of a leg showed beside a boot whenever
    the leg leaned.
    """
    along = (joint[0] - before[0], joint[1] - before[1])
    long = (along[0] ** 2 + along[1] ** 2) ** 0.5
    if long <= 0:
        return image
    along = (along[0] / long, along[1] / long)
    across = (-along[1], along[0])
    far = float(sum(image.get_size()))
    half = max(keep, half_width_at(image, before, joint, MEASURED_AT) * SLEEVE_WIDER)
    kept = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    kept.fill((255, 255, 255, 255))
    # Nothing from where the sleeve begins on, but the sleeve and the round end of it.
    back = (joint[0] - along[0] * long * SLEEVE, joint[1] - along[1] * long * SLEEVE)
    sides = [(back[0] + across[0] * far * way, back[1] + across[1] * far * way) for way in (1.0, -1.0)]
    pygame.draw.polygon(kept, (0, 0, 0, 0), [*sides, *((x + along[0] * far, y + along[1] * far) for x, y in reversed(sides))])
    sleeve = [(back[0] + across[0] * half * way, back[1] + across[1] * half * way) for way in (1.0, -1.0)]
    pygame.draw.polygon(kept, (255, 255, 255, 255), [*sleeve, *((x + along[0] * long * SLEEVE, y + along[1] * long * SLEEVE) for x, y in reversed(sleeve))])
    pygame.draw.circle(kept, (255, 255, 255, 255), joint, half)
    short = image.copy()
    short.blit(kept, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return short


def _well_inside(mask: pygame.Mask, reach: int) -> pygame.Mask:
    """Whatever of a mask is `reach` pixels in from its edge, or further."""
    inside = mask
    slant = max(1, round(reach * 0.7))
    for across, down in ((reach, 0), (-reach, 0), (0, reach), (0, -reach), (slant, slant), (-slant, slant), (slant, -slant), (-slant, -slant)):
        inside = inside.overlap_mask(mask, (across, down))
    return inside


# What has been joined, by the pictures it was made of and where each lay from the made part:
# a body goes through the same few shapes over and over, and the same hand lies on the same
# arm the same way each time round. The pictures are kept with it, so that none is ever
# taken for another that came after it.
_JOINED: dict[tuple, tuple[tuple[pygame.Surface, ...], pygame.Surface]] = {}
KEPT_JOINED = 4096


def joined(
    lined: pygame.Surface, unlined: pygame.Surface, corner: tuple[float, float], under: Sequence[Laid], line: float = 2.0
) -> pygame.Surface:
    """A made part with its line gone wherever it lies well over the limb it hangs from.

    `lined` and `unlined` are the same picture with the line round it and without, `corner` is
    where its corner goes, and `under` the pictures of the limb with where theirs go, all from
    the same spot. `line` is how thick the line round it is, in pixels. It is `lined` itself if
    none of its line is over the limb.
    """
    at = (round(corner[0]), round(corner[1]))
    key = (id(lined), id(unlined), round(line), *((id(image), round(x) - at[0], round(y) - at[1]) for image, x, y in under))
    kept = _JOINED.get(key)
    if kept is None:
        if len(_JOINED) >= KEPT_JOINED:
            # Half of them go, the longest kept first.
            for old in list(_JOINED)[: KEPT_JOINED // 2]:
                del _JOINED[old]
        kept = _JOINED[key] = ((lined, unlined, *(image for image, _, _ in under)), _joined(lined, unlined, corner, under, line))
    return kept[1]


def _joined(
    lined: pygame.Surface, unlined: pygame.Surface, corner: tuple[float, float], under: Sequence[Laid], line: float
) -> pygame.Surface:
    box = lined.get_rect(topleft=(round(corner[0]), round(corner[1])))
    beneath = pygame.Mask(box.size)
    for image, x, y in under:
        place = image.get_rect(topleft=(round(x), round(y)))
        shared = place.clip(box)
        if shared.width and shared.height:
            there = pygame.mask.from_surface(image.subsurface(shared.move(-place.x, -place.y)), LIMB_FROM)
            beneath.draw(there, (shared.x - box.x, shared.y - box.y))
    beneath = _well_inside(beneath, max(1, round(line)))
    if not beneath.count():
        return lined
    # Its line is whatever of it there is that is not wholly there without one.
    line = pygame.mask.from_surface(lined, 0)
    line.erase(pygame.mask.from_surface(unlined, WHOLE_FROM), (0, 0))
    gone = line.overlap_mask(beneath, (0, 0))
    if not gone.count():
        return lined
    one = lined.copy()
    one.blit(gone.to_surface(setcolor=(0, 0, 0, 0), unsetcolor=(255, 255, 255, 255)), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    edge = unlined.copy()
    edge.blit(gone.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0)), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    one.blit(edge, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return one
