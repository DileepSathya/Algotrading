import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from Backtest.backtest_engine import BacktestEngine
from Backtest.Strategies.Strategy_1_higher_high.strategy import HigherHighStrategy
from engines.exit_engine import ExitEngine, SLExit, TargetExit
from engines.position_sizing_engine import PositionSizingEngine
from engines.trade_engine import TradeEngine


def candles():
    rows = []
    for symbol, closes, volumes in (
        ('A', [100, 101, 103, 104], [100, 100, 110, 120]),
        ('Z', [100, 102, 106, 108], [100, 100, 300, 400]),
    ):
        for day, (close, volume) in enumerate(zip(closes, volumes), 1):
            rows.append(dict(symbol=symbol, date=f'2024-01-0{day}',
                             open=close - 1, high=close + .2, low=close - 2,
                             close=close, volume=volume))
    return pd.DataFrame(rows)


def strategy(**kwargs):
    return HigherHighStrategy(price_above_ema_period=False, ema_filter=False,
                              use_rsi=False, ema_period=1, **kwargs)


def backtest(subject, data, slots=1):
    return BacktestEngine(subject, TradeEngine(), ExitEngine([TargetExit(), SLExit()]),
                          PositionSizingEngine(100_000, slots)).run(data).to_dataframe()


class HigherHighExperimentFeatureTests(unittest.TestCase):
    def test_risk_budget_limits_quantity_and_preserves_capital_cap(self):
        subject = strategy(risk_per_trade_pct=.5)
        trades = backtest(subject, candles().query("symbol == 'A'"), slots=4)
        # First signal: entry 101, stop 99; 500 risk permits 250 shares,
        # but the 25,000 capital cap permits only 247.
        self.assertEqual(trades.iloc[0]['quantity'], 247)
        wide = candles().query("symbol == 'A'").copy()
        wide['low'] = wide['close'] - 10
        trades = backtest(subject, wide, slots=4)
        self.assertEqual(trades.iloc[0]['quantity'], 50)
        self.assertEqual(trades.iloc[0]['initial_risk_per_unit'], 10)

    def test_ranking_changes_actual_slot_winner_not_exit_order(self):
        for ranking in ('momentum', 'relative_volume'):
            subject = strategy(signal_ranking=ranking, momentum_lookback=2)
            # Restrict entry date to the first date with both ranking signals.
            subject.entry_start = pd.Timestamp('2024-01-03')
            trades = backtest(subject, candles())
            self.assertEqual(trades.iloc[0]['symbol'], 'Z')
        subject = strategy()
        subject.entry_start = pd.Timestamp('2024-01-03')
        self.assertEqual(backtest(subject, candles()).iloc[0]['symbol'], 'A')

    def test_indicators_are_causal_and_do_not_drop_warmup_rows(self):
        subject = strategy(momentum_lookback=2, atr_period=2)
        data = candles().query("symbol == 'A'")
        prepared = subject.prepare_data(data)
        self.assertEqual(len(prepared), 3)  # original previous-day warmup only
        row = prepared.iloc[1]
        self.assertAlmostEqual(row['momentum_return'], 3.0)
        self.assertAlmostEqual(row['atr'], 2.2)
        self.assertAlmostEqual(row['relative_volume'], 1.1)
        changed = data.copy()
        changed.loc[changed.index[-1], ['high', 'close', 'volume']] = [999, 998, 99999]
        pd.testing.assert_frame_equal(prepared.iloc[:-1], subject.prepare_data(changed).iloc[:-1])

    def test_ranking_does_not_reorder_simultaneous_exits(self):
        subject = strategy(signal_ranking='relative_volume', target_percent=1)
        trades = backtest(subject, candles(), slots=2)
        # On Jan 3 Z has much higher relative volume, but existing positions
        # still exit in the original A/Z order before ranked entries are considered.
        exited = trades.loc[trades.exit_date == pd.Timestamp('2024-01-03')]
        self.assertEqual(list(exited.symbol), ['A', 'Z'])
        self.assertEqual(list(exited.exit_reason), ['TARGET', 'TARGET'])

    def test_extension_and_reward_risk_filters_have_inclusive_boundaries(self):
        row = dict(symbol='A', date=pd.Timestamp('2024-01-03'), close=100.,
                   low=95., **{'1_ema': 96.}, trade_signal=True, atr=2.)
        self.assertIsNotNone(strategy(target_percent=10, max_extension_atr=2,
                                      min_reward_risk=2).generate_signal(row))
        self.assertIsNone(strategy(max_extension_atr=1.9).generate_signal(row))
        self.assertIsNone(strategy(target_percent=7, min_reward_risk=1.5).generate_signal(row))
        row['atr'] = float('nan')
        self.assertIsNone(strategy(max_extension_atr=2).generate_signal(row))
        self.assertIsNotNone(strategy().generate_signal(row))

    def test_invalid_settings_fail_early(self):
        for kwargs in ({'risk_per_trade_pct': 0}, {'risk_per_trade_pct': float('nan')},
                       {'risk_per_trade_pct': 101}, {'signal_ranking': 'future'},
                       {'atr_period': 0}, {'momentum_lookback': True},
                       {'max_extension_atr': -1}, {'min_reward_risk': 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                strategy(**kwargs)

    def test_missing_rank_goes_last_and_ties_are_alphabetical(self):
        subject = strategy(signal_ranking='momentum')
        rows = [dict(symbol='Z', momentum_return=2),
                dict(symbol='B', momentum_return=float('nan')),
                dict(symbol='A', momentum_return=2)]
        self.assertEqual([r['symbol'] for r in subject.rank_entry_candidates(rows)], ['A', 'Z', 'B'])


class ExperimentWorkflowTests(unittest.TestCase):
    def test_presets_are_independent_and_keep_baseline(self):
        from Backtest.Strategies.Strategy_1_higher_high.experiments import build_presets
        presets = build_presets()
        self.assertEqual(presets['baseline']['TARGET_PERCENT'], 7)
        self.assertFalse(presets['baseline']['TRAIL_STOP_LOSS'])
        self.assertEqual(presets['target_5_trail_4']['TARGET_PERCENT'], 5)
        self.assertEqual(presets['risk_0.5']['RISK_PER_TRADE_PCT'], .5)
        self.assertEqual(presets['risk_0.5']['TARGET_PERCENT'], 7)
        self.assertFalse(presets['risk_0.5']['TRAIL_STOP_LOSS'])
        self.assertEqual(presets['rank_momentum']['SIGNAL_RANKING'], 'momentum')

    def test_simulation_respects_warmup_and_settings(self):
        from Backtest.Strategies.Strategy_1_higher_high.run_backtest import default_settings, simulate
        settings = default_settings()
        settings.update(USE_RSI=False, EMA_FILTER=False, EMA_PERIOD=1,
                        RISK_PER_TRADE_PCT=.5, MAX_OPEN_POSITIONS=4)
        result = simulate(candles(), settings, entry_start='2024-01-03',
                          entry_end='2024-01-03', monte_carlo_simulations=2)
        self.assertTrue((result['trades']['entry_date'] == pd.Timestamp('2024-01-03')).all())
        self.assertTrue((result['trades']['exit_date'] <= pd.Timestamp('2024-01-03')).all())
        self.assertEqual(result['settings']['RISK_PER_TRADE_PCT'], .5)

    def test_batch_saves_comparison_and_full_configuration(self):
        from Backtest.Strategies.Strategy_1_higher_high.experiments import run_experiments
        from Backtest.Strategies.Strategy_1_higher_high.run_backtest import default_settings
        base = default_settings()
        base.update(USE_RSI=False, EMA_FILTER=False, EMA_PERIOD=1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.json'
            candles().to_json(path, orient='records')
            result = run_experiments(path, Path(folder),
                                     presets={'baseline': base, 'risk': {**base, 'RISK_PER_TRADE_PCT': .5}},
                                     validation=False, monte_carlo_simulations=2)
            summary = pd.read_csv(result['summary_csv'])
            self.assertEqual(list(summary['EXPERIMENT']), ['baseline', 'risk'])
            self.assertEqual(summary.iloc[0]['DELTA_CAGR_PP'], 0)
            manifest = json.loads((result['folder'] / 'manifest.json').read_text())
            self.assertEqual(manifest['presets']['risk']['RISK_PER_TRADE_PCT'], .5)
            for name in ('baseline', 'risk'):
                report_folder = Path(summary.set_index('EXPERIMENT').loc[name, 'REPORT_FOLDER'])
                self.assertTrue((report_folder / 'trades.csv').is_file())
                self.assertTrue((report_folder / 'settings.json').is_file())
            self.assertTrue((result['folder'] / 'stagnation_analysis.csv').is_file())

    def test_walk_forward_windows_and_empty_selection(self):
        from Backtest.Strategies.Strategy_1_higher_high.experiments import walk_forward, build_presets
        data = pd.concat([candles().assign(date=lambda x: pd.to_datetime(x.date) + pd.DateOffset(years=i))
                          for i in range(4)], ignore_index=True)
        presets = {'baseline': build_presets()['baseline']}
        folds, scores = walk_forward(data, presets, min_trades=999, monte_carlo_simulations=2)
        self.assertEqual(list(folds['TEST_YEAR']), [2026, 2027])
        self.assertTrue((pd.to_datetime(folds.TRAIN_END) < pd.to_datetime(folds.TEST_START)).all())
        self.assertTrue((folds.SELECTED_EXPERIMENT == 'baseline').all())
        self.assertTrue((folds.SELECTION_REASON == 'fallback_no_eligible_candidate').all())
        self.assertEqual(len(scores), 2)
        empty, _ = walk_forward(data.iloc[:0], presets, monte_carlo_simulations=2)
        self.assertTrue(empty.empty)

    def test_stagnation_uses_only_trades_still_open_after_checkpoint(self):
        from Backtest.Strategies.Strategy_1_higher_high.diagnostics import stagnation_analysis
        trades = pd.DataFrame([
            dict(symbol='A', entry_date='2024-01-01', exit_date='2024-01-04', entry=100, exit_price=104),
            dict(symbol='A', entry_date='2024-01-01', exit_date='2024-01-02', entry=100, exit_price=101),
        ])
        rows = stagnation_analysis(trades, candles(), checkpoints=(1,), progress_pct=2)
        self.assertEqual(rows.iloc[0]['trades'], 1)
        self.assertEqual(rows.iloc[0]['group'], 'stagnant')
        self.assertEqual(rows.iloc[0]['mean_remaining_return_pct'], 2.9703)

    def test_future_test_prices_cannot_change_training_scores_or_selection(self):
        from Backtest.Strategies.Strategy_1_higher_high.experiments import walk_forward
        from Backtest.Strategies.Strategy_1_higher_high.run_backtest import default_settings
        data = pd.concat([candles().assign(date=lambda x: pd.to_datetime(x.date) + pd.DateOffset(years=i))
                          for i in range(3)], ignore_index=True)
        base = default_settings()
        base.update(USE_RSI=False, EMA_FILTER=False, EMA_PERIOD=1)
        presets = {'baseline': base, 'risk': {**base, 'RISK_PER_TRADE_PCT': .5}}
        folds, scores = walk_forward(data, presets, min_trades=1, monte_carlo_simulations=2)
        changed = data.copy()
        changed.loc[changed.date.dt.year == 2026, ['open', 'high', 'low', 'close']] *= 3
        new_folds, new_scores = walk_forward(changed, presets, min_trades=1, monte_carlo_simulations=2)
        pd.testing.assert_frame_equal(scores, new_scores)
        self.assertEqual(list(folds.SELECTED_EXPERIMENT), list(new_folds.SELECTED_EXPERIMENT))

    def test_zero_trade_reports_and_diagnostics_remain_readable(self):
        from Backtest.Strategies.Strategy_1_higher_high.run_backtest import default_settings, simulate
        from Backtest.Strategies.Strategy_1_higher_high.diagnostics import stagnation_analysis
        raw = candles().iloc[:0]
        result = simulate(raw, default_settings(), monte_carlo_simulations=2)
        self.assertEqual(result['report'].total_trades, 0)
        diagnostic = stagnation_analysis(result['trades'], raw)
        self.assertTrue(diagnostic.empty)
        self.assertIn('mean_remaining_return_pct', diagnostic.columns)


if __name__ == '__main__':
    unittest.main()
