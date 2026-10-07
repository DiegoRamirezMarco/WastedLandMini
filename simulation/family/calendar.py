"""The calendar: the date worked out from the day a settlement is on.

It is the ordinary one: twelve months, each with the days it has always had, 365 to the year
and no leap years. Nothing is saved for it. Day 1 of a settlement is the first of January of
the year its data says it begins in.
"""

import zlib
from dataclasses import dataclass

DAYS_PER_YEAR = 365
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
MONTH_NAMES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


@dataclass(frozen=True)
class Date:
    year: int
    # From 1 to 12, and from 1 to however many days the month has.
    month: int
    day: int

    @property
    def label(self) -> str:
        """The date in words, such as `3 de marzo de 2226`."""
        return f"{self.day} de {MONTH_NAMES[self.month - 1]} de {self.year}"


def date_of(day: int, start_year: int) -> Date:
    """The date of a settlement's day, counted from 1. Days before it began count backwards."""
    years, left = divmod(day - 1, DAYS_PER_YEAR)
    for month, length in enumerate(MONTH_DAYS, start=1):
        if left < length:
            return Date(start_year + years, month, left + 1)
        left -= length
    raise AssertionError("a year has 365 days")


def years_between(born: int, day: int) -> int:
    """Whole years from the day somebody was born to another day: their age on it."""
    return max(0, (day - born) // DAYS_PER_YEAR)


def day_of_year_for(resident_id: str) -> int:
    """How far into a year somebody's birthday falls when all that is known is their age: always
    the same for the same ID, and different for most, so that birthdays are spread over the year."""
    return zlib.crc32(resident_id.encode("utf-8")) % DAYS_PER_YEAR
