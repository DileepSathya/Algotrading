from typing import Optional

from .models import Position
from .sizing import EqualCapitalSizer
from .validation import PositionSizingValidator


class PositionSizingEngine:
    """
    Controls whether a strategy signal can be converted
    into an actual position.

    Responsibilities
    ----------------
    - Maintain initial capital and realized P&L.
    - Maintain maximum allowed open positions.
    - Track active positions by symbol.
    - Track capital currently allocated to open positions.
    - Check whether another position can be opened.
    - Calculate capital allocation from current equity.
    - Calculate quantity.
    - Return a Position object.
    - Release allocated capital when a position closes.

    The Position Sizing Engine does NOT:
    - Generate strategy signals.
    - Calculate SL.
    - Calculate target.
    - Decide exit conditions.
    - Manage trade lifecycle.
    - Mark open positions to market.
    """

    def __init__(
        self,
        initial_capital: float,
        max_open_positions: int,
    ):
        PositionSizingValidator.validate_configuration(
            initial_capital=initial_capital,
            max_open_positions=max_open_positions,
        )

        self.initial_capital = float(initial_capital)

        self.max_open_positions = int(
            max_open_positions
        )

        # Total capital currently committed
        # to active positions.
        self.allocated_capital = 0.0
        # Profit or loss from positions already closed.
        self.realized_pnl = 0.0

        # Active positions indexed by symbol.
        #
        # Example:
        #
        # {
        #     "RELIANCE": Position(...),
        #     "TCS": Position(...),
        #     "INFY": Position(...)
        # }
        #
        self.active_positions: dict[str, Position] = {}

        self.sizer = EqualCapitalSizer()

    def reset(self) -> None:
        """Restore the starting capital and remove prior positions."""
        self.active_positions.clear()
        self.allocated_capital = 0.0
        self.realized_pnl = 0.0

    # ==================================================
    # CAPITAL
    # ==================================================

    @property
    def available_capital(self) -> float:
        """
        Realized equity not allocated to open positions.
        """

        return (
            self.initial_capital
            + self.realized_pnl
            - self.allocated_capital
        )

    @property
    def current_equity(self) -> float:
        return self.initial_capital + self.realized_pnl

    # ==================================================
    # POSITION LIMIT
    # ==================================================

    def can_open_position(self) -> bool:
        """
        Check whether another position can be opened.
        """

        return (
            len(self.active_positions)
            < self.max_open_positions
        )

    # ==================================================
    # POSITION SIZING
    # ==================================================

    def size_position(
        self,
        symbol: str,
        entry_price: float,
        direction: str = "LONG",
        risk_per_unit: float | None = None,
        risk_fraction: float | None = None,
    ) -> Optional[Position]:
        """
        Convert a strategy signal into a position.

        Returns
        -------
        Position
            If the position can be opened.

        None
            If the signal must be skipped.
        """

        if not symbol:
            raise ValueError(
                "Symbol cannot be empty."
            )

        symbol = str(symbol)

        PositionSizingValidator.validate_entry_price(
            entry_price
        )
        direction = str(direction).upper()
        if direction not in {"LONG", "SHORT"}:
            raise ValueError("Direction must be LONG or SHORT.")
        if (risk_per_unit is None) != (risk_fraction is None):
            raise ValueError("risk_per_unit and risk_fraction must be supplied together.")
        if risk_per_unit is not None and (risk_per_unit <= 0 or risk_fraction <= 0):
            raise ValueError("Risk values must be greater than 0.")

        # ----------------------------------------------
        # Prevent multiple active positions
        # for the same symbol
        # ----------------------------------------------

        if symbol in self.active_positions:
            return None

        # ----------------------------------------------
        # Check maximum open positions
        # ----------------------------------------------

        if not self.can_open_position():
            return None

        # ----------------------------------------------
        # Calculate equal allocation from realized equity.
        # ----------------------------------------------

        capital_per_position = (
            self.sizer.calculate_allocation(
                initial_capital=self.initial_capital + self.realized_pnl,
                max_open_positions=self.max_open_positions,
            )
        )

        # ----------------------------------------------
        # Cap the order by remaining cash.
        # ----------------------------------------------

        if self.available_capital <= 0:
            return None

        capital_per_position = min(capital_per_position, self.available_capital)

        # ----------------------------------------------
        # Calculate quantity
        # ----------------------------------------------

        quantity = self.sizer.calculate_quantity(
            allocated_capital=capital_per_position,
            entry_price=entry_price,
        )
        if risk_per_unit is not None:
            risk_quantity = int((self.current_equity * risk_fraction) // risk_per_unit)
            quantity = min(quantity, risk_quantity)

        # Cannot purchase even one share.
        if quantity <= 0:
            return None

        # ----------------------------------------------
        # Calculate actual capital used
        # ----------------------------------------------

        actual_capital_used = (
            quantity * entry_price
        )

        # ----------------------------------------------
        # Create position
        # ----------------------------------------------

        position = Position(
            symbol=symbol,
            entry_price=float(entry_price),
            quantity=quantity,
            allocated_capital=float(
                actual_capital_used
            ),
            direction=direction,
            equity_before=self.current_equity,
        )

        # ----------------------------------------------
        # Store active position
        # ----------------------------------------------

        self.active_positions[symbol] = position

        # ----------------------------------------------
        # Update allocated capital
        # ----------------------------------------------

        self.allocated_capital += (
            actual_capital_used
        )

        return position

    # ==================================================
    # CLOSE POSITION
    # ==================================================

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        transaction_cost: float = 0.0,
    ) -> Position:
        """
        Remove an active position, release its purchase cost,
        and apply realized P&L to future buying power.

        Parameters
        ----------
        symbol:
            Symbol whose active position should be closed.

        Returns
        -------
        Position:
            The position that was removed.

        exit_price:
            Sale price used to calculate realized P&L.
        """

        if not symbol:
            raise ValueError(
                "Symbol cannot be empty."
            )

        symbol = str(symbol)

        # ----------------------------------------------
        # Find active position
        # ----------------------------------------------

        if symbol not in self.active_positions:
            raise ValueError(
                f"No active position found for {symbol}."
            )

        position = self.active_positions[symbol]

        PositionSizingValidator.validate_entry_price(exit_price)
        price_pnl = float(exit_price) - position.entry_price
        if position.direction == "SHORT":
            price_pnl = -price_pnl
        self.realized_pnl += price_pnl * position.quantity - float(transaction_cost)

        # ----------------------------------------------
        # Release allocated capital
        # ----------------------------------------------

        self.allocated_capital -= (
            position.allocated_capital
        )

        # ----------------------------------------------
        # Remove active position
        # ----------------------------------------------

        del self.active_positions[symbol]

        # ----------------------------------------------
        # Prevent floating-point residue
        # ----------------------------------------------

        if abs(self.allocated_capital) < 1e-10:
            self.allocated_capital = 0.0

        return position

    # ==================================================
    # POSITION STATE
    # ==================================================

    def has_active_position(
        self,
        symbol: str,
    ) -> bool:
        """
        Check whether a symbol currently has
        an active position.
        """

        return symbol in self.active_positions

    def get_active_position(
        self,
        symbol: str,
    ) -> Optional[Position]:
        """
        Return the active position for a symbol.
        """

        return self.active_positions.get(symbol)

    def get_active_positions(
        self,
    ) -> dict[str, Position]:
        """
        Return a copy of all active positions.
        """

        return self.active_positions.copy()

    def get_open_positions(self) -> int:
        """
        Return the number of currently open positions.
        """

        return len(self.active_positions)

    # ==================================================
    # CAPITAL STATE
    # ==================================================

    def get_available_capital(self) -> float:
        return self.available_capital

    def get_allocated_capital(self) -> float:
        return self.allocated_capital

    def get_max_open_positions(self) -> int:
        return self.max_open_positions
