from dataclasses import dataclass
import pandas as pd


@dataclass
class BacktestResult:
    """
    Result produced by the Backtest Engine.

    Contains only completed trades.

    The Backtest Report Engine can consume the
    trades DataFrame and calculate performance
    statistics.
    """

    trades: pd.DataFrame

    def to_dataframe(self) -> pd.DataFrame:
        """
        Return a copy of the completed trades.
        """

        return self.trades.copy()

    def trade_count(self) -> int:
        """
        Return the number of completed trades.
        """

        return len(self.trades)