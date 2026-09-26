import math


class EqualCapitalSizer:
    """
    Allocates equal capital to every possible position.

    Example
    -------
    Initial capital = 100000
    Max open positions = 4

    Capital per position = 100000 / 4
                         = 25000

    If stock price = 1000:

    Quantity = floor(25000 / 1000)
             = 25
    """

    def calculate_allocation(
        self,
        initial_capital: float,
        max_open_positions: int,
    ) -> float:
        if initial_capital <= 0:
            raise ValueError(
                "Initial capital must be greater than 0."
            )

        if max_open_positions <= 0:
            raise ValueError(
                "Max open positions must be greater than 0."
            )

        return (
            initial_capital / max_open_positions
        )

    def calculate_quantity(
        self,
        allocated_capital: float,
        entry_price: float,
    ) -> int:
        if allocated_capital <= 0:
            raise ValueError(
                "Allocated capital must be greater than 0."
            )

        if entry_price <= 0:
            raise ValueError(
                "Entry price must be greater than 0."
            )

        return math.floor(
            allocated_capital / entry_price
        )