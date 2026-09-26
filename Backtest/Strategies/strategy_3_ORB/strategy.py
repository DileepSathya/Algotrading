from datetime import time

import pandas as pd

from .config import (FORCED_EXIT_TIME, ORB_START, ORB_END, RISK_FRACTION,
                     SL_RANGE_MULTIPLIER, TARGET_RANGE_MULTIPLIER,
                     ENTRY_START_TIME, ENTRY_END_TIME, MAX_STOP_LOSSES_PER_DAY,
                     MAX_STOP_LOSSES_PER_SYMBOL_PER_DAY)
from .models import ORBSignal


class ORBStrategy:
    """Multi-symbol intraday opening-range breakout strategy."""

    intraday = True

    def __init__(self, orb_start: time = ORB_START, orb_end: time = ORB_END,
                 forced_exit_time: time = FORCED_EXIT_TIME,
                 risk_fraction: float = RISK_FRACTION,
                 sl_range_multiplier: float = SL_RANGE_MULTIPLIER,
                 target_range_multiplier: float = TARGET_RANGE_MULTIPLIER,
                 entry_start_time: time = ENTRY_START_TIME,
                 entry_end_time: time = ENTRY_END_TIME,
                 max_stop_losses_per_day: int = MAX_STOP_LOSSES_PER_DAY,
                 max_stop_losses_per_symbol_per_day: int = MAX_STOP_LOSSES_PER_SYMBOL_PER_DAY):
        self.orb_start = orb_start
        self.orb_end = orb_end
        self.forced_exit_time = forced_exit_time
        self.risk_fraction = risk_fraction
        self.sl_range_multiplier = sl_range_multiplier
        self.target_range_multiplier = target_range_multiplier
        self.entry_start_time = entry_start_time
        self.entry_end_time = entry_end_time
        self.max_stop_losses_per_day = max_stop_losses_per_day
        self.max_stop_losses_per_symbol_per_day = max_stop_losses_per_symbol_per_day

    @staticmethod
    def _validate_input(df):
        required = {"date", "time", "symbol", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

    def prepare_data(self, df):
        self._validate_input(df)
        data = df.copy()
        data['prev_candle_vol']=data.groupby('symbol')['volume'].shift(1)
        data['vol_filter']=data['volume']>data['prev_candle_vol']
        data["trading_date"] = pd.to_datetime(data["date"]).dt.normalize()
        data["time"] = pd.to_datetime(data["time"].astype(str), format="mixed").dt.time
        data["timestamp"] = pd.to_datetime(
            data["trading_date"].dt.strftime("%Y-%m-%d") + " " + data["time"].astype(str)
        )
        data["date"] = data["timestamp"]
        data = data.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)
        opening = data[(data["time"] >= self.orb_start) & (data["time"] < self.orb_end)]
        levels = opening.groupby(["trading_date", "symbol"], as_index=False).agg(
            orb_high=("high", "max"), orb_low=("low", "min")
        )
        levels["orb_range"] = levels["orb_high"] - levels["orb_low"]
        data = data.merge(levels, on=["trading_date", "symbol"], how="left", sort=False)
        entry_start = max(self.orb_end, self.entry_start_time)
        entry_end = min(self.forced_exit_time, self.entry_end_time)
        data["entry_eligible"] = ((data["time"] >= entry_start)
                                  & (data["time"] < entry_end)
                                  & data["orb_range"].gt(0))
        return data.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)

    def generate_signal(self, row):
        if not bool(row.get("entry_eligible", False)):
            return None
        row_filter = row['vol_filter']
        close = float(row["close"])
        orb_high = float(row["orb_high"])
        orb_low = float(row["orb_low"])
        orb_range = float(row["orb_range"])

        

        if row_filter and (close > orb_high):
            direction = "LONG"
            sl = close - self.sl_range_multiplier * orb_range
            target = close + self.target_range_multiplier * orb_range
        elif row_filter and (close < orb_low):
            direction = "SHORT"
            sl = close + self.sl_range_multiplier * orb_range
            target = close - self.target_range_multiplier * orb_range
        else:
            return None
        metadata = {"trading_date": row["trading_date"], "orb_high": orb_high,
                    "orb_low": orb_low, "orb_range": orb_range,
                    "entry_timestamp": row["timestamp"]}
        return ORBSignal(str(row["symbol"]), row["timestamp"], close, sl, target,
                         direction, self.sl_range_multiplier * orb_range,
                         self.risk_fraction, metadata)


ORB = ORBStrategy
