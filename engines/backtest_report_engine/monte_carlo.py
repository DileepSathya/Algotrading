"""Bootstrap completed trade P&L to describe backtest outcome sensitivity."""

import numpy as np


def simulate_trade_paths(trades, initial_capital, simulations=5000, seed=42):
    """Return a summary and simulated equity paths, including starting capital."""
    if not isinstance(simulations, int) or simulations <= 0:
        raise ValueError("monte_carlo_simulations must be a positive integer")
    if not isinstance(seed, int) or seed < 0:
        raise ValueError("monte_carlo_seed must be a non-negative integer")
    if not np.isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("Initial capital must be finite and greater than zero")

    trade_count = len(trades)
    base = {
        "method": "trade_bootstrap_with_replacement",
        "simulations": simulations,
        "seed": seed,
        "trade_count": trade_count,
    }
    if trade_count < 2:
        return {"status": "insufficient_trades", **base}, None

    pnl = np.asarray(trades["pnl"], dtype=float)
    if not np.isfinite(pnl).all():
        raise ValueError("Completed trade P&L must contain only finite values")

    rng = np.random.default_rng(seed)
    sampled = rng.choice(pnl, size=(simulations, trade_count), replace=True)
    paths = np.column_stack((
        np.full(simulations, initial_capital),
        initial_capital + sampled.cumsum(axis=1),
    ))
    peaks = np.maximum.accumulate(paths, axis=1)
    max_drawdown = ((peaks - paths) / peaks * 100).max(axis=1)
    endings = paths[:, -1]

    return {
        "status": "available",
        **base,
        "median_ending_capital": round(float(np.median(endings)), 2),
        "ending_capital_5th_percentile": round(float(np.percentile(endings, 5)), 2),
        "ending_capital_95th_percentile": round(float(np.percentile(endings, 95)), 2),
        "median_max_drawdown_percent": round(float(np.median(max_drawdown)), 2),
        "max_drawdown_95th_percentile": round(float(np.percentile(max_drawdown, 95)), 2),
        "probability_of_loss_percent": round(float(np.mean(endings < initial_capital) * 100), 2),
    }, paths
