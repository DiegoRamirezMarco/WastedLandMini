"""Panel for dealing with whoever has stopped by the gate to trade: what they bring and ask for
it, what the settlement has that is nobody's and what they give for that, and the deal itself."""

from collections.abc import Mapping
from dataclasses import dataclass

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.item_icons import ICON_SIZE, ItemIcons
from graphics.palette import PALETTE, Color
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.panel import draw_item, draw_panel

PANEL_WIDTH = 372
PADDING = 6
BAND = LINE_HEIGHT + PADDING + 1
GUTTER = 10
ROW_HEIGHT = LINE_HEIGHT * 2 + 2
# The side of the deal a thing is on: bought from whoever is here, or sold to them.
BUY, SELL = "buy", "sell"
BRINGS_TITLE = "Trae"
HOLDS_TITLE = "Tiene el asentamiento"
NOTHING_BROUGHT = "No le queda nada"
NOTHING_HELD = "Nada que le interese"
DEAL_LABEL = "Cerrar trato"
DRAW_LABEL = "Dibujarle"
CART_LABEL = "Dibujar carro"
NOTHING_CHOSEN = "Elige con + lo que comprar y lo que vender."
BARTER_NOTE = "A trueque: lo que se le da ha de valer lo que se le pide."
DEAL_INTENT = ("trade_deal",)
DRAW_INTENT = ("trade_draw",)
CART_INTENT = ("trade_cart",)


def step_intent(side: str, item_id: str, by: int) -> tuple[str, str, str, int]:
    return ("trade_step", side, item_id, by)


@dataclass(frozen=True)
class GoodsRow:
    """One kind of thing on one side of the deal."""

    side: str
    item_id: str
    name: str
    # How many there are to be had, what one goes for, and how many are in the deal so far.
    units: int
    price: int
    chosen: int


def goods_rows(
    world: SimulationWorld, buy: Mapping[str, int], sell: Mapping[str, int]
) -> tuple[list[GoodsRow], list[GoodsRow]]:
    """What whoever is here brings, and what the settlement has that they would give something for."""
    merchant = world.merchant
    if merchant is None:
        return [], []
    resolve = world.registries.items.resolve
    brought = [
        GoodsRow(BUY, item_id, resolve(item_id).name, units, world.merchants.asks(world, item_id), min(units, buy.get(item_id, 0)))
        for item_id, units in merchant.goods.items()
    ]
    held = [
        GoodsRow(SELL, item_id, resolve(item_id).name, units, world.merchants.gives(world, item_id), min(units, sell.get(item_id, 0)))
        for item_id, units in world.fund.goods(world).items()
        if world.merchants.gives(world, item_id) > 0
    ]
    return sorted(brought, key=lambda row: row.name), sorted(held, key=lambda row: row.name)


def chosen(rows: list[GoodsRow]) -> dict[str, int]:
    """What of one side is in the deal, as units by item ID."""
    return {row.item_id: row.chosen for row in rows if row.chosen > 0}


def title(world: SimulationWorld) -> str:
    merchant, definition = world.merchant, world.merchants.definition(world)
    if merchant is None or definition is None:
        return ""
    who = definition.keeper_name or definition.name.capitalize()
    hour, minute = merchant.leaves_at // 60 % 24, merchant.leaves_at % 60
    return f"{who} · se queda hasta las {hour:02d}:{minute:02d}"


def purses(world: SimulationWorld) -> str:
    """What each side has to pay with, or that nothing is paid."""
    coin, merchant = world.fund.currency(world), world.merchant
    if coin is None or merchant is None:
        return BARTER_NOTE
    return f"Fondo: {coin.amount(world.trading.fund)} · Lleva encima: {coin.amount(merchant.purse)}"


def balance(world: SimulationWorld, brought: list[GoodsRow], held: list[GoodsRow]) -> tuple[str, str]:
    """How the deal chosen so far comes out, and the colour to say it in."""
    if not chosen(brought) and not chosen(held):
        return NOTHING_CHOSEN, "dust"
    owed = sum(row.chosen * row.price for row in brought)
    earned = sum(world.fund.worth_of_goods(world, row.item_id, row.chosen, row.price) for row in held)
    coin = world.fund.currency(world)
    if coin is None:
        short = earned < owed
        return f"Das por valor de {earned} y pides por valor de {owed}" + (": no llega" if short else ""), "ember" if short else "lichen"
    if owed > earned:
        short = owed - earned > world.trading.fund
        return f"El fondo paga {coin.amount(owed - earned)}" + (": no alcanza" if short else ""), "ember" if short else "lamp"
    if earned > owed:
        short = earned - owed > (world.merchant.purse if world.merchant is not None else 0)
        return f"El fondo cobra {coin.amount(earned - owed)}" + (": no lleva tanto" if short else ""), "ember" if short else "lichen"
    return "Sale a la par", "lichen"


def _columns(rect: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect]:
    width = (rect.width - PADDING * 2 - GUTTER) // 2
    top = rect.y + BAND + 3 + LINE_HEIGHT + 3
    return (
        pygame.Rect(rect.x + PADDING, top, width, 0),
        pygame.Rect(rect.x + PADDING + width + GUTTER, top, width, 0),
    )


