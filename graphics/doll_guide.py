"""What is traced over when a resident is drawn: every part in a zone of its own, the cuts between
them, and under it all a figure drawn as one might draw it, to take as a reference.

The figure is put together from what each part is said to wear in the template. It is only ever a
guide: nothing of it ends up in anybody's drawing unless they trace it.
"""

import math

import pygame

from graphics.doll import GUIDE_FAR, GUIDE_JOINT, GUIDE_MIDDLE, GUIDE_NEAR, DollTemplate, PartSpec
from graphics.palette import PALETTE

Point = tuple[float, float]
Color = tuple[int, int, int]

INK = PALETTE["ink"]
SKIN = PALETTE["skin_3"]
SHIRT = PALETTE["lamp"]
TROUSERS = PALETTE["teal"]
SHOE = PALETTE["rust_dark"]
HAIR = PALETTE["earth_dark"]
EYE = PALETTE["paper"]
# What each part of the figure wears, by the role its part has in the template.
ROLE_COLORS = {"skin": SKIN, "hand": SKIN, "sleeve": SKIN, "head": SKIN, "shirt": SHIRT, "waist": TROUSERS, "leg": TROUSERS, "shin": TROUSERS, "shoe": SHOE}
# How solid a zone is on the guide, out of 255: every other part of a limb a little more, to tell them apart.
ZONE_FILLS = (46, 78)
ZONE_EDGE = 2
# A cut is drawn as dashes this long, this far apart.
DASH = (7, 5)
CLEAR = (0, 0, 0, 0)


def side_tint(bone: str) -> Color:
    """The colour of a part on the guide: one for the near side of the body, one for the far, one for the middle."""
    return GUIDE_NEAR if bone.endswith("_right") else (GUIDE_FAR if bone.endswith("_left") else GUIDE_MIDDLE)


class _Frame:
    """A part as something to draw along: where it starts, which way it runs, and which way is across it."""

    def __init__(self, spec: PartSpec) -> None:
        dx, dy = spec.end[0] - spec.start[0], spec.end[1] - spec.start[1]
        self.length = math.hypot(dx, dy) or 1.0
        self.start, self.end, self.radius = spec.start, spec.end, spec.radius
        self.along = (dx / self.length, dy / self.length)
        # Across is the way the figure faces, to the right of the canvas; for a part lying along that way, down.
        across = (-self.along[1], self.along[0])
        if across[0] < -0.5 or (abs(across[0]) <= 0.5 and across[1] < 0):
            across = (-across[0], -across[1])
        self.across = across

    def at(self, along: float, across: float = 0.0) -> Point:
        """A point so many pixels along the part from its first joint, and so many to the side."""
        return (
            self.start[0] + self.along[0] * along + self.across[0] * across,
            self.start[1] + self.along[1] * along + self.across[1] * across,
        )


class _Sheet:
    """A canvas on which shapes are put down one over another, each with a dark line round it."""

    def __init__(self, size: tuple[int, int], line: int) -> None:
        self.size = size
        self.line = line
        self.surface = pygame.Surface(size, pygame.SRCALPHA)
        self._reach = [
            (dx, dy)
            for dx in range(-line, line + 1)
            for dy in range(-line, line + 1)
            if dx * dx + dy * dy <= line * line
        ]

    def blob(self) -> pygame.Surface:
        return pygame.Surface(self.size, pygame.SRCALPHA)

    def stamp(self, blob: pygame.Surface) -> None:
        """Put a shape down with its outline: whatever it covers of what was there is gone."""
        shape = pygame.mask.from_surface(blob)
        grown = pygame.Mask(self.size)
        for offset in self._reach:
            grown.draw(shape, offset)
        self.surface.blit(grown.to_surface(setcolor=(*INK, 255), unsetcolor=CLEAR), (0, 0))
        self.surface.blit(blob, (0, 0))

    def stroke(self, start: Point, end: Point) -> None:
        pygame.draw.line(self.surface, INK, start, end, self.line)


def _capsule(target: pygame.Surface, color: Color, start: Point, end: Point, radius: float) -> None:
    radius = max(1, round(radius))
    pygame.draw.line(target, color, start, end, radius * 2 + 1)
    pygame.draw.circle(target, color, start, radius)
    pygame.draw.circle(target, color, end, radius)


