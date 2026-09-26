from datetime import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

EMA_PERIOD = 9
TARGET_PCT_FROM_ENTRY = 0.5
FORCED_EXIT_TIME = time(14, 30)
SIGNAL_START_TIME = time(9, 30)
RISK_FRACTION = 0.005

INITIAL_CAPITAL = 100_000.0
MAX_OPEN_POSITIONS = 4
MAX_LOSS_TRADES_PER_SYMBOL_PER_DAY = 5
MAX_LOSS_TRADES_PER_DAY = 4
MAX_DAILY_LOSS_PCT = 1.0
DEFAULT_DATA = PROJECT_ROOT / "artifacts/backtest/hist_data_5_part2.json"
DEFAULT_REPORTS = PROJECT_ROOT / "artifacts/backtest_reports"
