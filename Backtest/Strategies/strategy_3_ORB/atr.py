"""Daily OHLC aggregation and no-look-ahead Wilder ATR helpers."""

import pandas as pd


def aggregate_daily_ohlc(intraday: pd.DataFrame) -> pd.DataFrame:
    """Aggregate timestamped intraday bars into daily candles per symbol."""
    ordered = intraday.sort_values(["symbol", "timestamp"], kind="stable")
    return (
        ordered.groupby(["trading_date", "symbol"], as_index=False, sort=True)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
    )


def wilder_atr(true_range: pd.Series, period: int) -> pd.Series:
    """Return Wilder ATR seeded by the mean of the first ``period`` ranges."""
    if period <= 0:
        raise ValueError("ATR period must be a positive integer")

    values = pd.to_numeric(true_range, errors="coerce")
    result = pd.Series(float("nan"), index=values.index, dtype=float)
    if len(values) < period or values.iloc[:period].isna().any():
        return result

    previous_atr = float(values.iloc[:period].mean())
    result.iloc[period - 1] = previous_atr
    for position in range(period, len(values)):
        current_range = values.iloc[position]
        if pd.isna(current_range):
            previous_atr = float("nan")
        elif pd.isna(previous_atr):
            continue
        else:
            previous_atr = ((previous_atr * (period - 1)) + float(current_range)) / period
            result.iloc[position] = previous_atr
    return result


def calculate_historical_atr(daily: pd.DataFrame, period: int) -> pd.DataFrame:
    """Attach ATR using only completed daily candles before each output day."""
    ordered = daily.copy()
    ordered["trading_date"] = pd.to_datetime(ordered["trading_date"]).dt.normalize()
    ordered = ordered.sort_values(["symbol", "trading_date"], kind="stable").reset_index(drop=True)
    ordered["atr"] = float("nan")

    for _, symbol_rows in ordered.groupby("symbol", sort=False):
        previous_close = symbol_rows["close"].shift(1)
        true_range = pd.concat(
            [
                symbol_rows["high"] - symbol_rows["low"],
                (symbol_rows["high"] - previous_close).abs(),
                (symbol_rows["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        completed_atr = wilder_atr(true_range, period)
        ordered.loc[symbol_rows.index, "atr"] = completed_atr.shift(1).to_numpy()

    return ordered
