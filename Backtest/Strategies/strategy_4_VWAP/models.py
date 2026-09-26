from dataclasses import dataclass
from datetime import datetime


@dataclass
class VWAPSignal:
    symbol: str
    entry_date: datetime
    entry_price: float
    sl: float
    target: float
    direction: str
    risk_per_unit: float
    risk_fraction: float
    metadata: dict
