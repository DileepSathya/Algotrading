import math

import pandas as pd

from .config import (
    BIGGER_EMA_PERIOD,
    CLOSE_THRESHOLD,
    EMA_FILTER,
    EMA_PERIOD,
    EMA_PERIOD_VOL,
    PRICE_ABOVE_EMA_PERIOD,
    RSI_MAX_VALUE,
    RSI_MIN_VALUE,
    RSI_PERIOD,
    SMALLER_EMA_PERIOD,
    TARGET_PERCENT,
    USE_RSI,
)

from .models import StrategySignal


class HigherHighStrategy:
    """
    Higher High trading strategy.

    Entry conditions
    ----------------
    1. Current close > previous day's close
    2. Current high > previous day's high
    3. Current low > previous day's low
    4. Current close is in the upper 70% of
       the current candle range
    5. Current close is at or above the configured EMA
       when PRICE_ABOVE_EMA_PERIOD is enabled
    6. Smaller-period EMA is above the bigger-period EMA
       when EMA_FILTER is enabled
    7. RSI is inside the configured inclusive range
       when USE_RSI is enabled

    Entry
    -----
    Entry price = current candle close

    Stop Loss
    ---------
    SL = minimum of:
        - current candle low
        - current candle configured EMA

    Target
    ------
    Target = entry price + configured target percentage
    """

    def __init__(
        self,
        close_threshold: float = CLOSE_THRESHOLD,
        ema_period: int = EMA_PERIOD,
        price_above_ema_period: bool = PRICE_ABOVE_EMA_PERIOD,
        ema_filter: bool = EMA_FILTER,
        smaller_ema_period: int = SMALLER_EMA_PERIOD,
        bigger_ema_period: int = BIGGER_EMA_PERIOD,
        use_rsi: bool = USE_RSI,
        rsi_period: int = RSI_PERIOD,
        rsi_min_value: float = RSI_MIN_VALUE,
        rsi_max_value: float = RSI_MAX_VALUE,
        ema_period_vol: int = EMA_PERIOD_VOL,
        target_percent: float = TARGET_PERCENT,
        risk_per_trade_pct: float | None = None,
        signal_ranking: str = "alphabetical",
        momentum_lookback: int = 20,
        atr_period: int = 14,
        max_extension_atr: float | None = None,
        min_reward_risk: float | None = None,
    ):
        self.close_threshold = close_threshold
        self.ema_period = ema_period
        self.price_above_ema_period = price_above_ema_period
        self.ema_column = f"{self.ema_period}_ema"
        self.ema_filter = ema_filter
        self.smaller_ema_column = f"{smaller_ema_period}_ema"
        self.bigger_ema_column = f"{bigger_ema_period}_ema"
        self.smaller_ema_period = smaller_ema_period
        self.bigger_ema_period = bigger_ema_period
        self.use_rsi = use_rsi
        self.rsi_period = rsi_period
        self.rsi_min_value = rsi_min_value
        self.rsi_max_value = rsi_max_value
        self.rsi_column = f"rsi_{self.rsi_period}"
        self.ema_period_vol = ema_period_vol
        self.target_percent = target_percent
        for name, value in (("risk_per_trade_pct", risk_per_trade_pct),
                            ("max_extension_atr", max_extension_atr),
                            ("min_reward_risk", min_reward_risk)):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be a finite positive number or None")
        if risk_per_trade_pct is not None and risk_per_trade_pct > 100:
            raise ValueError("risk_per_trade_pct must be at most 100")
        for name, value in (("momentum_lookback", momentum_lookback), ("atr_period", atr_period)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if signal_ranking not in {"alphabetical", "momentum", "relative_volume"}:
            raise ValueError("signal_ranking must be alphabetical, momentum or relative_volume")
        self.risk_per_trade_pct = risk_per_trade_pct
        self.signal_ranking = signal_ranking
        self.momentum_lookback = momentum_lookback
        self.atr_period = atr_period
        self.max_extension_atr = max_extension_atr
        self.min_reward_risk = min_reward_risk
        self.entry_start = None
        self.entry_end = None

    # ==================================================
    # PUBLIC METHOD
    # ==================================================

    def prepare_data(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Prepare historical data required by the strategy.

        Adds:
            prev_day_close
            prev_day_high
            prev_day_low
            range
            Configured close EMA
            close_>_threshold_range
            trade_signal
        """

        self._validate_input(df)

        data = df.copy()

        # --------------------------------------------------
        # Sort data
        # --------------------------------------------------

        data["date"] = pd.to_datetime(
            data["date"]
        )

        data = (
            data
            .sort_values(
                ["symbol", "date"]
            )
            .reset_index(drop=True)
        )

        # --------------------------------------------------
        # Previous day's values
        # --------------------------------------------------

        data["prev_day_close"] = (
            data
            .groupby("symbol")["close"]
            .shift(1)
        )

        data["prev_day_high"] = (
            data
            .groupby("symbol")["high"]
            .shift(1)
        )

        data["prev_day_low"] = (
            data
            .groupby("symbol")["low"]
            .shift(1)
        )

        # --------------------------------------------------
        # Candle range percentage
        # --------------------------------------------------

        data["range"] = (
            (
                data["high"]
                - data["low"]
            )
            / data["low"]
        ) * 100

        # --------------------------------------------------
        # EMA
        # --------------------------------------------------

        data[self.ema_column] = (
            data
            .groupby("symbol")["close"]
            .transform(
                lambda x: x.ewm(
                    span=self.ema_period,
                    adjust=False
                ).mean()
            )
            .round(2)
        )

        for period, column in (
            (self.smaller_ema_period, self.smaller_ema_column),
            (self.bigger_ema_period, self.bigger_ema_column),
        ):
            data[column] = (
                data
                .groupby("symbol")["close"]
                .transform(
                    lambda x: x.ewm(
                        span=period,
                        adjust=False
                    ).mean()
                )
                .round(2)
            )

        data[self.rsi_column] = (
            data
            .groupby("symbol")["close"]
            .transform(self._calculate_rsi)
            .round(2)
        )

        # --------------------------------------------------
        # Close position inside candle
        # --------------------------------------------------

        data["close_>_70th_range"] = (
            data["close"]
            >=
            (
                data["low"]
                +
                (
                    data["high"]
                    - data["low"]
                )
                * self.close_threshold
            )
        )

                # --------------------------------------------------
        # Previous day's volume
        # --------------------------------------------------

        data["prev_day_vol"] = (
            data
            .groupby("symbol")["volume"]
            .shift(1)
        )

        # --------------------------------------------------
        # Previous-volume EMA
        # --------------------------------------------------

        data["20_vol_ma"] = (
            data
            .groupby("symbol")["volume"]
            .transform(
                lambda x: x.ewm(
                    span=self.ema_period_vol,
                    adjust=False
                ).mean()
            )
        )

        # Use only information available BEFORE current candle
        data["20_vol_ma"] = (
            data
            .groupby("symbol")["20_vol_ma"]
            .shift(1)
            .round(2)
        )



        # --------------------------------------------------
        # Entry signal
        # --------------------------------------------------

        price_above_ema = (
            data["close"] >= data[self.ema_column]
            if self.price_above_ema_period
            else True
        )
        ema_filter_passes = (
            data[self.smaller_ema_column] > data[self.bigger_ema_column]
            if self.ema_filter
            else True
        )
        rsi_filter_passes = (
            data[self.rsi_column].between(
                self.rsi_min_value,
                self.rsi_max_value,
                inclusive="both",
            )
            if self.use_rsi
            else True
        )

        data["trade_signal"] = (
            (data["close"] > data["prev_day_close"])
            & (data["high"] > data["prev_day_high"])
            & (data["low"] > data["prev_day_low"])
            & (
                (data["volume"] >= data["prev_day_vol"])
                | (data["volume"] >= data["20_vol_ma"])
            )
            & data["close_>_70th_range"]
            & price_above_ema
            & ema_filter_passes
            & rsi_filter_passes
        )

        dropna_columns = list(data.columns)
        if not self.use_rsi:
            dropna_columns.remove(self.rsi_column)
        # New diagnostic indicators must not change the original warmup or
        # remove candles needed to manage an already-open position.
        true_range = pd.concat([
            data["high"] - data["low"],
            (data["high"] - data["prev_day_close"]).abs(),
            (data["low"] - data["prev_day_close"]).abs(),
        ], axis=1).max(axis=1)
        data["atr"] = true_range.groupby(data["symbol"]).transform(
            lambda values: values.rolling(self.atr_period, min_periods=self.atr_period).mean()
        )
        previous = data.groupby("symbol")["close"].shift(self.momentum_lookback)
        data["momentum_return"] = (data["close"] / previous.where(previous > 0) - 1) * 100
        data["relative_volume"] = data["volume"] / data["20_vol_ma"].where(data["20_vol_ma"] > 0)
        data = data.dropna(subset=dropna_columns)



        return data

    # ==================================================
    # SIGNAL GENERATION
    # ==================================================

    def generate_signal(
        self,
        row: pd.Series
    ) -> StrategySignal | None:
        """
        Generate a trade setup from a single candle.

        Returns None when there is no entry signal.
        """

        if not bool(row["trade_signal"]):
            return None
        date = pd.Timestamp(row["date"])
        if self.entry_start is not None and date < self.entry_start:
            return None
        if self.entry_end is not None and date > self.entry_end:
            return None
        if self.signal_ranking != "alphabetical":
            column = "momentum_return" if self.signal_ranking == "momentum" else "relative_volume"
            if not math.isfinite(float(row.get(column, float("nan")))):
                return None

        entry_price = float(
            row["close"]
        )

        # --------------------------------------------------
        # Strategy-defined Stop Loss
        # --------------------------------------------------

        sl = min(
            float(row["low"]),
            float(row[self.ema_column])
        )

        # --------------------------------------------------
        # Strategy-defined Target
        # --------------------------------------------------

        target = (
            entry_price
            * (
                1
                + self.target_percent / 100
            )
        )

        risk = entry_price - sl
        reward_risk = (target - entry_price) / risk if risk > 0 else float("nan")
        atr = float(row.get("atr", float("nan")))
        extension = (entry_price - float(row[self.ema_column])) / atr if atr > 0 else float("nan")
        if self.max_extension_atr is not None and (
            not math.isfinite(extension) or extension > self.max_extension_atr
        ):
            return None
        if self.min_reward_risk is not None and (
            not math.isfinite(reward_risk) or reward_risk < self.min_reward_risk
        ):
            return None
        if self.risk_per_trade_pct is not None and (not math.isfinite(risk) or risk <= 0):
            return None

        return StrategySignal(
            symbol=str(row["symbol"]),
            entry_date=row["date"],
            entry_price=entry_price,
            sl=sl,
            target=target,
            risk_per_unit=risk if self.risk_per_trade_pct is not None else None,
            risk_fraction=self.risk_per_trade_pct / 100 if self.risk_per_trade_pct is not None else None,
            metadata={"initial_risk_per_unit": risk, "entry_reward_risk": reward_risk,
                      "entry_extension_atr": extension,
                      "entry_relative_volume": row.get("relative_volume", float("nan")),
                      "entry_momentum_return": row.get("momentum_return", float("nan"))},
        )

    def rank_entry_candidates(self, rows):
        """Order only this day's entries; exits retain their original order."""
        if self.signal_ranking == "alphabetical":
            return rows
        column = "momentum_return" if self.signal_ranking == "momentum" else "relative_volume"

        def key(row):
            value = float(row.get(column, float("nan")))
            return (-value if math.isfinite(value) else float("inf"), str(row["symbol"]))

        return sorted(rows, key=key)

    # ==================================================
    # VALIDATION
    # ==================================================

    def _calculate_rsi(self, close: pd.Series) -> pd.Series:
        change = close.diff()
        gain = change.clip(lower=0)
        loss = -change.clip(upper=0)
        average_gain = gain.ewm(
            alpha=1 / self.rsi_period,
            adjust=False,
            min_periods=self.rsi_period,
        ).mean()
        average_loss = loss.ewm(
            alpha=1 / self.rsi_period,
            adjust=False,
            min_periods=self.rsi_period,
        ).mean()
        relative_strength = average_gain / average_loss
        return 100 - (100 / (1 + relative_strength))

    @staticmethod
    def _validate_input(
        df: pd.DataFrame
    ) -> None:
        """
        Validate required historical market columns.
        """

        required_columns = {
            "date",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing_columns = (
            required_columns
            - set(df.columns)
        )

        if missing_columns:
            raise ValueError(
                "Missing required columns: "
                f"{sorted(missing_columns)}"
            )
