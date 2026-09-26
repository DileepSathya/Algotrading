# ORB Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a deterministic, auditable, multi-symbol intraday ORB backtest using the existing shared engine and report framework.

**Architecture:** Extend the shared trade, exit, position-sizing, orchestration, and artifact boundaries with backward-compatible direction, risk-sizing, timestamp, metadata, and optional-cost support. Implement ORB as a normal strategy package and layer ORB-specific analysis onto the existing standard report artifacts.

**Tech Stack:** Python 3.12, pandas, unittest/pytest-compatible tests, matplotlib, existing project engines.

**Spec:** `docs/superpowers/specs/2026-09-25-orb-backtest-design.md`

## Global Constraints

- Make no Git commits, branches, pushes, resets, index changes, or repository-history changes.
- Reuse the existing backtest and reporting engines; do not add a parallel framework.
- Preserve Strategy 1 behavior through backward-compatible defaults.
- Use integer-share floor rounding.
- Use 0.25% of current realized equity as maximum ORB risk per trade.
- Evaluate SL/target only after the entry candle.
- Configure SL before target for deterministic conservative ambiguous-candle handling.
- Default transaction costs to zero because the repository defines no cost convention.
- Never carry ORB positions overnight.

## Review Focus

- Interleaved symbols at one timestamp must be processed in deterministic symbol order and see equity updated by exits before entries.
- Missing 14:30 candles must still produce a same-day defensive close at the last available candle.
- A symbol/day with missing or zero-range opening data must never create a trade.
- Short positions whose notional exceeds available capital must be capped consistently with long positions.
- Re-running the same engine and full dataset must reset all state and reproduce identical trades and metrics.

---

### Task 1: Direction-aware shared trade lifecycle

**Files:**
- Modify: `engines/trade_engine/models/trade.py`
- Modify: `engines/trade_engine/engine.py`
- Modify: `engines/exit_engine/engine.py`
- Modify: `engines/exit_engine/rules/base.py`
- Modify: `engines/exit_engine/rules/stop_loss.py`
- Modify: `engines/exit_engine/rules/target.py`
- Create: `engines/exit_engine/rules/time_exit.py`
- Modify: `engines/exit_engine/rules/__init__.py`
- Modify: `engines/exit_engine/__init__.py`
- Create: `tests/test_short_trade_support.py`

**Interfaces:**
- `Trade(..., direction="LONG", metadata=None, transaction_cost=0.0)` validates direction and exposes gross/net P&L.
- `TradeEngine.open_trade(..., direction="LONG", metadata=None, equity_before=None)` remains compatible with existing callers.
- `ExitEngine.check(..., direction="LONG")` passes direction to each rule.
- `TimeExit("14:30")` returns `ExitResult(close, "TIME")` at or after the cutoff.

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_short_trade_profit_and_cost_are_direction_aware():
    trade = Trade("A", TS, 100, 105, 90, 10, 1000, direction="SHORT", transaction_cost=4)
    trade.close(TS2, 90, "TARGET")
    assert trade.gross_pnl == 100
    assert trade.pnl == 96

def test_short_stop_and_target_reverse_long_thresholds():
    assert SLExit().check(short_bar, 100, 105, 90, direction="SHORT").exit_reason == "SL"
    assert TargetExit().check(short_target_bar, 100, 105, 90, direction="SHORT").exit_reason == "TARGET"

def test_time_exit_uses_candle_close_for_either_direction():
    result = TimeExit("14:30").check(cutoff_bar, 100, 95, 110, direction="SHORT")
    assert (result.exit_price, result.exit_reason) == (101, "TIME")
```

- [ ] **Step 2: Run `python -m pytest tests/test_short_trade_support.py -q` and verify failures identify missing direction/time behavior.**
- [ ] **Step 3: Implement direction validation, gross/cost/net P&L, metadata serialization, direction-aware reusable exits, and `TimeExit`.**

```python
price_pnl = exit_price - entry_price if direction == "LONG" else entry_price - exit_price
gross_pnl = price_pnl * quantity
pnl = gross_pnl - transaction_cost
```

- [ ] **Step 4: Run the focused test and existing exit/report tests; require zero failures.**
- [ ] **Step 5: Record a local verification checkpoint only; perform no Git operation.**

### Task 2: Risk-based sizing and direction-aware equity

**Files:**
- Modify: `engines/position_sizing_engine/models/position.py`
- Modify: `engines/position_sizing_engine/engine.py`
- Create: `engines/position_sizing_engine/sizing/risk_based.py`
- Modify: `engines/position_sizing_engine/sizing/__init__.py`
- Create: `tests/test_risk_position_sizing.py`

**Interfaces:**
- `size_position(symbol, entry_price, direction="LONG", risk_per_unit=None, risk_fraction=None)` uses equal capital when risk values are absent.
- `Position` stores direction and equity before entry.
- `close_position(symbol, exit_price, transaction_cost=0.0)` updates realized net P&L directionally.
- `current_equity` returns initial capital plus realized net P&L.

- [ ] **Step 1: Write failing sizing tests with hand-derived quantities.**

```python
def test_risk_quantity_is_floor_of_quarter_percent_equity_over_stop_distance():
    sizing = PositionSizingEngine(100_000, 4)
    position = sizing.size_position("A", 100, risk_per_unit=2.5, risk_fraction=0.0025)
    assert position.quantity == 100
    assert position.equity_before == 100_000

