from datetime import datetime
import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if __package__ in {None, ""}:
    sys.path.insert(0, str(PROJECT_ROOT))

from Backtest.backtest_engine import BacktestEngine, HistoricalDataLoader
from engines.backtest_report_engine import BacktestReportEngine
from engines.exit_engine import EMAExit, ExitEngine, SLExit, TargetExit
from engines.position_sizing_engine import PositionSizingEngine
from engines.trade_engine import TradeEngine
from Backtest.Strategies.Strategy_1_higher_high import config as strategy_config

if __package__ in {None, ""}:
    from Backtest.Strategies.Strategy_1_higher_high.config import (
        DEFAULT_DATA,
        DEFAULT_REPORTS,
        EXIT_EMA_PERIOD,
        INITIAL_CAPITAL,
        MAX_OPEN_POSITIONS,
        TRAIL_STOP_LOSS,
        TRAIL_STOP_LOSS_CANDLE_COUNT,
    )
    from Backtest.Strategies.Strategy_1_higher_high.exits import TrailingStopExit
    from Backtest.Strategies.Strategy_1_higher_high.reporting import (
        save_higher_high_artifacts,
    )
    from Backtest.Strategies.Strategy_1_higher_high.strategy import HigherHighStrategy
else:
    from .config import (
        DEFAULT_DATA,
        DEFAULT_REPORTS,
        EXIT_EMA_PERIOD,
        INITIAL_CAPITAL,
        MAX_OPEN_POSITIONS,
        TRAIL_STOP_LOSS,
        TRAIL_STOP_LOSS_CANDLE_COUNT,
    )
    from .exits import TrailingStopExit
    from .reporting import save_higher_high_artifacts
    from .strategy import HigherHighStrategy


STRATEGY_KEYS = (
    "CLOSE_THRESHOLD", "EMA_PERIOD", "PRICE_ABOVE_EMA_PERIOD", "EMA_FILTER",
    "SMALLER_EMA_PERIOD", "BIGGER_EMA_PERIOD", "USE_RSI", "RSI_PERIOD",
    "RSI_MIN_VALUE", "RSI_MAX_VALUE", "EMA_PERIOD_VOL", "TARGET_PERCENT",
    "RISK_PER_TRADE_PCT", "SIGNAL_RANKING", "MOMENTUM_LOOKBACK", "ATR_PERIOD",
    "MAX_EXTENSION_ATR", "MIN_REWARD_RISK",
)
RUN_KEYS = ("MAX_OPEN_POSITIONS", "EXIT_EMA_PERIOD", "TRAIL_STOP_LOSS", "TRAIL_STOP_LOSS_CANDLE_COUNT")


def default_settings():
    return {key: getattr(strategy_config, key) for key in STRATEGY_KEYS + RUN_KEYS}


def simulate(raw, settings, initial_capital=INITIAL_CAPITAL, transaction_cost_model=None,
             entry_start=None, entry_end=None, monte_carlo_simulations=5000):
    """Run in memory; pre-window data warms indicators but cannot open trades."""
    import pandas as pd

    unknown = set(settings) - set(STRATEGY_KEYS + RUN_KEYS)
    if unknown:
        raise ValueError(f"Unknown settings: {sorted(unknown)}")
    settings = {**default_settings(), **settings}
    strategy = HigherHighStrategy(**{key.lower(): settings[key] for key in STRATEGY_KEYS})
    strategy.entry_start = pd.Timestamp(entry_start) if entry_start is not None else None
    strategy.entry_end = pd.Timestamp(entry_end) if entry_end is not None else None
    if strategy.entry_start is not None and strategy.entry_end is not None and strategy.entry_start > strategy.entry_end:
        raise ValueError("entry_start must not be later than entry_end")
    if strategy.entry_end is not None:
        raw = raw.loc[pd.to_datetime(raw["date"]) <= strategy.entry_end].copy()
    sizing = PositionSizingEngine(initial_capital, settings["MAX_OPEN_POSITIONS"])
    exit_rules = [TargetExit(), SLExit()]
    if settings["TRAIL_STOP_LOSS"]:
        exit_rules.append(TrailingStopExit(settings["TRAIL_STOP_LOSS_CANDLE_COUNT"]))
    exit_rules.append(EMAExit(settings["EXIT_EMA_PERIOD"]))
    engine = BacktestEngine(
        strategy,
        TradeEngine(),
        ExitEngine(exit_rules),
        sizing,
        transaction_cost_model=transaction_cost_model,
    )
    trades = engine.run(raw).to_dataframe()
    report_engine = BacktestReportEngine(
        trades,
        initial_capital,
        "HigherHighStrategy",
        monte_carlo_simulations=monte_carlo_simulations,
        monte_carlo_seed=42,
    )
    return {
        "report": report_engine.generate(),
        "report_engine": report_engine,
        "trades": trades,
        "position_sizing": sizing,
        "settings": settings,
    }


def save_result(result, reports_root):
    from engines.backtest_report_engine.artifacts import ReportArtifactWriter

    report_engine = result["report_engine"]
    folder = ReportArtifactWriter(reports_root).write(
        result["report"], report_engine.curve_data(), report_engine._monte_carlo_paths
    )
    save_higher_high_artifacts(result["trades"], folder, result["report"].initial_capital)
    (folder / "settings.json").write_text(json.dumps(result["settings"], indent=2), encoding="utf-8")
    result["report_folder"] = folder
    return folder


def run(data_path=DEFAULT_DATA, reports_root=DEFAULT_REPORTS, initial_capital=INITIAL_CAPITAL,
        max_open_positions=MAX_OPEN_POSITIONS, transaction_cost_model=None, combination=None,
        settings=None):
    effective = default_settings()
    effective["MAX_OPEN_POSITIONS"] = max_open_positions
    if combination is not None:
        # Legacy sweeps keep their original optional-feature defaults.
        effective.update(RISK_PER_TRADE_PCT=None, SIGNAL_RANKING="alphabetical",
                         MAX_EXTENSION_ATR=None, MIN_REWARD_RISK=None)
        effective.update(combination)
    if settings is not None:
        effective.update(settings)
    result = simulate(HistoricalDataLoader.load_json(str(data_path)), effective,
                      initial_capital, transaction_cost_model)
    save_result(result, reports_root)
    result["combination"] = combination
    return result


def main(argv=()):
    parser = argparse.ArgumentParser(description="Higher High backtest and OHLCV experiments")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--single", action="store_true", help="Run the settings in config.py once")
    mode.add_argument("--experiments", action="store_true", help="Compare named experiment presets")
    parser.add_argument("--no-validation", action="store_true", help="Skip rolling yearly checks")
    args = parser.parse_args(argv)

    if args.experiments or (not args.single and not strategy_config.run_combinations
                           and strategy_config.RUN_EXPERIMENTS):
        from Backtest.Strategies.Strategy_1_higher_high.experiments import run_experiments
        run_experiments(validation=strategy_config.EXPERIMENT_VALIDATION and not args.no_validation)
        return

    if strategy_config.run_combinations and not args.single:
        if __package__ in {None, ""}:
            from Backtest.Strategies.Strategy_1_higher_high.run_combinations import (
                main as combinations_main,
            )
        else:
            from .run_combinations import main as combinations_main
        combinations_main()
        return

    result = run()
    print(result["report"])
    print(f"Completed trades      : {len(result['trades'])}")
    print(f"Report folder         : {result['report_folder'].resolve()}")


if __name__ == "__main__":
    print(datetime.now())
    main(sys.argv[1:])
    print(datetime.now())
