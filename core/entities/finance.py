"""Utility finance dataclass, encapsulates spending and savings."""

from dataclasses import dataclass


@dataclass(slots=True)
class Finance:
    spent: float = 0.0
    savings: float = 0.0

    def add_spent(self, amount: float) -> None:
        self.spent += amount

    def add_savings(self, amount: float) -> None:
        self.savings += amount 