def _draw_part(sheet: _Sheet, spec: PartSpec, unit: int) -> None:
    """Draw what one part of the figure looks like, whole, without minding where it is cut."""
    frame = _Frame(spec)
    role, radius, length = spec.wears, spec.radius, frame.length
    color = ROLE_COLORS.get(role, GUIDE_MIDDLE)
    blob = sheet.blob()

    if role == "head":
        _draw_head(sheet, spec)
    elif role == "shirt":
        # A trunk from the waist up, a little wider at the shoulders, with a round neckline.
        shoulder = radius * 0.42
        pygame.draw.polygon(blob, color, [
            frame.at(0, -radius * 0.86), frame.at(0, radius * 0.86),
            frame.at(length - shoulder, radius), frame.at(length, radius - shoulder),
            frame.at(length, -radius + shoulder), frame.at(length - shoulder, -radius),
        ])
        for side in (-1, 1):
            pygame.draw.circle(blob, color, frame.at(length - shoulder, side * (radius - shoulder)), shoulder)
        sheet.stamp(blob)
        collar = sheet.blob()
        pygame.draw.circle(collar, SKIN, frame.at(length, 0), radius * 0.4)
        sheet.stamp(collar)
    elif role == "waist":
        pygame.draw.polygon(blob, color, [
            frame.at(0, -radius * 0.86), frame.at(0, radius * 0.86),
            frame.at(length + unit * 0.5, radius * 0.9), frame.at(length + unit * 0.5, -radius * 0.9),
        ])
        sheet.stamp(blob)
        # A belt, and the cord it is tied with.
        sheet.stroke(frame.at(unit * 0.45, -radius * 0.86), frame.at(unit * 0.45, radius * 0.86))
        sheet.stroke(frame.at(unit * 0.45, radius * 0.2), frame.at(unit * 1.2, radius * 0.12))
        sheet.stroke(frame.at(unit * 0.45, radius * 0.34), frame.at(unit * 1.1, radius * 0.4))
    elif role == "sleeve":
        _capsule(blob, SKIN, frame.start, frame.end, radius)
        sheet.stamp(blob)
        sleeve = sheet.blob()
        cuff, wide = length * 0.62, radius + unit * 0.14
        pygame.draw.polygon(sleeve, SHIRT, [frame.at(0, -wide), frame.at(0, wide), frame.at(cuff, wide), frame.at(cuff, -wide)])
        pygame.draw.circle(sleeve, SHIRT, frame.start, wide)
        sheet.stamp(sleeve)
    elif role == "hand":
        # A mitten with a thumb on the side it faces, and a line or two for fingers.
        palm = frame.at(length * 0.55)
        _capsule(blob, color, frame.start, palm, radius * 0.82)
        pygame.draw.circle(blob, color, frame.at(length * 0.62), radius)
        pygame.draw.circle(blob, color, frame.at(length * 0.3, radius * 1.05), radius * 0.48)
        sheet.stamp(blob)
        for across in (-radius * 0.3, radius * 0.25):
            sheet.stroke(frame.at(length * 0.72, across), frame.at(length * 0.62 + radius, across))
    elif role in ("leg", "shin"):
        top, bottom = (radius, radius * 0.9) if role == "leg" else (radius * 0.9, radius * 0.84)
        pygame.draw.polygon(blob, color, [
            frame.at(0, -top), frame.at(0, top), frame.at(length, bottom), frame.at(length, -bottom),
        ])
        if role == "leg":
            pygame.draw.circle(blob, color, frame.start, top)
        sheet.stamp(blob)
        if role == "shin":
            # The turn-up of a trouser leg.
            sheet.stroke(frame.at(length - unit * 0.35, -bottom), frame.at(length - unit * 0.35, bottom))
    elif role == "shoe":
        # A shoe under the ankle: a heel behind it, a rounded toe ahead, and a sole.
        heel, toe, height = -unit * 1.25, length + unit * 1.0, unit * 1.3
        pygame.draw.polygon(blob, color, [
            frame.at(heel, 0), frame.at(unit * 1.25, 0), frame.at(length + unit * 0.5, height * 0.38),
            frame.at(toe, height * 0.75), frame.at(toe, height), frame.at(heel, height),
        ])
        pygame.draw.circle(blob, color, frame.at(length + unit * 0.5, height * 0.68), height * 0.34)
        sheet.stamp(blob)
        sheet.stroke(frame.at(heel, height - unit * 0.28), frame.at(toe, height - unit * 0.28))
    else:
        _capsule(blob, color, frame.start, frame.end, radius)
        sheet.stamp(blob)


def _draw_head(sheet: _Sheet, spec: PartSpec) -> None:
    """A head seen from the side, facing right: hair over the top and down the back, an ear, a face."""
    (x, y), radius = spec.end, spec.radius

    def at(across: float, down: float) -> Point:
        return (x + across * radius, y + down * radius)

    head = sheet.blob()
    pygame.draw.circle(head, SKIN, (x, y), radius)
    pygame.draw.circle(head, SKIN, at(0.98, 0.16), radius * 0.15)
    pygame.draw.ellipse(head, SKIN, pygame.Rect(at(-0.05, 0.35), (radius * 0.95, radius * 0.72)))
    sheet.stamp(head)

    hair = sheet.blob()
    pygame.draw.circle(hair, HAIR, at(-0.04, -0.06), radius * 1.04)
    # The face is what the hair leaves bare: everything ahead of the ear and under the fringe.
    pygame.draw.polygon(hair, CLEAR, [at(-0.3, -0.42), at(0.3, -0.62), at(2, -0.5), at(2, 2), at(-0.62, 2), at(-0.62, 0.3)])
    sheet.stamp(hair)

    ear = sheet.blob()
    pygame.draw.ellipse(ear, SKIN, pygame.Rect(at(-0.46, -0.1), (radius * 0.3, radius * 0.42)))
    sheet.stamp(ear)
    eye = sheet.blob()
    pygame.draw.ellipse(eye, EYE, pygame.Rect(at(0.34, -0.3), (radius * 0.32, radius * 0.4)))
    sheet.stamp(eye)
    pygame.draw.circle(sheet.surface, INK, at(0.56, -0.1), max(2, radius * 0.08))
    sheet.stroke(at(0.28, -0.44), at(0.7, -0.5))
    sheet.stroke(at(0.5, 0.56), at(0.86, 0.5))


