# Graphics Rules
- Rendering consumes state; it never owns it.
- Bodies are parts drawn over a skeleton from `skeleton/`; faces are generated modular faces or optional custom PNGs.
- A posed body is drawn once per frame of its clip and kept. Only a body that physics is moving is drawn joint by joint.
- Missing custom assets must have a safe fallback.
- Follow the style contract in `docs/visual-style.md`: draw on the internal canvas, take colours from `graphics/palette.py`, load images through `AssetStore`.
