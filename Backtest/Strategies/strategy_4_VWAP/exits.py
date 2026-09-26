import pandas as pd

from engines.exit_engine.models import ExitResult
from engines.exit_engine.rules import ExitRule


class EMACrossExit(ExitRule):
    """Exit only when close crosses the configured EMA against the trade."""

    def __init__(self, period: int):
        if isinstance(period, bool) or not isinstance(period, int) or period <= 0:
            raise ValueError("EMA exit period must be a positive integer")
        self.period = period
        self.column = f"exit_ema_{period}"
        self.previous_ema_column = f"previous_exit_ema_{period}"

    def prepare_data(self, data):
        prepared = data.copy()
        ordered = prepared.reset_index(drop=True)
        ordered["date"] = pd.to_datetime(ordered["date"])
        if "time" in ordered:
            clock = (
                ordered["date"].dt.normalize().dt.strftime("%Y-%m-%d")
                + " "
                + ordered["time"].astype(str)
            )
            ordered["_ema_clock"] = pd.to_datetime(clock, format="mixed")
        else:
            ordered["_ema_clock"] = ordered["date"]
        ordered = ordered.sort_values(["symbol", "_ema_clock"], kind="stable")
        grouped = ordered.groupby("symbol", sort=False)
        ordered[self.column] = grouped["close"].transform(
            lambda close: close.ewm(span=self.period, adjust=False).mean()
        ).round(2)
        ordered["previous_close"] = grouped["close"].shift(1)
        ordered[self.previous_ema_column] = ordered.groupby("symbol", sort=False)[
            self.column
        ].shift(1)
        restored = ordered.sort_index()
        for column in (self.column, "previous_close", self.previous_ema_column):
            prepared[column] = restored[column].to_numpy()
        return prepared

    def check(self, row, entry_price, sl, target, direction="LONG"):
        previous_close = row.get("previous_close")
        previous_ema = row.get(self.previous_ema_column)
        if pd.isna(previous_close) or pd.isna(previous_ema):
            return None

        close = float(row["close"])
        ema = float(row[self.column])
        if direction == "LONG":
            crossed = float(previous_close) >= float(previous_ema) and close < ema
        else:
            crossed = float(previous_close) <= float(previous_ema) and close > ema
        if crossed:
            return ExitResult(exit_price=close, exit_reason=f"{self.period}_EMA_CROSS")
        return None