def reference(template: DollTemplate, canvas: str) -> pygame.Surface:
    """The example figure on one canvas: each part drawn whole, then kept only where it is its own."""
    size = template.canvases[canvas]
    figure = pygame.Surface(size, pygame.SRCALPHA)
    line = max(2, template.unit // 5)
    for bone, spec in template.parts.items():
        if spec.canvas != canvas:
            continue
        sheet = _Sheet(size, line)
        _draw_part(sheet, spec, template.unit)
        # Past a cut it would be on somebody else's part: a limb is drawn in one piece and cut straight.
        own = template.region(bone)
        for joint, _ in template.cuts(spec):
            if not template.sharing(spec, joint):
                # Where nothing else begins, as at a shoulder, the game rounds the end off by itself.
                pygame.draw.circle(own, (255, 255, 255, 255), joint, spec.radius + line * 2)
        sheet.surface.blit(own, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        figure.blit(sheet.surface, (0, 0))
    return figure


def _dashes(target: pygame.Surface, color: Color, start: Point, end: Point, width: int) -> None:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= 0:
        return
    step, covered = sum(DASH), 0.0
    while covered < length:
        stop = min(length, covered + DASH[0])
        pygame.draw.line(
            target,
            color,
            (start[0] + dx * covered / length, start[1] + dy * covered / length),
            (start[0] + dx * stop / length, start[1] + dy * stop / length),
            width,
        )
        covered += step


def cuts(template: DollTemplate, canvas: str) -> list[tuple[Point, Point]]:
    """Every line a drawing on this canvas is cut along, once each, as its two ends."""
    lines: dict[tuple[int, int, int, int], tuple[Point, Point]] = {}
    for spec in template.parts.values():
        if spec.canvas != canvas or spec.whole:
            continue
        for joint, keep in template.cuts(spec):
            reach = template.reach_at(spec, joint)
            across = (-keep[1], keep[0])
            ends = (
                (joint[0] - across[0] * reach, joint[1] - across[1] * reach),
                (joint[0] + across[0] * reach, joint[1] + across[1] * reach),
            )
            first, second = sorted(ends)
            # Both parts that meet at a joint are cut along the same line there; the longer one is drawn.
            key = (round(joint[0]), round(joint[1]), round(abs(across[0]) * 10), round(abs(across[1]) * 10))
            known = lines.get(key)
            if known is None or math.dist(*known) < math.dist(first, second):
                lines[key] = (first, second)
    return list(lines.values())


def build_guide(template: DollTemplate, canvas: str) -> pygame.Surface:
    """What is shown under a canvas to draw over.

    Each part has a zone of its own, tinted by the side of the body it is on and edged; the zones
    of a limb meet along dashed lines, which is where a drawing is cut and where the limb bends;
    there is a dot at every joint; and the example figure stands in the middle of it all.
    """
    size = template.canvases[canvas]
    guide = pygame.Surface(size, pygame.SRCALPHA)
    mine = [(bone, spec) for bone, spec in template.parts.items() if spec.canvas == canvas]
    regions = {bone: template.region(bone) for bone, spec in mine if not spec.whole}
    for index, (bone, region) in enumerate(regions.items()):
        zone = pygame.mask.from_surface(region)
        zone.to_surface(guide, setcolor=(*side_tint(bone), ZONE_FILLS[index % 2]), unsetcolor=None)
    guide.blit(reference(template, canvas), (0, 0))
    for bone, region in regions.items():
        edge = pygame.mask.from_surface(region).outline()
        if len(edge) > 2:
            pygame.draw.lines(guide, side_tint(bone), True, edge, ZONE_EDGE)
    for start, end in cuts(template, canvas):
        _dashes(guide, GUIDE_JOINT, start, end, ZONE_EDGE)
    radius = max(2, template.unit // 5)
    for _, spec in mine:
        for joint in (spec.start,) if spec.whole else (spec.start, spec.end):
            pygame.draw.circle(guide, INK, joint, radius + 1)
            pygame.draw.circle(guide, GUIDE_JOINT, joint, radius)
    return guide


def label_spots(template: DollTemplate, canvas: str) -> dict[str, pygame.Rect]:
    """Where each part of a canvas is, as the box round its zone, for whoever names the parts on the guide."""
    spots = {}
    for bone, spec in template.parts.items():
        if spec.canvas == canvas and not spec.whole:
            boxes = pygame.mask.from_surface(template.region(bone)).get_bounding_rects()
            if boxes:
                spots[bone] = boxes[0].unionall(boxes[1:])
    return spots
