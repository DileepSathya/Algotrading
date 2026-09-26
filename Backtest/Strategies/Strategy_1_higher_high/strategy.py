import pandas as pd

from .config import (
    CLOSE_THRESHOLD,
    EMA_PERIOD,
    EMA_PERIOD_VOL,
    TARGET_PERCENT,
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

    Entry
    -----
    Entry price = current candle close

    Stop Loss
    ---------
    SL = minimum of:
        - current candle low
        - current candle 9 EMA

    Target
    ------
    Target = entry price + 10%
    """

    def __init__(
        self,
        close_threshold: float = CLOSE_THRESHOLD,
        ema_period: int = EMA_PERIOD,
        ema_period_vol: int = EMA_PERIOD_VOL,
        target_percent: float = TARGET_PERCENT,
    ):
        self.close_threshold = close_threshold
        self.ema_period = ema_period
        self.ema_period_vol = ema_period_vol
        self.target_percent = target_percent

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
            9 EMA
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

        data["9_ema"] = (
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

        data["trade_signal"] = (
    (data["close"] > data["prev_day_close"]) &
    (data["high"] > data["prev_day_high"]) &
    (data["low"] > data["prev_day_low"]) &
    (
        (data["volume"] >= data["prev_day_vol"]) |
        (data["volume"] >= data["20_vol_ma"])
    ) &
    data["close_>_70th_range"]
)

        data=data.dropna()



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

        entry_price = float(
            row["close"]
        )

        # --------------------------------------------------
        # Strategy-defined Stop Loss
        # --------------------------------------------------

        sl = min(
            float(row["low"]),
            float(row["9_ema"])
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

        return StrategySignal(
            symbol=str(row["symbol"]),
            entry_date=row["date"],
            entry_price=entry_price,
            sl=sl,
            target=target,
        )

    # ==================================================
    # VALIDATION
    # ==================================================

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