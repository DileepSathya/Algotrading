"""Named, reference-relative experiments using only the supplied OHLCV history."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pandas as pd

from Backtest.backtest_engine import HistoricalDataLoader
from engines.backtest_report_engine.metrics.return_metrics import ReturnMetrics
from . import config
from .diagnostics import stagnation_analysis
from .run_backtest import default_settings, simulate, save_result
from .run_combinations import report_to_metric_csv_row


def build_presets():
    baseline = default_settings()
    baseline.update(TARGET_PERCENT=7.0, TRAIL_STOP_LOSS=False, TRAIL_STOP_LOSS_CANDLE_COUNT=2,
                    RISK_PER_TRADE_PCT=None, SIGNAL_RANKING="alphabetical",
                    MAX_EXTENSION_ATR=None, MIN_REWARD_RISK=None)
    presets = {"baseline": baseline}
    for target in (5, 7):
        if target != 7:
            presets[f"target_{target}"] = {**baseline, "TARGET_PERCENT": target}
        for count in (2, 3, 4):
            presets[f"target_{target}_trail_{count}"] = {
                **baseline, "TARGET_PERCENT": target, "TRAIL_STOP_LOSS": True,
                "TRAIL_STOP_LOSS_CANDLE_COUNT": count,
            }
    for risk in (.5, .75, 1.0):
        presets[f"risk_{risk:g}"] = {**baseline, "RISK_PER_TRADE_PCT": risk}
    for ranking in ("momentum", "relative_volume"):
        presets[f"rank_{ranking}"] = {**baseline, "SIGNAL_RANKING": ranking}
    for extension in (1.5, 2.0):
        presets[f"extension_{extension:g}_atr"] = {**baseline, "MAX_EXTENSION_ATR": extension}
    for ratio in (1.0, 1.5):
        presets[f"reward_risk_{ratio:g}"] = {**baseline, "MIN_REWARD_RISK": ratio}
    return presets


def metrics(result, start, end):
    row = report_to_metric_csv_row(result["report"])
    # An additional common-window annualization makes period comparisons fair.
    # Existing report CAGR and drawdown calculations remain unchanged.
    report = result["report"]
    row["WINDOW_CAGR"] = round(ReturnMetrics.cagr(
        report.initial_capital, report.ending_capital, start, end), 4)
    row["CAGR_DRAWDOWN_RATIO"] = round(row["WINDOW_CAGR"] / max(row["MAX_DRAWDOWN_PCT"], 1.0), 4)
    trades = result["trades"]
    row["AVG_HOLDING_DAYS"] = round(float(trades.holding_period.mean()), 2) if len(trades) else 0.0
    row["AVERAGE_WIN"] = report.average_win
    row["AVERAGE_LOSS"] = report.average_loss
    return row


def walk_forward(raw, presets, initial_capital=config.INITIAL_CAPITAL,
                 train_years=config.VALIDATION_TRAIN_YEARS, min_trades=config.VALIDATION_MIN_TRADES,
                 monte_carlo_simulations=1):
    """Choose on trailing calendar years; test next year with fresh capital.

    Each fold is independent. Warmup uses earlier history; test data never enters
    the training simulations. These are historical robustness checks, not an
    untouched holdout or a single continuously compounded live portfolio.
    """
    fold_columns = ["TEST_YEAR", "TRAIN_START", "TRAIN_END", "TEST_START", "TEST_END",
                    "SELECTED_EXPERIMENT", "SELECTION_REASON", "SELECTED_RETURN_PCT",
                    "BASELINE_RETURN_PCT", "SELECTED_WIN_RATE_PCT", "BASELINE_WIN_RATE_PCT",
                    "SELECTED_DRAWDOWN_PCT", "BASELINE_DRAWDOWN_PCT", "SELECTED_TRADES", "BASELINE_TRADES"]
    score_columns = ["TEST_YEAR", "EXPERIMENT", "TRAIN_TRADES", "TRAIN_WINDOW_CAGR",
                     "TRAIN_DRAWDOWN_PCT", "SCORE", "ELIGIBLE"]
    if raw.empty:
        return pd.DataFrame(columns=fold_columns), pd.DataFrame(columns=score_columns)
    dates = pd.to_datetime(raw.date)
    folds, scores = [], []
    for year in range(dates.min().year + train_years, dates.max().year + 1):
        train_start = pd.Timestamp(year=year - train_years, month=1, day=1)
        train_end = pd.Timestamp(year=year - 1, month=12, day=31)
        test_start = pd.Timestamp(year=year, month=1, day=1)
        test_end = min(pd.Timestamp(year=year, month=12, day=31), dates.max())
        if not dates.between(test_start, test_end).any():
            continue
        eligible = []
        for name, settings in presets.items():
            result = simulate(raw, settings, initial_capital, entry_start=train_start,
                              entry_end=train_end, monte_carlo_simulations=monte_carlo_simulations)
            row = metrics(result, max(train_start, dates.min()), train_end)
            qualifies = row["TOTAL_TRADES"] >= min_trades and row["TOTAL_RETURN_PCT"] > 0
            score = row["CAGR_DRAWDOWN_RATIO"]
            scores.append(dict(TEST_YEAR=year, EXPERIMENT=name, TRAIN_TRADES=row["TOTAL_TRADES"],
                               TRAIN_WINDOW_CAGR=row["WINDOW_CAGR"], TRAIN_DRAWDOWN_PCT=row["MAX_DRAWDOWN_PCT"],
                               SCORE=score, ELIGIBLE=qualifies))
            if qualifies:
                eligible.append((score, name))
        selected = sorted(eligible, key=lambda item: (-item[0], item[1]))[0][1] if eligible else "baseline"
        selected_result = simulate(raw, presets[selected], initial_capital, entry_start=test_start,
                                   entry_end=test_end, monte_carlo_simulations=monte_carlo_simulations)
        baseline_result = selected_result if selected == "baseline" else simulate(
            raw, presets["baseline"], initial_capital, entry_start=test_start,
            entry_end=test_end, monte_carlo_simulations=monte_carlo_simulations)
        candidate, baseline = selected_result["report"], baseline_result["report"]
        folds.append(dict(TEST_YEAR=year, TRAIN_START=str(train_start.date()), TRAIN_END=str(train_end.date()),
                          TEST_START=str(test_start.date()), TEST_END=str(test_end.date()),
                          SELECTED_EXPERIMENT=selected,
                          SELECTION_REASON="training_score" if eligible else "fallback_no_eligible_candidate",
                          SELECTED_RETURN_PCT=candidate.total_return, BASELINE_RETURN_PCT=baseline.total_return,
                          SELECTED_WIN_RATE_PCT=candidate.win_rate, BASELINE_WIN_RATE_PCT=baseline.win_rate,
                          SELECTED_DRAWDOWN_PCT=candidate.max_drawdown_percent,
                          BASELINE_DRAWDOWN_PCT=baseline.max_drawdown_percent,
                          SELECTED_TRADES=candidate.total_trades, BASELINE_TRADES=baseline.total_trades))
        print(f"Validation {year}: selected {selected}; return {candidate.total_return:.2f}% "
              f"vs baseline {baseline.total_return:.2f}%", flush=True)
    return pd.DataFrame(folds, columns=fold_columns), pd.DataFrame(scores, columns=score_columns)


def run_experiments(data_path=config.DEFAULT_DATA, reports_root=config.DEFAULT_REPORTS,
                    initial_capital=config.INITIAL_CAPITAL, presets=None,
                    validation=True, monte_carlo_simulations=5000):
    presets = build_presets() if presets is None else presets
    if "baseline" not in presets:
        raise ValueError("Experiments must include a baseline")
    for name in presets:
        if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for c in name) or name in {".", ".."}:
            raise ValueError(f"Invalid experiment name: {name!r}")
    raw = HistoricalDataLoader.load_json(str(data_path))
    if raw.empty:
        raise ValueError("Experiment input contains no candles")
    folder = Path(reports_root).resolve() / "HigherHighStrategy" / "experiments" / (
        datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8])
    folder.mkdir(parents=True)
    effective_presets = {name: {**default_settings(), **settings} for name, settings in presets.items()}
    code_paths = list(Path(__file__).parent.glob("*.py"))
    code_paths += list((config.PROJECT_ROOT / "Backtest" / "backtest_engine").rglob("*.py"))
    code_paths += list((config.PROJECT_ROOT / "engines").rglob("*.py"))
    manifest = dict(data_path=str(Path(data_path).resolve()),
                    data_sha256=hashlib.sha256(Path(data_path).read_bytes()).hexdigest(),
                    code_sha256={str(path.relative_to(config.PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sorted(code_paths)},
                    initial_capital=initial_capital, start=str(raw.date.min()), end=str(raw.date.max()),
                    presets=effective_presets, monte_carlo_simulations=monte_carlo_simulations,
                    monte_carlo_seed=42, validation=validation,
                    validation_train_years=config.VALIDATION_TRAIN_YEARS,
                    validation_min_trades=config.VALIDATION_MIN_TRADES,
                    assumptions="Original close entries, target-first exits, zero costs and realized-trade drawdown retained.",
                    validation_note="Previously inspected history; independent yearly folds, not untouched holdout.")
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    rows, diagnostics = [], []
    baseline_metrics = None
    names = ["baseline"] + [name for name in presets if name != "baseline"]
    summary_path = folder / "experiment_summary.csv"
    for index, name in enumerate(names, 1):
        result = simulate(raw, effective_presets[name], initial_capital,
                          monte_carlo_simulations=monte_carlo_simulations)
        report_folder = save_result(result, folder / name)
        row = metrics(result, raw.date.min(), raw.date.max())
        if baseline_metrics is None:
            baseline_metrics = row.copy()
        row.update(EXPERIMENT=name, REPORT_FOLDER=str(report_folder.resolve()))
        for column, delta in (("CAGR", "DELTA_CAGR_PP"), ("TOTAL_RETURN_PCT", "DELTA_RETURN_PP"),
                              ("WIN_RATE_PCT", "DELTA_WIN_RATE_PP"), ("MAX_DRAWDOWN_PCT", "DELTA_DRAWDOWN_PP")):
            row[delta] = round(row[column] - baseline_metrics[column], 4)
        row["IMPROVES_ALL_FOUR"] = all(row[c] > baseline_metrics[c] for c in ("CAGR", "TOTAL_RETURN_PCT", "WIN_RATE_PCT")) and row["MAX_DRAWDOWN_PCT"] < baseline_metrics["MAX_DRAWDOWN_PCT"]
        rows.append(row)
        pd.DataFrame(rows).to_csv(summary_path, index=False)
        diagnostics.append(stagnation_analysis(result["trades"], raw).assign(experiment=name))
        print(f"[{index}/{len(names)}] {name}: return={row['TOTAL_RETURN_PCT']:.2f}% "
              f"CAGR={row['CAGR']:.2f}% DD={row['MAX_DRAWDOWN_PCT']:.2f}% "
              f"win={row['WIN_RATE_PCT']:.2f}%", flush=True)
    pd.concat(diagnostics, ignore_index=True).to_csv(folder / "stagnation_analysis.csv", index=False)
    if validation:
        folds, scores = walk_forward(raw, effective_presets, initial_capital)
        folds.to_csv(folder / "walk_forward.csv", index=False)
        scores.to_csv(folder / "training_scores.csv", index=False)
    summary = pd.DataFrame(rows)
    print("\nFull-history comparisons (not automatic setting recommendations):")
    print(summary[["EXPERIMENT", "TOTAL_RETURN_PCT", "CAGR", "MAX_DRAWDOWN_PCT", "WIN_RATE_PCT", "IMPROVES_ALL_FOUR"]].to_string(index=False))
    print(f"\nExperiment summary: {summary_path}")
    return {"folder": folder, "summary_csv": summary_path, "summary": summary}
