
from datetime import datetime
from typing import Optional

from .models import Trade


class TradeEngine:
    """
    Manages the lifecycle of multiple trades.

    Rules
    -----
    - Only ONE active trade is allowed per symbol.
    - Multiple different symbols can be active simultaneously.

    Example
    -------
    RELIANCE -> active
    TCS      -> active
    INFY     -> active

    But:

    RELIANCE -> already active -> cannot open another RELIANCE trade.

    Responsibilities
    ----------------
    - Create/open trades using information supplied by
      the Strategy Engine.
    - Close trades using information supplied by
      the Exit Engine.
    - Calculate trade P&L through the Trade model.
    - Maintain active trade state.

    The Trade Engine does NOT:
    - Generate entry signals.
    - Calculate SL.
    - Calculate target.
    - Decide when to exit.
    - Decide the exit price.
    """

    def __init__(self):
        # Active trades are stored by symbol.
        #
        # Example:
        #
        # {
        #     "RELIANCE": Trade(...),
        #     "TCS": Trade(...),
        #     "INFY": Trade(...)
        # }
        #
        # This allows multiple stocks to be held at the
        # same time while preventing multiple positions
        # in the same stock.
        self.active_trades: dict[str, Trade] = {}

    def reset(self) -> None:
        """Clear positions from a previous backtest run."""
        self.active_trades.clear()

    # ==================================================
    # OPEN TRADE
    # ==================================================

    def open_trade(
    self,
    symbol: str,
    entry_date: datetime,
    entry_price: float,
    sl: float,
    target: float,
    quantity: int = 1,
    capital_allocated: float | None = None,
    direction: str = "LONG",
    metadata: dict | None = None,
    transaction_cost: float = 0.0,
    equity_before: float | None = None,
) -> Trade:
        """
        Open a new trade for a symbol.

        Only one active trade is allowed per symbol.

        Raises
        ------
        ValueError
            If the symbol already has an active trade.
        """

        if not symbol:
            raise ValueError(
                "Symbol cannot be empty."
            )

        # --------------------------------------------------
        # ONE POSITION PER STOCK
        # --------------------------------------------------

        if symbol in self.active_trades:
            raise ValueError(
                f"Cannot open a new trade for {symbol}. "
                f"A trade is already active."
            )

        # --------------------------------------------------
        # VALIDATE TRADE VALUES
        # --------------------------------------------------

        if entry_price <= 0:
            raise ValueError(
                "Entry price must be greater than 0."
            )

        if sl <= 0:
            raise ValueError(
                "Stop loss must be greater than 0."
            )

        if target <= 0:
            raise ValueError(
                "Target must be greater than 0."
            )

        # --------------------------------------------------
        # CREATE TRADE
        # --------------------------------------------------

        trade = Trade(
    symbol=symbol,
    entry_date=entry_date,
    entry_price=entry_price,
    sl=sl,
    target=target,
    quantity=quantity,
    capital_allocated=(
        capital_allocated
        if capital_allocated is not None
        else entry_price * quantity
    ),
    direction=direction,
    metadata=metadata,
    transaction_cost=transaction_cost,
    equity_before=equity_before,
)

        # Store trade using symbol as the key.
        self.active_trades[symbol] = trade

        return trade

    # ==================================================
    # CLOSE TRADE
    # ==================================================

    def close_trade(
        self,
        symbol: str,
        exit_date: datetime,
        exit_price: float,
        exit_reason: str
    ) -> Trade:
        """
        Close the active trade for a specific symbol.

        Exit information is supplied by the Exit Engine.

        After closing, the trade is removed from
        active_trades so that a future signal for the
        same stock can open a new position.
        """

        if not symbol:
            raise ValueError(
                "Symbol cannot be empty."
            )

        # --------------------------------------------------
        # CHECK ACTIVE TRADE
        # --------------------------------------------------

        if symbol not in self.active_trades:
            raise ValueError(
                f"No active trade found for {symbol}."
            )

        # --------------------------------------------------
        # VALIDATE EXIT
        # --------------------------------------------------

        if exit_price <= 0:
            raise ValueError(
                "Exit price must be greater than 0."
            )

        if not exit_reason:
            raise ValueError(
                "Exit reason cannot be empty."
            )

        # --------------------------------------------------
        # CLOSE TRADE
        # --------------------------------------------------

        trade = self.active_trades[symbol]

        trade.close(
            exit_date=exit_date,
            exit_price=exit_price,
            exit_reason=exit_reason
        )

        # --------------------------------------------------
        # REMOVE FROM ACTIVE POSITIONS
        # --------------------------------------------------

        del self.active_trades[symbol]

        return trade

    # ==================================================
    # GET ACTIVE TRADE
    # ==================================================

    def get_active_trade(
        self,
        symbol: str
    ) -> Optional[Trade]:
        """
        Return the active trade for a specific symbol.

        Returns None if the symbol has no active trade.
        """

        return self.active_trades.get(symbol)

    # ==================================================
    # GET ALL ACTIVE TRADES
    # ==================================================

    def get_active_trades(self) -> dict[str, Trade]:
        """
        Return all currently active trades.

        Returns
        -------
        dict[str, Trade]
            Dictionary containing active trades keyed
            by symbol.
        """

        return self.active_trades.copy()

    # ==================================================
    # CHECK SYMBOL
    # ==================================================

    def has_active_trade(
        self,
        symbol: str
    ) -> bool:
        """
        Check whether a specific symbol currently
        has an active trade.
        """

        return symbol in self.active_trades

    # ==================================================
    # CHECK ANY ACTIVE TRADE
    # ==================================================

    def has_any_active_trade(self) -> bool:
        """
        Check whether there is at least one active trade
        across all symbols.
        """

        return bool(self.active_trades)

    # ==================================================
    # ACTIVE TRADE COUNT
    # ==================================================

    def active_trade_count(self) -> int:
        """
        Return the number of currently active positions.
        """

        return len(self.active_trades)