def test_profitable_short_increases_next_trade_risk_budget():
    first = sizing.size_position("A", 100, direction="SHORT", risk_per_unit=5, risk_fraction=0.0025)
    sizing.close_position("A", 90)
    second = sizing.size_position("B", 100, risk_per_unit=5, risk_fraction=0.0025)
    assert sizing.current_equity == 100_500
    assert second.quantity == 50
```

- [ ] **Step 2: Run `python -m pytest tests/test_risk_position_sizing.py -q`; verify failures are caused by the absent API.**
- [ ] **Step 3: Implement the risk sizer and backward-compatible optional parameters; cap quantity by available notional and reject non-positive risk.**

```python
risk_amount = current_equity * risk_fraction
risk_quantity = math.floor(risk_amount / risk_per_unit)
cash_quantity = math.floor(available_capital / entry_price)
quantity = min(risk_quantity, cash_quantity)
```

- [ ] **Step 4: Run focused sizing tests plus `tests/test_position_sizing_backtest.py`; require zero failures.**
- [ ] **Step 5: Record a local verification checkpoint only; perform no Git operation.**

### Task 3: Timestamp-aware backtest orchestration and audit state

**Files:**
- Modify: `Backtest/backtest_engine/engine.py`
- Modify: `Backtest/backtest_engine/models/backtest_result.py` only if a small result helper is required
- Create: `tests/test_intraday_backtest_engine.py`

**Interfaces:**
- Signals may provide `direction`, `risk_per_unit`, `risk_fraction`, and `metadata`; missing attributes receive legacy defaults.
- Intraday rows use a strategy-prepared `timestamp`; daily rows retain `date` behavior.
- The engine records equity before/after and closes intraday positions at the last same-day candle if the normal time exit cannot run.

- [ ] **Step 1: Write failing event-order tests.**

```python
def test_entry_candle_cannot_trigger_its_own_stop_or_target():
    trades = intraday_engine().run(entry_bar_touching_both_plus_next_bar).to_dataframe()
    assert trades.iloc[0].exit_timestamp == next_timestamp

def test_missing_cutoff_candle_closes_at_last_same_day_close():
    trade = intraday_engine().run(day_ending_at_1425).to_dataframe().iloc[0]
    assert trade.exit_reason == "END_OF_DAY"
    assert trade.exit_timestamp.date() == trade.entry_timestamp.date()
```

- [ ] **Step 2: Run `python -m pytest tests/test_intraday_backtest_engine.py -q`; verify the legacy date loop fails these temporal contracts.**
- [ ] **Step 3: Implement timestamp-grouped two-phase processing, signal attribute defaults, metadata propagation, direction-aware closing, equity audit fields, and defensive daily settlement.**

```python
for timestamp, candle_set in data.groupby("timestamp", sort=True):
    active_at_start = set(trade_engine.get_active_trades())
    check_exits(candle_set, active_at_start)
    open_signals(candle_set, excluded_symbols=active_at_start)
```

- [ ] **Step 4: Run intraday tests, all shared engine tests, and Strategy 1 regression tests; require zero failures.**
- [ ] **Step 5: Record a local verification checkpoint only; perform no Git operation.**

### Task 4: Complete the ORB strategy

**Files:**
- Modify: `Backtest/Strategies/strategy_3_ORB/strategy.py`
- Create: `Backtest/Strategies/strategy_3_ORB/config.py`
- Create: `Backtest/Strategies/strategy_3_ORB/models.py`
- Create: `Backtest/Strategies/strategy_3_ORB/__init__.py`
- Create: `tests/test_orb_strategy.py`
- Create: `tests/test_orb_backtest.py`

**Interfaces:**
- `ORBStrategy.prepare_data(df)` returns sorted intraday candles with trading date, timestamp, ORB columns, and entry eligibility.
- `ORBStrategy.generate_signal(row)` returns an `ORBSignal` for a valid long/short breakout or `None`.
- `ORBSignal` exposes the shared signal fields plus direction, risk fields, and ORB audit metadata.

- [ ] **Step 1: Write failing ORB calculation and signal tests.**

```python
def test_opening_range_is_isolated_by_symbol_and_day():
    prepared = ORBStrategy().prepare_data(two_symbols_two_days)
    assert prepared.loc[key_a_day1, ["orb_high", "orb_low"]].tolist() == [105, 95]
    assert prepared.loc[key_b_day1, ["orb_high", "orb_low"]].tolist() == [210, 190]

def test_breakout_at_0955_is_ineligible_but_1000_is_eligible():
    assert strategy.generate_signal(prepared_0955) is None
    assert strategy.generate_signal(prepared_1000).direction == "LONG"

def test_short_signal_uses_half_range_stop_and_full_range_target():
    signal = strategy.generate_signal(short_breakout)
    assert (signal.entry_price, signal.sl, signal.target) == (94, 99, 84)
