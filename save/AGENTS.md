# Persistence Rules
- Persistence is infrastructure; simulation objects do not write themselves to disk.
- Save stable IDs and plain serializable data.
- Never serialize pygame surfaces, callbacks or live references.
- Missing custom content must not make saves unloadable; use placeholders/fallbacks.
