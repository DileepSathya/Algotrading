import tempfile
import unittest
from datetime import time
from pathlib import Path
from unittest import mock

import pandas as pd

from Backtest.Strategies.strategy_3_ORB import config as orb_config
from Backtest.Strategies.strategy_3_ORB.run_backtest import main as run_backtest_main, run
from Backtest.Strategies.strategy_3_ORB.run_combinations import (
    COMBINATION_SUMMARY_COLUMNS,
    build_combination_summary_row,
    combination_to_csv_row,
    combination_to_strategy_kwargs,
    consolidated_report_path,
    generate_combinations,
    report_to_metric_csv_row,
    run_combination_batch,
    save_consolidated_combination_csv,
    validate_combination_config,
)
from engines.backtest_report_engine.models.report import BacktestReport
from Backtest.Strategies.strategy_3_ORB.strategy import ORBStrategy


def sample_report(**overrides):
    defaults = dict(
        strategy_name="ORBStrategy",
        initial_capital=100_000.0,
        ending_capital=112_500.0,
        total_pnl=12_500.0,
        total_return=12.5,
        average_pnl=250.0,
        total_trades=50,
        winning_trades=28,
        losing_trades=22,
        win_rate=56.0,
        average_win=500.0,
        average_loss=-200.0,
        profit_factor=1.85,
        max_drawdown=5_000.0,
        max_drawdown_percent=8.2,
        winning_streak=5,
        losing_streak=3,
        cagr=9.1,
        sharpe_ratio=1.2,
        monte_carlo={"status": "unavailable"},
    )
    defaults.update(overrides)
    return BacktestReport(**defaults)


def sample_config():
    return {
        "ORB_START": [time(9, 15), time(9, 20)],
        "ORB_END": [time(9, 30)],
        "FORCED_EXIT_TIME": [time(14, 30)],
        "SL_RANGE_MULTIPLIER": [1.0, 1.5],
        "TARGET_RANGE_MULTIPLIER": [1.5],
        "ENTRY_START_TIME": [time(9, 30)],
        "ENTRY_END_TIME": [time(11, 30)],
        "MAX_STOP_LOSSES_PER_DAY": [2],
        "MAX_STOP_LOSSES_PER_SYMBOL_PER_DAY": [2],
    }


class ORBCombinationUtilityTests(unittest.TestCase):
    def test_cartesian_product_size_and_values(self):
        combos = generate_combinations(sample_config())
        self.assertEqual(len(combos), 4)
        self.assertEqual(
            combos[0],
            {
                "ORB_START": time(9, 15),
                "ORB_END": time(9, 30),
                "FORCED_EXIT_TIME": time(14, 30),
                "SL_RANGE_MULTIPLIER": 1.0,
                "TARGET_RANGE_MULTIPLIER": 1.5,
                "ENTRY_START_TIME": time(9, 30),
                "ENTRY_END_TIME": time(11, 30),
                "MAX_STOP_LOSSES_PER_DAY": 2,
                "MAX_STOP_LOSSES_PER_SYMBOL_PER_DAY": 2,
            },
        )
        starts = {combo["ORB_START"] for combo in combos}
        multipliers = {combo["SL_RANGE_MULTIPLIER"] for combo in combos}
        self.assertEqual(starts, {time(9, 15), time(9, 20)})
        self.assertEqual(multipliers, {1.0, 1.5})

    def test_validate_rejects_missing_empty_and_invalid_types(self):
        incomplete = dict(sample_config())
        del incomplete["ORB_END"]
        with self.assertRaises(ValueError):
            validate_combination_config(incomplete)

        empty = dict(sample_config())
        empty["ORB_START"] = []
        with self.assertRaises(ValueError):
            validate_combination_config(empty)

        bad_time = dict(sample_config())
        bad_time["ORB_START"] = ["09:15"]
        with self.assertRaises(TypeError):
            validate_combination_config(bad_time)

    def test_combination_to_strategy_kwargs_isolated_instances(self):
        combo_a = generate_combinations(sample_config())[0]
        combo_b = generate_combinations(sample_config())[-1]
        strategy_a = ORBStrategy(**combination_to_strategy_kwargs(combo_a))
        strategy_b = ORBStrategy(**combination_to_strategy_kwargs(combo_b))
        self.assertEqual(strategy_a.orb_start, time(9, 15))
        self.assertEqual(strategy_b.orb_start, time(9, 20))
        self.assertEqual(strategy_a.sl_range_multiplier, 1.0)
        self.assertEqual(strategy_b.sl_range_multiplier, 1.5)

    def test_report_to_metric_csv_row(self):
        metrics = report_to_metric_csv_row(sample_report())
        self.assertEqual(metrics["TOTAL_RETURN_PCT"], 12.5)
        self.assertEqual(metrics["TOTAL_TRADES"], 50)
        self.assertEqual(metrics["WINNING_TRADES"], 28)
        self.assertEqual(metrics["LOSING_TRADES"], 22)
        self.assertEqual(metrics["PROFIT_FACTOR"], 1.85)
        self.assertEqual(metrics["MAX_DRAWDOWN_PCT"], 8.2)
        self.assertEqual(metrics["WIN_RATE_PCT"], 56.0)
        self.assertEqual(metrics["WINNING_STREAK"], 5)
        self.assertEqual(metrics["LOSING_STREAK"], 3)
        self.assertEqual(metrics["CAGR"], 9.1)

    def test_consolidated_csv_columns_and_row_values(self):
        combo = generate_combinations(sample_config())[2]
        row = build_combination_summary_row(combo, sample_report())
        with tempfile.TemporaryDirectory() as folder:
            path = save_consolidated_combination_csv([row], folder)
            frame = pd.read_csv(path)
            self.assertEqual(list(frame.columns), list(COMBINATION_SUMMARY_COLUMNS))
            self.assertEqual(frame.iloc[0]["ORB_START"], "09:20:00")
            self.assertEqual(frame.iloc[0]["SL_RANGE_MULTIPLIER"], 1.0)
            self.assertEqual(frame.iloc[0]["TOTAL_TRADES"], 50)
            self.assertEqual(frame.iloc[0]["PROFIT_FACTOR"], 1.85)
            self.assertEqual(path, consolidated_report_path(folder))


