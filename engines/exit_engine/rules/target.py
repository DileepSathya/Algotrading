from .base import ExitRule
from ..models import ExitResult


class TargetExit(ExitRule):
    """
    Exit when the candle's high reaches
    or crosses the target price.
    """

    def check(
        self,
        row,
        entry_price: float,
        sl: float,
        target: float,
        direction: str = "LONG",
    ) -> ExitResult | None:

        triggered = row["high"] >= target if direction == "LONG" else row["low"] <= target
        if triggered:
            return ExitResult(
                exit_price=target,
                exit_reason="TARGET"
            )

        return None
