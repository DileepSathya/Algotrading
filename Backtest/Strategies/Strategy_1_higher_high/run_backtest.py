from datetime import datetime
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

if __package__ in {None, ""}:
    from Backtest.Strategies.Strategy_1_higher_high.config import (
        DEFAULT_DATA,
        DEFAULT_REPORTS,
        EXIT_EMA_PERIOD,
        INITIAL_CAPITAL,
        MAX_OPEN_POSITIONS,
    )
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
    )
    from .reporting import save_higher_high_artifacts
    from .strategy import HigherHighStrategy


def run(
    data_path=DEFAULT_DATA,
    reports_root=DEFAULT_REPORTS,
    initial_capital=INITIAL_CAPITAL,
    max_open_positions=MAX_OPEN_POSITIONS,
    transaction_cost_model=None,
    combination=None,
):
    raw = HistoricalDataLoader.load_json(str(data_path))
    exit_ema_period = EXIT_EMA_PERIOD
    if combination is None:
        strategy = HigherHighStrategy()
    else:
        from .run_combinations import (
            combination_to_run_settings,
            combination_to_strategy_kwargs,
        )

        strategy = HigherHighStrategy(**combination_to_strategy_kwargs(combination))
        run_settings = combination_to_run_settings(combination)
        max_open_positions = run_settings["max_open_positions"]
        exit_ema_period = run_settings["exit_ema_period"]
    sizing = PositionSizingEngine(initial_capital, max_open_positions)
    engine = BacktestEngine(
        strategy,
        TradeEngine(),
        ExitEngine([TargetExit(), SLExit(), EMAExit(exit_ema_period)]),
        sizing,
        transaction_cost_model=transaction_cost_model,
    )
    trades = engine.run(raw).to_dataframe()
    report_engine = BacktestReportEngine(
        trades,
        initial_capital,
        "HigherHighStrategy",
        reports_root=reports_root,
        monte_carlo_seed=42,
    )
    report, folder = report_engine.generate_and_save()
    save_higher_high_artifacts(trades, folder, initial_capital)
    return {
        "report": report,
        "report_folder": folder,
        "trades": trades,
        "position_sizing": sizing,
        "combination": combination,
    }


def main():
    if __package__ in {None, ""}:
        from Backtest.Strategies.Strategy_1_higher_high import config as strategy_config
    else:
        from . import config as strategy_config

    if strategy_config.run_combinations:
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
    main()
    print(datetime.now())
