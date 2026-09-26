from datetime import time

import pandas as pd

from .base import ExitRule
from ..models import ExitResult


class TimeExit(ExitRule):
    """Exit at the candle close at or after an intraday cutoff."""

    def __init__(self, cutoff="14:30"):
        parsed = pd.to_datetime(str(cutoff), format="mixed").time()
        self.cutoff = time(parsed.hour, parsed.minute, parsed.second)

    def check(self, row, entry_price, sl, target, direction="LONG"):
        value = row.get("time")
        candle_time = value if isinstance(value, time) else pd.to_datetime(str(value), format="mixed").time()
        if candle_time >= self.cutoff:
            return ExitResult(exit_price=float(row["close"]), exit_reason="TIME")
        return None
