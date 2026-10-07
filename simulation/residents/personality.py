from dataclasses import dataclass


@dataclass
class Personality:
    aggression: float = 50.0
    empathy: float = 50.0
    impulsiveness: float = 50.0
    sociability: float = 50.0
    greed: float = 50.0
    courage: float = 50.0
    # Counts for nothing in anyone who is not an adult.
    libido: float = 50.0
    # How readily others are won over by them, and how well others do under them.
    charisma: float = 50.0
    leadership: float = 50.0
