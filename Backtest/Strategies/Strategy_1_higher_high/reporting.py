from pathlib import Path

import pandas as pd


PERFORMANCE_COLUMNS = [
    "trades",
    "wins",
    "losses",
    "win_rate",
    "gross_pnl",
    "transaction_cost",
    "net_pnl",
]


def _performance_table(trades: pd.DataFrame, key: str) -> pd.DataFrame:
    rows = []
    for value, group in trades.groupby(key, dropna=False, sort=True):
        wins = int((group["pnl"] > 0).sum())
        count = len(group)
        rows.append(
            {
                key: str(value),
                "trades": count,
                "wins": wins,
                "losses": int((group["pnl"] < 0).sum()),
                "win_rate": round(100 * wins / count, 2) if count else 0.0,
                "gross_pnl": round(float(group["gross_pnl"].sum()), 2),
                "transaction_cost": round(float(group["transaction_cost"].sum()), 2),
                "net_pnl": round(float(group["pnl"].sum()), 2),
            }
        )
    return pd.DataFrame(rows, columns=[key, *PERFORMANCE_COLUMNS])


def build_higher_high_tables(trades_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    trades = trades_df.copy()
    for column in ("symbol", "direction", "exit_reason"):
        if column not in trades:
            trades[column] = pd.Series(dtype="object")
    for column in ("gross_pnl", "transaction_cost", "pnl"):
        if column not in trades:
            trades[column] = pd.Series(dtype="float64")
    if "exit_date" not in trades:
        trades["exit_date"] = pd.Series(dtype="datetime64[ns]")
    trades["exit_date"] = pd.to_datetime(trades["exit_date"])

    tables = {
        "direction": _performance_table(trades, "direction"),
        "symbol": _performance_table(trades, "symbol"),
        "exit_reason": _performance_table(trades, "exit_reason"),
    }
    monthly = trades.assign(period=trades["exit_date"].dt.to_period("M").astype(str))
    yearly = trades.assign(period=trades["exit_date"].dt.year.astype("Int64").astype(str))
    tables["monthly"] = _performance_table(monthly, "period")
    tables["yearly"] = _performance_table(yearly, "period")
    return tables


def _save_unavailable_monte_carlo_chart(folder: Path, initial_capital: float) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    figure, axis = plt.subplots(figsize=(12, 6))
    axis.axhline(initial_capital, color="gray", linestyle="--", label="Initial capital")
    axis.text(
        0.5,
        0.5,
        "Monte Carlo simulation requires at least two completed trades",
        ha="center",
        va="center",
        transform=axis.transAxes,
    )
    axis.set_title("HigherHighStrategy - Monte Carlo Equity")
    axis.set_xlabel("Completed trades")
    axis.set_ylabel("Capital")
    axis.legend()
    figure.tight_layout()
    figure.savefig(folder / "monte_carlo_equity.png", dpi=150)
    plt.close(figure)


def save_higher_high_artifacts(
    trades_df: pd.DataFrame,
    folder,
    initial_capital: float,
) -> None:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    trades_df.to_csv(folder / "trades.csv", index=False)

    filenames = {
        "direction": "direction_performance.csv",
        "symbol": "symbol_performance.csv",
        "exit_reason": "exit_reason_performance.csv",
        "monthly": "monthly_performance.csv",
        "yearly": "yearly_performance.csv",
    }
    for key, table in build_higher_high_tables(trades_df).items():
        table.to_csv(folder / filenames[key], index=False)

    monte_carlo_path = folder / "monte_carlo_equity.png"
    if not monte_carlo_path.exists():
        _save_unavailable_monte_carlo_chart(folder, initial_capital)
