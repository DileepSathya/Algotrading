import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (FORCED_EXIT_TIME, ORB_END, ORB_START, RISK_FRACTION,
                     SL_RANGE_MULTIPLIER, TARGET_RANGE_MULTIPLIER)


def validate_trade_invariants(trades, orb_end=ORB_END):
    checked = trades.copy()
    if checked.empty:
        return {"trades_checked": 0, "overnight_trades": 0, "pre_orb_entries": 0}
    entry = pd.to_datetime(checked["entry_timestamp"])
    exit_ = pd.to_datetime(checked["exit_timestamp"])
    pre_window = entry.dt.time < orb_end
    if pre_window.any():
        raise AssertionError(f"{int(pre_window.sum())} entries occurred before {orb_end.strftime('%H:%M')}")
    overnight = entry.dt.normalize() != exit_.dt.normalize()
    if overnight.any():
        raise AssertionError(f"{int(overnight.sum())} overnight trades found")
    if not np.allclose(checked["orb_high"] - checked["orb_low"], checked["orb_range"]):
        raise AssertionError("ORB range does not equal high minus low")
    signed = np.where(checked["direction"].eq("LONG"),
                      checked["exit_price"] - checked["entry"],
                      checked["entry"] - checked["exit_price"])
    gross = signed * checked["quantity"]
    if not np.allclose(gross, checked["gross_pnl"]):
        raise AssertionError("gross P&L is inconsistent")
    if not np.allclose(checked["gross_pnl"] - checked["transaction_cost"], checked["pnl"]):
        raise AssertionError("net P&L is inconsistent")
    return {"trades_checked": int(len(checked)), "overnight_trades": 0, "pre_orb_entries": 0}


def _prepare_raw(raw):
    data = raw.copy()
    data["trading_date"] = pd.to_datetime(data["date"]).dt.normalize()
    data["time"] = pd.to_datetime(data["time"].astype(str), format="mixed").dt.time
    data["timestamp"] = pd.to_datetime(data["trading_date"].dt.strftime("%Y-%m-%d") + " " + data["time"].astype(str))
    return {(day, str(symbol)): group.sort_values("timestamp", kind="stable")
            for (day, symbol), group in data.groupby(["trading_date", "symbol"], sort=False)}


def audit_trade(raw, trade, prepared_groups=None, orb_start=ORB_START, orb_end=ORB_END,
                forced_exit_time=FORCED_EXIT_TIME, risk_fraction=RISK_FRACTION,
                sl_range_multiplier=SL_RANGE_MULTIPLIER,
                target_range_multiplier=TARGET_RANGE_MULTIPLIER):
    groups = prepared_groups if prepared_groups is not None else _prepare_raw(raw)
    day = pd.Timestamp(trade["entry_timestamp"]).normalize()
    rows = groups[(day, str(trade["symbol"]))]
    opening = rows[(rows["time"] >= orb_start) & (rows["time"] < orb_end)]
    high, low = float(opening["high"].max()), float(opening["low"].min())
    direction = trade["direction"]
    entry_ts = pd.Timestamp(trade["entry_timestamp"])
    exit_ts = pd.Timestamp(trade["exit_timestamp"])
    entry_rows = rows[rows["timestamp"] == entry_ts]
    entry_ok = (not entry_rows.empty and np.isclose(float(entry_rows.iloc[0]["close"]), trade["entry"])
                and (trade["entry"] > high if direction == "LONG" else trade["entry"] < low))
    orb_range = high - low
    expected_sl = (trade["entry"] - sl_range_multiplier * orb_range if direction == "LONG"
                   else trade["entry"] + sl_range_multiplier * orb_range)
    expected_target = (trade["entry"] + target_range_multiplier * orb_range if direction == "LONG"
                       else trade["entry"] - target_range_multiplier * orb_range)
    risk_quantity = int((float(trade["equity_before"]) * risk_fraction)
                        // (sl_range_multiplier * orb_range))
    sizing_ok = int(trade["quantity"]) <= risk_quantity and int(trade["quantity"]) > 0

    expected_exit = None
    later = rows[rows["timestamp"] > entry_ts]
    for _, candle in later.iterrows():
        if direction == "LONG" and candle["low"] <= expected_sl:
            expected_exit = (candle["timestamp"], expected_sl, "SL")
        elif direction == "SHORT" and candle["high"] >= expected_sl:
            expected_exit = (candle["timestamp"], expected_sl, "SL")
        elif direction == "LONG" and candle["high"] >= expected_target:
            expected_exit = (candle["timestamp"], expected_target, "TARGET")
        elif direction == "SHORT" and candle["low"] <= expected_target:
            expected_exit = (candle["timestamp"], expected_target, "TARGET")
        elif candle["time"] >= forced_exit_time:
            expected_exit = (candle["timestamp"], float(candle["close"]), "TIME")
        if expected_exit is not None:
            break
    if expected_exit is None:
        last = rows.iloc[-1]
        expected_exit = (last["timestamp"], float(last["close"]), "END_OF_DAY")
    exit_ok = (pd.Timestamp(expected_exit[0]) == exit_ts
               and np.isclose(expected_exit[1], trade["exit_price"])
               and expected_exit[2] == trade["exit_reason"])
    expected_gross = ((trade["exit_price"] - trade["entry"]) if direction == "LONG"
                      else (trade["entry"] - trade["exit_price"])) * trade["quantity"]
    return {"orb": bool(np.isclose(high, trade["orb_high"]) and np.isclose(low, trade["orb_low"])),
            "entry": bool(entry_ok),
            "same_day": entry_ts.date() == exit_ts.date(),
            "levels": bool(np.isclose(expected_sl, trade["sl"]) and np.isclose(expected_target, trade["target"])),
            "sizing": bool(sizing_ok),
            "exit": bool(exit_ok),
            "pnl": bool(np.isclose(expected_gross, trade["gross_pnl"]))}


def validate_and_save(raw, trades, folder, sample_each_direction=3, orb_start=ORB_START,
                      orb_end=ORB_END, forced_exit_time=FORCED_EXIT_TIME,
                      risk_fraction=RISK_FRACTION,
                      sl_range_multiplier=SL_RANGE_MULTIPLIER,
                      target_range_multiplier=TARGET_RANGE_MULTIPLIER,
                      full_source_audit=False):
    summary = validate_trade_invariants(trades, orb_end=orb_end)
    groups = _prepare_raw(raw)
    samples = [
        trades[trades["direction"] == direction].head(sample_each_direction)
        for direction in ("LONG", "SHORT")
    ]
    sampled_trades = pd.concat(samples) if samples else trades.iloc[0:0]
    source_trades = trades if full_source_audit else sampled_trades
    failures = []
    checked = {}
    for index, row in source_trades.iterrows():
        checks = audit_trade(raw, row, groups, orb_start, orb_end, forced_exit_time,
                             risk_fraction, sl_range_multiplier, target_range_multiplier)
        checked[index] = checks
        if not all(checks.values()):
            failures.append({"trade_index": int(index), **checks})
            if len(failures) >= 10:
                break
    if failures:
        raise AssertionError(f"source-candle validation failed: {failures}")
    audits = []
    for index, row in sampled_trades.iterrows():
        checks = checked[index]
        audits.append({"trade_index": int(index), "symbol": row["symbol"],
                       "direction": row["direction"], **checks})
    result = {**summary, "source_candle_audits": int(len(source_trades)), "manual_audits": audits}
    Path(folder, "validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
