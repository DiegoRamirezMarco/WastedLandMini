"""Credit lent between friends: asked for by whoever is short, and owed until it is paid back.

A loan is a matter between the two of them, and a fact like any other: whoever sees it made
knows of it. Paid back, it is forgotten. Left unpaid too long, it tells on what the lender
thinks of whoever owes it.
"""

from typing import TYPE_CHECKING

from simulation.economy.terms import Debt
from simulation.events.event import DomainEvent
from simulation.residents.resident import Resident

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

LOAN_IMPORTANCE = 20
OVERDUE_IMPORTANCE = 35
# How fond of somebody, and no less trusting than this, a lender has to be, and no greedier.
LENDER_AFFECTION = 35.0
LENDER_TRUST = 0.0
LENDER_MAX_GREED = 70.0
REPAID_FEELINGS = {"trust": 5.0}
OVERDUE_FEELINGS = {"resentment": 12.0, "trust": -12.0}


class LendingSystem:
    def owed(self, world: "SimulationWorld", debtor_id: str, creditor_id: str) -> Debt | None:
        """What one resident owes another, if anything."""
        return next(
            (debt for debt in world.debts if debt.debtor_id == debtor_id and debt.creditor_id == creditor_id), None
        )

    def after_exchange(self, world: "SimulationWorld", resident: Resident, partner: Resident) -> None:
        """What passes between two residents who have just talked: `resident` pays back what
        they owe `partner` if they have it by now, or asks to be lent something if they are short."""
        coin = world.fund.currency(world)
        if coin is None:
            return
        economy = world.registries.economy
        debt = self.owed(world, resident.resident_id, partner.resident_id)
        if debt is not None:
            if resident.credits >= debt.amount + economy.poor_below:
                self._repay(world, resident, partner, debt)
            return
        if resident.credits >= economy.poor_below or economy.loan_size <= 0:
            return
        if any(owed.debtor_id == resident.resident_id for owed in world.debts):
            # Nobody is lent more while they still owe.
            return
        feelings = world.relationships.get((partner.resident_id, resident.resident_id))
        if feelings is None or feelings.affection < LENDER_AFFECTION or feelings.trust < LENDER_TRUST:
            return
        if partner.personality.greed > LENDER_MAX_GREED or partner.credits < economy.loan_size + economy.gift_savings:
            return
        partner.credits -= economy.loan_size
        resident.credits += economy.loan_size
        world.debts.append(Debt(resident.resident_id, partner.resident_id, economy.loan_size, world.clock.day))
        lent = coin.amount(economy.loan_size)
        world.emit_event(
            DomainEvent(
                "loan_made",
                LOAN_IMPORTANCE,
                f"{partner.name} le presta {lent} a {resident.name}",
                [partner.resident_id, resident.resident_id],
                data={"amount": economy.loan_size},
            ),
            at=resident.tile,
            fact_text=f"{partner.name} le prestó {lent} a {resident.name}",
            subjects=[resident.resident_id, partner.resident_id],
        )

    def _repay(self, world: "SimulationWorld", debtor: Resident, creditor: Resident, debt: Debt) -> None:
        debtor.credits -= debt.amount
        creditor.credits += debt.amount
        world.debts.remove(debt)
        feelings = world.relationship(creditor.resident_id, debtor.resident_id)
        for feeling, delta in REPAID_FEELINGS.items():
            feelings.adjust(feeling, delta)
        coin = world.trading.currency
        paid = coin.amount(debt.amount) if coin is not None else "lo que le debía"
        world.emit_event(
            DomainEvent(
                "loan_repaid",
                LOAN_IMPORTANCE,
                f"{debtor.name} le devuelve {paid} a {creditor.name}",
                [debtor.resident_id, creditor.resident_id],
                data={"amount": debt.amount},
            ),
            at=debtor.tile,
        )

    def tick(self, world: "SimulationWorld") -> None:
        """Once a day, drop what is owed to or by someone who is gone, and have a loan that has
        gone unpaid too long tell on what its lender thinks of whoever owes it."""
        if world.clock.minute != 0 or world.clock.hour != 0 or not world.debts:
            return
        world.debts = [
            debt for debt in world.debts if debt.debtor_id in world.residents and debt.creditor_id in world.residents
        ]
        for debt in world.debts:
            if debt.overdue or world.clock.day - debt.since < world.registries.economy.loan_days:
                continue
            debt.overdue = True
            debtor, creditor = world.residents[debt.debtor_id], world.residents[debt.creditor_id]
            feelings = world.relationship(creditor.resident_id, debtor.resident_id)
            for feeling, delta in OVERDUE_FEELINGS.items():
                feelings.adjust(feeling, delta)
            world.emit_event(
                DomainEvent(
                    "loan_overdue",
                    OVERDUE_IMPORTANCE,
                    f"{debtor.name} sigue sin devolverle a {creditor.name} lo que le prestó",
                    [creditor.resident_id, debtor.resident_id],
                    data={"amount": debt.amount},
                )
            )
