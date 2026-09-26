from pathlib import Path
import sys
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if __package__ in {None, ""}:
    sys.path.insert(0, str(PROJECT_ROOT))

from Backtest.backtest_engine import BacktestEngine, HistoricalDataLoader
from engines.backtest_report_engine import BacktestReportEngine
from engines.exit_engine import ExitEngine, SLExit, TargetExit, TimeExit
from engines.position_sizing_engine import PositionSizingEngine
from engines.trade_engine import TradeEngine

if __package__ in {None, ""}:
    from Backtest.Strategies.strategy_4_VWAP.config import (
        DEFAULT_DATA, DEFAULT_REPORTS, EMA_PERIOD, FORCED_EXIT_TIME,
        INITIAL_CAPITAL, MAX_OPEN_POSITIONS,
    )
    from Backtest.Strategies.strategy_4_VWAP.exits import EMACrossExit
    from Backtest.Strategies.strategy_4_VWAP.reporting import save_vwap_artifacts
    from Backtest.Strategies.strategy_4_VWAP.strategy import VWAPStrategy
    from Backtest.Strategies.strategy_4_VWAP.validate_results import validate_and_save
else:
    from .config import (
        DEFAULT_DATA, DEFAULT_REPORTS, EMA_PERIOD, FORCED_EXIT_TIME,
        INITIAL_CAPITAL, MAX_OPEN_POSITIONS,
    )
    from .exits import EMACrossExit
    from .reporting import save_vwap_artifacts
    from .strategy import VWAPStrategy
    from .validate_results import validate_and_save


def run(
    data_path=DEFAULT_DATA,
    reports_root=DEFAULT_REPORTS,
    initial_capital=INITIAL_CAPITAL,
    max_open_positions=MAX_OPEN_POSITIONS,
    transaction_cost_model=None,
):
    raw = HistoricalDataLoader.load_json(str(data_path))
    strategy = VWAPStrategy(ema_period=EMA_PERIOD)
    sizing = PositionSizingEngine(initial_capital, max_open_positions)
    rules = [
        SLExit(),
        TargetExit(),
        EMACrossExit(strategy.ema_period),
        TimeExit(FORCED_EXIT_TIME.strftime("%H:%M")),
    ]
    engine = BacktestEngine(
        strategy,
        TradeEngine(),
        ExitEngine(rules),
        sizing,
        transaction_cost_model=transaction_cost_model,
    )
    trades = engine.run(raw).to_dataframe()
    report_engine = BacktestReportEngine(
        trades, initial_capital, "VWAPStrategy", reports_root=reports_root,
        monte_carlo_seed=42,
    )
    report, folder = report_engine.generate_and_save()
    analysis = save_vwap_artifacts(trades, folder)
    validation = validate_and_save(
        raw,
        trades,
        folder,
        target_pct_from_entry=strategy.target_pct_from_entry,
        forced_exit_time=strategy.forced_exit_time,
        signal_start_time=strategy.signal_start_time,
        risk_fraction=strategy.risk_fraction,
        ema_period=strategy.ema_period,
    )
    return {
        "report": report,
        "report_folder": folder,
        "trades": trades,
        "analysis": analysis,
        "validation": validation,
        "position_sizing": sizing,
    }


def main():
    result = run()
    print(result["report"])
    print(f"Completed trades      : {len(result['trades'])}")
    print(f"Report folder         : {result['report_folder'].resolve()}")


if __name__ == "__main__":
    print(datetime.now())
    main()

    print(datetime.now())
