
import pandas as pd


class ReturnMetrics:
    """
    Calculates return and equity-related metrics.

    This class works with completed trades.

    Trade P&L from the current Trade model includes quantity.
    Equity is still based on realized completed trades and does
    not mark open positions to market.
    """

    # ==================================================
    # TOTAL PNL
    # ==================================================

    @staticmethod
    def total_pnl(trades: pd.DataFrame) -> float:
        """
        Calculate total P&L across all completed trades.
        """

        if trades.empty:
            return 0.0

        return float(
            trades["pnl"].sum()
        )

    # ==================================================
    # TOTAL RETURN
    # ==================================================

    @staticmethod
    def total_return(
        capital: float,
        ending_capital: float
    ) -> float:
        """
        Calculate total return as a percentage.

        Total Return =
            ((Ending Capital / Initial Capital) - 1) * 100
        """

        if capital <= 0:
            raise ValueError(
                "Initial capital must be greater than 0."
            )

        return (
            (ending_capital / capital) - 1
        ) * 100

    # ==================================================
    # CAGR
    # ==================================================

    @staticmethod
    def cagr(
        capital: float,
        ending_capital: float,
        start_date,
        end_date
    ) -> float:
        """
        Calculate Compound Annual Growth Rate.

        CAGR =
            (Ending / Beginning) ^ (1 / Years) - 1

        Returns percentage.
        """

        if capital <= 0:
            raise ValueError(
                "Initial capital must be greater than 0."
            )

        if ending_capital <= 0:
            return 0.0

        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        days = (
            end_date - start_date
        ).days

        # Avoid division by zero for same-day backtests.
        if days <= 0:
            return 0.0

        years = days / 365.25

        return (
            (
                ending_capital / capital
            ) ** (1 / years)
            - 1
        ) * 100

    # ==================================================
    # EQUITY CURVE
    # ==================================================

    @staticmethod
    def equity_curve(
        trades: pd.DataFrame,
        initial_capital: float
    ) -> pd.DataFrame:
        """
        Build an equity curve from completed trades.

        The equity curve is based on cumulative P&L.

        Returns
        -------
        pd.DataFrame

        Columns
        -------
        date
        pnl
        cumulative_pnl
        equity
        """

        if initial_capital <= 0:
            raise ValueError(
                "Initial capital must be greater than 0."
            )

        if trades.empty:
            return pd.DataFrame(
                columns=[
                    "date",
                    "pnl",
                    "cumulative_pnl",
                    "equity",
                ]
            )

        required_columns = {
            "exit_date",
            "pnl",
        }

        missing_columns = (
            required_columns
            - set(trades.columns)
        )

        if missing_columns:
            raise ValueError(
                "Trades DataFrame is missing required "
                f"columns: {sorted(missing_columns)}"
            )

        equity = trades[
            ["exit_date", "pnl"]
        ].copy()

        equity["exit_date"] = pd.to_datetime(
            equity["exit_date"]
        )

        # Make sure trades are chronological.
        equity = (
            equity
            .sort_values("exit_date")
            .reset_index(drop=True)
        )

        # Cumulative P&L.
        equity["cumulative_pnl"] = (
            equity["pnl"].cumsum()
        )

        # Equity = Initial Capital + cumulative P&L.
        equity["equity"] = (
            initial_capital
            + equity["cumulative_pnl"]
        )

        # Rename exit_date to date for a generic
        # equity-curve interface.
        equity = equity.rename(
            columns={
                "exit_date": "date"
            }
        )

        return equity[
            [
                "date",
                "pnl",
                "cumulative_pnl",
                "equity",
            ]
        ]
