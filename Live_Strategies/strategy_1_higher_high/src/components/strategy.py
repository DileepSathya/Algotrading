
import math
from pathlib import Path

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
    PUT_SL_PCT,
    PUT_TG_PCT,
    PUT_LOT_SIZE,
)

from .models import StrategySignal


class HigherHighStrategy:
    """Higher High trading strategy."""

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
        self.ema_column = f"{ema_period}_ema"

        self.ema_filter = ema_filter
        self.smaller_ema_period = smaller_ema_period
        self.bigger_ema_period = bigger_ema_period
        self.smaller_ema_column = f"{smaller_ema_period}_ema"
        self.bigger_ema_column = f"{bigger_ema_period}_ema"

        self.use_rsi = use_rsi
        self.rsi_period = rsi_period
        self.rsi_min_value = rsi_min_value
        self.rsi_max_value = rsi_max_value
        self.rsi_column = f"rsi_{rsi_period}"

        self.ema_period_vol = ema_period_vol
        self.target_percent = target_percent

        for name, value in (
            ("risk_per_trade_pct", risk_per_trade_pct),
            ("max_extension_atr", max_extension_atr),
            ("min_reward_risk", min_reward_risk),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(
                    f"{name} must be a finite positive number or None"
                )

        if risk_per_trade_pct is not None and risk_per_trade_pct > 100:
            raise ValueError("risk_per_trade_pct must be at most 100")

        for name, value in (
            ("momentum_lookback", momentum_lookback),
            ("atr_period", atr_period),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")

        if signal_ranking not in {
            "alphabetical", "momentum", "relative_volume"
        }:
            raise ValueError(
                "signal_ranking must be alphabetical, momentum or relative_volume"
            )

        self.risk_per_trade_pct = risk_per_trade_pct
        self.signal_ranking = signal_ranking
        self.momentum_lookback = momentum_lookback
        self.atr_period = atr_period
        self.max_extension_atr = max_extension_atr
        self.min_reward_risk = min_reward_risk

        self.entry_start = None
        self.entry_end = None

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate indicators and generate entry conditions."""

        self._validate_input(df)

        data = df.copy()
        data["date"] = pd.to_datetime(data["date"])
        data = data.sort_values(["symbol", "date"]).reset_index(drop=True)

        grouped = data.groupby("symbol", sort=False)

        data["prev_day_close"] = grouped["close"].shift(1)
        data["prev_day_high"] = grouped["high"].shift(1)
        data["prev_day_low"] = grouped["low"].shift(1)
        data["prev_day_vol"] = grouped["volume"].shift(1)

        data["range"] = (
            (data["high"] - data["low"]) / data["low"]
        ) * 100

        for period, column in (
            (self.ema_period, self.ema_column),
            (self.smaller_ema_period, self.smaller_ema_column),
            (self.bigger_ema_period, self.bigger_ema_column),
        ):
            data[column] = (
                data.groupby("symbol")["close"]
                .transform(
                    lambda x: x.ewm(span=period, adjust=False).mean()
                )
                .round(2)
            )

        data[self.rsi_column] = (
            data.groupby("symbol")["close"]
            .transform(self._calculate_rsi)
            .round(2)
        )

        data["close_>_70th_range"] = (
            data["close"]
            >= data["low"]
            + (data["high"] - data["low"]) * self.close_threshold
        )

        data["20_vol_ma"] = (
            data.groupby("symbol")["volume"]
            .transform(
                lambda x: x.ewm(
                    span=self.ema_period_vol,
                    adjust=False,
                ).mean()
            )
            .groupby(data["symbol"])
            .shift(1)
            .round(2)
        )

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

        true_range = pd.concat(
            [
                data["high"] - data["low"],
                (data["high"] - data["prev_day_close"]).abs(),
                (data["low"] - data["prev_day_close"]).abs(),
            ],
            axis=1,
        ).max(axis=1)

        data["atr"] = true_range.groupby(data["symbol"]).transform(
            lambda x: x.rolling(
                self.atr_period,
                min_periods=self.atr_period,
            ).mean()
        )

        previous_close = data.groupby("symbol")["close"].shift(
            self.momentum_lookback
        )

        data["momentum_return"] = (
            data["close"] / previous_close.where(previous_close > 0) - 1
        ) * 100

        data["relative_volume"] = (
            data["volume"] / data["20_vol_ma"].where(data["20_vol_ma"] > 0)
        )

        dropna_columns = list(data.columns)

        if not self.use_rsi:
            dropna_columns.remove(self.rsi_column)

        return data.dropna(subset=dropna_columns)

    def generate_signal(self, row: pd.Series) -> StrategySignal | None:
        """Generate a trade signal from a candle."""

        if not bool(row["trade_signal"]):
            return None

        date = pd.Timestamp(row["date"])

        if self.entry_start is not None and date < self.entry_start:
            return None

        if self.entry_end is not None and date > self.entry_end:
            return None

        if self.signal_ranking != "alphabetical":
            column = (
                "momentum_return"
                if self.signal_ranking == "momentum"
                else "relative_volume"
            )

            if not math.isfinite(float(row.get(column, float("nan")))):
                return None

        entry_price = float(row["close"])
        sl = min(float(row["low"]), float(row[self.ema_column]))

        target = entry_price * (1 + self.target_percent / 100)

        risk = entry_price - sl
        reward_risk = (
            (target - entry_price) / risk
            if risk > 0
            else float("nan")
        )

        atr = float(row.get("atr", float("nan")))
        extension = (
            (entry_price - float(row[self.ema_column])) / atr
            if atr > 0
            else float("nan")
        )

        if self.max_extension_atr is not None and (
            not math.isfinite(extension)
            or extension > self.max_extension_atr
        ):
            return None

        if self.min_reward_risk is not None and (
            not math.isfinite(reward_risk)
            or reward_risk < self.min_reward_risk
        ):
            return None

        if self.risk_per_trade_pct is not None and (
            not math.isfinite(risk) or risk <= 0
        ):
            return None

        return StrategySignal(
            symbol=str(row["symbol"]),
            entry_date=row["date"],
            entry_price=entry_price,
            sl=sl,
            target=target,
            risk_per_unit=(
                risk if self.risk_per_trade_pct is not None else None
            ),
            risk_fraction=(
                self.risk_per_trade_pct / 100
                if self.risk_per_trade_pct is not None
                else None
            ),
            metadata={
                "initial_risk_per_unit": risk,
                "entry_reward_risk": reward_risk,
                "entry_extension_atr": extension,
                "entry_relative_volume": row.get(
                    "relative_volume", float("nan")
                ),
                "entry_momentum_return": row.get(
                    "momentum_return", float("nan")
                ),
            },
        )

    def rank_entry_candidates(self, rows):
        """Rank entry candidates without changing exit order."""

        if self.signal_ranking == "alphabetical":
            return rows

        column = (
            "momentum_return"
            if self.signal_ranking == "momentum"
            else "relative_volume"
        )

        def key(row):
            value = float(row.get(column, float("nan")))
            return (
                -value if math.isfinite(value) else float("inf"),
                str(row["symbol"]),
            )

        return sorted(rows, key=key)

    
    def save_signals_to_csv(self, df: pd.DataFrame, option_provider=None, output_path=None) -> None:
        """Generate entry signals and save them to CSV."""

        output_path = Path(output_path) if output_path is not None else Path(
            r"D:\FM\ALGOTRADING\Live_Strategies\strategy_1_higher_high"
            r"\artifacts\trades\higher_high_signals.csv"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = self.prepare_data(df)
        signals = []

        for _, row in data.iterrows():
            signal = self.generate_signal(row)

            if signal is not None:
                signals.append({
                    "date": signal.entry_date,
                    "symbol": signal.symbol,
                    "symbol_entry_price": signal.entry_price,
                    "symbol_SL_price": signal.sl,
                    "symbol_TG_price": signal.target,
                })

        from src import logger
        option_columns = ['put_symbol', 'put_entry_price', 'expiry', 'expiry_timestamp', 'strike',
                          'delta', 'iv', 'expiry_month']
        today = pd.Timestamp.now(tz="Asia/Kolkata").date()
        current_month_signals_to_enrich = []
        for signal in signals:
            signal.update({column: None for column in option_columns})
            signal['put_prev_day_high'] = None
            day = pd.Timestamp(signal['date'])
            if day.tzinfo is not None:
                day = day.tz_convert('Asia/Kolkata')
            if (day.year, day.month) == (today.year, today.month):
                current_month_signals_to_enrich.append(signal)
        if current_month_signals_to_enrich and option_provider is None:
            try:
                from .historical_put_option import HistoricalOptionData
                option_provider = HistoricalOptionData()
            except Exception:
                logger.exception('Option provider initialization failed; retaining stock signals')
        option_cache = {}
        for signal in current_month_signals_to_enrich:
            day = pd.Timestamp(signal['date'])
            if day.tzinfo is not None:
                day = day.tz_convert('Asia/Kolkata')
            key = (signal['symbol'], day.date().isoformat())
            if key not in option_cache:
                try:
                    option_cache[key] = option_provider.select_for_signal(*key) if option_provider is not None else {}
                except Exception:
                    logger.exception('Option enrichment failed for %s on %s', *key)
                    option_cache[key] = {}
            signal.update({column: option_cache[key].get(column) for column in option_columns})
            signal['put_prev_day_high'] = option_cache[key].get('put_prev_day_high')
        for signal in signals:
            entry = signal.get('put_entry_price')
            try:
                entry = float(entry)
                if not math.isfinite(entry) or entry <= 0:
                    entry = None
            except (TypeError, ValueError):
                entry = None
            signal['put_lot_size'] = PUT_LOT_SIZE
            signal['put_SL_price'] = entry * (1 - PUT_SL_PCT / 100) if entry is not None else None
            if PUT_TG_PCT == 'prev_day_high':
                signal['put_TG_price'] = signal.get('put_prev_day_high') if entry is not None else None
            else:
                signal['put_TG_price'] = entry * (1 + PUT_TG_PCT / 100) if entry is not None else None
        columns = ['date', 'symbol', 'symbol_entry_price', 'symbol_SL_price',
                   'symbol_TG_price', *option_columns, 'put_SL_price', 'put_TG_price', 'put_lot_size']
        signals_df = pd.DataFrame(signals, columns=columns)

        signals_df = signals_df.sort_values(
            ["date"]
        ).reset_index(drop=True)

        signals_df.to_csv(output_path, index=False)

        signal_dates = pd.to_datetime(signals_df["date"])
        if signal_dates.dt.tz is not None:
            signal_dates = signal_dates.dt.tz_convert("Asia/Kolkata")

        current_month_signals = signals_df.loc[
            (signal_dates.dt.year == today.year)
            & (signal_dates.dt.month == today.month)
        ]
        current_day_signals = signals_df.loc[
            signal_dates.dt.date == today
        ]

        for filename, selected_signals in (
            ("current_month_signals.csv", current_month_signals),
            ("current_day_signals.csv", current_day_signals),
        ):
            selected_path = output_path.with_name(filename)
            selected_signals.to_csv(selected_path, index=False)
            print(f"Saved {len(selected_signals)} signals to: {selected_path}")

        print(f"Generated {len(signals_df)} signals.")
        print(f"Saved to: {output_path}")


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
    def _validate_input(df: pd.DataFrame) -> None:
        required_columns = {
            "date", "symbol", "open", "high", "low", "close", "volume"
        }

        missing_columns = required_columns - set(df.columns)

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {sorted(missing_columns)}"
            )
