# Higher High backtest experiments

Run the usual script:

```powershell
python D:\FM\ALGOTRADING\Backtest\Strategies\Strategy_1_higher_high\run_backtest.py
```

With `run_combinations = True` (the current setting), this runs the Cartesian
grid in `COMBINATION_CONFIG`. The supplied full grid contains 62,208 runs;
reduce parameter lists before starting if you want a smaller sweep.

With `run_combinations = False`, the default runs 17 named experiments and chronological yearly checks.
It prints progress and a comparison table. It does not adopt the best result
or change your single-run settings automatically.

## Modes

```powershell
# Original single run using config.py, including any optional controls you enable
python Backtest\Strategies\Strategy_1_higher_high\run_backtest.py --single

# Full-history comparisons only (faster)
python Backtest\Strategies\Strategy_1_higher_high\run_backtest.py --experiments --no-validation
```

`RUN_EXPERIMENTS = False` restores the single-run default. The existing
`run_combinations = True` flag retains priority unless a CLI mode is explicit.
Cartesian sweeps support the six new risk/ranking/filter parameters, including
`None` for disabled limits. Every value is included in the summary CSV and saved
settings. Older grids that omit these parameters retain their disabled/default
behavior. RSI, trailing-count and momentum-lookback choices can yield equivalent
runs when their corresponding features are disabled; the grid is not deduplicated.

## What is compared

All named presets start from the existing EMA/RSI/volume settings in config.py.
The reference explicitly fixes a 7% target, no trailing exit, equal-capital
sizing, alphabetical entry order, and no new entry filters.

- Exit comparisons: 5% and 7% targets, trailing exit off or 2/3/4 preceding candles.
- Risk comparisons: 0.5%, 0.75%, 1% of realized account equity per trade.
- Ranking comparisons: strongest trailing 20-session return or highest relative volume.
- Extension comparisons: maximum 1.5 or 2 ATR above the entry EMA.
- Reward/risk comparisons: minimum planned target distance / initial stop distance of 1 or 1.5.

Each risk, ranking or filter preset changes only that control relative to the
reference. They are not combined with whichever exit happened to win in sample.

Risk quantity is the smaller of the existing cash/position cap and
`floor(equity * risk_percentage / 100 / (entry - initial_stop))`.
Risk budgets are per trade, not a total portfolio risk cap.

Ranking applies only to that day's entry candidates; ties use symbol order.
Stocks without sufficient indicator history are ineligible for that ranking.
Momentum uses the current close versus the close N observed sessions earlier.
Relative volume uses current volume / the shifted volume EMA already in the strategy.
ATR is the trailing simple average of true range, including the current candle.
These features use no future candles and no external benchmark.

Optional single-run controls in config.py:

| Setting | Disabled/default | Example |
|---|---|---|
| RISK_PER_TRADE_PCT | None | 0.75 |
| SIGNAL_RANKING | alphabetical | momentum or relative_volume |
| MOMENTUM_LOOKBACK | 20 | 20 sessions |
| ATR_PERIOD | 14 | 14 sessions |
| MAX_EXTENSION_ATR | None | 2.0 |
| MIN_REWARD_RISK | None | 1.5 |

## Results

Each execution creates a separate directory under
`artifacts/backtest_reports/HigherHighStrategy/experiments/`:

- `experiment_summary.csv`: metrics, baseline deltas and paths to individual reports.
- `manifest.json`: complete presets, input and source-code hashes, dates and capital.
- Each experiment's folder: existing charts, JSON/text reports, trades, yearly/monthly
  tables and `settings.json` containing the exact settings.
- `walk_forward.csv`: each test year's selected preset versus the reference.
- `training_scores.csv`: every preset's training score and eligibility per fold.
- `stagnation_analysis.csv`: continuation results for positions still open after
  5/10/15 observed sessions. Progress below 1% is classified as stagnant.

Positive return/CAGR/win-rate deltas are improvements. Negative drawdown deltas
are improvements. `IMPROVES_ALL_FOUR` requires strict improvement in all four
rounded existing report metrics. `CAGR` retains the report's trade-date period;
`WINDOW_CAGR` uses the common data window. `CAGR_DRAWDOWN_RATIO` divides the latter
by drawdown with a 1-percentage-point floor to avoid division by zero.

Yearly checks select the highest training ratio from the preceding two calendar
years, requiring positive return and at least 30 trades. Ties use preset name.
If nothing qualifies, use the reference. Training simulations stop before the
test year. Earlier candles warm indicators without opening trades. Each test
year starts fresh with the same capital and no positions; the final year may
be partial. These are independent historical robustness checks, not a stitched
portfolio or untouched holdout. Already-inspected history remains inspected.

Stagnation continuation measures the return from checkpoint close to the original
exit, excluding trades exiting on or before the checkpoint. It is descriptive:
it does not simulate a time exit or the subsequent reuse of freed capital.

The existing close-entry, target-first, gap-fill, zero-cost and realized-trade
drawdown assumptions are retained as requested. No benchmark data is required.
