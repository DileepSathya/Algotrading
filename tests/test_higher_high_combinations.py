import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from Backtest.Strategies.Strategy_1_higher_high import config as higher_high_config
from Backtest.Strategies.Strategy_1_higher_high.run_backtest import main as run_backtest_main
from Backtest.Strategies.Strategy_1_higher_high.run_combinations import (
    COMBINATION_SUMMARY_COLUMNS,
    combination_to_run_settings,
    combination_to_strategy_kwargs,
    generate_combinations,
    run_combination_batch,
    validate_combination_config,
)
from engines.backtest_report_engine.models.report import BacktestReport


def sample_config():
    return {
        "CLOSE_THRESHOLD": [0.7, 0.8],
        "EMA_PERIOD": [9],
        "EMA_PERIOD_VOL": [20],
        "TARGET_PERCENT": [5.0, 10.0],
        "MAX_OPEN_POSITIONS": [4],
        "EXIT_EMA_PERIOD": [10],
    }


def sample_report():
    return BacktestReport(
        strategy_name="HigherHighStrategy",
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


class HigherHighCombinationUtilityTests(unittest.TestCase):
    def test_generates_cartesian_product_and_maps_parameters(self):
        combinations = generate_combinations(sample_config())

        self.assertEqual(len(combinations), 4)
        self.assertEqual(
            combination_to_strategy_kwargs(combinations[-1]),
            {
                "close_threshold": 0.8,
                "ema_period": 9,
                "ema_period_vol": 20,
                "target_percent": 10.0,
            },
        )
        self.assertEqual(
            combination_to_run_settings(combinations[-1]),
            {"max_open_positions": 4, "exit_ema_period": 10},
        )

    def test_validation_rejects_missing_empty_and_invalid_values(self):
        missing = sample_config()
        del missing["EMA_PERIOD"]
        with self.assertRaises(ValueError):
            validate_combination_config(missing)

        empty = sample_config()
        empty["TARGET_PERCENT"] = []
        with self.assertRaises(ValueError):
            validate_combination_config(empty)

        invalid = sample_config()
        invalid["MAX_OPEN_POSITIONS"] = [2.5]
        with self.assertRaises(TypeError):
            validate_combination_config(invalid)


class HigherHighCombinationWorkflowTests(unittest.TestCase):
    def test_batch_continues_after_failure_and_writes_consolidated_summary(self):
        configuration = sample_config()
        configuration["CLOSE_THRESHOLD"] = [0.7]
        configuration["TARGET_PERCENT"] = [5.0, 10.0]

        with tempfile.TemporaryDirectory() as folder:
            reports_root = Path(folder)

            def fake_run(**kwargs):
                if kwargs["combination"]["TARGET_PERCENT"] == 10.0:
                    raise RuntimeError("boom")
                return {"report": sample_report()}

            with mock.patch(
                "Backtest.Strategies.Strategy_1_higher_high.run_backtest.run",
                side_effect=fake_run,
            ):
                result = run_combination_batch(
                    reports_root=reports_root,
                    combination_config=configuration,
                )

            self.assertEqual((result["completed"], result["failed"]), (1, 1))
            summary = pd.read_csv(result["summary_csv"])
            self.assertEqual(list(summary.columns), list(COMBINATION_SUMMARY_COLUMNS))
            self.assertEqual(summary.iloc[0]["CLOSE_THRESHOLD"], 0.7)
            self.assertEqual(summary.iloc[0]["TOTAL_TRADES"], 50)
            self.assertTrue(result["failures_path"].is_file())

    def test_main_routes_using_run_combinations_flag(self):
        single_result = {
            "report": "report",
            "trades": pd.DataFrame(),
            "report_folder": Path("."),
        }
        with mock.patch.object(higher_high_config, "run_combinations", False):
            with mock.patch(
                "Backtest.Strategies.Strategy_1_higher_high.run_backtest.run",
                return_value=single_result,
            ) as single_run:
                run_backtest_main()
                single_run.assert_called_once_with()

        with mock.patch.object(higher_high_config, "run_combinations", True):
            with mock.patch(
                "Backtest.Strategies.Strategy_1_higher_high.run_combinations.main"
            ) as combination_main:
                run_backtest_main()
                combination_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
