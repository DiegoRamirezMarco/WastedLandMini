# Graphics Rules
- Rendering consumes state; it never owns it.
- Support simple body rendering plus generated modular faces and optional custom PNG faces.
- Missing custom assets must have a safe fallback.
- Follow the style contract in `docs/visual-style.md`: draw on the internal canvas, take colours from `graphics/palette.py`, load images through `AssetStore`.
