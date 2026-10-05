# Illustrations

Pictures made outside the game go here. The game shows them at the resolution of the window, in
place of its own pixel art, and draws whatever is missing as it always has. Nothing in this folder
has to follow the style contract: any size, any colours. A picture is brought to the size it is
shown at, so keep its proportions close to the ones given.

| File | What it is | Shown at | Make it |
|---|---|---|---|
| `map/<map_id>.png` | The bare ground of the whole map, seen from straight above: no buildings, no objects, no people | 32 pixels a tile at the default zoom. `settlement` is 60×36 tiles, 1920×1152 | Landscape, about 5:3 |
| `buildings/<room_id>.png` | A roofed building with its roof on, seen from the open ground in front: roof at the top, front wall with the door along the bottom, filling the picture from edge to edge. Clear corners are fine: the ground shows through | Twice the size `python -m tools.art.buildings` lists | The proportions that command lists |
| `faces/<resident_id>/<expression>.png` | Head and shoulders. Expressions are `neutral`, `angry`, `sad`, `happy`. One picture alone does for all four; otherwise a missing one falls back on `neutral` | 256×256 in the dock, 128×128 in the panel | Square |
| `dolls/<resident_id>/body.png` and `head.png` | A resident drawn for their paper doll: the body with each part in its zone (trunk, hips, neck, arms, hands, legs, feet), and the head. The game writes these itself from its editor (`Dibujar` in the menu, or `F2`), and reads them back whatever made them | Cut into parts and laid over the skeleton, at any zoom | 320×384 and 192×192, over the guide the editor shows |
| `ui/panel.png` | The skin of the bar, the menu, the panel and the dock: a border all round, an eighth of each side wide, and a plain dark middle that text can be read on | Stretched to each of them, border kept | Square |

What stands on the ground (fences, walls, floors, furniture, residents) is still the game's own
art, drawn over the illustrated ground.
