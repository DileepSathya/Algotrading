from dataclasses import dataclass


@dataclass
class Position:
    """
    Represents the position created by the Position Sizing Engine.

    This object contains the result of position sizing.
    It does not represent the complete trade lifecycle.
    """

    symbol: str
    entry_price: float
    quantity: int
    allocated_capital: float
    direction: str = "LONG"
    equity_before: float | None = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "allocated_capital": self.allocated_capital,
            "direction": self.direction,
            "equity_before": self.equity_before,
        }
