import pandas as pd
from pathlib import Path

from .validation.validator import ReportValidator
from .metrics.trade_metrics import TradeMetrics
from .metrics.return_metrics import ReturnMetrics
from .metrics.risk_metrics import RiskMetrics
from .models.report import BacktestReport
from .artifacts import ReportArtifactWriter
from .monte_carlo import simulate_trade_paths


class BacktestReportEngine:
    """
    Main engine responsible for generating a backtest report.

    Input:
        Completed trade DataFrame
        Initial capital

    Output:
        BacktestReport
    """

    def __init__(
        self,
        trades_df: pd.DataFrame,
        capital: float,
        strategy_name: str,
        reports_root=Path(
            "D:/FM/ALGOTRADING/artifacts/backtest_reports"
        ),
        monte_carlo_simulations: int = 5000,
        monte_carlo_seed: int = 42,
    ):
        self.trades_df = trades_df.copy()
        self.capital = capital
        self.strategy_name = strategy_name
        self.reports_root = Path(reports_root)
        self.monte_carlo_simulations = monte_carlo_simulations
        self.monte_carlo_seed = monte_carlo_seed
        self._monte_carlo_paths = None

    # ========================================================
    # PUBLIC API
    # ========================================================

    def generate(self) -> BacktestReport:
        """
        Generate the complete backtest performance report.
        """

        # ----------------------------------------------------
        # 1. Validate input
        # ----------------------------------------------------

        ReportValidator.validate(
            df=self.trades_df,
            capital=self.capital
        )

        # ----------------------------------------------------
        # 2. Prepare trades
        # ----------------------------------------------------

        trades = self._prepare_trades()
        monte_carlo, self._monte_carlo_paths = simulate_trade_paths(
            trades, self.capital, self.monte_carlo_simulations, self.monte_carlo_seed
        )

        # ----------------------------------------------------
        # 3. Handle no completed trades
        # ----------------------------------------------------

        if trades.empty:
            return self._empty_report(monte_carlo)

        # ----------------------------------------------------
        # 4. Trade metrics
        # ----------------------------------------------------

        total_trades = TradeMetrics.total_trades(
            trades
        )

        winning_trades = TradeMetrics.winning_trades(
            trades
        )

        losing_trades = TradeMetrics.losing_trades(
            trades
        )

        win_rate = TradeMetrics.win_rate(
            trades
        )

        average_pnl = TradeMetrics.average_pnl(
            trades
        )

        average_win = TradeMetrics.average_win(
            trades
        )

        average_loss = TradeMetrics.average_loss(
            trades
        )

        profit_factor = TradeMetrics.profit_factor(
            trades
        )

        winning_streak = TradeMetrics.winning_streak(
            trades
        )

        losing_streak = TradeMetrics.losing_streak(
            trades
        )

        # ----------------------------------------------------
        # 5. Return metrics
        # ----------------------------------------------------

        total_pnl = ReturnMetrics.total_pnl(
            trades
        )

        ending_capital = (
            self.capital + total_pnl
        )

        total_return = ReturnMetrics.total_return(
            self.capital,
            ending_capital
        )

        cagr = ReturnMetrics.cagr(
            capital=self.capital,
            ending_capital=ending_capital,
            start_date=trades["entry_date"].min(),
            end_date=trades["exit_date"].max()
        )

        # ----------------------------------------------------
        # 6. Equity curve
        # ----------------------------------------------------

        equity = ReturnMetrics.equity_curve(
            trades=trades,
            initial_capital=self.capital
        )

        # ----------------------------------------------------
        # 7. Risk metrics
        # ----------------------------------------------------

        max_drawdown = RiskMetrics.max_drawdown(
            equity
        )

        max_drawdown_percent = (
            RiskMetrics.max_drawdown_percent(
                equity
            )
        )

        sharpe_ratio = RiskMetrics.sharpe_ratio(
            trades=trades,
            capital=self.capital
        )

        # ----------------------------------------------------
        # 8. Create report
        # ----------------------------------------------------

        return BacktestReport(

            strategy_name=self.strategy_name,

            initial_capital=round(
                self.capital,
                2
            ),

            ending_capital=round(
                ending_capital,
                2
            ),

            total_pnl=round(
                total_pnl,
                2
            ),

            total_return=round(
                total_return,
                2
            ),

            average_pnl=round(
                average_pnl,
                2
            ),

            total_trades=int(
                total_trades
            ),

            winning_trades=int(
                winning_trades
            ),

            losing_trades=int(
                losing_trades
            ),

            win_rate=round(
                win_rate,
                2
            ),

            average_win=round(
                average_win,
                2
            ),

            average_loss=round(
                average_loss,
                2
            ),

            profit_factor=(
                round(profit_factor, 2)
                if profit_factor != float("inf")
                else float("inf")
            ),

            max_drawdown=round(
                max_drawdown,
                2
            ),

            max_drawdown_percent=round(
                max_drawdown_percent,
                2
            ),

            winning_streak=int(
                winning_streak
            ),

            losing_streak=int(
                losing_streak
            ),

            cagr=round(
                cagr,
                2
            ),

            sharpe_ratio=round(
                sharpe_ratio,
                2
            ),
            monte_carlo=monte_carlo,
        )

    def curve_data(self) -> pd.DataFrame:
        """Return dated equity and percentage-drawdown points."""
        ReportValidator.validate(
            df=self.trades_df,
            capital=self.capital,
        )
        trades = self._prepare_trades()

        if trades.empty:
            initial_date = pd.Timestamp.now().normalize()
            return pd.DataFrame(
                {
                    "date": [initial_date],
                    "equity": [float(self.capital)],
                    "drawdown": [0.0],
                }
            )

        equity = ReturnMetrics.equity_curve(
            trades=trades,
            initial_capital=self.capital,
        )[["date", "equity"]]
        initial_point = pd.DataFrame(
            {
                "date": [trades["entry_date"].min()],
                "equity": [float(self.capital)],
            }
        )
        curves = pd.concat([initial_point, equity], ignore_index=True)
        running_peak = curves["equity"].cummax()
        curves["drawdown"] = (
            (curves["equity"] / running_peak) - 1
        ) * 100
        return curves

    def generate_and_save(self):
        """Generate a report and save its text, JSON, and chart artifacts."""
        report = self.generate()
        run_folder = ReportArtifactWriter(self.reports_root).write(
            report=report,
            curves=self.curve_data(),
            monte_carlo_paths=self._monte_carlo_paths,
        )
        return report, run_folder

    # ========================================================
    # PRIVATE METHODS
    # ========================================================

    def _prepare_trades(self) -> pd.DataFrame:
        """
        Prepare completed trades for metric calculations.
        """

        trades = self.trades_df.copy()

        # Convert dates
        trades["entry_date"] = pd.to_datetime(
            trades["entry_date"]
        )

        trades["exit_date"] = pd.to_datetime(
            trades["exit_date"]
        )

        # Keep only completed trades
        trades = trades[
            trades["exit_price"].notna()
            &
            trades["exit_date"].notna()
        ].copy()

        # Sort chronologically
        trades = (
            trades
            .sort_values("exit_date")
            .reset_index(drop=True)
        )

        return trades

    # ========================================================

    def _empty_report(self, monte_carlo) -> BacktestReport:
        """
        Return an empty report when there are
        no completed trades.
        """

        return BacktestReport(

            strategy_name=self.strategy_name,

            initial_capital=round(
                self.capital,
                2
            ),

            ending_capital=round(
                self.capital,
                2
            ),

            total_pnl=0.0,

            total_return=0.0,

            average_pnl=0.0,

            total_trades=0,

            winning_trades=0,

            losing_trades=0,

            win_rate=0.0,

            average_win=0.0,

            average_loss=0.0,

            profit_factor=0.0,

            max_drawdown=0.0,

            max_drawdown_percent=0.0,

            winning_streak=0,

            losing_streak=0,

            cagr=0.0,

            sharpe_ratio=0.0,
            monte_carlo=monte_carlo,
        )
