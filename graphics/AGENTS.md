# Graphics Rules
- Rendering consumes state; it never owns it.
- Bodies are parts drawn over a skeleton from `skeleton/`; faces are generated modular faces or optional custom PNGs.
- A posed body is drawn once per frame of its clip and kept. Only a body that physics is moving is drawn joint by joint.
- A paper doll is laid over its skeleton part by part every frame. Its arms and legs are limbs of rubber (`graphics/hose.py`): the parts named together under `doll.hoses` are bent as one piece. Which parts those are is data; code never names one.
- Bending needs numpy and must stay optional: without it, or with a bone of the limb gone, the jointed parts are drawn. Bent limbs are kept and shown again; only so many new ones are bent in a frame.
- Missing custom assets must have a safe fallback.
- Follow the style contract in `docs/visual-style.md`: draw on the internal canvas, take colours from `graphics/palette.py`, load images through `AssetStore`.
