class PositionSizingValidator:

    @staticmethod
    def validate_configuration(
        initial_capital: float,
        max_open_positions: int,
    ) -> None:

        if initial_capital <= 0:
            raise ValueError(
                "Initial capital must be greater than 0."
            )

        if max_open_positions <= 0:
            raise ValueError(
                "Max open positions must be greater than 0."
            )

    @staticmethod
    def validate_entry_price(
        entry_price: float,
    ) -> None:

        if entry_price <= 0:
            raise ValueError(
                "Entry price must be greater than 0."
            )

    @staticmethod
    def validate_available_capital(
        available_capital: float,
    ) -> None:

        if available_capital < 0:
            raise ValueError(
                "Available capital cannot be negative."
            )