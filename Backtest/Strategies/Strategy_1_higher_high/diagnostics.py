"""Holding-time diagnostics, without introducing a new exit rule."""

import pandas as pd


def stagnation_analysis(trades, raw, checkpoints=(5, 10, 15), progress_pct=1.0):
    """Measure continuation after a checkpoint, conditional on still being open.

    Sessions are observed candles for that stock, excluding its entry candle.
    A trade exiting on the checkpoint is excluded: intraday exits happen before
    the hypothetical checkpoint-close decision. This is descriptive, not a
    portfolio backtest of a time exit (freed capital would change later trades).
    """
    columns = ["sessions", "group", "trades", "mean_progress_pct",
               "mean_remaining_return_pct", "continuation_positive_pct"]
    if trades.empty:
        return pd.DataFrame(columns=columns)
    prices = raw.copy()
    prices["date"] = pd.to_datetime(prices["date"])
    by_symbol = {symbol: group.sort_values("date") for symbol, group in prices.groupby("symbol")}
    rows = []
    for trade in trades.to_dict("records"):
        history = by_symbol.get(trade["symbol"])
        if history is None:
            continue
        following = history.loc[history.date > pd.Timestamp(trade["entry_date"])]
        for sessions in checkpoints:
            if len(following) < sessions:
                continue
            candle = following.iloc[sessions - 1]
            if candle.date >= pd.Timestamp(trade["exit_date"]) or candle.close <= 0:
                continue
            progress = 100 * (candle.close / trade["entry"] - 1)
            remaining = 100 * (trade["exit_price"] / candle.close - 1)
            rows.append(dict(sessions=sessions, group="stagnant" if progress < progress_pct else "progressing",
                             progress=progress, remaining=remaining, positive=remaining > 0))
    if not rows:
        return pd.DataFrame(columns=columns)
    result = pd.DataFrame(rows).groupby(["sessions", "group"], as_index=False).agg(
        trades=("progress", "size"), mean_progress_pct=("progress", "mean"),
        mean_remaining_return_pct=("remaining", "mean"), continuation_positive_pct=("positive", "mean")
    )
    result["continuation_positive_pct"] *= 100
    return result[columns].round(4)
