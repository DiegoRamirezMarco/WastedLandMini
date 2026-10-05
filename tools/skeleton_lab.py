"""A room to try the articulated bodies in, away from the game.

    python -m tools.skeleton_lab

Point at a body and:
    left click / right click   strike it towards the right / the left
    D                          knock it down; it gets up again
    K                          kill it
    1 2 3 4                    take off its left arm, right arm, left leg, right leg
    H                          take off its head
With nobody under the mouse these do it to everybody. Also:
    C      next clip (idle, walk, work...)      F      turn everybody round
    B      show the joints and bones            N      twenty more bodies
    R      start again                          Esc    quit

The corner says how many bodies there are, how many physics is moving, and what a frame costs.
"""

import random
import time
from dataclasses import dataclass

import pygame

from graphics.assets import ASSETS_DIR, AssetStore
from graphics.body_renderer import FRAME_ORIGIN, FRAME_SIZE, BodyRenderer
from graphics.font import FONT_SHEET, SHEET_SIZE, BitmapFont
from graphics.palette import PALETTE
from settings import FPS, INTERNAL_HEIGHT, INTERNAL_WIDTH, SCALE, SCREEN_HEIGHT, SCREEN_WIDTH
from skeleton.character import BodyPart, Character
from skeleton.plan import FACINGS, builtin_plan
from skeleton.rig import Skeleton

BODIES = ("marta", "raul", "lucia", "tomas", "ines", "vera", "paco", "nuria", "sergio")
START_COUNT = 9
MORE = 20
SPACING = 34
ROW_HEIGHT = 56
FIRST_ROW = 96
MARGIN = 40
BLOW = (190.0, -80.0)
PART_KEYS = {
    pygame.K_1: "arm_left",
    pygame.K_2: "arm_right",
    pygame.K_3: "leg_left",
    pygame.K_4: "leg_right",
    pygame.K_h: "head",
}
# Turns of each clip per second.
CLIP_RATE = 1.4


@dataclass
class Actor:
    body_id: str
    character: Character