class ORBCombinationWorkflowTests(unittest.TestCase):
    def test_single_run_main_does_not_invoke_combination_batch(self):
        with mock.patch("Backtest.Strategies.strategy_3_ORB.config.run_combinations", False):
            with mock.patch("Backtest.Strategies.strategy_3_ORB.run_backtest.run") as run_mock:
                run_mock.return_value = {
                    "report": "report",
                    "trades": pd.DataFrame({"symbol": ["A"]}),
                    "report_folder": Path("."),
                }
                run_backtest_main()
                run_mock.assert_called_once_with()

    def test_combination_main_delegates_to_batch_runner(self):
        with mock.patch("Backtest.Strategies.strategy_3_ORB.config.run_combinations", True):
            with mock.patch(
                "Backtest.Strategies.strategy_3_ORB.run_combinations.run_combination_batch"
            ) as batch_mock:
                batch_mock.return_value = {
                    "total_combinations": 1,
                    "completed": 1,
                    "failed": 0,
                    "summary_csv": Path("summary.csv"),
                    "failures": [],
                }
                run_backtest_main()
                batch_mock.assert_called_once()

    def test_run_passes_combination_without_mutating_config(self):
        combo = generate_combinations(sample_config())[0]
        before = orb_config.ORB_START
        empty_trades = pd.DataFrame(
            columns=[
                "symbol",
                "direction",
                "entry",
                "exit_price",
                "quantity",
                "gross_pnl",
                "transaction_cost",
                "pnl",
                "entry_timestamp",
                "exit_timestamp",
                "exit_reason",
            ]
        )
        report_folder = Path(tempfile.mkdtemp())
        with mock.patch(
            "Backtest.Strategies.strategy_3_ORB.run_backtest.HistoricalDataLoader.load_json",
            return_value=pd.DataFrame(),
        ):
            with mock.patch(
                "Backtest.Strategies.strategy_3_ORB.run_backtest.BacktestEngine.run"
            ) as engine_run:
                engine_run.return_value.to_dataframe.return_value = empty_trades
                with mock.patch(
                    "Backtest.Strategies.strategy_3_ORB.run_backtest.BacktestReportEngine.generate_and_save",
                    return_value=("report", report_folder),
                ):
                    with mock.patch(
                        "Backtest.Strategies.strategy_3_ORB.run_backtest.save_orb_artifacts",
                        return_value={},
                    ):
                        with mock.patch(
                            "Backtest.Strategies.strategy_3_ORB.run_backtest.validate_and_save",
                            return_value={},
                        ):
                            result = run(combination=combo)
        self.assertEqual(orb_config.ORB_START, before)
        self.assertEqual(result["combination"]["ORB_START"], time(9, 15))

    def test_batch_continues_after_failure_and_writes_summary_for_successes(self):
        combos = generate_combinations(
            {
                **sample_config(),
                "SL_RANGE_MULTIPLIER": [1.0, 2.0],
                "ORB_START": [time(9, 15)],
            }
        )
        self.assertEqual(len(combos), 2)
        with tempfile.TemporaryDirectory() as folder:
            reports_root = Path(folder)
            call_count = {"n": 0}

            def fake_run(**kwargs):
                call_count["n"] += 1
                if kwargs["combination"]["SL_RANGE_MULTIPLIER"] == 2.0:
                    raise RuntimeError("boom")
                return {
                    "report": sample_report(profit_factor=1.1, total_trades=10),
                    "report_folder": reports_root / "run",
                }

            with mock.patch(
                "Backtest.Strategies.strategy_3_ORB.run_backtest.run",
                side_effect=fake_run,
            ):
                result = run_combination_batch(
                    reports_root=reports_root,
                    combination_config={
                        **sample_config(),
                        "SL_RANGE_MULTIPLIER": [1.0, 2.0],
                        "ORB_START": [time(9, 15)],
                    },
                )
            self.assertEqual(result["completed"], 1)
            self.assertEqual(result["failed"], 1)
            self.assertTrue(result["summary_csv"].is_file())
            summary = pd.read_csv(result["summary_csv"])
            self.assertEqual(len(summary), 1)
            self.assertEqual(summary.iloc[0]["SL_RANGE_MULTIPLIER"], 1.0)
            self.assertEqual(summary.iloc[0]["TOTAL_TRADES"], 10)
            self.assertEqual(summary.iloc[0]["PROFIT_FACTOR"], 1.1)
            self.assertEqual(call_count["n"], 2)


if __name__ == "__main__":
    unittest.main()
