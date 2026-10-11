# Higher High experiment verification

The existing Strategy 1 script completed 17 experiments and three rolling yearly
checks on the available history, with exit code 0. Results:

`artifacts/backtest_reports/HigherHighStrategy/experiments/20261010-201136-930ab5b2/`

Baseline matched the saved result exactly: 429 trades, 59.83% return, 10.45%
CAGR, 12.36% realized drawdown and 39.16% win rate.

The 5% target/four-candle exit produced 91.02% return, 14.71% CAGR, 10.88%
drawdown and 44.24% win rate. This is a full-history comparison, not a selected
production configuration. Rolling selection outperformed the reference in 2024
and partial 2026 but underperformed it in 2025 (7.82% versus 18.89% return).

## Tests

Final full discovery: 142 tests, 137 passed, 5 failed. All 34 Higher High tests
passed. `git diff --check` passed; direct script `--help` passed.

The five failures were reproduced with the original HEAD backtest engine loaded
in memory, without changing checkout files:

- `test_loss_trade_limits.LossTradeLimitTests.test_strategy_4_exposes_configured_loss_limits`: existing configuration is 5, test expects 2.
- `test_orb_backtest.ORBBacktestTests.test_entry_candle_does_not_trigger_target`: existing result TARGET, test expects TIME.
- `test_orb_backtest.ORBBacktestTests.test_short_target_and_audit_fields`: existing target 79.0, test expects 76.5.
- `test_orb_strategy.ORBStrategyTests.test_opening_range_is_isolated_by_symbol_and_day`: existing low 98, test expects 95.
- `test_orb_strategy.ORBStrategyTests.test_short_signal_uses_half_range_stop_and_full_range_target`: existing target 79.0, test expects 76.5.

These unrelated strategies/configurations were not changed.

An independent read-only review found no important defects. Its minor test gap
was covered by an additional simultaneous-exit ordering regression test.

## Runtime

The project's `venv/Scripts/python.exe` could not start its referenced Python312
installation in this environment. Verification used the available Python 3.12
runtime and the existing project packages; no packages were installed:

```powershell
& 'C:\Users\hp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -c "import site, runpy; site.addsitedir(r'D:\FM\ALGOTRADING\venv\Lib\site-packages'); runpy.run_path(r'D:\FM\ALGOTRADING\Backtest\Strategies\Strategy_1_higher_high\run_backtest.py', run_name='__main__')"
```

## Scope decisions

- Preserved fill, costs and metric assumptions explicitly excluded by the user.
- Added optional entry ranking to the shared engine after its unchanged exit loop.
- Kept stagnant-trade work diagnostic, without imposing an unsupported time exit.
- Each validation fold starts fresh; prior history warms indicators but cannot
  open positions before the fold. Test prices cannot alter training selection.
- Monte Carlo sampling in validation is minimal because it is not used in the
  training score; full reports use the existing 5,000 simulations and seed 42.
- Signal execution reads risk/metadata attributes directly; the legacy to_dict
  representation remains unchanged.
