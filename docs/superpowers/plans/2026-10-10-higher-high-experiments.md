# Higher High Experiments Implementation Plan

> **For agentic workers:** Use test-driven development to implement this plan task-by-task.

**Goal:** Running Strategy 1's existing script produces reproducible comparisons of OHLCV-only strategy experiments.

**Architecture:** Keep the existing entry and execution assumptions as the reference. Add optional strategy risk, ranking and entry filters; an experiment runner compares explicit presets and saves settings, trades, reports and chronological validation.

**Tech Stack:** Python, pandas, existing backtest/report engines, pytest.

**Spec:** User-approved revised plan in this conversation: exits, risk sizing, signal ranking, extension/reward-risk filters, investigate stagnant trades. Exclude baseline/execution corrections and benchmark dependencies.

## Global Constraints

- Modify the user's checkout so the requested absolute script path works.
- Preserve zero-cost, close-entry, target-first, realized-drawdown assumptions.
- Keep original single-run and Cartesian sweep modes available.
- Do not automatically select settings using the full-history winner.
- No new dependencies, commits or external writes required.

## Review Focus

- Optional indicators must not remove early exit candles or alter the reference.
- Ranking changes entries only, with deterministic symbol tie breaks.
- Risk percentage must become a fraction and retain the existing capital cap.
- Test periods must not influence training selection; warmup must not open trades.
- Empty/no-trade data and repeated runs must produce valid, separate artifacts.

### Task 1: Optional strategy controls

Files: strategy.py, models.py, config.py, Backtest/backtest_engine/engine.py, tests/test_higher_high_experiments.py.

- [ ] Write failing tests for capped risk quantity, ranking under a one-slot portfolio, causal ATR/momentum, filter boundaries, invalid options and disabled-feature parity.
- [ ] Implement risk_per_trade_pct, signal_ranking, momentum_lookback, atr_period, max_extension_atr, min_reward_risk. Supply signal metadata and risk fields. Add an optional entry-only ranking hook to the shared engine.
- [ ] Run targeted tests; verify original strategies remain unchanged.

### Task 2: Runnable experiment comparisons

Files: run_backtest.py, experiments.py, config.py, tests/test_higher_high_experiments.py.

- [ ] Test reference-relative presets, run configuration forwarding, distinct artifacts and comparison deltas.
- [ ] Extract an in-memory simulate helper reused by single runs and experiments. Default main to a bounded named experiment suite; keep legacy combination routing first and provide --single.
- [ ] Compare 5/7 percent exits, 2/3/4 candle stops, 0.5/0.75/1 percent risk, momentum/relative-volume ranking, and individual extension/reward-risk filters against the frozen reference. Save full settings and input identity.
- [ ] Verify small fixture end-to-end and direct script invocation.

### Task 3: Chronological checks and stagnant-trade analysis

Files: experiments.py, diagnostics.py, tests/test_higher_high_experiments.py.

- [ ] Test train-before-test folds, no warmup trades, empty folds and checkpoint eligibility.
- [ ] Use trailing two-calendar-year training windows to select a preset by CAGR/drawdown with minimum trade count, then evaluate it and the reference in the next year. Save each fold and selection; do not label reused historical data untouched validation.
- [ ] Save checkpoint continuation outcomes for still-open trades at 5/10/15 sessions; do not impose a time exit without evidence.

### Task 4: Verify and document

- [ ] Run the complete test suite, inspect the diff and run the requested script on the available data.
- [ ] Document modes, parameters, comparison definitions and current metric assumptions in the strategy README.
- [ ] Report observed results without claiming guaranteed improvements.

## Progress and decisions

- Implementation authorized directly by user; proceed in the requested checkout without another approval gate.
- Original config remains the single-run reference; experiment mode is the default entry-point experience.
- Stagnation work is diagnostic only, as the agreed plan requires evidence before imposing an exit.
- Tasks 1-4 complete: optional controls, comparison runner, rolling validation,
  diagnostics and README implemented. Real-data execution succeeded for all 17
  presets and three folds. All 34 Higher High tests pass; full discovery has
  137 passes and five independently reproduced pre-existing failures.
- Independent review found no important defects; added coverage for unchanged
  simultaneous-exit ordering. Detailed evidence and runtime command are in
  `2026-10-10-higher-high-verification.md` beside this plan.