def trade_board_height(world: SimulationWorld) -> int:
    brought, held = goods_rows(world, {}, {})
    rows = max(1, len(brought), len(held))
    return BAND + 3 + LINE_HEIGHT + 3 + LINE_HEIGHT + 1 + rows * ROW_HEIGHT + 4 + BUTTON_HEIGHT + 4 + BUTTON_HEIGHT + PADDING


def _floor(rect: pygame.Rect) -> int:
    """Where the rows of things stop, to leave room for how the deal comes out and its buttons."""
    return rect.bottom - PADDING - BUTTON_HEIGHT - 4 - BUTTON_HEIGHT - 4


def trade_buttons(
    font: BitmapFont,
    rect: pygame.Rect,
    world: SimulationWorld,
    buy: Mapping[str, int],
    sell: Mapping[str, int],
    drawable: bool = False,
) -> list[Button]:
    """A way to take one more or one fewer of each thing, to close the deal, and to draw whoever it is."""
    if world.merchant is None:
        return []
    buttons: list[Button] = []
    floor = _floor(rect)
    for column, rows in zip(_columns(rect), goods_rows(world, buy, sell)):
        y = column.y + LINE_HEIGHT + 1
        for row in rows:
            if y + ROW_HEIGHT > floor:
                break
            more = Button.at(font, 0, y + (ROW_HEIGHT - BUTTON_HEIGHT) // 2, "+", step_intent(row.side, row.item_id, 1))
            more.rect.right = column.right
            fewer = Button.at(font, 0, more.rect.y, "-", step_intent(row.side, row.item_id, -1))
            fewer.rect.right = more.rect.left - 18
            buttons += [fewer, more]
            y += ROW_HEIGHT
    deal = Button.at(font, 0, rect.bottom - PADDING - BUTTON_HEIGHT * 2 - 4, DEAL_LABEL, DEAL_INTENT)
    deal.rect.right = rect.right - PADDING
    buttons.append(deal)
    definition = world.merchants.definition(world)
    if drawable and definition is not None:
        x, y = rect.x + PADDING, rect.bottom - PADDING - BUTTON_HEIGHT
        if definition.keeper_id:
            draw = Button.at(font, x, y, DRAW_LABEL, DRAW_INTENT)
            buttons.append(draw)
            x = draw.rect.right + 4
        if world.registries.interactables.find(definition.cart or "") is not None:
            buttons.append(Button.at(font, x, y, CART_LABEL, CART_INTENT))
    return buttons


def draw_trade_board(
    target: pygame.Surface,
    font: BitmapFont,
    icons: ItemIcons,
    rect: pygame.Rect,
    world: SimulationWorld,
    buy: Mapping[str, int],
    sell: Mapping[str, int],
    drawable: bool = False,
    band_color: Color | None = None,
) -> None:
    draw_panel(target, rect, band=BAND, band_color=band_color)
    x, width = rect.x + PADDING, rect.width - PADDING * 2
    font.draw(target, font.truncate(title(world), width), (x, rect.y + PADDING - 1), PALETTE["paper"])
    font.draw(target, font.truncate(purses(world), width), (x, rect.y + BAND + 3), PALETTE["sand"])
    brought, held = goods_rows(world, buy, sell)
    buttons = {button.intent: button for button in trade_buttons(font, rect, world, buy, sell, drawable)}
    floor = _floor(rect)
    coin = world.fund.currency(world)
    sides = ((BRINGS_TITLE, NOTHING_BROUGHT, brought), (HOLDS_TITLE, NOTHING_HELD, held))
    for column, (heading, nothing, rows) in zip(_columns(rect), sides):
        font.draw(target, heading, column.topleft, PALETTE["lamp"])
        y = column.y + LINE_HEIGHT + 1
        if not rows:
            font.draw(target, nothing, (column.x, y), PALETTE["stone"])
        for row in rows:
            more, fewer = buttons.get(step_intent(row.side, row.item_id, 1)), buttons.get(step_intent(row.side, row.item_id, -1))
            if more is None or fewer is None:
                break
            draw_item(target, icons, row.item_id, pygame.Rect(column.x, y + (ROW_HEIGHT - ICON_SIZE[1]) // 2, *ICON_SIZE))
            left = column.x + ICON_SIZE[0] + 3
            room = fewer.rect.left - 3 - left
            font.draw(target, font.truncate(row.name, room), (left, y), PALETTE["paper" if row.chosen else "bone"])
            each = coin.amount(row.price) if coin is not None else f"vale {row.price}"
            font.draw(target, font.truncate(f"x{row.units} · {each}", room), (left, y + LINE_HEIGHT), PALETTE["stone"])
            fewer.draw(target, font)
            more.draw(target, font)
            count = str(row.chosen)
            middle = (fewer.rect.right + more.rect.left) // 2
            font.draw(target, count, (middle - font.width(count) // 2, more.rect.y + 1), PALETTE["glow" if row.chosen else "iron"])
            y += ROW_HEIGHT
    deal = buttons.get(DEAL_INTENT)
    text, color = balance(world, brought, held)
    if deal is not None:
        deal.draw(target, font, active=bool(chosen(brought) or chosen(held)))
        font.draw(target, font.truncate(text, deal.rect.left - 6 - x), (x, deal.rect.y + 1), PALETTE[color])
    for intent in (DRAW_INTENT, CART_INTENT):
        if intent in buttons:
            buttons[intent].draw(target, font)
