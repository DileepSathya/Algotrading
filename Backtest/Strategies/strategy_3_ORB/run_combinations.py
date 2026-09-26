"""Cartesian-product parameter sweeps for the ORB backtest workflow."""

from __future__ import annotations

import itertools
import json
import traceback
from datetime import time
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from . import config as orb_config

COMBINATION_PARAMETER_COLUMNS = (
    "ORB_START",
    "ORB_END",
    "FORCED_EXIT_TIME",
    "SL_RANGE_MULTIPLIER",
    "TARGET_RANGE_MULTIPLIER",
    "ENTRY_START_TIME",
    "ENTRY_END_TIME",
    "MAX_STOP_LOSSES_PER_DAY",
    "MAX_STOP_LOSSES_PER_SYMBOL_PER_DAY",
)

COMBINATION_METRIC_COLUMNS = (
    "TOTAL_RETURN_PCT",
    "TOTAL_TRADES",
    "WINNING_TRADES",
    "LOSING_TRADES",
    "PROFIT_FACTOR",
    "MAX_DRAWDOWN_PCT",
    "WIN_RATE_PCT",
    "WINNING_STREAK",
    "LOSING_STREAK",
    "CAGR",
)

COMBINATION_SUMMARY_COLUMNS = COMBINATION_PARAMETER_COLUMNS + COMBINATION_METRIC_COLUMNS

_TIME_KEYS = frozenset(
    {
        "ORB_START",
        "ORB_END",
        "FORCED_EXIT_TIME",
        "ENTRY_START_TIME",
        "ENTRY_END_TIME",
    }
)
_FLOAT_KEYS = frozenset({"SL_RANGE_MULTIPLIER", "TARGET_RANGE_MULTIPLIER"})
_INT_KEYS = frozenset({"MAX_STOP_LOSSES_PER_DAY", "MAX_STOP_LOSSES_PER_SYMBOL_PER_DAY"})


def _is_time(value: Any) -> bool:
    return isinstance(value, time)


def _validate_value(key: str, value: Any) -> None:
    if key in _TIME_KEYS:
        if not _is_time(value):
            raise TypeError(f"{key} values must be datetime.time instances, got {type(value)!r}")
        return
    if key in _FLOAT_KEYS:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"{key} values must be numeric, got {type(value)!r}")
        return
    if key in _INT_KEYS:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{key} values must be int, got {type(value)!r}")
        return
    raise KeyError(f"Unknown combination parameter: {key}")


def validate_combination_config(combination_config: dict[str, list[Any]]) -> None:
    missing = [key for key in COMBINATION_PARAMETER_COLUMNS if key not in combination_config]
    if missing:
        raise ValueError(f"COMBINATION_CONFIG missing required keys: {missing}")
    extra = sorted(set(combination_config) - set(COMBINATION_PARAMETER_COLUMNS))
    if extra:
        raise ValueError(f"COMBINATION_CONFIG has unknown keys: {extra}")
    for key in COMBINATION_PARAMETER_COLUMNS:
        values = combination_config[key]
        if not isinstance(values, list):
            raise TypeError(f"{key} must be a list, got {type(values)!r}")
        if not values:
            raise ValueError(f"{key} must not be an empty list")
        for value in values:
            _validate_value(key, value)


def generate_combinations(combination_config: dict[str, list[Any]]) -> list[dict[str, Any]]:
    validate_combination_config(combination_config)
    keys = COMBINATION_PARAMETER_COLUMNS
    value_lists = [combination_config[key] for key in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*value_lists)]


def combination_to_strategy_kwargs(combination: dict[str, Any]) -> dict[str, Any]:
    return {
        "orb_start": combination["ORB_START"],
        "orb_end": combination["ORB_END"],
        "forced_exit_time": combination["FORCED_EXIT_TIME"],
        "sl_range_multiplier": float(combination["SL_RANGE_MULTIPLIER"]),
        "target_range_multiplier": float(combination["TARGET_RANGE_MULTIPLIER"]),
        "entry_start_time": combination["ENTRY_START_TIME"],
        "entry_end_time": combination["ENTRY_END_TIME"],
        "max_stop_losses_per_day": int(combination["MAX_STOP_LOSSES_PER_DAY"]),
        "max_stop_losses_per_symbol_per_day": int(combination["MAX_STOP_LOSSES_PER_SYMBOL_PER_DAY"]),
    }