class Lab:
    def __init__(self, canvas: pygame.Surface, seed: int = 1) -> None:
        self.canvas = canvas
        self.plan = builtin_plan()
        assets = AssetStore(ASSETS_DIR)
        self.renderer = BodyRenderer(assets, self.plan)
        self.font = BitmapFont(assets.image(FONT_SHEET, size=SHEET_SIZE))
        self.random = random.Random(seed)
        self.clips = list(self.plan.clips)
        self.clip = 0
        self.turned = 0
        self.show_bones = False
        self.time = 0.0
        self.pointer = (0, 0)
        # Milliseconds the last frame spent on physics and on drawing.
        self.cost = (0.0, 0.0)
        self.actors: list[Actor] = []
        self.parts: list[tuple[str, BodyPart]] = []
        self.reset()

    def reset(self) -> None:
        self.actors, self.parts = [], []
        self.add(START_COUNT)

    def add(self, count: int) -> None:
        per_row = (self.canvas.get_width() - MARGIN * 2) // SPACING + 1
        for _ in range(count):
            index = len(self.actors)
            actor = Actor(BODIES[index % len(BODIES)], Character(self.plan))
            actor.character.x = MARGIN + (index % per_row) * SPACING
            actor.character.y = FIRST_ROW + (index // per_row) * ROW_HEIGHT
            self.actors.append(actor)

    def _facing(self, index: int) -> str:
        facings = list(FACINGS)
        return facings[(index + self.turned) % len(facings)]

    def _under_pointer(self) -> list[Actor]:
        """Whoever the mouse is on, or everybody if it is on nobody."""
        for actor in reversed(self.actors):
            body = actor.character
            frame = pygame.Rect(body.x - FRAME_ORIGIN[0], body.y - FRAME_ORIGIN[1], *FRAME_SIZE)
            if frame.inflate(6, 4).collidepoint(self.pointer):
                return [actor]
        return list(self.actors)

    def strike(self, towards: float) -> None:
        for actor in self._under_pointer():
            actor.character.hit(BLOW[0] * towards, BLOW[1], self._struck(actor.character))

    def _struck(self, character: Character) -> str:
        """The joint nearest the mouse, so that a blow lands where it is aimed."""
        pose = character.pose()
        return min(pose, key=lambda joint: (pose[joint][0] - self.pointer[0]) ** 2 + (pose[joint][1] - self.pointer[1]) ** 2)

    def knock_down(self) -> None:
        for actor in self._under_pointer():
            side = self.random.choice((-1.0, 1.0))
            actor.character.knock_down(BLOW[0] * side, BLOW[1], self._struck(actor.character))

    def kill(self) -> None:
        for actor in self._under_pointer():
            if actor.character.alive:
                side = self.random.choice((-1.0, 1.0))
                actor.character.kill(BLOW[0] * side, BLOW[1], self._struck(actor.character))

    def sever(self, part: str) -> None:
        for actor in self._under_pointer():
            side = self.random.choice((-1.0, 1.0))
            piece = actor.character.sever(part, 70 * side, -150, self.random.uniform(-9, 9))
            if piece is not None:
                self.parts.append((actor.body_id, piece))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.pointer = (event.pos[0] // SCALE, event.pos[1] // SCALE)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            self.pointer = (event.pos[0] // SCALE, event.pos[1] // SCALE)
            self.strike(1.0 if event.button == 1 else -1.0)
        elif event.type != pygame.KEYDOWN:
            return
        elif event.key in PART_KEYS:
            self.sever(PART_KEYS[event.key])
        elif event.key == pygame.K_d:
            self.knock_down()
        elif event.key == pygame.K_k:
            self.kill()
        elif event.key == pygame.K_c:
            self.clip = (self.clip + 1) % len(self.clips)
        elif event.key == pygame.K_f:
            self.turned += 1
        elif event.key == pygame.K_b:
            self.show_bones = not self.show_bones
        elif event.key == pygame.K_n:
            self.add(MORE)
        elif event.key == pygame.K_r:
            self.reset()

    def awake(self) -> int:
        """How many bodies and parts physics is moving right now."""
        return sum(1 for actor in self.actors if not actor.character.at_rest) + sum(
            1 for _, part in self.parts if not part.at_rest
        )

    def update(self, seconds: float) -> None:
        started = time.perf_counter()
        self.time += seconds
        for actor in self.actors:
            actor.character.update(seconds)
        for _, part in self.parts:
            part.update(seconds)
        self.cost = ((time.perf_counter() - started) * 1000, self.cost[1])

    def render(self) -> None:
        started = time.perf_counter()
        self.canvas.fill(PALETTE["earth"])
        clip = self.clips[self.clip]
        for index, actor in enumerate(self.actors):
            body = actor.character
            facing = self._facing(index)
            frames = self.renderer.frames(clip, facing)
            frame = int(self.time * CLIP_RATE * frames) % frames
            if body.alive:
                body.stand(body.x, body.y, facing, clip, frame / frames)
            if body.skeleton is not None:
                self.renderer.draw_limp(self.canvas, body.skeleton, actor.body_id)
                self._bones(body.skeleton)
            else:
                picture, origin = self.renderer.frame(actor.body_id, facing, clip, frame, tuple(body.lost))
                self.canvas.blit(picture, (body.x - origin[0], body.y - origin[1]))
        for body_id, part in self.parts:
            self.renderer.draw_limp(self.canvas, part.skeleton, body_id)
            self._bones(part.skeleton)
        lines = (
            f"{len(self.actors)} cuerpos, {len(self.parts)} partes sueltas, {self.awake()} con física",
            f"física {self.cost[0]:.2f} ms   dibujo {self.cost[1]:.2f} ms   clip: {clip}",
            "clic golpea   D derriba   K mata   1-4 H corta   C clip   F gira   B huesos   N más   R reinicia",
        )
        for row, line in enumerate(lines):
            self.font.draw(self.canvas, line, (6, 6 + row * 12), PALETTE["paper"])
        self.cost = (self.cost[0], (time.perf_counter() - started) * 1000)

    def _bones(self, skeleton: Skeleton) -> None:
        if not self.show_bones:
            return
        for bone in skeleton.bones.values():
            pygame.draw.line(self.canvas, PALETTE["glow"], (bone.a.x, bone.a.y), (bone.b.x, bone.b.y))
        for joint in skeleton.joints.values():
            self.canvas.set_at((round(joint.x), round(joint.y)), PALETTE["ember"])


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Wasteland Minis: cuerpos articulados")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    canvas = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
    lab = Lab(canvas)
    clock = pygame.time.Clock()
    running = True
    while running:
        seconds = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            lab.handle_event(event)
        lab.update(seconds)
        lab.render()
        pygame.transform.scale(canvas, screen.get_size(), screen)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
