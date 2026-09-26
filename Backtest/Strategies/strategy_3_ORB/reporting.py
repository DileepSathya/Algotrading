import json
from pathlib import Path

import pandas as pd


def _performance_table(trades, key):
    rows = []
    for value, group in trades.groupby(key, dropna=False, sort=True):
        wins = int((group["pnl"] > 0).sum())
        count = len(group)
        rows.append({key: str(value), "trades": count, "wins": wins,
                     "losses": int((group["pnl"] < 0).sum()),
                     "win_rate": round(100 * wins / count, 2) if count else 0.0,
                     "gross_pnl": round(float(group["gross_pnl"].sum()), 2),
                     "transaction_cost": round(float(group["transaction_cost"].sum()), 2),
                     "net_pnl": round(float(group["pnl"].sum()), 2)})
    return pd.DataFrame(rows)


def build_orb_analysis(trades_df):
    trades = trades_df.copy()
    required = ["symbol", "direction", "orb_range", "exit_timestamp", "exit_reason",
                "gross_pnl", "transaction_cost", "pnl"]
    for column in required:
        if column not in trades:
            trades[column] = pd.Series(dtype="object" if column in {"symbol", "direction", "exit_reason"} else "float64")
    trades["exit_timestamp"] = pd.to_datetime(trades["exit_timestamp"])
    if trades.empty:
        empty_performance = lambda key: pd.DataFrame(columns=[key, "trades", "wins", "losses", "win_rate",
                                                               "gross_pnl", "transaction_cost", "net_pnl"])
        tables = {"direction": empty_performance("direction"), "symbol": empty_performance("symbol"),
                  "exit_reason": empty_performance("exit_reason"), "monthly": empty_performance("period"),
                  "yearly": empty_performance("period"),
                  "orb_range": pd.DataFrame(columns=["statistic", "value"])}
        return {"total_trades": 0, "direction": {}, "symbol": {}, "exit_reason": {},
                "monthly": {}, "yearly": {}, "orb_range": {}}, tables
    tables = {
        "direction": _performance_table(trades, "direction"),
        "symbol": _performance_table(trades, "symbol"),
        "exit_reason": _performance_table(trades, "exit_reason"),
    }
    monthly_source = trades.assign(period=trades["exit_timestamp"].dt.to_period("M").astype(str))
    yearly_source = trades.assign(period=trades["exit_timestamp"].dt.year.astype(str))
    tables["monthly"] = _performance_table(monthly_source, "period")
    tables["yearly"] = _performance_table(yearly_source, "period")
    range_stats = trades["orb_range"].describe(percentiles=[0.25, 0.5, 0.75]).to_dict()
    tables["orb_range"] = pd.DataFrame([{"statistic": key, "value": float(value)}
                                         for key, value in range_stats.items()])

    def keyed(table, key):
        return {str(row[key]): {k: v for k, v in row.items() if k != key}
                for row in table.to_dict(orient="records")}

    analysis = {
        "total_trades": int(len(trades)),
        "direction": keyed(tables["direction"], "direction"),
        "symbol": keyed(tables["symbol"], "symbol"),
        "exit_reason": keyed(tables["exit_reason"], "exit_reason"),
        "monthly": keyed(tables["monthly"], "period"),
        "yearly": keyed(tables["yearly"], "period"),
        "orb_range": {k: round(float(v), 6) for k, v in range_stats.items()},
    }
    return analysis, tables


def save_orb_artifacts(trades_df, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    trades_df.to_csv(folder / "trades.csv", index=False)
    analysis, tables = build_orb_analysis(trades_df)
    (folder / "orb_analysis.json").write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    filenames = {"direction": "direction_performance.csv", "symbol": "symbol_performance.csv",
                 "exit_reason": "exit_reason_performance.csv", "monthly": "monthly_performance.csv",
                 "yearly": "yearly_performance.csv", "orb_range": "orb_range_statistics.csv"}
    for key, filename in filenames.items():
        tables[key].to_csv(folder / filename, index=False)
    return analysis
