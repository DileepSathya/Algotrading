"""
Configuration for Strategy-1: Higher High.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

# --------------------------------------------------
# Entry configuration
# --------------------------------------------------
CLOSE_THRESHOLD = 0.80
# --------------------------------------------------
# Indicator configuration
# --------------------------------------------------
EMA_PERIOD = 12
EMA_PERIOD_VOL = 20
# --------------------------------------------------
# Target configuration
# --------------------------------------------------
TARGET_PERCENT = 5.0
# --------------------------------------------------
# Backtest configuration
# --------------------------------------------------
DEFAULT_DATA = PROJECT_ROOT / "artifacts/backtest/hist_data_D.json"
DEFAULT_REPORTS = PROJECT_ROOT / "artifacts/backtest_reports"
INITIAL_CAPITAL = 100_000.0
MAX_OPEN_POSITIONS = 2
EXIT_EMA_PERIOD = 20


# When False, run_backtest uses the module-level defaults above (single run).
# When True, run_combinations executes the Cartesian product of COMBINATION_CONFIG.
run_combinations = False

COMBINATION_CONFIG = {
    "CLOSE_THRESHOLD": [0.60, 0.70, 0.80],
    "EMA_PERIOD": [9, 12],
    "EMA_PERIOD_VOL": [20, 30],
    "TARGET_PERCENT": [5.0, 10.0],
    "MAX_OPEN_POSITIONS": [2, 4],
    "EXIT_EMA_PERIOD": [10, 20],
}