# Illustrations

What is drawn inside the game (`dolls/`, `objects/`, `coins/` and the folders under `buildings/`) belongs to
a game being played, as a save does, and is not kept in the repository.

Pictures made outside the game go here. The game shows them at the resolution of the window, in
place of its own pixel art, and draws whatever is missing as it always has. Nothing in this folder
has to follow the style contract: any size, any colours. A picture is brought to the size it is
shown at, so keep its proportions close to the ones given.

| File | What it is | Shown at | Make it |
|---|---|---|---|
| `map/<map_id>.png` | The bare ground of the whole map, seen from straight above: no buildings, no objects, no people | 32 pixels a tile at the default zoom. `settlement` is 60×36 tiles, 1920×1152 | Landscape, about 5:3 |
| `buildings/<room_id>/inside.png`, `walls.png`, `roof.png`, `door.png` | Four aligned parts of one roofed building. The inside is empty. The roof is shown until the room is looked into; then the inside is below furniture and people, with walls and door in front | Twice the size `python -m tools.art.buildings` lists | All four use the same canvas and the guides in the `Edificios` editor (`F4`) |
| `buildings/<room_id>.png` | The older one-piece, roof-on building format. It remains supported when there are no four-part drawings for that room | Twice the size `python -m tools.art.buildings` lists | The proportions that command lists |
| `faces/<resident_id>/<expression>.png` | Head and shoulders. Expressions are `neutral`, `angry`, `sad`, `happy`. One picture alone does for all four; otherwise a missing one falls back on `neutral` | 256×256 in the dock, 128×128 in the panel | Square |
| `dolls/<resident_id>/body.png` and `head.png` | A resident drawn for their paper doll: the body with each part in its zone (trunk, hips, neck, arms, hands, legs, feet), and the head. The editor names every part, marks where each piece bends and shows a plain figure to go by. Beside them it keeps `build.json`, the doll's own measures: how long each part was made and where its limbs and head are joined on. The game writes these itself from its editor (`Dibujar` in the menu, or `F2`), and reads them back whatever made them | Cut into parts and laid over the skeleton, at any zoom | 400×384 and 192×192, over the guide the editor shows. A body of 384×384 or of 320×384, as the paper used to be, is still read and laid out as today's |
| `objects/<kind>.png` | A kind of furniture or loose object, seen as everything on the map is. One picture does for every object of that kind. The game writes these from its editor (`Arte` on something selected in Urbanismo), and reads them back whatever made them | 32 pixels a tile at the default zoom | 64 pixels a tile: as wide as the object's tiles and as tall as its sprite, so a bed is 64×128 |
| `coins/<currency_id>.png` | The coin of a currency the settlement has made: `credits` for the one the ready-made settlement trades with, `currency_2` and so on for those made in a game. The game writes these from its editor (`Dibujar moneda` in `Fondo`), and reads them back whatever made them | 22×22 in the bar, 44×44 in the board of the fund, 18×18 in a resident's panel | 96×96, with a clear background, and bold enough to read small |
| `ui/panel.png` | The skin of the bar, the menu, the panel and the dock: a border all round, an eighth of each side wide, and a plain dark middle that text can be read on. Without it they are the game's own plates | Stretched to each of them, border kept | Square |
| `ui/icons/<name>.png` | An icon of the interface, in place of the one the game draws. In the menu, tile and all: `people`, `work`, `study`, `stores`, `government`, `fund`, `events`, `map`, `save`, `urbanism`, `draw`, `buildings`, `voice`. In the bar on top: `sun`, `moon`, `people`, `food`, `water`, `energy`, `medicine`, `scrap`, `mood` for how spirits stand, `coin` for a currency nobody has drawn, and whatever a resource of a pack says it goes by. In the catalogue of Urbanismo, over what cannot be made yet: `lock` | 36×36 in the menu, 22×22 in the bar, 26×26 for the padlock | Square, with a clear background, and bold enough to read small |

Whatever is missing here the game draws itself, at the resolution of the window: the ground, the
buildings, every kind of object, the items, and a plain figure for whoever has no doll. A picture
of yours takes its place on the map. Inside a building it is the game's picture of an object that
is shown, since yours is drawn for the map, from above.

Furniture and loose objects nobody has drawn are the game's own art. A four-part building may be made one
piece at a time: any missing part falls back safely, and a building with no drawings looks exactly
as it did before.
