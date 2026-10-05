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

Vector memory, TTS voice modulation, complex combat, romance and external exploration belong after this slice is stable.
