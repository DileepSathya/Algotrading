import json
from pathlib import Path

import pandas as pd


def _performance_table(trades, key):
    rows = []
    for value, group in trades.groupby(key, dropna=False, sort=True):
        wins = int((group["pnl"] > 0).sum())
        count = len(group)
        rows.append({
            key: str(value),
            "trades": count,
            "wins": wins,
            "losses": int((group["pnl"] < 0).sum()),
            "win_rate": round(100 * wins / count, 2) if count else 0.0,
            "gross_pnl": round(float(group["gross_pnl"].sum()), 2),
            "transaction_cost": round(float(group["transaction_cost"].sum()), 2),
            "net_pnl": round(float(group["pnl"].sum()), 2),
        })
    return pd.DataFrame(rows)


def _empty_performance(key):
    return pd.DataFrame(columns=[
        key, "trades", "wins", "losses", "win_rate",
        "gross_pnl", "transaction_cost", "net_pnl",
    ])


def _statistics_table(series):
    statistics = series.describe(percentiles=[0.25, 0.5, 0.75]).to_dict()
    table = pd.DataFrame([
        {"statistic": key, "value": float(value)} for key, value in statistics.items()
    ])
    return statistics, table


def build_vwap_analysis(trades_df):
    trades = trades_df.copy()
    text_columns = {"symbol", "direction", "exit_reason"}
    required = [
        "symbol", "direction", "risk_per_unit", "vwap", "exit_timestamp",
        "exit_reason", "gross_pnl", "transaction_cost", "pnl",
    ]
    for column in required:
        if column not in trades:
            dtype = "object" if column in text_columns else "float64"
            trades[column] = pd.Series(dtype=dtype)
    trades["exit_timestamp"] = pd.to_datetime(trades["exit_timestamp"])

    if trades.empty:
        tables = {
            "direction": _empty_performance("direction"),
            "symbol": _empty_performance("symbol"),
            "exit_reason": _empty_performance("exit_reason"),
            "monthly": _empty_performance("period"),
            "yearly": _empty_performance("period"),
            "risk_per_unit": pd.DataFrame(columns=["statistic", "value"]),
            "vwap": pd.DataFrame(columns=["statistic", "value"]),
        }
        analysis = {
            "total_trades": 0,
            "direction": {},
            "symbol": {},
            "exit_reason": {},
            "monthly": {},
            "yearly": {},
            "risk_per_unit": {},
            "vwap": {},
        }
        return analysis, tables

    tables = {
        "direction": _performance_table(trades, "direction"),
        "symbol": _performance_table(trades, "symbol"),
        "exit_reason": _performance_table(trades, "exit_reason"),
    }
    monthly = trades.assign(period=trades["exit_timestamp"].dt.to_period("M").astype(str))
    yearly = trades.assign(period=trades["exit_timestamp"].dt.year.astype(str))
    tables["monthly"] = _performance_table(monthly, "period")
    tables["yearly"] = _performance_table(yearly, "period")
    risk_stats, tables["risk_per_unit"] = _statistics_table(trades["risk_per_unit"])
    vwap_stats, tables["vwap"] = _statistics_table(trades["vwap"])

    def keyed(table, key):
        return {
            str(row[key]): {name: value for name, value in row.items() if name != key}
            for row in table.to_dict(orient="records")
        }

    analysis = {
        "total_trades": int(len(trades)),
        "direction": keyed(tables["direction"], "direction"),
        "symbol": keyed(tables["symbol"], "symbol"),
        "exit_reason": keyed(tables["exit_reason"], "exit_reason"),
        "monthly": keyed(tables["monthly"], "period"),
        "yearly": keyed(tables["yearly"], "period"),
        "risk_per_unit": {key: round(float(value), 6) for key, value in risk_stats.items()},
        "vwap": {key: round(float(value), 6) for key, value in vwap_stats.items()},
    }
    return analysis, tables


def save_vwap_artifacts(trades_df, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    trades_df.to_csv(folder / "trades.csv", index=False)
    analysis, tables = build_vwap_analysis(trades_df)
    (folder / "vwap_analysis.json").write_text(
        json.dumps(analysis, indent=2), encoding="utf-8"
    )
    filenames = {
        "direction": "direction_performance.csv",
        "symbol": "symbol_performance.csv",
        "exit_reason": "exit_reason_performance.csv",
        "monthly": "monthly_performance.csv",
        "yearly": "yearly_performance.csv",
        "risk_per_unit": "risk_per_unit_statistics.csv",
        "vwap": "vwap_statistics.csv",
    }
    for key, filename in filenames.items():
        tables[key].to_csv(folder / filename, index=False)
    return analysis
