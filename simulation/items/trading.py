from dataclasses import dataclass


@dataclass
class TradeOffer:
    proposer_id: str
    receiver_id: str
    offered_instance_ids: list[str]
    requested_instance_ids: list[str]
