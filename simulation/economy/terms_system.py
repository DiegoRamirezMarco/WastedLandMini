"""How the settlement settles what it trades with: barter, or a currency the player has made.

It is the residents who settle it. The player makes the currency, puts the change to them and
says what they think, and each resident answers for themselves: more for it than against, and
it is done. It can be changed back the same way, in the middle of a game.
"""

from typing import TYPE_CHECKING

from simulation.economy.terms import Currency, TradeResult, TradingState, singular_of, tidy_currency_name
from simulation.events.event import DomainEvent
from simulation.politics.proposal import ADOPT_CURRENCY, RETURN_TO_BARTER
from simulation.residents.resident import Resident

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

CURRENCY_PROPOSAL = "currency_proposal"
BARTER_PROPOSAL = "barter_proposal"
# What a resident who has had enough of how things are traded makes up their mind about.
CURRENCY_RAISED = "currency_raised"
BARTER_RAISED = "barter_raised"
# What an outcome of those may be: putting it to everyone that they trade this way.
RAISES = ("currency", "barter")
NAMED_IMPORTANCE = 30
ADVICE = "encourage"
CHANGED_IMPORTANCE = 60
KEPT_IMPORTANCE = 40
# ID of the currency a settlement that was already running has: the credits it always had.
CREDITS_ID = "credits"
ASKED_RECENTLY = "asked_recently"
NOBODY_HOME = "nobody_home"
OBSTACLES = {
    ASKED_RECENTLY: "Se les preguntó hace poco con qué comerciar",
    NOBODY_HOME: "No hay nadie a quien preguntárselo",
}