```

- [ ] **Step 2: Run `python -m pytest tests/test_orb_strategy.py tests/test_orb_backtest.py -q`; verify failures reflect the incomplete current strategy.**
- [ ] **Step 3: Implement input-only data preparation, per-symbol/day ORB aggregation, post-window eligibility, long/short signals, and audit metadata.**

```python
opening = data[(data.time >= time(9, 15)) & (data.time < time(10, 0))]
levels = opening.groupby(["trading_date", "symbol"]).agg(orb_high=("high", "max"), orb_low=("low", "min"))
eligible = data["time"] >= time(10, 0)
```

- [ ] **Step 4: Run focused ORB tests and the full test suite; require zero failures.**
- [ ] **Step 5: Record a local verification checkpoint only; perform no Git operation.**

### Task 5: ORB analysis and report artifacts

**Files:**
- Modify: `engines/backtest_report_engine/artifacts.py`
- Create: `Backtest/Strategies/strategy_3_ORB/reporting.py`
- Create: `tests/test_orb_report_artifacts.py`

**Interfaces:**
- `build_orb_analysis(trades_df) -> dict[str, object]` returns direction, symbol, exit-reason, range, monthly, and yearly data.
- `BacktestReportEngine.generate_and_save(extra_artifacts=None)` preserves existing output when optional artifacts are absent.
- ORB artifact writing emits `trades.csv`, `orb_analysis.json`, and one CSV per requested table.

- [ ] **Step 1: Write failing artifact tests using two long and two short literal trades.**

```python
def test_orb_analysis_reports_direction_win_rates_and_exit_counts():
    analysis = build_orb_analysis(auditable_trades())
    assert analysis["direction"]["LONG"]["win_rate"] == 50.0
    assert analysis["exit_reason"]["TIME"]["trades"] == 1

def test_saved_orb_run_contains_audit_and_period_tables(tmp_path):
    files = save_orb_report(tmp_path, auditable_trades())
    assert {"trades.csv", "orb_analysis.json", "monthly_performance.csv", "yearly_performance.csv"} <= files
```

- [ ] **Step 2: Run `python -m pytest tests/test_orb_report_artifacts.py -q`; verify failures identify missing analysis/artifact support.**
- [ ] **Step 3: Implement pure analysis aggregation and optional reusable artifact writing without changing standard report semantics.**

```python
monthly = trades.assign(period=trades.exit_timestamp.dt.to_period("M").astype(str)).groupby("period")["pnl"].agg(["count", "sum"])
yearly = trades.assign(period=trades.exit_timestamp.dt.year).groupby("period")["pnl"].agg(["count", "sum"])
```

- [ ] **Step 4: Run artifact tests plus existing `test_backtest_report_artifacts.py` and `test_monte_carlo_report.py`; require zero failures.**
- [ ] **Step 5: Record a local verification checkpoint only; perform no Git operation.**

### Task 6: Runnable full backtest, manual audit, and determinism

**Files:**
- Create: `Backtest/Strategies/strategy_3_ORB/run_backtest.py`
- Create: `Backtest/Strategies/strategy_3_ORB/validate_results.py`
- Create: `tests/test_orb_result_validation.py`
- Output: `artifacts/backtest_reports/ORBStrategy/<timestamp>/...`

**Interfaces:**
- `run_backtest.py` exposes `run(data_path, reports_root, initial_capital=100000.0)` and a CLI main guard.
- `validate_results.py` checks temporal invariants and manually recomputes selected long/short trades from raw candles.

- [ ] **Step 1: Write failing validation tests proving pre-10:00 entries, overnight exits, bad ORB levels, and inconsistent P&L are rejected.**

```python
def test_validation_rejects_overnight_trade():
    with pytest.raises(AssertionError, match="overnight"):
        validate_trade_invariants(raw, overnight_trade)

def test_manual_recalculation_accepts_literal_short_trade():
    result = audit_trade(raw_short_day, literal_short_trade)
    assert result == {"orb": True, "entry": True, "exit": True, "sizing": True, "pnl": True}
```

- [ ] **Step 2: Run `python -m pytest tests/test_orb_result_validation.py -q`; verify the absent validator causes failure.**
- [ ] **Step 3: Implement the runner and validator, including stable sorting and fixed Monte Carlo seed.**
- [ ] **Step 4: Run `python -m pytest -q`; report every failure by name and fix only failures caused by this work.**
- [ ] **Step 5: Run the full ORB backtest twice against `artifacts/backtest/hist_data_5.json`, saving each run separately.**
- [ ] **Step 6: Compare canonicalized trade CSV content and report JSON metrics between runs; require equality after excluding output-folder timestamps.**
- [ ] **Step 7: Run result validation across every trade and manually audit at least three long and three short trades against raw candles.**
- [ ] **Step 8: Confirm zero open positions, zero overnight trades, no entries before 10:00, all expected artifacts present, and capture symbols/trades/key metrics for the final response.**
- [ ] **Step 9: Inspect local file differences without staging or committing, then provide the requested completion summary.**
