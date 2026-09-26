from dataclasses import dataclass


@dataclass
class ExitResult:
    """
    Represents the result of an exit rule.

    If an exit condition is triggered, this object
    contains the exit price and the reason.
    """

    exit_price: float
    exit_reason: str

    def to_dict(self) -> dict:
        """
        Convert the result into a dictionary.
        """

        return {
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
        }