
from dataclasses import dataclass


@dataclass
class BacktestReport:
    """
    Final summary produced by BacktestReportEngine.

    This model contains only aggregated backtest
    performance metrics.

    Individual trades remain available separately
    through the trades DataFrame.
    """

    strategy_name: str

    # ================================================
    # CAPITAL / RETURN
    # ================================================

    initial_capital: float
    ending_capital: float
    total_pnl: float
    total_return: float

    # ================================================
    # TRADE METRICS
    # ================================================

    average_pnl: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float

    average_win: float
    average_loss: float
    profit_factor: float

    # ================================================
    # RISK METRICS
    # ================================================

    max_drawdown: float
    max_drawdown_percent: float

    # ================================================
    # STREAK METRICS
    # ================================================

    winning_streak: int
    losing_streak: int

    # ================================================
    # ANNUALIZED / RISK-ADJUSTED METRICS
    # ================================================

    cagr: float
    sharpe_ratio: float
    monte_carlo: dict

    # ================================================
    # CONVERSION
    # ================================================

    def to_dict(self) -> dict:
        """
        Convert the report into a dictionary.
        """

        return {
            "strategy_name": self.strategy_name,
            "initial_capital": self.initial_capital,
            "ending_capital": self.ending_capital,
            "total_pnl": self.total_pnl,
            "total_return": self.total_return,
            "average_pnl": self.average_pnl,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_percent": self.max_drawdown_percent,
            "winning_streak": self.winning_streak,
            "losing_streak": self.losing_streak,
            "cagr": self.cagr,
            "sharpe_ratio": self.sharpe_ratio,
            "monte_carlo": self.monte_carlo,
        }

    def _monte_carlo_text(self) -> str:
        summary = self.monte_carlo
        header = "\n========== Monte Carlo Analysis ==========\n"
        if summary["status"] != "available":
            return header + "Unavailable: at least 2 completed trades are required.\n"

        return (
            header
            + f"Method                 : Trade P&L bootstrap with replacement\n"
            + f"Simulations / Seed     : {summary['simulations']} / {summary['seed']}\n"
            + f"Trades per simulation  : {summary['trade_count']}\n"
            + f"Median ending capital  : {summary['median_ending_capital']:.2f}\n"
            + f"Ending capital 5%-95%  : {summary['ending_capital_5th_percentile']:.2f} to {summary['ending_capital_95th_percentile']:.2f}\n"
            + f"Median max drawdown    : {summary['median_max_drawdown_percent']:.2f}%\n"
            + f"95th pct max drawdown  : {summary['max_drawdown_95th_percentile']:.2f}%\n"
            + f"Ending below start     : {summary['probability_of_loss_percent']:.2f}% of simulated runs\n"
            + f"Interpretation         : {summary['probability_of_loss_percent']:.2f}% of simulated runs ended below initial capital.\n"
            + "These outcomes assume historical trade P&L can be resampled independently; they are not forecasts.\n"
        )

    def __str__(self) -> str:
        """
        Human-readable report output.
        """

        return (
            "\n"
            "========== BACKTEST REPORT ==========\n"
            f"Strategy Name         : {self.strategy_name}\n"
            f"Initial Capital       : {self.initial_capital:.2f}\n"
            f"Ending Capital        : {self.ending_capital:.2f}\n"
            f"Total P&L             : {self.total_pnl:.2f}\n"
            f"Total Return          : {self.total_return:.2f}%\n"
            f"Average P&L           : {self.average_pnl:.2f}\n"
            "\n"
            f"Total Trades          : {self.total_trades}\n"
            f"Winning Trades        : {self.winning_trades}\n"
            f"Losing Trades         : {self.losing_trades}\n"
            f"Win Rate              : {self.win_rate:.2f}%\n"
            f"Average Win           : {self.average_win:.2f}\n"
            f"Average Loss          : {self.average_loss:.2f}\n"
            f"Profit Factor         : {self.profit_factor:.2f}\n"
            "\n"
            f"Maximum Drawdown      : {self.max_drawdown:.2f}\n"
            f"Maximum Drawdown %    : {self.max_drawdown_percent:.2f}%\n"
            f"Winning Streak        : {self.winning_streak}\n"
            f"Losing Streak         : {self.losing_streak}\n"
            "\n"
            f"CAGR                  : {self.cagr:.2f}%\n"
            f"Sharpe Ratio          : {self.sharpe_ratio:.2f}\n"
            "=====================================\n"
            + self._monte_carlo_text()
        )
