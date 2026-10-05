"""Generate the starter art, sound effects and music.

    python -m tools.make_art            write missing files into assets/ and custom_content/
    python -m tools.make_art --out DIR  write the assets into another directory, e.g. to preview changes

A file that already exists is kept, so anything edited by hand is never overwritten. To regenerate
one, delete it first.
"""

import argparse
from collections.abc import Sequence
from pathlib import Path

import pygame

from graphics.assets import ASSETS_DIR
from tools.art import faces, font, items, music, objects, residents, sounds, tiles, ui, workplaces

CUSTOM_CONTENT_DIR = ASSETS_DIR.parent / "custom_content"
Asset = pygame.Surface | bytes


def build_all() -> dict[str, Asset]:
    """Return every generated file keyed by its path relative to `assets/`. Images are surfaces."""
    return {
        **tiles.build(), **objects.build(), **workplaces.build(), **residents.build(),
        **font.build(), **ui.build(), **faces.build(), **items.build(), **sounds.build(), **music.build(),
    }


def build_custom() -> dict[str, Asset]:
    """Generated files for the example content packs, relative to `custom_content/`."""
    return dict(items.build_custom())


def write_missing(files: dict[str, Asset], root: Path) -> None:
    for relative_path, asset in sorted(files.items()):
        path = root / relative_path
        if path.exists():
            print(f"kept   {relative_path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(asset, bytes):
            path.write_bytes(asset)
        else:
            pygame.image.save(asset, str(path))
        print(f"wrote  {relative_path}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate the starter art and sound effects.")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    write_missing(build_all(), args.out or ASSETS_DIR)
    if args.out is None:
        write_missing(build_custom(), CUSTOM_CONTENT_DIR)


if __name__ == "__main__":
    main()
