
import pandas as pd


class TradeMetrics:
    """
    Calculates trade-level performance metrics.

    This class is responsible only for metrics based on
    completed trades.

    It does NOT:
    - Calculate entry signals
    - Calculate exits
    - Manage capital
    - Manage positions
    - Calculate position sizing
    """

    # ==================================================
    # TOTAL TRADES
    # ==================================================

    @staticmethod
    def total_trades(trades: pd.DataFrame) -> int:
        """
        Return total number of completed trades.
        """

        return len(trades)

    # ==================================================
    # WINNING TRADES
    # ==================================================

    @staticmethod
    def winning_trades(trades: pd.DataFrame) -> int:
        """
        Return number of profitable trades.
        """

        if trades.empty:
            return 0

        return int(
            (trades["pnl"] > 0).sum()
        )

    # ==================================================
    # LOSING TRADES
    # ==================================================

    @staticmethod
    def losing_trades(trades: pd.DataFrame) -> int:
        """
        Return number of losing trades.

        Breakeven trades (PnL == 0) are not considered
        winning or losing trades.
        """

        if trades.empty:
            return 0

        return int(
            (trades["pnl"] < 0).sum()
        )

    # ==================================================
    # WIN RATE
    # ==================================================

    @staticmethod
    def win_rate(trades: pd.DataFrame) -> float:
        """
        Calculate win rate as a percentage.

        Win Rate =
            Winning Trades / Total Trades * 100
        """

        total = TradeMetrics.total_trades(trades)

        if total == 0:
            return 0.0

        wins = TradeMetrics.winning_trades(trades)

        return (
            wins / total
        ) * 100

    # ==================================================
    # AVERAGE PNL
    # ==================================================

    @staticmethod
    def average_pnl(trades: pd.DataFrame) -> float:
        """
        Calculate average PnL per trade.
        """

        if trades.empty:
            return 0.0

        return float(
            trades["pnl"].mean()
        )

    # ==================================================
    # AVERAGE WIN
    # ==================================================

    @staticmethod
    def average_win(trades: pd.DataFrame) -> float:
        """
        Calculate average PnL of winning trades only.
        """

        winning = trades[
            trades["pnl"] > 0
        ]

        if winning.empty:
            return 0.0

        return float(
            winning["pnl"].mean()
        )

    # ==================================================
    # AVERAGE LOSS
    # ==================================================

    @staticmethod
    def average_loss(trades: pd.DataFrame) -> float:
        """
        Calculate average PnL of losing trades only.

        The returned value is negative because the
        underlying PnL values are negative.
        """

        losing = trades[
            trades["pnl"] < 0
        ]

        if losing.empty:
            return 0.0

        return float(
            losing["pnl"].mean()
        )

    # ==================================================
    # PROFIT FACTOR
    # ==================================================

    @staticmethod
    def profit_factor(trades: pd.DataFrame) -> float:
        """
        Calculate Profit Factor.

        Profit Factor =
            Gross Profit / Absolute Gross Loss

        Example:
            Gross Profit = 10,000
            Gross Loss   = -5,000

            Profit Factor = 2.0
        """

        if trades.empty:
            return 0.0

        gross_profit = trades.loc[
            trades["pnl"] > 0,
            "pnl"
        ].sum()

        gross_loss = trades.loc[
            trades["pnl"] < 0,
            "pnl"
        ].sum()

        # No losing trades.
        if gross_loss == 0:

            if gross_profit > 0:
                return float("inf")

            return 0.0

        return float(
            gross_profit / abs(gross_loss)
        )

    # ==================================================
    # WINNING STREAK
    # ==================================================

    @staticmethod
    def winning_streak(trades: pd.DataFrame) -> int:
        """
        Calculate the maximum consecutive winning trades.

        Trades are evaluated in their existing DataFrame
        order. The Backtest Report Engine sorts completed
        trades chronologically before calling this method.
        """

        if trades.empty:
            return 0

        max_streak = 0
        current_streak = 0

        for pnl in trades["pnl"]:

            if pnl > 0:
                current_streak += 1

                max_streak = max(
                    max_streak,
                    current_streak
                )

            else:
                current_streak = 0

        return max_streak

    # ==================================================
    # LOSING STREAK
    # ==================================================

    @staticmethod
    def losing_streak(trades: pd.DataFrame) -> int:
        """
        Calculate the maximum consecutive losing trades.

        Breakeven trades reset the losing streak.
        """

        if trades.empty:
            return 0

        max_streak = 0
        current_streak = 0

        for pnl in trades["pnl"]:

            if pnl < 0:
                current_streak += 1

                max_streak = max(
                    max_streak,
                    current_streak
                )

            else:
                current_streak = 0

        return max_streak