class TermsSystem:
    def settle_on_credits(self, world: "SimulationWorld") -> None:
        """Have a settlement that is already running trade with the credits such a one always had.

        Its fund starts with what a currency just taken up would have put in it.
        """
        economy = world.registries.economy
        world.trading = TradingState(
            currency=Currency(CREDITS_ID, economy.credits_name, economy.credits_singular),
            in_use=True,
            fund=economy.fund_per_resident * len(world.residents),
            currency_count=1,
        )

    def obstacle(self, world: "SimulationWorld") -> str | None:
        """What stands in the way of asking the residents how they would trade, as a short code. None if nothing does."""
        if not self._asked(world):
            return NOBODY_HOME
        asked_on = world.trading.asked_on
        if asked_on is not None and world.clock.day - asked_on < world.registries.economy.trade_ask_days:
            return ASKED_RECENTLY
        return None

    def propose_currency(
        self, world: "SimulationWorld", name: str, singular: str | None = None, option_id: str | None = ADVICE
    ) -> TradeResult:
        """Put it to the residents that they trade with a currency of this name, made by the player.

        If they take it up, prices, wages and the fund are counted in it from then on. The first
        currency a settlement takes up puts something in every pocket and in the fund. One that
        comes after another takes over what was held in the one before.

        A settlement that has a government decides it as it decides anything: it becomes a
        proposal, and the result says whether one was laid before those who decide.
        """
        trading = world.trading
        name = tidy_currency_name(name)
        if not name:
            return TradeResult(False, "Una moneda tiene que llamarse de alguna manera")
        if trading.in_use and trading.currency is not None:
            return TradeResult(False, f"Ya se comercia con {trading.currency.name}")
        if world.government.kind is not None:
            raised = world.politics.voting.propose(
                world, ADOPT_CURRENCY, params={"name": name, "singular": tidy_currency_name(singular or "")}
            )
            return TradeResult(raised.ok, raised.message)
        error = self.obstacle(world)
        if error is not None:
            return TradeResult(False, OBSTACLES[error])
        said = self._ask(world, CURRENCY_PROPOSAL, f"comerciar con {name}", option_id)
        if said is None:
            return TradeResult(False, "No hay manera de preguntárselo")
        yes, no = said
        if yes <= no:
            return self._kept(world, f"El asentamiento sigue con el trueque: {yes} por comerciar con {name}, {no} en contra")
        return self.adopt(world, name, singular, f": {yes} a favor, {no} en contra")

    def adopt(self, world: "SimulationWorld", name: str, singular: str | None = None, how: str = "") -> TradeResult:
        """Have the settlement trade with a currency of this name from now on. `how` is what
        there is to add about how it was settled."""
        trading = world.trading
        name = tidy_currency_name(name)
        if not name:
            return TradeResult(False, "Una moneda tiene que llamarse de alguna manera")
        first = trading.currency is None
        if first or trading.currency.name != name:
            trading.currency_count += 1
            trading.currency = Currency(
                f"currency_{trading.currency_count}", name, tidy_currency_name(singular or "") or singular_of(name)
            )
        trading.in_use = True
        if first:
            self._issue(world)
        return self._changed(world, f"El asentamiento empieza a comerciar con {name}{how}")

    def revert(self, world: "SimulationWorld", how: str = "") -> TradeResult:
        """Have the settlement go back to barter from now on."""
        world.trading.in_use = False
        return self._changed(world, f"El asentamiento vuelve al trueque{how}")

    def propose_barter(self, world: "SimulationWorld", option_id: str | None = ADVICE) -> TradeResult:
        """Put it to the residents that they go back to barter. What anybody holds in coin counts
        for nothing meanwhile, and is there if the settlement takes a currency up again."""
        trading = world.trading
        if not trading.in_use or trading.currency is None:
            return TradeResult(False, "Ya se comercia por trueque")
        if world.government.kind is not None:
            raised = world.politics.voting.propose(world, RETURN_TO_BARTER)
            return TradeResult(raised.ok, raised.message)
        error = self.obstacle(world)
        if error is not None:
            return TradeResult(False, OBSTACLES[error])
        name = trading.currency.name
        said = self._ask(world, BARTER_PROPOSAL, "volver al trueque", option_id)
        if said is None:
            return TradeResult(False, "No hay manera de preguntárselo")
        yes, no = said
        if yes <= no:
            return self._kept(world, f"El asentamiento sigue con {name}: {yes} por volver al trueque, {no} en contra")
        return self.revert(world, f": {yes} a favor, {no} en contra")

    def maybe_raise(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Have a resident who has had enough of how things are traded think of saying so.

        Under barter it is a currency they would raise, and with a currency going back to barter.
        Whether they do is theirs to decide and the player's to advise on. Returns whether it
        came to that: not while the residents were asked lately, or they have a decision open.
        """
        kind = BARTER_RAISED if world.fund.currency(world) is not None else CURRENCY_RAISED
        if kind not in world.registries.decisions or self.obstacle(world) is not None:
            return False
        if resident.away or world.interventions.asking_obstacle(world, resident, kind) is not None:
            return False
        world.trading.refusals.pop(resident.resident_id, None)
        return world.interventions.ask(world, resident, kind) is not None

    def raised(self, world: "SimulationWorld", resident: Resident, what: str) -> TradeResult:
        """A resident puts it to everyone that they trade another way. Nobody is advised: each answers alone.

        A currency nobody has named yet goes by the plain name such a thing has, until the
        player gives it one. Where there is a government it is a proposal of theirs, if the
        government lets them make one: if not, they have nobody to put it to, and hold that
        against it.
        """
        economy = world.registries.economy
        made = world.trading.currency
        name = made.name if made is not None else economy.credits_name
        singular = made.singular if made is not None else economy.credits_singular
        if world.government.kind is not None:
            voting = world.politics.voting
            kind = RETURN_TO_BARTER if what == "barter" else ADOPT_CURRENCY
            if kind not in world.registries.proposals.residents_raise:
                # How the settlement trades is the player's to say (S45): they have nobody to put it to.
                unheard = world.registries.proposals.aftermath["unheard_resentment"]
                world.politics.legitimacy.profile(world, resident).adjust("resentment", unheard)
                return TradeResult(False, f"{resident.name} no tiene a quién proponérselo")
            if what == "barter":
                raised = voting.raise_as(world, resident, RETURN_TO_BARTER)
            else:
                raised = voting.raise_as(world, resident, ADOPT_CURRENCY, params={"name": name, "singular": singular})
            if not raised.ok and not voting.may_propose(world, resident):
                unheard = world.registries.proposals.aftermath["unheard_resentment"]
                world.politics.legitimacy.profile(world, resident).adjust("resentment", unheard)
            return TradeResult(raised.ok, raised.message)
        if what == "barter":
            return self.propose_barter(world, None)
        return self.propose_currency(world, name, singular, None)

    def rename(self, world: "SimulationWorld", name: str, singular: str | None = None) -> TradeResult:
        """Give the currency the settlement has the name the player wants for it. What is held of it is the same."""
        made = world.trading.currency
        name = tidy_currency_name(name)
        if made is None:
            return TradeResult(False, "No hay moneda a la que poner nombre")
        if not name:
            return TradeResult(False, "Una moneda tiene que llamarse de alguna manera")
        before = made.name
        made.name, made.singular = name, tidy_currency_name(singular or "") or singular_of(name)
        text = f"Lo que se llamaba {before} se llama ahora {name}"
        world.emit_event(DomainEvent("currency_named", NAMED_IMPORTANCE, text, data={"currency_id": made.currency_id}))
        return TradeResult(True, text)

    def decision_inputs(self, world: "SimulationWorld", resident: Resident) -> dict[str, float]:
        """What a resident weighs about how to trade, each from 0 to 1: what they have put by
        in coin, what they own in things, and whether they hold a job."""
        economy = world.registries.economy
        resolve = world.registries.items.resolve
        things = sum(
            resolve(item.definition_id).base_value * item.quantity
            for inventory in (resident.inventory, *world.containers.values())
            for item in inventory.items
            if item.owner_id == resident.resident_id
        )
        return {
            "savings": min(1.0, max(0.0, resident.credits) / economy.savings_scale),
            "goods": min(1.0, things / economy.goods_scale),
            "idle": 0.0 if resident.job_id in world.registries.jobs else 1.0,
        }

    # ----- particulars -----

    def _asked(self, world: "SimulationWorld") -> list[Resident]:
        """Whoever has a say: everyone who is in the settlement to be asked."""
        return [resident for resident in world.residents.values() if not resident.away]

    def _ask(self, world: "SimulationWorld", kind: str, thing: str, option_id: str | None) -> tuple[int, int] | None:
        """Ask everyone who is in. Returns how many are for it and how many against, or None if it cannot be asked."""
        if kind not in world.registries.decisions:
            return None
        trading = world.trading
        trading.asked_on = world.clock.day
        trading.refusals.clear()
        trading.asked_about, trading.answers = thing, {}
        for resident in self._asked(world):
            outcome = world.interventions.put_to(
                world, resident, kind, thing, self.decision_inputs(world, resident), option_id
            )
            trading.answers[resident.resident_id] = outcome is not None and outcome.agrees
        yes = sum(trading.answers.values())
        return (yes, len(trading.answers) - yes)

    def _issue(self, world: "SimulationWorld") -> None:
        """Start a currency off: something in every pocket, and something in the fund for each of them."""
        economy = world.registries.economy
        for resident in world.residents.values():
            resident.credits += economy.starting_credits
        world.fund.pay_in(world, economy.fund_per_resident * len(world.residents))

    def _changed(self, world: "SimulationWorld", text: str) -> TradeResult:
        coin = world.fund.currency(world)
        world.emit_event(
            DomainEvent(
                "trade_terms_changed",
                CHANGED_IMPORTANCE,
                text,
                data={"currency_id": coin.currency_id if coin is not None else None},
            )
        )
        return TradeResult(True, text)

    def _kept(self, world: "SimulationWorld", text: str) -> TradeResult:
        world.emit_event(DomainEvent("trade_terms_kept", KEPT_IMPORTANCE, text))
        return TradeResult(False, text)
