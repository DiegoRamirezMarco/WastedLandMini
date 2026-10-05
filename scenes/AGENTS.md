# Scene Rules
- Scenes own presentation and input, never authoritative gameplay truth.
- Scenes may read simulation state.
- Player input must be translated into simulation commands/decisions rather than mutating deep resident fields directly.
- The global view handles overview; the interaction view handles important close-up moments.
