import json
import re
from datetime import datetime
from pathlib import Path


class ReportArtifactWriter:
    """Persist one backtest run and its charts in an isolated folder."""

    def __init__(self, reports_root):
        self.reports_root = Path(reports_root)

    def write(self, report, curves, monte_carlo_paths=None):
        run_folder = self._create_run_folder(report.strategy_name)

        (run_folder / "backtest_report.txt").write_text(
            str(report),
            encoding="utf-8",
        )
        (run_folder / "backtest_report.json").write_text(
            json.dumps(report.to_dict(), indent=2),
            encoding="utf-8",
        )
        self._save_charts(report.strategy_name, curves, run_folder)
        if monte_carlo_paths is not None:
            self._save_monte_carlo_chart(report.strategy_name, monte_carlo_paths, run_folder)
        return run_folder

    @staticmethod
    def _save_monte_carlo_chart(strategy_name, paths, run_folder):
        import numpy as np
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        steps = np.arange(paths.shape[1])
        lower, median, upper = np.percentile(paths, [5, 50, 95], axis=0)
        figure, axis = plt.subplots(figsize=(12, 6))
        axis.fill_between(steps, lower, upper, alpha=0.25, label="5th-95th percentile")
        axis.plot(steps, median, linewidth=2, label="Median")
        axis.axhline(paths[0, 0], color="gray", linestyle="--", label="Initial capital")
        axis.set_title(f"{strategy_name} - Monte Carlo Equity")
        axis.set_xlabel("Completed trades")
        axis.set_ylabel("Capital")
        axis.grid(True, alpha=0.3)
        axis.legend()
        figure.tight_layout()
        figure.savefig(run_folder / "monte_carlo_equity.png", dpi=150)
        plt.close(figure)

    def _create_run_folder(self, strategy_name):
        safe_name = re.sub(r"[^A-Za-z0-9]+", "-", strategy_name).strip("-")
        safe_name = safe_name or "strategy"
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        strategy_folder = self.reports_root / safe_name
        run_folder = strategy_folder / timestamp

        if run_folder.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            run_folder = strategy_folder / timestamp

        run_folder.mkdir(parents=True, exist_ok=False)
        return run_folder

    @staticmethod
    def _save_charts(strategy_name, curves, run_folder):
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        chart_specs = (
            ("equity", "Equity Curve", "Equity", "equity_curve.png"),
            ("drawdown", "Drawdown Curve", "Drawdown (%)", "drawdown_curve.png"),
        )

        for column, title, y_label, filename in chart_specs:
            figure, axis = plt.subplots(figsize=(12, 6))
            axis.plot(curves["date"], curves[column], linewidth=2)
            axis.set_title(f"{strategy_name} - {title}")
            axis.set_xlabel("Date")
            axis.set_ylabel(y_label)
            axis.grid(True, alpha=0.3)
            figure.autofmt_xdate()
            figure.tight_layout()
            figure.savefig(run_folder / filename, dpi=150)
            plt.close(figure)
