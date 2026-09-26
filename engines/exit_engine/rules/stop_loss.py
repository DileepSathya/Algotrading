from .base import ExitRule
from ..models import ExitResult


class SLExit(ExitRule):
    """
    Exit when the candle's low reaches
    or crosses the stop-loss price.
    """

    def check(
        self,
        row,
        entry_price: float,
        sl: float,
        target: float,
        direction: str = "LONG",
    ) -> ExitResult | None:

        triggered = row["low"] <= sl if direction == "LONG" else row["high"] >= sl
        if triggered:
            return ExitResult(
                exit_price=sl,
                exit_reason="SL"
            )

        return None
