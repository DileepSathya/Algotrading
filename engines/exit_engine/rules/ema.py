from .base import ExitRule
from ..models import ExitResult
import pandas as pd


class EMAExit(ExitRule):
    """
    Exit when the candle closes below the selected EMA.
    """

    def __init__(self, period: int):
        if isinstance(period, bool) or not isinstance(period, int) or period <= 0:
            raise ValueError("EMA exit period must be a positive integer")
        self.period = period
        self.column = f"exit_ema_{period}"

    def prepare_data(self, data):
        prepared = data.copy()
        ordered = prepared.reset_index(drop=True)
        ordered["date"] = pd.to_datetime(ordered["date"])
        ordered = ordered.sort_values(["symbol", "date"])
        ordered[self.column] = (
            ordered.groupby("symbol")["close"]
            .transform(lambda close: close.ewm(span=self.period, adjust=False).mean())
            .round(2)
        )
        prepared[self.column] = ordered.sort_index()[self.column].to_numpy()
        return prepared

    def check(
        self,
        row,
        entry_price: float,
        sl: float,
        target: float,
        direction: str = "LONG",
    ) -> ExitResult | None:

        if row["close"] < row[self.column]:
            return ExitResult(
                exit_price=row["close"],
                exit_reason=f"{self.period}_EMA"
            )

        return None
