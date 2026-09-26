from typing import Sequence

from .models import ExitResult
from .rules import ExitRule


class ExitEngine:
    """
    Coordinates multiple exit rules.

    Rules are evaluated in the order supplied during
    initialization.

    The first triggered rule determines the exit.
    """

    def __init__(
        self,
        rules: Sequence[ExitRule]
    ):
        if not rules:
            raise ValueError(
                "At least one exit rule is required."
            )

        self.rules = list(rules)

    def prepare_data(self, data):
        """Calculate exit indicators on the full history before entries are filtered."""
        prepared = data.copy()
        for rule in self.rules:
            prepared = rule.prepare_data(prepared)
        return prepared

    def check(
        self,
        row,
        entry_price: float,
        sl: float,
        target: float,
        direction: str = "LONG",
    ) -> ExitResult | None:
        """
        Check all configured exit rules.

        Parameters
        ----------
        row:
            Current market candle.

        entry_price:
            Trade entry price.

        sl:
            Stop-loss price supplied by the Strategy Engine.

        target:
            Target price supplied by the Strategy Engine.

        Returns
        -------
        ExitResult | None
            ExitResult if any rule triggers.
            None if no exit condition is met.
        """

        for rule in self.rules:

            result = rule.check(
                row=row,
                entry_price=entry_price,
                sl=sl,
                target=target,
                direction=direction,
            )

            if result is not None:
                return result

        return None
