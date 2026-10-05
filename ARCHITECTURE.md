# Architecture

The project is split into a pure simulation core and a Pygame presentation shell.

```text
Player input
    -> scenes / UI
    -> commands / decisions
    -> simulation
    -> domain events
    -> scenes / audio / history / save
```

## Boundaries

```text
simulation  -X-> pygame
world       -X-> pygame
scenes       -> pygame
scenes       -> simulation public APIs
skeleton    -X-> pygame, simulation
graphics     -> skeleton
save         -> serializable simulation state
custom data  -> registries -> domain definitions
```

## Initial vertical slice

1. A top-down, open-air settlement: shacks and premises to walk into, and residents with jobs.
2. Three residents with needs and autonomous actions.
3. Directional relationships.
4. Small conversations and arguments.
5. `!` notifications for intervention candidates.
6. A close interaction scene for important moments.
7. Items with ownership, trade and theft hooks.
8. JSON save/load.
9. Custom item and food folders.

## Bodies

Which limbs a resident has lost is gameplay, so it lives in the simulation and is saved. How a
body stands, reels and falls is presentation: `skeleton/` holds the joints, bones, poses and
physics in pure Python, `graphics/body_renderer.py` draws parts over the bones, and
`scenes/body_stage.py` keeps a body for each resident and moves them as domain events say. That
runs on real time with randomness of its own, and none of it is saved.

Vector memory, TTS voice modulation, complex combat, romance and external exploration belong after this slice is stable.
