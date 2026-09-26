from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if __package__ in {None, ""}:
    sys.path.insert(0, str(PROJECT_ROOT))

from Backtest.backtest_engine import BacktestEngine, HistoricalDataLoader
from engines.backtest_report_engine import BacktestReportEngine
from engines.exit_engine import ExitEngine, SLExit, TargetExit, TimeExit
from engines.position_sizing_engine import PositionSizingEngine
from engines.trade_engine import TradeEngine

if __package__ in {None, ""}:
    from Backtest.Strategies.strategy_3_ORB.reporting import save_orb_artifacts
    from Backtest.Strategies.strategy_3_ORB.strategy import ORBStrategy
    from Backtest.Strategies.strategy_3_ORB.validate_results import validate_and_save
else:
    from .reporting import save_orb_artifacts
    from .strategy import ORBStrategy
    from .validate_results import validate_and_save


DEFAULT_DATA = PROJECT_ROOT / "artifacts/backtest/hist_data_5.json"
DEFAULT_REPORTS = PROJECT_ROOT / "artifacts/backtest_reports"


def run(data_path=DEFAULT_DATA, reports_root=DEFAULT_REPORTS, initial_capital=100_000.0,
        max_open_positions=4, transaction_cost_model=None, combination=None):
    raw = HistoricalDataLoader.load_json(str(data_path))
    sizing = PositionSizingEngine(initial_capital, max_open_positions)
    if combination is None:
        strategy = ORBStrategy()
    else:
        from .run_combinations import combination_to_strategy_kwargs

        strategy = ORBStrategy(**combination_to_strategy_kwargs(combination))
    forced_exit_label = strategy.forced_exit_time.strftime("%H:%M")
    engine = BacktestEngine(strategy, TradeEngine(),
                            ExitEngine([SLExit(), TargetExit(), TimeExit(forced_exit_label)]), sizing,
                            transaction_cost_model=transaction_cost_model)
    trades = engine.run(raw).to_dataframe()
    report_engine = BacktestReportEngine(trades, initial_capital, "ORBStrategy",
                                         reports_root=reports_root, monte_carlo_seed=42)
    report, folder = report_engine.generate_and_save()
    analysis = save_orb_artifacts(trades, folder)
    validation = validate_and_save(raw, trades, folder, orb_start=strategy.orb_start,
                                   orb_end=strategy.orb_end,
                                   forced_exit_time=strategy.forced_exit_time,
                                   risk_fraction=strategy.risk_fraction,
                                   sl_range_multiplier=strategy.sl_range_multiplier,
                                   target_range_multiplier=strategy.target_range_multiplier)
    return {"report": report, "report_folder": folder, "trades": trades,
            "analysis": analysis, "validation": validation, "position_sizing": sizing,
            "combination": combination}


def main():
    if __package__ in {None, ""}:
        from Backtest.Strategies.strategy_3_ORB import config as orb_config
    else:
        from . import config as orb_config

    if orb_config.run_combinations:
        if __package__ in {None, ""}:
            from Backtest.Strategies.strategy_3_ORB.run_combinations import main as combinations_main
        else:
            from .run_combinations import main as combinations_main
        combinations_main()
        return

    result = run()
    print(result["report"])
    print(f"Symbols               : {result['trades']['symbol'].nunique()}")
    print(f"Completed trades      : {len(result['trades'])}")
    print(f"Report folder         : {result['report_folder'].resolve()}")


if __name__ == "__main__":
    main()
