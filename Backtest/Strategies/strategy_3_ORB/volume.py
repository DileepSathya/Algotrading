"""Previous-day volume eligibility calculated without look-ahead."""

import pandas as pd


def calculate_historical_volume_filter(daily: pd.DataFrame, period: int) -> pd.DataFrame:
    """Attach previous volume, its earlier rolling average, and eligibility."""
    if period <= 0:
        raise ValueError("Volume period must be a positive integer")

    ordered = daily.copy()
    ordered["trading_date"] = pd.to_datetime(ordered["trading_date"]).dt.normalize()
    ordered = ordered.sort_values(["symbol", "trading_date"], kind="stable").reset_index(drop=True)
    grouped_volume = ordered.groupby("symbol", sort=False)["volume"]
    ordered["previous_day_volume"] = grouped_volume.shift(1)
    ordered["previous_volume_average"] = grouped_volume.transform(
        lambda values: values.shift(2).rolling(period, min_periods=period).mean()
    )
    ordered["volume_eligible"] = (
        ordered["previous_day_volume"].notna()
        & ordered["previous_volume_average"].notna()
        & ordered["previous_day_volume"].ge(ordered["previous_volume_average"])
    )
    return ordered
