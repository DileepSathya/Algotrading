import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (
    EMA_PERIOD,
    FORCED_EXIT_TIME,
    RISK_FRACTION,
    SIGNAL_START_TIME,
    TARGET_PCT_FROM_ENTRY,
)
from .exits import EMACrossExit
from .strategy import VWAPStrategy


def validate_trade_invariants(trades, signal_start_time=SIGNAL_START_TIME):
    checked = trades.copy()
    if checked.empty:
        return {"trades_checked": 0, "overnight_trades": 0, "pre_start_entries": 0}
    entry = pd.to_datetime(checked["entry_timestamp"])
    exit_ = pd.to_datetime(checked["exit_timestamp"])
    pre_start = entry.dt.time < signal_start_time
    if pre_start.any():
        raise AssertionError(
            f"{int(pre_start.sum())} entries occurred before {signal_start_time.strftime('%H:%M')}"
        )
    overnight = entry.dt.normalize() != exit_.dt.normalize()
    if overnight.any():
        raise AssertionError(f"{int(overnight.sum())} overnight trades found")
    signed = np.where(
        checked["direction"].eq("LONG"),
        checked["exit_price"] - checked["entry"],
        checked["entry"] - checked["exit_price"],
    )
    if not np.allclose(signed * checked["quantity"], checked["gross_pnl"]):
        raise AssertionError("gross P&L is inconsistent")
    if not np.allclose(checked["gross_pnl"] - checked["transaction_cost"], checked["pnl"]):
        raise AssertionError("net P&L is inconsistent")
    return {
        "trades_checked": int(len(checked)),
        "overnight_trades": 0,
        "pre_start_entries": 0,
    }


def _prepare_raw(raw, ema_period, target_pct_from_entry, forced_exit_time,
                 signal_start_time, risk_fraction):
    exit_rule = EMACrossExit(ema_period)
    with_ema = exit_rule.prepare_data(raw)
    strategy = VWAPStrategy(
        ema_period=ema_period,
        target_pct_from_entry=target_pct_from_entry,
        forced_exit_time=forced_exit_time,
        signal_start_time=signal_start_time,
        risk_fraction=risk_fraction,
    )
    prepared = strategy.prepare_data(with_ema)
    groups = {
        (day, str(symbol)): group.sort_values("timestamp", kind="stable")
        for (day, symbol), group in prepared.groupby(["trading_date", "symbol"], sort=False)
    }
    return groups, exit_rule


