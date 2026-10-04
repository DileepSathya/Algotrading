import pandas as pd

from engines.exit_engine.models import ExitResult
from engines.exit_engine.rules import ExitRule


class TrailingStopExit(ExitRule):
    """Exit at the minimum low of the preceding completed daily candles."""

    def __init__(self, candle_count: int):
        if isinstance(candle_count, bool) or not isinstance(candle_count, int) or candle_count <= 0:
            raise ValueError("Trailing stop candle count must be a positive integer")
        self.candle_count = candle_count
        self.column = f"trailing_stop_{candle_count}"

    def prepare_data(self, data):
        prepared = data.copy().reset_index(drop=True)
        prepared["date"] = pd.to_datetime(prepared["date"])
        ordered = prepared.sort_values(["symbol", "date"], kind="stable")
        ordered[self.column] = ordered.groupby("symbol", sort=False)["low"].transform(
            lambda low: low.rolling(self.candle_count, min_periods=self.candle_count)
            .min()
            .shift(1)
        )
        prepared[self.column] = ordered.sort_index()[self.column].to_numpy()
        return prepared

    def check(self, row, entry_price, sl, target, direction="LONG"):
        trailing_stop = row.get(self.column)
        if pd.isna(trailing_stop):
            return None

        if direction == "LONG" and float(row["low"]) <= float(trailing_stop):
            return ExitResult(exit_price=float(trailing_stop), exit_reason="TRAILING_SL")
        return None
