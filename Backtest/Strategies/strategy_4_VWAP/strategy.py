from datetime import time

import pandas as pd

from .config import (
    EMA_PERIOD,
    FORCED_EXIT_TIME,
    MAX_DAILY_LOSS_PCT,
    MAX_LOSS_TRADES_PER_DAY,
    MAX_LOSS_TRADES_PER_SYMBOL_PER_DAY,
    RISK_FRACTION,
    SIGNAL_START_TIME,
    TARGET_PCT_FROM_ENTRY,
)
from .models import VWAPSignal


class VWAPStrategy:
    """Intraday VWAP strategy with entry-candle risk levels."""

    intraday = True
    allow_same_candle_reentry = True
    allow_same_candle_reentry = True

    def __init__(
        self,
        ema_period: int = EMA_PERIOD,
        target_pct_from_entry: float = TARGET_PCT_FROM_ENTRY,
        forced_exit_time: time = FORCED_EXIT_TIME,
        signal_start_time: time = SIGNAL_START_TIME,
        risk_fraction: float = RISK_FRACTION,
        max_loss_trades_per_day: int = MAX_LOSS_TRADES_PER_DAY,
        max_loss_trades_per_symbol_per_day: int = MAX_LOSS_TRADES_PER_SYMBOL_PER_DAY,
        max_daily_loss_pct: float = MAX_DAILY_LOSS_PCT,
    ):
        if isinstance(ema_period, bool) or not isinstance(ema_period, int) or ema_period <= 0:
            raise ValueError("EMA period must be a positive integer")
        if target_pct_from_entry <= 0:
            raise ValueError("Target percentage must be greater than 0")
        if risk_fraction <= 0:
            raise ValueError("Risk fraction must be greater than 0")
        if signal_start_time >= forced_exit_time:
            raise ValueError("Signal start time must be before forced exit time")
        if max_loss_trades_per_day <= 0 or max_loss_trades_per_symbol_per_day <= 0:
            raise ValueError("Loss-trade limits must be greater than 0")
        if max_daily_loss_pct <= 0:
            raise ValueError("Max daily loss percentage must be greater than 0")
        self.ema_period = ema_period
        self.target_pct_from_entry = float(target_pct_from_entry)
        self.forced_exit_time = forced_exit_time
        self.signal_start_time = signal_start_time
        self.risk_fraction = float(risk_fraction)
        self.max_loss_trades_per_day = int(max_loss_trades_per_day)
        self.max_loss_trades_per_symbol_per_day = int(
            max_loss_trades_per_symbol_per_day
        )
        self.max_daily_loss_pct = float(max_daily_loss_pct)

    @staticmethod
    def _validate_input(df):
        required = {"date", "time", "symbol", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

    def prepare_data(self, df):
        self._validate_input(df)
        data = df.copy()
        data["trading_date"] = pd.to_datetime(data["date"]).dt.normalize()
        data["time"] = pd.to_datetime(data["time"].astype(str), format="mixed").dt.time
        data["timestamp"] = pd.to_datetime(
            data["trading_date"].dt.strftime("%Y-%m-%d") + " " + data["time"].astype(str)
        )
        data["date"] = data["timestamp"]
        data = data.sort_values(["symbol", "timestamp"], kind="stable").reset_index(drop=True)

        session = [data["symbol"], data["trading_date"]]
        typical_price = (data["high"] + data["low"] + data["close"]) / 3.0
        cumulative_volume = data["volume"].groupby(session, sort=False).cumsum()
        cumulative_value = (typical_price * data["volume"]).groupby(session, sort=False).cumsum()
        data["vwap"] = cumulative_value.div(cumulative_volume.where(cumulative_volume.gt(0)))
        data["previous_volume"] = data.groupby(
            ["symbol", "trading_date"], sort=False
        )["volume"].shift(1)
        data["previous_close"] = data.groupby(
            ["symbol", "trading_date"], sort=False
        )["close"].shift(1)
        data["previous_vwap"] = data.groupby(
            ["symbol", "trading_date"], sort=False
        )["vwap"].shift(1)
        data["entry_eligible"] = (
            (data["time"] >= self.signal_start_time)
            & (data["time"] < self.forced_exit_time)
            & data["previous_volume"].notna()
            & data["previous_close"].notna()
            & data["previous_vwap"].notna()
            & data["vwap"].notna()
        )
        return data.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)

    def generate_signal(self, row):
        if not bool(row.get("entry_eligible", False)):
            return None
        if float(row["volume"]) <= float(row["previous_volume"]):
            return None

        close = float(row["close"])
        vwap = float(row["vwap"])
        previous_close = float(row["previous_close"])
        previous_vwap = float(row["previous_vwap"])
        if previous_close <= previous_vwap and close > vwap:
            direction = "LONG"
            sl = float(row["low"])
            risk = close - sl
            target = close * (1 + self.target_pct_from_entry / 100)
        elif previous_close >= previous_vwap and close < vwap:
            direction = "SHORT"
            sl = float(row["high"])
            risk = sl - close
            target = close * (1 - self.target_pct_from_entry / 100)
        else:
            return None

        if risk <= 0:
            return None
        metadata = {
            "trading_date": row["trading_date"],
            "vwap": vwap,
            "previous_close": previous_close,
            "previous_vwap": previous_vwap,
            "risk_per_unit": risk,
            "entry_timestamp": row["timestamp"],
        }
        return VWAPSignal(
            str(row["symbol"]), row["timestamp"], close, sl, target,
            direction, risk, self.risk_fraction, metadata,
        )
VWAP = VWAPStrategy(ema_period=EMA_PERIOD)
