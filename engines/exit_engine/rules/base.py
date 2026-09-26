from abc import ABC, abstractmethod

from ..models import ExitResult


class ExitRule(ABC):
    """
    Base class for all exit rules.
    """

    def prepare_data(self, data):
        """Add any indicator columns this rule needs before strategy filtering."""
        return data

    @abstractmethod
    def check(
        self,
        row,
        entry_price: float,
        sl: float,
        target: float,
        direction: str = "LONG",
    ) -> ExitResult | None:
        """
        Check whether the exit rule is triggered.

        Returns
        -------
        ExitResult
            If the exit condition is triggered.

        None
            If the exit condition is not triggered.
        """

        pass
