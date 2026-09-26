# ORB Backtest Design

## Goal

Turn `Backtest/Strategies/strategy_3_ORB` into a production-quality intraday opening-range-breakout backtest that uses the repository's shared engines, supports long and short positions correctly, produces auditable trades and complete reports, and preserves existing strategy behavior.

## Scope and constraints

- Calculate the opening range independently for each `symbol + trading day` from candles at or after 09:15 and strictly before 10:00.
- Evaluate breakouts only from 10:00 onward, after the opening range is fully known.
- Enter at the breakout candle close when close is above ORB high (long) or below ORB low (short).
- Start SL/target evaluation on the next candle, never the entry candle.
- Force any remaining position out at the close of that day's 14:30 candle; never carry overnight.
- Preserve the shared engine and extend it through backward-compatible defaults instead of creating an ORB-only backtester.
- Preserve existing one-active-trade-per-symbol behavior and the current no-same-candle re-entry behavior.
- Make no Git commits, branches, pushes, resets, or other repository-history/index changes.

## ORB trade rules

For an entry price `E` and opening range `R = orb_high - orb_low`:

- Long: `close > orb_high`, stop `E - 0.5R`, target `E + R`.
- Short: `close < orb_low`, stop `E + 0.5R`, target `E - R`.
- Risk budget: `current realized equity * 0.0025`.
- Quantity: floor of `risk budget / (0.5R)`, subject to the shared engine's position/capital constraints and integer-share convention.
- A zero or invalid ORB range produces no signal.

If a later candle touches both stop and target and OHLC cannot establish order, the exit engine evaluates the stop first. This is deterministic and conservative. Gap behavior uses the existing level-fill convention: an activated stop or target fills at its configured level.

## Shared engine changes

### Trade model and trade engine

Add a direction field with a backward-compatible `LONG` default. Calculate gross P&L as `(exit-entry)*quantity` for long trades and `(entry-exit)*quantity` for short trades. Record transaction costs and net P&L separately, with `pnl` remaining the net value consumed by the reporting engine. Carry strategy metadata into the completed-trade dictionary so ORB values and equity audit fields survive the shared lifecycle.

### Exit engine

Pass trade direction to reusable exit rules. Long stop/target tests remain low-at-or-below stop and high-at-or-above target. Short tests become high-at-or-above stop and low-at-or-below target. Rule order defines ambiguous-bar precedence; ORB configures stop before target.

Add a reusable time-exit rule that compares a candle timestamp/time with the configured cutoff and exits at that candle's close. It applies to either direction.

### Position sizing

Extend the shared sizing interface to accept direction and an optional risk-per-unit. When risk-per-unit is provided, calculate integer quantity from current realized equity and the requested risk fraction. Retain equal-capital sizing when those optional values are absent so Strategy 1 and its tests continue to behave as before.

Short positions reserve notional capital under the existing capital/slot convention. Closing them applies direction-aware realized P&L and releases the reserved notional. Equity-before and equity-after values use initial capital plus realized net P&L; open positions are not marked to market.

### Transaction costs

The repository has no existing transaction-cost convention. Introduce an optional reusable cost callable/model at the trade-engine boundary and default it to zero. The ORB runner will use that zero-cost default unless a project cost model is configured later. Reports will expose gross P&L, transaction costs, and net P&L so this assumption is explicit rather than hidden.

### Intraday orchestration

Normalize a combined candle timestamp from `date + time`, sort globally by timestamp then symbol, and process each timestamp in two phases: exits for positions that existed before that candle, then new entries. This retains portfolio-aware sizing across symbols and prevents entry-candle exits. At each trading-day boundary, any remaining intraday trade must already have closed by the strategy's time rule; otherwise the engine performs a defensive end-of-day close at the final available candle and labels it accordingly. Final-data settlement remains for non-intraday strategies.

## ORB strategy package

Complete the package with configuration, signal model/metadata, strategy implementation, package exports, and a runnable backtest script. `prepare_data` must operate on its supplied DataFrame (never reread a global file), calculate ORB values by symbol and date, reject pre-10:00 entries, and retain timestamps. The signal includes direction, ORB values, stop distance, and audit metadata.

The runner loads `artifacts/backtest/hist_data_5.json`, constructs the existing shared engines, runs the strategy, writes trades and reports, and prints a concise summary. Defaults remain reproducible, including a fixed Monte Carlo seed.

## Reporting and artifacts

Use `BacktestReportEngine` for all standard metrics and existing equity, drawdown, and Monte Carlo charts. Extend artifact writing in a general optional-analysis form rather than branching the core report for ORB.

Each ORB run folder contains:

- `backtest_report.txt` and `backtest_report.json`
- `trades.csv` with symbol, trading date, direction, ORB high/low/range, entry timestamp/price, stop, target, exit timestamp/price/reason, quantity, equity before/after, gross P&L, costs, and net P&L
- `orb_analysis.json` and readable CSV tables for direction, symbol, exit reason, ORB-range statistics, monthly performance, and yearly performance
- `equity_curve.png`, `drawdown_curve.png`, and existing Monte Carlo output

Direction tables include trade count, wins, losses, win rate, gross P&L, costs, and net P&L. Exit analysis distinguishes `SL`, `TARGET`, `TIME`, defensive end-of-day, and end-of-backtest exits.

## Validation and tests

Tests will be written and observed failing before their implementations. Coverage includes:

- ORB isolation by symbol and trading date, and exclusion of pre-10:00 candles from breakout signals.
- Long and short signal prices, stops, targets, and direction.
- Entry-candle exclusion from exit evaluation.
- Direction-aware stop, target, P&L, realized equity, and transaction costs.
- Conservative stop-first behavior when both thresholds occur in one candle.
- Risk sizing based on 0.25% of current realized equity, integer rounding, and invalid/zero ranges.
- 14:30 close exit and absence of overnight positions.
- Required trade audit fields and ORB report tables/artifacts.
- Existing Strategy 1/shared-engine regression suite.
- Repeated full-data runs producing identical trades and metrics (artifact folder timestamps may differ).

After automated verification, sample long and short trades will be independently recalculated from source candles, including ORB bounds, next-candle exit eligibility, position size, and P&L. Additional checks will assert that every entry is at or after 10:00, every exit shares the entry trading date, and every ORB is derived only from that symbol/day's pre-10:00 candles.

## Success criteria

The full ORB dataset completes without open positions, every trade is auditable, the requested analysis artifacts are present, sampled long and short calculations reconcile, all tests pass, existing strategies retain their behavior, and two full runs are deterministic apart from timestamped output directories.
