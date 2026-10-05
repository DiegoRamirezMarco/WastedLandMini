# Tools Rules
- Tools are development helpers. The game and the simulation never import from `tools/`.
- Art generators only use colours from `graphics/palette.py` and follow `docs/visual-style.md`.
- A generator never overwrites an existing PNG.
- Randomness in a generator must be seeded so the output is reproducible.
