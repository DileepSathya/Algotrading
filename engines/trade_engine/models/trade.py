from dataclasses import dataclass
from typing import Any, Optional
from datetime import datetime


@dataclass
class Trade:
    symbol: str

    entry_date: datetime
    entry_price: float

    sl: float
    target: float

    quantity: int
    capital_allocated: float

    direction: str = "LONG"
    metadata: Optional[dict[str, Any]] = None
    transaction_cost: float = 0.0
    equity_before: Optional[float] = None

    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None

    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    gross_pnl: Optional[float] = None
    equity_after: Optional[float] = None

    is_closed: bool = False

    def __post_init__(self):
        self.direction = str(self.direction).upper()
        if self.direction not in {"LONG", "SHORT"}:
            raise ValueError("Direction must be LONG or SHORT.")
        self.metadata = dict(self.metadata or {})

    def close(
        self,
        exit_date,
        exit_price,
        exit_reason
    ):
        if self.is_closed:
            raise ValueError(
                "Trade is already closed."
            )

        self.exit_date = exit_date
        self.exit_price = exit_price
        self.exit_reason = exit_reason

        price_pnl = self.exit_price - self.entry_price
        if self.direction == "SHORT":
            price_pnl = -price_pnl
        self.gross_pnl = price_pnl * self.quantity
        self.pnl = self.gross_pnl - self.transaction_cost

        # Return based on capital actually deployed
        self.pnl_percent = (
            self.pnl / self.capital_allocated
        ) * 100

        self.is_closed = True

    def to_dict(self) -> dict:
        values = {
            "symbol": self.symbol,

            "direction": self.direction,

            "entry_date": self.entry_date,
            "entry": self.entry_price,

            "sl": self.sl,
            "target": self.target,

            "quantity": self.quantity,
            "capital_allocated": self.capital_allocated,

            "exit_date": self.exit_date,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,

            "gross_pnl": self.gross_pnl,
            "transaction_cost": self.transaction_cost,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,

            "equity_before": self.equity_before,
            "equity_after": self.equity_after,

            "is_closed": self.is_closed,
        }
        values.update(self.metadata)
        return values