def combination_to_csv_row(combination: dict[str, Any]) -> dict[str, Any]:
    row = {}
    for key in COMBINATION_PARAMETER_COLUMNS:
        value = combination[key]
        if key in _TIME_KEYS:
            row[key] = value.strftime("%H:%M:%S")
        elif key in _FLOAT_KEYS:
            row[key] = float(value)
        else:
            row[key] = int(value)
    return row


def report_to_metric_csv_row(report) -> dict[str, Any]:
    """Map BacktestReport fields to consolidated CSV metric columns."""
    return {
        "TOTAL_RETURN_PCT": float(report.total_return),
        "TOTAL_TRADES": int(report.total_trades),
        "WINNING_TRADES": int(report.winning_trades),
        "LOSING_TRADES": int(report.losing_trades),
        "PROFIT_FACTOR": float(report.profit_factor),
        "MAX_DRAWDOWN_PCT": float(report.max_drawdown_percent),
        "WIN_RATE_PCT": float(report.win_rate),
        "WINNING_STREAK": int(report.winning_streak),
        "LOSING_STREAK": int(report.losing_streak),
        "CAGR": float(report.cagr),
    }


def build_combination_summary_row(combination: dict[str, Any], report) -> dict[str, Any]:
    return {
        **combination_to_csv_row(combination),
        **report_to_metric_csv_row(report),
    }


def consolidated_report_path(reports_root: Path) -> Path:
    return Path(reports_root) / "ORBStrategy" / "combination_summary.csv"


def save_consolidated_combination_csv(rows: Iterable[dict[str, Any]], reports_root: Path) -> Path:
    path = consolidated_report_path(reports_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(list(rows), columns=list(COMBINATION_SUMMARY_COLUMNS))
    frame.to_csv(path, index=False)
    return path


def run_combination_batch(
    data_path=None,
    reports_root=None,
    initial_capital=100_000.0,
    max_open_positions=4,
    transaction_cost_model=None,
    combination_config=None,
):
    from .run_backtest import DEFAULT_DATA, DEFAULT_REPORTS, run

    data_path = DEFAULT_DATA if data_path is None else data_path
    reports_root = DEFAULT_REPORTS if reports_root is None else reports_root
    combination_config = orb_config.COMBINATION_CONFIG if combination_config is None else combination_config

    combinations = generate_combinations(combination_config)
    expected = len(combinations)
    completed_rows = []
    failures = []

    print(f"Expected combinations : {expected}")
    print("Running combination batch...")

    for index, combination in enumerate(combinations, start=1):
        label = f"combination {index}/{expected}"
        try:
            result = run(
                data_path=data_path,
                reports_root=reports_root,
                initial_capital=initial_capital,
                max_open_positions=max_open_positions,
                transaction_cost_model=transaction_cost_model,
                combination=combination,
            )
            completed_rows.append(build_combination_summary_row(combination, result["report"]))
            print(f"[OK] {label} — completed {len(completed_rows)}/{expected}")
        except Exception as exc:
            failures.append(
                {
                    "combination": combination_to_csv_row(combination),
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )
            print(f"[FAILED] {label} — completed {len(completed_rows)}/{expected}: {exc}")

    summary_path = None
    if completed_rows:
        summary_path = save_consolidated_combination_csv(completed_rows, reports_root)

    failures_path = Path(reports_root) / "ORBStrategy" / "combination_failures.json"
    if failures:
        failures_path.parent.mkdir(parents=True, exist_ok=True)
        failures_path.write_text(json.dumps(failures, indent=2), encoding="utf-8")

    return {
        "total_combinations": len(combinations),
        "completed": len(completed_rows),
        "failed": len(failures),
        "summary_csv": summary_path,
        "failures_path": failures_path if failures else None,
        "failures": failures,
    }


def main():
    if not orb_config.run_combinations:
        raise RuntimeError("run_combinations is False; use run_backtest.main() for a single run.")
    result = run_combination_batch()
    print("--- Combination batch summary ---")
    print(f"Expected combinations : {result['total_combinations']}")
    print(f"Completed combinations: {result['completed']}")
    print(f"Failed combinations   : {result['failed']}")
    if result["summary_csv"] is not None:
        print(f"Combination summary CSV: {result['summary_csv'].resolve()}")
    if result["failures"]:
        print(f"Failure details       : {result['failures_path'].resolve()}")


if __name__ == "__main__":
    main()
