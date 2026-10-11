import json
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
    combination_to_csv_row,
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
        "PRICE_ABOVE_EMA_PERIOD": [True, False],
        "EMA_FILTER": [True, False],
        "SMALLER_EMA_PERIOD": [20],
        "BIGGER_EMA_PERIOD": [50],
        "USE_RSI": [True, False],
        "RSI_PERIOD": [10],
        "RSI_MIN_VALUE": [50.0],
        "RSI_MAX_VALUE": [70.0],
        "EMA_PERIOD_VOL": [20],
        "TARGET_PERCENT": [5.0, 10.0],
        "MAX_OPEN_POSITIONS": [4],
        "EXIT_EMA_PERIOD": [10],
        "TRAIL_STOP_LOSS": [True],
        "TRAIL_STOP_LOSS_CANDLE_COUNT": [2],
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
    def test_new_controls_expand_map_and_serialize(self):
        grid = {key: [values[0]] for key, values in sample_config().items()}
        grid.update(RISK_PER_TRADE_PCT=[None, .75],
                    SIGNAL_RANKING=['alphabetical', 'momentum', 'relative_volume'],
                    MOMENTUM_LOOKBACK=[20], ATR_PERIOD=[14],
                    MAX_EXTENSION_ATR=[None, 2.0], MIN_REWARD_RISK=[None, 1.5])
        combinations = generate_combinations(grid)
        self.assertEqual(len(combinations), 24)
        kwargs = combination_to_strategy_kwargs(combinations[-1])
        self.assertEqual(kwargs['risk_per_trade_pct'], .75)
        self.assertEqual(kwargs['signal_ranking'], 'relative_volume')
        self.assertEqual(kwargs['momentum_lookback'], 20)
        self.assertEqual(kwargs['atr_period'], 14)
        self.assertEqual(kwargs['max_extension_atr'], 2.0)
        self.assertEqual(kwargs['min_reward_risk'], 1.5)
        self.assertIsNone(combination_to_csv_row(combinations[0])['RISK_PER_TRADE_PCT'])
        self.assertEqual(combination_to_csv_row(combinations[-1])['SIGNAL_RANKING'], 'relative_volume')

    def test_new_control_validation_rejects_invalid_values(self):
        for key, value in [('RISK_PER_TRADE_PCT', 0), ('RISK_PER_TRADE_PCT', 101),
                           ('MAX_EXTENSION_ATR', float('nan')), ('MIN_REWARD_RISK', -1),
                           ('SIGNAL_RANKING', 'unknown'), ('ATR_PERIOD', 0),
                           ('MOMENTUM_LOOKBACK', True)]:
            grid = sample_config()
            grid[key] = [value]
            with self.subTest(key=key, value=value), self.assertRaises((ValueError, TypeError)):
                generate_combinations(grid)

    def test_generates_cartesian_product_and_maps_parameters(self):
        combinations = generate_combinations(sample_config())

        self.assertEqual(len(combinations), 32)
        self.assertEqual(
            combination_to_strategy_kwargs(combinations[-1]),
            {
                "close_threshold": 0.8,
                "ema_period": 9,
                "price_above_ema_period": False,
                "ema_filter": False,
                "smaller_ema_period": 20,
                "bigger_ema_period": 50,
                "use_rsi": False,
                "rsi_period": 10,
                "rsi_min_value": 50.0,
                "rsi_max_value": 70.0,
                "ema_period_vol": 20,
                "target_percent": 10.0,
            },
        )
        self.assertEqual(
            combination_to_run_settings(combinations[-1]),
            {
                "max_open_positions": 4,
                "exit_ema_period": 10,
                "trail_stop_loss": True,
                "trail_stop_loss_candle_count": 2,
            },
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

        invalid_flag = sample_config()
        invalid_flag["TRAIL_STOP_LOSS"] = [1]
        with self.assertRaises(TypeError):
            validate_combination_config(invalid_flag)

        invalid_ema_filter = sample_config()
        invalid_ema_filter["PRICE_ABOVE_EMA_PERIOD"] = [1]
        with self.assertRaises(TypeError):
            validate_combination_config(invalid_ema_filter)

        invalid_crossover_filter = sample_config()
        invalid_crossover_filter["EMA_FILTER"] = [1]
        with self.assertRaises(TypeError):
            validate_combination_config(invalid_crossover_filter)

        invalid_rsi_filter = sample_config()
        invalid_rsi_filter["USE_RSI"] = [1]
        with self.assertRaises(TypeError):
            validate_combination_config(invalid_rsi_filter)


class HigherHighCombinationWorkflowTests(unittest.TestCase):
    def test_real_batch_applies_risk_and_records_new_controls(self):
        configuration = {key: [values[0]] for key, values in sample_config().items()}
        configuration.update(EMA_PERIOD=[1], USE_RSI=[False], EMA_FILTER=[False],
                             TRAIL_STOP_LOSS=[False], RISK_PER_TRADE_PCT=[.5],
                             SIGNAL_RANKING=['relative_volume'], MOMENTUM_LOOKBACK=[2],
                             ATR_PERIOD=[2], MAX_EXTENSION_ATR=[None], MIN_REWARD_RISK=[None])
        candles = [dict(symbol='A', date=f'2024-01-0{day}', open=price - 1,
                        high=price + .1, low=price - 10, close=price, volume=1000)
                   for day, price in enumerate([100, 101, 102], 1)]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'data.json'
            path.write_text(json.dumps(candles), encoding='utf-8')
            result = run_combination_batch(data_path=path, reports_root=root,
                                            combination_config=configuration)
            self.assertEqual((result['completed'], result['failed']), (1, 0))
            row = pd.read_csv(result['summary_csv']).iloc[0]
            self.assertEqual(row.RISK_PER_TRADE_PCT, .5)
            self.assertEqual(row.SIGNAL_RANKING, 'relative_volume')
            self.assertTrue(pd.isna(row.MAX_EXTENSION_ATR))
            trades = pd.read_csv(next(root.rglob('trades.csv')))
            self.assertEqual(trades.iloc[0]['quantity'], 50)

    def test_batch_continues_after_failure_and_writes_consolidated_summary(self):
        configuration = sample_config()
        configuration["CLOSE_THRESHOLD"] = [0.7]
        configuration["PRICE_ABOVE_EMA_PERIOD"] = [True]
        configuration["EMA_FILTER"] = [True]
        configuration["USE_RSI"] = [True]
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
            self.assertTrue(bool(summary.iloc[0]["PRICE_ABOVE_EMA_PERIOD"]))
            self.assertTrue(bool(summary.iloc[0]["EMA_FILTER"]))
            self.assertTrue(bool(summary.iloc[0]["USE_RSI"]))
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
                run_backtest_main(["--single"])
                single_run.assert_called_once_with()

        with mock.patch.object(higher_high_config, "run_combinations", True):
            with mock.patch(
                "Backtest.Strategies.Strategy_1_higher_high.run_combinations.main"
            ) as combination_main:
                run_backtest_main()
                combination_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