def audit_trade(raw, trade, prepared=None, ema_rule=None,
                target_pct_from_entry=TARGET_PCT_FROM_ENTRY, forced_exit_time=FORCED_EXIT_TIME,
                signal_start_time=SIGNAL_START_TIME, risk_fraction=RISK_FRACTION,
                ema_period=EMA_PERIOD):
    if prepared is None or ema_rule is None:
        groups, exit_rule = _prepare_raw(
            raw, ema_period, target_pct_from_entry, forced_exit_time,
            signal_start_time, risk_fraction,
        )
    else:
        groups, exit_rule = prepared, ema_rule
    entry_ts = pd.Timestamp(trade["entry_timestamp"])
    exit_ts = pd.Timestamp(trade["exit_timestamp"])
    rows = groups[(entry_ts.normalize(), str(trade["symbol"]))]
    entry_rows = rows[rows["timestamp"] == entry_ts]
    if entry_rows.empty:
        return {key: False for key in (
            "vwap", "cross", "volume", "entry", "same_day", "levels", "sizing", "exit", "pnl"
        )}

    entry_row = entry_rows.iloc[0]
    direction = str(trade["direction"])
    entry_price = float(trade["entry"])
    calculated_vwap = float(entry_row["vwap"])
    vwap_ok = np.isclose(calculated_vwap, float(trade["vwap"]))
    signal_side_ok = entry_price > calculated_vwap if direction == "LONG" else entry_price < calculated_vwap
    previous_close = float(entry_row["previous_close"])
    previous_vwap = float(entry_row["previous_vwap"])
    cross_ok = (
        previous_close <= previous_vwap
        if direction == "LONG"
        else previous_close >= previous_vwap
    ) and signal_side_ok
    volume_ok = (
        pd.notna(entry_row["previous_volume"])
        and float(entry_row["volume"]) > float(entry_row["previous_volume"])
    )
    entry_ok = (
        np.isclose(float(entry_row["close"]), entry_price)
        and signal_side_ok
        and entry_row["time"] >= signal_start_time
        and entry_row["time"] < forced_exit_time
    )
    expected_sl = float(entry_row["low"] if direction == "LONG" else entry_row["high"])
    risk = entry_price - expected_sl if direction == "LONG" else expected_sl - entry_price
    expected_target = entry_price * (
        1 + target_pct_from_entry / 100
        if direction == "LONG"
        else 1 - target_pct_from_entry / 100
    )
    levels_ok = (
        np.isclose(expected_sl, float(trade["sl"]))
        and np.isclose(expected_target, float(trade["target"]))
        and np.isclose(risk, float(trade["risk_per_unit"]))
    )
    risk_quantity = int((float(trade["equity_before"]) * risk_fraction) // risk)
    sizing_ok = 0 < int(trade["quantity"]) <= risk_quantity

    expected_exit = None
    for _, candle in rows[rows["timestamp"] > entry_ts].iterrows():
        if direction == "LONG" and candle["low"] <= expected_sl:
            expected_exit = (candle["timestamp"], expected_sl, "SL")
        elif direction == "SHORT" and candle["high"] >= expected_sl:
            expected_exit = (candle["timestamp"], expected_sl, "SL")
        elif direction == "LONG" and candle["high"] >= expected_target:
            expected_exit = (candle["timestamp"], expected_target, "TARGET")
        elif direction == "SHORT" and candle["low"] <= expected_target:
            expected_exit = (candle["timestamp"], expected_target, "TARGET")
        else:
            ema_exit = exit_rule.check(
                candle, entry_price, expected_sl, expected_target, direction
            )
            if ema_exit is not None:
                expected_exit = (candle["timestamp"], ema_exit.exit_price, ema_exit.exit_reason)
            elif candle["time"] >= forced_exit_time:
                expected_exit = (candle["timestamp"], float(candle["close"]), "TIME")
        if expected_exit is not None:
            break
    if expected_exit is None:
        last = rows.iloc[-1]
        expected_exit = (last["timestamp"], float(last["close"]), "END_OF_DAY")
    exit_ok = (
        pd.Timestamp(expected_exit[0]) == exit_ts
        and np.isclose(float(expected_exit[1]), float(trade["exit_price"]))
        and expected_exit[2] == trade["exit_reason"]
    )
    expected_gross = (
        (float(trade["exit_price"]) - entry_price)
        if direction == "LONG"
        else (entry_price - float(trade["exit_price"]))
    ) * int(trade["quantity"])
    return {
        "vwap": bool(vwap_ok),
        "cross": bool(cross_ok),
        "volume": bool(volume_ok),
        "entry": bool(entry_ok),
        "same_day": entry_ts.date() == exit_ts.date(),
        "levels": bool(levels_ok),
        "sizing": bool(sizing_ok),
        "exit": bool(exit_ok),
        "pnl": bool(np.isclose(expected_gross, float(trade["gross_pnl"]))),
    }


def validate_and_save(raw, trades, folder, sample_each_direction=3,
                      target_pct_from_entry=TARGET_PCT_FROM_ENTRY,
                      forced_exit_time=FORCED_EXIT_TIME,
                      signal_start_time=SIGNAL_START_TIME,
                      risk_fraction=RISK_FRACTION, ema_period=EMA_PERIOD,
                      full_source_audit=False):
    summary = validate_trade_invariants(trades, signal_start_time=signal_start_time)
    groups, exit_rule = _prepare_raw(
        raw, ema_period, target_pct_from_entry, forced_exit_time,
        signal_start_time, risk_fraction,
    )
    samples = [
        trades[trades["direction"] == direction].head(sample_each_direction)
        for direction in ("LONG", "SHORT")
    ]
    sampled = pd.concat(samples) if samples else trades.iloc[0:0]
    source_trades = trades if full_source_audit else sampled
    checked = {}
    failures = []
    for index, row in source_trades.iterrows():
        checks = audit_trade(
            raw, row, groups, exit_rule, target_pct_from_entry, forced_exit_time,
            signal_start_time, risk_fraction, ema_period,
        )
        checked[index] = checks
        if not all(checks.values()):
            failures.append({"trade_index": int(index), **checks})
            if len(failures) >= 10:
                break
    if failures:
        raise AssertionError(f"source-candle validation failed: {failures}")
    audits = [
        {"trade_index": int(index), "symbol": row["symbol"],
         "direction": row["direction"], **checked[index]}
        for index, row in sampled.iterrows()
    ]
    result = {
        **summary,
        "source_candle_audits": int(len(source_trades)),
        "manual_audits": audits,
    }
    Path(folder, "validation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result
