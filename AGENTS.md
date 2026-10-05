# Project Rules

## Core architecture
- The simulation layer must never depend on pygame.
- Pygame is limited to presentation, input, scene management and audio playback.
- Authoritative gameplay state lives in `simulation/` and `world/`.
- `main.py` only boots the application.
- Prefer small focused classes and composition over god objects.

## Data-driven design
- Items, foods, traits, personalities and event definitions should be data-driven.
- Built-in and custom content must use the same domain models and registries.
- Gameplay logic must never branch on display names.

## Resident agency
- Residents act autonomously.
- Player choices influence decisions but do not normally force outcomes.
- Relationships are directional: A -> B is independent from B -> A.
- Knowledge is local to residents. A character must not know something merely because the world state knows it.

## Major events
- Important irreversible events should create a visible intervention opportunity when reasonably possible.
- Events and player decisions are separate concepts.
- Important changes should emit domain events so UI/audio/history can react without owning gameplay logic.

## Determinism
- Simulation randomness must go through the project RNG service.
- Simulation time uses game time, never wall-clock time.
- Headless simulation must be possible without initializing pygame.

## Persistence
- Save stable IDs, not live object references.
- Never serialize pygame objects, callbacks, file handles or transient render state.
- New save fields require backwards-compatible defaults or migrations.

## Quality
- Add typing to public interfaces.
- Add regression tests for simulation bugs.
- Keep code and data schemas easy to mod.
