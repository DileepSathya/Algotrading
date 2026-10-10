"""
Configuration for Strategy-1: Higher High.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

# --------------------------------------------------
# Entry configuration
# --------------------------------------------------
CLOSE_THRESHOLD = 0.70
# --------------------------------------------------
# Indicator configuration
# --------------------------------------------------
PRICE_ABOVE_EMA_PERIOD = True
EMA_PERIOD = 20
EMA_FILTER = True
SMALLER_EMA_PERIOD = 20
BIGGER_EMA_PERIOD = 50
USE_RSI = True
RSI_PERIOD = 10
RSI_MIN_VALUE = 40.0
RSI_MAX_VALUE = 90.0

EMA_PERIOD_VOL = 10
# --------------------------------------------------
# Target configuration
# --------------------------------------------------
TARGET_PERCENT = 7.0
# --------------------------------------------------
# Backtest configuration
# --------------------------------------------------
DEFAULT_DATA = PROJECT_ROOT / "artifacts/backtest/hist_data_D.json"
DEFAULT_REPORTS = PROJECT_ROOT / "artifacts/backtest_reports"
INITIAL_CAPITAL = 100_000.0
MAX_OPEN_POSITIONS = 4
EXIT_EMA_PERIOD = 20
TRAIL_STOP_LOSS = False
TRAIL_STOP_LOSS_CANDLE_COUNT = 2


# When False, run_backtest uses the module-level defaults above (single run).
# When True, run_combinations executes the Cartesian product of COMBINATION_CONFIG.
run_combinations = False

COMBINATION_CONFIG = {
    "CLOSE_THRESHOLD": [0.70],
    "EMA_PERIOD": [20],
    "PRICE_ABOVE_EMA_PERIOD": [True, False],
    "EMA_FILTER": [True, False],
    "SMALLER_EMA_PERIOD": [20],
    "BIGGER_EMA_PERIOD": [50],
    "USE_RSI": [True, False],
    "RSI_PERIOD": [10],
    "RSI_MIN_VALUE": [30,40,50.0],
    "RSI_MAX_VALUE": [70.0,80,90,100],
    "EMA_PERIOD_VOL": [10],
    "TARGET_PERCENT": [5.0],
    "MAX_OPEN_POSITIONS": [4],
    "EXIT_EMA_PERIOD": [20],
    "TRAIL_STOP_LOSS": [True, False],
    "TRAIL_STOP_LOSS_CANDLE_COUNT": [2,3,4],
}
